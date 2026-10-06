# Development

Day-to-day commands for working on this repo. The `check` job of CI (`.github/workflows/ci.yml`) runs exactly these, so if they pass locally they pass there; the `eval` job is described under Eval, and the `deploy` job under Deployment.

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

Tests parametrized over all 48 generated documents (the parse coverage tests, the Layout and generator tests, the perfect oracle through the pipeline) carry `@pytest.mark.slow` and are excluded from the default run by `addopts` in `pyproject.toml`, so the default run stays under thirty seconds; CI runs both suites on every pull request and on every push that changes more than docs (a push of only `**/*.md`, `docs/**` or `.scratch/**` runs no job). A new test over all 48 documents gets the marker too.

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

## Eval

```
uv run python -m cvr.eval.run                          # every generated document, real labeller, through the cache
uv run python -m cvr.eval.run --layout text-box        # one Layout (repeatable)
uv run python -m cvr.eval.run --candidate c04          # one Candidate (repeatable); combines with --layout
uv run python -m cvr.eval.run --no-cache               # a live call for every document (the baseline runs); still refreshes the cache
```

Each document goes through `cvr.pipeline.reformat` with the real labeller (`CVR_LABEL_*` configure it; `ANTHROPIC_API_KEY` is needed only on a cache miss), out through the adapter and into every metric. The run writes `eval/report.json` and `eval/report.md` (both gitignored), prints a one-line verdict plus one line per failure naming the metric and the candidates, and exits 1 on any hard-gate breach (errors, added, dropped, provenance, PII, image, ordering, structural leaves) or missed threshold in `eval/thresholds.yaml` (placeholders until ticket 10). `--thresholds`, `--out` and `--cache-dir` point it elsewhere.

In CI the `eval` job (after `check`, on pull requests and pushes to `main` only) runs this command with `ANTHROPIC_API_KEY` from the repository secret of that name (set it with `gh secret set ANTHROPIC_API_KEY`; the workflow never holds a key, and a missing one fails the job with a message saying so; a pull request from a fork gets no secrets, so it cannot pass). It restores `.cache/eval-responses/` from `actions/cache`, so a pull request that changes nothing the answers depend on replays them for free while one that changes the prompt, schema, `CVR_LABEL_*` or a document pays for live calls (a full uncached run is about $3.3 and four minutes); a push to `main` runs `--no-cache`, unless it changes only docs, which runs nothing. Whatever the verdict, the job uploads `report.json` and `report.md` as the `eval-report` artifact, appends the markdown to the job summary and, on a pull request, posts it as a comment that later runs edit in place. Runs of one workflow, event and ref cancel each other, except on `main`.

The response cache is `.cache/eval-responses/`, one JSON file per answer, keyed on the whole `LabellerConfig`, the prompt and schema hashes and the source document's sha256: a second run over unchanged inputs makes no LLM call, and a change to any of them misses. It is gitignored and must stay out of the Docker image (ticket 12's `.dockerignore`). Delete the directory to clear it. Four documents are labelled at once (parse, render and scoring run one document at a time: python-docx shares one lxml parser, which is not thread-safe); a provider still unavailable after the client's own two retries (a 429, an overload) is retried up to five more times with exponential backoff and jitter, and the report counts every retry.

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

## Deployment

A push to `main` that passes `eval` is deployed by the `deploy` job of `ci.yml` (ADR-0010):

1. Build the image and push it to `ghcr.io/koflynn/cv-reformatter:<sha>`.
2. Log out of GHCR and run `PULL=1 sh scripts/check-image.sh` on an anonymous pull.
3. Sign in to Azure through OIDC (`azure/login`, with the repository variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID`).
4. Run `az containerapp update --image` on `AZURE_CONTAINER_APP` in `AZURE_RESOURCE_GROUP`.
5. Run `sh scripts/smoke-deploy.sh <app url>`.

No Azure secret is stored in GitHub, and the job is the only one with `id-token: write`.

The Azure resources are provisioned once, by hand:

```
bash scripts/provision-azure.sh                  # the wizard, from the repo root in Git Bash
sh scripts/smoke-deploy.sh https://<app url>     # wake the app, post one document, check .docx + X-Run-Id
IMAGE=ghcr.io/koflynn/cv-reformatter:<tag> PULL=1 sh scripts/check-image.sh   # inspect a published image
```

The wizard needs the Azure CLI (`winget install -e --id Microsoft.AzureCLI`), Docker Desktop and `gh`. It walks through twelve stages:

1. Sign in to Azure.
2. Names and region (defaults `cvr-rg`, `cvr-log`, `cvr-cae`, `cvr-ca`, `cvr-github-deploy`, `northeurope`).
3. Create the resource group and the Log Analytics workspace.
4. Create the Container Apps environment.
5. Push the `:bootstrap` image.
6. Make the GHCR package public and give the repo's Actions write access to it (in the browser).
7. Create the container app, with the Anthropic key typed hidden.
8. Run the smoke test.
9. Create the Entra app registration with its federated credential for `repo:KOFlynn@6141875/cv-reformatter@1367290670:ref:refs/heads/main` (GitHub's immutable subject format; the wizard reads the prefix from `gh api repos/<repo>/actions/oidc/customization/sub`).
10. Set the repository variables.
11. Set a cost budget (in the portal).
12. Print the record for ADR-0010.

It remembers its values in `.env.azure` (gitignored, no secret in it) and can be re-run: the environment, the app and the Entra pieces are skipped when they exist (a federated credential with a different subject is updated), and the other stages are safe to repeat.

Day-to-day operations:

```
curl https://<app url>/health                    # warm the endpoint before a demo (scaled to zero, it cold-starts)
az containerapp revision list -n cvr-ca -g cvr-rg -o table
az monitor log-analytics query --workspace <workspace id> --analytics-query "ContainerAppConsoleLogs_CL | where Log_s has '<run id>'"
az group delete -n cvr-rg                        # the kill switch: removes every billable resource
```

Rotating the app's key, with the key read hidden so it never reaches the shell history (it is on `az`'s command line for the moment it runs), then a restart so the running revision reads it:

```
read -rs KEY && az containerapp secret set -n cvr-ca -g cvr-rg --secrets "anthropic-api-key=$KEY" -o none; unset KEY
az containerapp revision restart -n cvr-ca -g cvr-rg --revision "$(az containerapp show -n cvr-ca -g cvr-rg --query properties.latestRevisionName -o tsv)"
```

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
| Eval | `eval/thresholds.yaml` (committed), `eval/report.{json,md}` (generated, gitignored), `.cache/eval-responses/` (gitignored) |
| Tests | `tests/`, mirroring the package (`tests/text/`, `tests/eval/`, ...) |
| Golden set | `fixtures/candidates/*.json` (ground truth), `fixtures/generated/` (documents and manifests, committed) |
| Template | `templates/fictitious_recruitment.docx`, built by `src/cvr/template/build.py` and committed |
| Image | `Dockerfile`, `.dockerignore`, `scripts/check-image.sh` |
| Deployment | the `deploy` job in `.github/workflows/ci.yml`, `scripts/provision-azure.sh`, `scripts/smoke-deploy.sh`, ADR-0010 |
| Specs and tickets | `.scratch/<feature>/spec.md`, `.scratch/<feature>/issues/NN-*.md` |
| Glossary | `CONTEXT.md` |
| Decisions | `docs/adr/` |
| Original brief | `docs/project-brief.md` |
