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
uv run pytest                    # full suite
uv run pytest -q                 # terse output
uv run pytest tests/text         # one directory
uv run pytest tests/text/test_tokenise.py
uv run pytest -k confusable      # tests whose name matches a substring
uv run pytest -x                 # stop at the first failure
```

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
uv run ruff format . && uv run ruff check . && uv run pytest
```

## Where things are

| | |
|---|---|
| Package | `src/cvr/` (`text`, `models`, `eval`, `golden`, `template`, `parse`, `label`, `verify`, `transform`, `render`) |
| Tests | `tests/`, mirroring the package (`tests/text/`, `tests/eval/`, ...) |
| Golden set | `fixtures/candidates/*.json` (ground truth), `fixtures/generated/` (documents and manifests, committed) |
| Template | `templates/fictitious_recruitment.docx`, built by `src/cvr/template/build.py` and committed |
| Specs and tickets | `.scratch/<feature>/spec.md`, `.scratch/<feature>/issues/NN-*.md` |
| Glossary | `CONTEXT.md` |
| Decisions | `docs/adr/` |
| Original brief | `docs/project-brief.md` |
