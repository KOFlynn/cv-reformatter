# Development

Day-to-day commands for working on this repo. CI (`.github/workflows/ci.yml`) runs exactly these, so if they pass locally they pass there.

## Setup

```
uv sync                          # create .venv and install everything, using the Python 3.12 pinned in .python-version
```

`uv run <cmd>` runs a command inside that `.venv` without activating it. If you would rather have the tools on your PATH:

```
.venv\Scripts\Activate.ps1       # PowerShell
.venv\Scripts\activate           # cmd / Git Bash
```

after which plain `pytest`, `ruff` and `python` refer to the project's copies.

## Tests

```
uv run pytest                    # default suite, about twenty seconds
uv run pytest -m slow            # the slow suite: every test over all 48 generated documents
uv run pytest -m ""              # both
uv run pytest -q                 # terse output
uv run pytest tests/text         # one directory
uv run pytest tests/text/test_tokenise.py
uv run pytest -k confusable      # tests whose name matches a substring
uv run pytest -x                 # stop at the first failure
```

Tests parametrized over all 48 generated documents (the parse coverage tests, the Layout and generator tests, the perfect oracle through the pipeline) carry `@pytest.mark.slow` and are excluded from the default run by `addopts` in `pyproject.toml`, so the default run stays under thirty seconds; CI runs both suites on every push. A new test over all 48 documents gets the marker too.

No test calls an LLM or opens a `.docx` in a metric; see `CLAUDE.md` for the working rules.

`tests/docx_text.py` is a test-side helper, not a package: the golden and template tests import it as `from docx_text import all_text`, which works because the root `tests/conftest.py` makes pytest put `tests/` on `sys.path`.

## Golden set

```
uv run python -m cvr.golden.generate             # every Candidate through every Layout into fixtures/generated/
uv run python -m cvr.golden.generate --out DIR   # somewhere else, for a look without touching the committed pairs
```

Each pair is `<candidate-id>__<layout-name>.docx` plus `.manifest.json`. Output is byte-stable, so rerunning over unchanged code rewrites identical files and `git status` stays clean. After any change to a Layout or a Candidate, regenerate and commit the result: `tests/golden/test_generate.py` fails if the committed pairs differ from a fresh generation.

## Template

```
uv run python -m cvr.template.build              # rebuild templates/fictitious_recruitment.docx from the script
```

The template is built by script and never hand-edited (ADR-0006): Word splits docxtpl tags across runs as you type them. After any change to `src/cvr/template/build.py`, rebuild and commit the result; `tests/template/test_build.py` fails if the committed file's text and tags differ from a fresh build. `cvr.template.fill(content, unplaced)` renders it, and `cvr.template.template_tokens()` reads its fixed words back out for the eval whitelist.

## Running the API locally

```
uv run python -m cvr.api                         # serve on http://127.0.0.1:8000
curl http://127.0.0.1:8000/health                # liveness: {"status":"ok"}; never touches the labeller
curl -F "file=@fixtures/generated/c04__single-column.docx" -OJ http://127.0.0.1:8000/reformat
                                                 # saves c04__single-column-reformatted.docx; -i to see X-Run-Id
```

In PowerShell use `curl.exe`, not the `curl` alias. `POST /reformat` takes one multipart field, `file`, a `.docx`; anything else is a 415. Every response carries `X-Run-Id`; each `/reformat` request writes its transform log to standard output as one summary JSON line and one line per block, all with that run id. There are no other routes (no `/docs`, no `/openapi.json`).

The real labeller is built on the first document, not at startup, so `/health` works without a key; `/reformat` without one answers 500. `/reformat` calls the real model and costs money: for anything but a deliberate check, use the tests, which inject the oracle labeller.

| Variable | Read by | Default | |
|---|---|---|---|
| `CVR_API_HOST` | `python -m cvr.api` | `127.0.0.1` | interface to bind; a container sets `0.0.0.0` |
| `CVR_API_PORT` | `python -m cvr.api` | `8000` | port to listen on |
| `ANTHROPIC_API_KEY` | the labeller | (none) | required for `/reformat`, not for `/health` |
| `CVR_LABEL_PROVIDER` | the labeller | `anthropic` | LangChain provider id |
| `CVR_LABEL_MODEL` | the labeller | `claude-opus-5-5` | model name |
| `CVR_LABEL_EFFORT` | the labeller | `medium` | `low`, `medium`, `high`, `xhigh` or `max` |
| `CVR_LABEL_TEMPERATURE` | the labeller | unset | sent only when set |
| `CVR_LABEL_EXTRA` | the labeller | unset | JSON object of any other sampling kwarg |

A change to any `CVR_LABEL_*` value counts as a model change: run the eval.

## Running the API in a container

Needs Docker Desktop (WSL2 backend). From the repo root:

```
docker build -t cvr:local .
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY cvr:local
                                                 # -e NAME with no value passes the key from your shell
curl http://127.0.0.1:8000/health
curl -F "file=@fixtures/generated/c04__single-column.docx" -OJ http://127.0.0.1:8000/reformat
sh scripts/check-image.sh                        # build and check the image: size, user, absent paths,
                                                 # no key in history or filesystem, /health, one /reformat
```

The image is `python:3.12-slim` (the version in `.python-version`) in two stages: the builder runs `uv sync --locked --no-dev`, dependencies first so a source change reuses that layer; the runtime stage copies the virtual environment, `src/` and the template, and runs `python -m cvr.api` as the non-root user `cvr` with `CVR_API_HOST=0.0.0.0` and `CVR_API_PORT=8000`. The project is installed editable, because `cvr.template.paths` finds the template beside `src/`, so `/app` keeps the repo's layout. Every variable in the table above can be passed with `-e`.

The key is a runtime `-e` only: never a `--build-arg`, never in the Dockerfile, never in a file in the build context. `.dockerignore` is an allowlist (`pyproject.toml`, `uv.lock`, `.python-version`, `src/` without `cvr/golden` and `cvr/eval`, the template); anything else, including `.env`, `.cache/`, `eval/`, `fixtures/`, `tests/` and `.git`, never reaches the build. `tests/docker/` checks the Dockerfile, the allowlist and that the service imports neither `cvr.golden` nor `cvr.eval` without Docker; `scripts/check-image.sh` checks a built image. `/reformat` in the container calls the real model, like the local server.

## Lint and format

```
uv run ruff check .              # lint: ruff defaults plus import sorting (CI "Lint" step)
uv run ruff check . --fix        # apply the auto-fixable lint fixes
uv run ruff format .             # reformat files in place
uv run ruff format --check .     # report files that would change, modify nothing (CI "Format check" step)
```

Ruff configuration lives in `pyproject.toml` under `[tool.ruff]`.

## Dependencies

```
uv add <package>                 # runtime dependency
uv add --dev <package>           # dev-group dependency (pytest, ruff, ...)
uv remove <package>
uv lock                          # refresh uv.lock after editing pyproject.toml by hand
uv sync --locked                 # what CI runs: fails if uv.lock is out of date with pyproject.toml
```

`uv.lock` is committed. If CI fails at the Sync step, run `uv lock` locally and commit the result.

## Before pushing

```
uv run ruff format . && uv run ruff check . && uv run pytest && uv run pytest -m slow
```

## Where things are

| | |
|---|---|
| Package | `src/cvr/` (`text`, `models`, `eval`, `golden`, `template`, `parse`, `label`, `verify`, `transform`, `render`, `pipeline`, `api`) |
| Tests | `tests/`, mirroring the package (`tests/text/`, `tests/eval/`, ...) |
| Golden set | `fixtures/candidates/*.json` (ground truth), `fixtures/generated/` (documents and manifests, committed) |
| Template | `templates/fictitious_recruitment.docx`, built by `src/cvr/template/build.py` and committed |
| Image | `Dockerfile`, `.dockerignore`, `scripts/check-image.sh` |
| Specs and tickets | `.scratch/<feature>/spec.md`, `.scratch/<feature>/issues/NN-*.md` |
| Glossary | `CONTEXT.md` |
| Decisions | `docs/adr/` |
| Original brief | `docs/project-brief.md` |
