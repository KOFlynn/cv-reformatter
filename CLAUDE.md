# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of truth

`docs/project-brief.md` is the original build spec this project started from. This file is a distilled summary of it for day-to-day work; consult the brief directly for full detail or if something here seems ambiguous or incomplete.

## Project status

**Phase 0 (spec, template, golden set, eval metrics) is complete. Phase 1 (the pipeline) is in progress: the five nodes (`parse`, `label`, `verify`, `transform`, `render`), the pipeline function `cvr.pipeline.reformat`, the FastAPI service `cvr.api` and its `Dockerfile` exist.** The pipeline is proven end to end with oracle labellers; the eval runner (`python -m cvr.eval.run`, ticket 09) calls it with the real labeller behind a response cache and gates on the report. Its first live run over all 48 documents passed (ticket 09's comment) and found a content line removed under `RM_PERSONAL`, which no hard gate saw; ticket 17 added `removal_precision` as a hard gate, and ticket 18 narrowed the prompt (1.1.0). Ticket 10 set the thresholds from three baseline runs on that prompt (`eval/baseline-2026-09-29.json`: tunable placement at least 98%, appendix at most 2%, punctuation hard), and its follow-up, ticket 19 (a repeated skill quoted once), is done on prompt 1.3.0 (tunable placement 100%, appendix 0.70%, thresholds unchanged). The image (ticket 12) was built and passed `scripts/check-image.sh` under Docker Desktop on 2026-09-29 (325 MB, one real `/reformat`). Ticket 14 adds the `deploy` job, the provisioning wizard `scripts/provision-azure.sh`, the smoke test `scripts/smoke-deploy.sh` and ADR-0010; the maintainer ran the wizard on 2026-10-02, the app is live and deployed from `main`, and the cost to 2026-10-06 was €0.00 (ticket 14's comment). `label` is the one package that calls an LLM, and only through `RealLabeller`; no unit test does.

What exists, by package under `src/cvr/`:

- `text`: `CONFUSABLES`, `canonicalise`, `tokenise`. Standard library only; the one normalisation every metric and every Layout shares.
- `models`: `CVContent`, `ExperienceEntry`, `EducationEntry`, `DateValue`; `PII`, `Referee`, `Personal` and the `RemovalRule` ids; the source side, `SourceBlock`, `Span`, `Image`, `Removal` and `Normalisation` (the `NORM_INVISIBLE` event); the labelling result, `Labelling` (a `ContentReferences` tree of `Reference`s plus `RemovalReference`s under the closed `TextRemovalRule`) or `LabellingFailure`, whose JSON schema is strict-compatible; the verified side, `VerifiedContent` of `Unit`s (one or more `Span`s of one block); the transformed side, `TransformedContent` (the strings render prints, in output order); the `Run` and its transform log, one section per node (`LabelRun` from label; normalisations, removals, `LedgerEntry` ledgers, `Residue` and `label_failed` from parse and verify; `date_map` as one `(normalised date, Span)` pair per date and `split_map` from transform), assembled by the pipeline function, JSON-round-trippable, `unplaced` derived from the residue.
- `golden`: `Candidate`, `Tag` (closed vocabulary, one predicate each), `load_candidates` over `fixtures/candidates/` (twelve Candidates, the spec's allocation table); the `Layout` base and its `Manifest`; the four Layouts of the style matrix (`single-column`, `two-column`, `text-box`, `header-footer`); `python -m cvr.golden.generate` writing the 48 committed `fixtures/generated/<id>__<layout>.docx` + `.manifest.json` pairs.
- `eval`: the ten metrics as pure functions with sorted `Finding`s: `added_tokens`, `dropped_tokens`, `removal_precision`, `provenance_violations`, `punctuation_fidelity`, `pii_leak`, `image_leak`, `placement_accuracy`, `ordering_report`, `appendix_rate`. `removal_precision(removals, pii, headings)` (ticket 17) judges every text removal in the `Run`'s log against what its own rule may remove: the Candidate's `PII` values for that rule, or for `RM_HEADING` the headings the Layout wrote (the `Manifest`'s `headings`, version 3); canonical substring matching, backstop removals judged like the labeller's. Entry alignment in `eval.alignment`, leaves by field type in `eval.leaves`. `eval.adapter` (imported by path, not from `cvr.eval`): `adapt(document) -> Adapted`, the inverse of `render`, a rendered document's leaves by field type (name, profile, skills, education entries, experience entries, certifications, additional, appendix) read back through the template's headings, paragraph styles and the same composite-line conventions, so the Phase 0 metrics can be fed from real output without changing. `eval.run` (imported by path, and with `api` the only importer of `cvr.pipeline`): the runner, `python -m cvr.eval.run [--layout X] [--candidate cNN] [--no-cache]`. `run.documents` (the generated set and its filters), `run.score` (every metric over one real `Run` and the manifest's headings, taken over from `tests/pipeline/`), `run.cache` (the response cache in the gitignored `.cache/eval-responses/`, keyed on the whole `LabellerConfig`, the prompt and schema hashes and the source sha256; `--no-cache` skips lookups and refreshes entries), `run.runner` (four labellings in flight, the `.docx` work one document at a time since python-docx shares one lxml parser across threads; `ProviderUnavailable` retried with exponential backoff and jitter, retries counted), `run.thresholds` (`eval/thresholds.yaml`, set by ticket 10 from the dated baseline beside it) and `run.report` (totals, per layout, per tag, per candidate, then config, versions, tokens, cost, wall time and cache use; the gate: hard gates per document (errors, added, dropped, removal precision, provenance, PII, image, ordering, structural placement), thresholds on the run's totals, each failure naming its metric and candidates, and a wrongful removal its rule and text too). Writes `eval/report.json` and `eval/report.md`, both gitignored; exit 1 on any failure.
- `parse`: `parse(bytes) -> ParsedDocument`, the pipeline's first node: ordered `SourceBlock`s with address ids (body, table cells, headers and footers by type, text boxes at their anchor), invisibles stripped under `NORM_INVISIBLE`, every image collected by content hash and removed under `RM_PHOTO`. Proven over all 48 generated documents against `tests/docx_text.py`.
- `verify`: `verify(blocks, labelling) -> VerifiedDocument`, the pipeline's third node: one claim ledger per block filled removals → regex backstop → content in tree-walk order → heading backstop → coverage (asserted by a test); matching on canonical text through the offset map, slicing raw. Out: the `VerifiedContent` tree, the flat `(path, Span)` claims, `Removal`s under their rules, `Rejection`s with reasons, `Residue` split into separator and unplaced, the ledgers, `label_failed`. The backstops in `verify.backstops`, the ledger in `verify.ledger`. ADR-0008.
- `transform`: the pipeline's fourth node, pure over `VerifiedContent` (`models`/`text` only, never `verify`). `transform_content` projects every `Unit` to the string the renderer prints (a multi-span unit joined by one space of template text, logged in `split_map`), splits each entry's `dates` reference into a normalised start/end (`transform.dates.split_dates`: whole-as-one-date tried before splitting on a range separator; accepted formats to `MM/YYYY`/`YYYY`/`Present`, else a verbatim literal; a lone date is the entry's `end`, logged in `date_map`), and reorders experience/education entries (`transform.order`: end date descending, Present first, then start descending, then source order). `date_map` and `split_map` are transform's section of the `Run`.
- `template`: `python -m cvr.template.build` writing `templates/fictitious_recruitment.docx` (committed, never hand-edited, ADR-0006); `fill(content, unplaced)` through docxtpl; `template_text`/`template_tokens` read from the built file for the eval whitelist.
- `render`: the pipeline's fifth node. `render(content, unplaced)` fills the committed template through `cvr.template.fill` from transform's `TransformedContent` and the Run's unplaced `Span`s, composing nothing of its own (every composite line is the template's own Jinja, as it always was); a rejected leaf's `None` becomes an empty string on the way in, never invented text. Its inverse is the adapter in `eval`. The renderer round-trip test (`render` then `eval.adapter.adapt`, over every Candidate) is what catches a composite line assembled in the wrong order, since no eval metric can (ADR-0007 amendment). Depends on `models` and `template`; never on another node or on `eval`.
- `label`: `RealLabeller`, a `blocks -> labelling result` callable built from `LabellerConfig` (provider, model, effort, optional temperature and any other sampling knob, read from `CVR_LABEL_*`); `init_chat_model` plus `with_structured_output(Labelling, method="json_schema")`, Anthropic-specific options isolated in `anthropic_kwargs`. `prompt.md`; `versions.json` records the prompt and schema versions with the hash each stands for, and import fails with `VersionMismatch` naming the fix if `prompt.md` or the `Labelling` schema changed without a bump; `PROMPT_HASH`, `SCHEMA_HASH` and `CONTENT_HASH` (both together); each call fills a `LabelRun` (the Run's label section, in `models`) with all of that plus tokens and cost (`PRICE_TABLE` in `label.pricing`, one place, checked 2026-09-23). A malformed, schema-invalid or refused answer returns a `LabellingFailure` value; a provider still unavailable after the client's two retries raises `ProviderUnavailable`, a request rejected as configured raises `LabellerMisconfigured` (`label.errors`), anything else propagates. One spike test reaches the real model and is skipped without `ANTHROPIC_API_KEY`; the eval is the labeller's real test. ADR-0009.
- `pipeline`: `reformat(source_bytes, labeller, *, run_id=None) -> (output_bytes, Run)` (the caller's run id, or a fresh `uuid4` hex), parse → label → verify → transform → render, each called once in that order, the `Run` assembled from each node's section (the labeller's `LabelRun` read from its `last_run`, as `RealLabeller` records it). The labeller is injected (`Labeller`: blocks in, labelling result out), so nothing else here reaches an LLM. Only `api` and the eval runner may import it, pinned by a test.
- `api`: `create_app(labeller=None)`, the FastAPI service, and `python -m cvr.api` serving it with uvicorn on `CVR_API_HOST`/`CVR_API_PORT` (default `127.0.0.1:8000`). Two routes and no others (FastAPI's `/docs`, `/redoc`, `/openapi.json` are off): `POST /reformat` (multipart field `file`, a `.docx`; the output `.docx` with `Content-Disposition: attachment; filename="<stem>-reformatted.docx"`) and `GET /health` (liveness, never touches the labeller). Middleware issues the run id before the request is read and sets `X-Run-Id` on every response, 4xx and 5xx included; the Run gets the same id through `reformat(..., run_id=)`. Non-`.docx` → 415; `ProviderUnavailable` → 503; `LabellerMisconfigured` or anything else → 500; a labelling failure → 200 with the banner document. Without an injected labeller, `RealLabeller` is built once per process on the first document (so `/health` needs no key), and documents run one at a time because the labeller keeps `last_run` on itself. `api.log`: each `/reformat` request writes one summary JSON line plus one line per block to standard output, all with the run id, together the whole Run, none reaching 32 KB (`MAX_LINE_BYTES`) for any golden-set document (tested, not enforced); a failed request logs its summary alone, with the error and any `LabelRun` already paid for; `/health` is not logged. Tests inject the oracle (`tests/api/`).
- The image (`Dockerfile`, `.dockerignore`, repo root): two stages on `python:3.12-slim`, `uv sync --locked --no-dev` (dependencies, then the project, installed editable so `cvr.template.paths` finds the template beside `src/`), `python -m cvr.api` as the non-root user `cvr` on `0.0.0.0:8000`. `.dockerignore` is an allowlist: the project files, `src/` without `cvr/golden` and `cvr/eval`, and the template; nothing else reaches the build. The key is a runtime `-e` only. `tests/docker/` checks the Dockerfile and the allowlist statically and that the service runs with `cvr.golden` and `cvr.eval` unimportable; `scripts/check-image.sh` checks a built image (size, user, absent paths, no key in history or filesystem, `/health`, one `/reformat`).
- Deployment (ticket 14, ADR-0010): the `deploy` job in `ci.yml` (needs `eval`, `push` to `main` only, the one job with `id-token: write`, plus `packages: write`) builds and pushes `ghcr.io/koflynn/cv-reformatter:<sha>` (a public package), logs out and runs `PULL=1 sh scripts/check-image.sh` on an anonymous pull, signs in with `azure/login` through OIDC (`vars.AZURE_CLIENT_ID`/`AZURE_TENANT_ID`/`AZURE_SUBSCRIPTION_ID`, repository variables, never secrets), runs `az containerapp update --image` on `vars.AZURE_CONTAINER_APP` in `vars.AZURE_RESOURCE_GROUP`, then `scripts/smoke-deploy.sh <url>` (wakes the app, posts `c04__single-column.docx`, asserts 200, a `.docx` and `X-Run-Id`, writes the run id and its Log Analytics query to the job summary). The resources (`cvr-rg`, `cvr-log`, `cvr-cae`, `cvr-ca` in `northeurope`; Entra app `cvr-github-deploy` with the federated subject `repo:KOFlynn@6141875/cv-reformatter@1367290670:ref:refs/heads/main`, GitHub's immutable format, which the wizard reads from `gh api repos/<repo>/actions/oidc/customization/sub` and which ADR-0010 explains, and Contributor on `cvr-rg`) are provisioned once by `scripts/provision-azure.sh`, a wizard the maintainer runs in Git Bash (it remembers values in the gitignored `.env.azure`). `tests/ci/test_workflow.py` pins the job's shape statically.
- `tests/pipeline/`: the oracle labeller (`oracle.py`: answers from a Candidate and its manifest by locating every content string, PII value and referee line in the parsed blocks; a string it cannot locate raises `OracleMiss`, never skips), the five imperfect oracles (omitted leaf, unlocatable quote, double claim, schema-invalid answer, and a bullet removed under `RM_PERSONAL`, the only one that trips `removal_precision`), and `pipeline_support`, which re-exports the runner's `score` and `document` for them. The perfect oracle over all 48 documents scores clean on every metric.
- `tests/eval/fake_pipeline.py` and `tests/eval/corruptions.py`: the "test the test" harness, an honest pipeline over every Candidate plus the ten-row corruption table with declared blast radii and directions, asserted equal to the spec's table over every committed Candidate (so a new Candidate must carry what every row damages: a job with bullets, two jobs, an email, an apostrophe or a hyphen). `PipelineResult.split_map` and `provenance_violations`' `split_map` argument (ticket 05) are how "join two slices out of source order" fails provenance alone; `PipelineResult.removals`, the removal log, is how "remove a content line under a PII rule" fails removal precision (and placement recall) alone.

Where the detail is: the Phase 0 spec and its tickets under `.scratch/phase-0/` (`spec.md`, `issues/NN-*.md`), the vocabulary in `CONTEXT.md`, the decisions in `docs/adr/0001`–`0010`, and the exit criteria in the brief §10.

## Commands

```
uv sync                       # install, using the Python 3.12 pinned in .python-version
uv run pytest -q              # unit tests (tests/), about twenty seconds, the slow suite excluded
uv run pytest -q -m slow      # the slow suite: every test over all 48 generated documents, about half a minute
uv run pytest tests/text      # one directory
uv run ruff check .           # lint (defaults + import sorting)
uv run ruff format .          # format (CI runs --check)
uv run python -m cvr.golden.generate    # regenerate fixtures/generated/ after a Candidate or Layout change; commit the result
uv run python -m cvr.template.build     # rebuild templates/fictitious_recruitment.docx after a build.py change; commit the result
uv run python -m cvr.api                # serve the API on CVR_API_HOST:CVR_API_PORT (default 127.0.0.1:8000); /reformat calls the real model
uv run python -m cvr.eval.run           # the eval over all 48 documents with the real labeller (needs ANTHROPIC_API_KEY on a cache miss); --layout, --candidate, --no-cache
docker build -t cvr:local .             # the service image (needs Docker Desktop)
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY cvr:local   # the key from your shell, at run time only
sh scripts/check-image.sh               # build and check the image; paste the output into the PR
bash scripts/provision-azure.sh         # the one-off Azure provisioning wizard (maintainer, Git Bash, needs az)
sh scripts/smoke-deploy.sh https://<app url>   # smoke-test the live endpoint (calls the model once)
```

CI (`.github/workflows/ci.yml`) is three jobs, `check`, `eval`, then `deploy` (on `push` to `main` only, needs `eval`; see the Deployment entry above), under `contents: read` and one concurrency group per workflow, event and ref (a newer push cancels the older run; pushes to `main` are never cancelled). `check` runs sync, lint, format check, the default tests and the slow suite on every push and pull request. `eval` (`needs: check`, only on `pull_request` and on `push` to `main`, the one job with `pull-requests: write`) is the gate: it runs `python -m cvr.eval.run` against `eval/thresholds.yaml` with the key from the repository secret `ANTHROPIC_API_KEY` (a missing key fails the job with a named error; fork PRs never get it), restores the response cache from `actions/cache` (saved only on success; a push to `main` runs `--no-cache`, a live run that refreshes it), then, pass or fail, uploads `report.json` and `report.md` as the `eval-report` artifact, appends the markdown to the job summary and, on a PR, posts it as one comment found by the marker `<!-- cvr-eval-report -->` and edited on re-runs. A full uncached run is about $3.3 and four minutes. Branch protection requiring `check` and `eval` on `main` is pending (ticket 13). A new test parametrized over all 48 generated documents gets `@pytest.mark.slow`, so the default run stays under thirty seconds. The golden generator is byte-stable and `tests/golden/test_generate.py` fails if the committed pairs differ from a fresh generation. The template builder is not byte-stable: the zip entries carry the build time, so a later rebuild differs in bytes though every part inside is identical, and `tests/template/test_build.py` compares text and tags only. Do not commit a rebuilt template unless `build.py` changed. The fuller command reference (dependency management, venv activation, useful pytest flags, running the API locally and its environment variables) is `docs/development.md`.

Package layout under `src/cvr/`: `text` and `models` sit at the bottom; `golden`, `template`, `parse`, `verify`, `transform`, `render` and `label` depend on them and never on each other, except that `render` depends on `template`, which it fills. `eval`'s metrics depend on `text` and `models` only; `eval.adapter`, imported by its own path and never re-exported from `cvr.eval`, also depends on `template` (for the review-appendix banner) and python-docx; `eval.run` depends on `pipeline`, `label`, `parse`, `golden` and PyYAML (a dev-group dependency, since `eval` never reaches the image); `eval` may depend on pipeline packages, never the reverse. `cvr.text` is standard library only. `label` additionally depends on LangChain (`langchain`, `langchain-anthropic`) and is the only pipeline package that reaches the network. `pipeline` imports every node and is imported only by `api` and the eval runner. `api` depends on `pipeline`, `label` (for `RealLabeller` and its errors), `models`, FastAPI and uvicorn. `golden` and `eval` are excluded from the runtime image by `.dockerignore`; nothing production-facing imports either, and `tests/docker/test_runtime_imports.py` fails if the service does.

## What this is

A portfolio demo (not a real product, no real users, no real CVs) that reformats a candidate CV (`.docx`) into a fictional recruitment agency's branded Word template. Sections are reordered, dates normalised, PII removed — but **no wording is ever changed or generated**. The project exists to evidence a specific set of AI-engineering skills (LangGraph, an MCP server, Docker/CI/CD to Azure via OIDC, an eval gate, Langfuse tracing) — see the brief §1 for the exact gap-to-deliverable mapping. Do not add functionality outside that scope.

## The core design invariant

**The LLM never writes output text — it only labels.** The LLM returns `{field, block_id, quote}` assignments pointing at source text; a verifier checks each quote is an exact substring of the source block; the rendered output always uses the located source slice, never the LLM's string. Any change that routes LLM-generated strings into the rendered document is a defect. See the brief §2 for the full mechanism.

## Planned architecture

```
.docx ──► parse ──► label (LLM) ──► verify ──┬──► transform ──► render ──► .docx
                                   ▲         │   (remove, dates,  (docxtpl)
                                   └─ retry ◄┘    sort)
                                  (≤ N, Phase 2)   unplaced ──► appendix
```

| Component | Responsibility |
|---|---|
| `parse` | `.docx` → ordered `SourceBlock`s (python-docx for paragraphs/tables/headers/footers; raw XML via lxml for text boxes, which python-docx doesn't expose) |
| `label` | Blocks → `Assignment`s via an LLM, provider-agnostic through LangChain chat model interfaces with structured output |
| `verify` | Assignments → verified `Span`s; exact-substring + full source coverage check |
| `transform` | Removal rules, regex PII backstop, date normalisation (`MM/YYYY`), reverse-chronological ordering — pure functions, no LLM |
| `render` | Fills `templates/fictitious_recruitment.docx` via docxtpl, including the "unplaced text" review appendix |
| `graph` | Phase 2: LangGraph state machine over the same nodes. Phase 1 is a plain function pipeline with identical node boundaries, so the swap is mechanical |
| `api` | FastAPI: `POST /reformat`, `GET /health` |
| `mcp` | Phase 3: MCP server exposing `reformat_cv` |

Layout (brief §13, adjusted by the Phase 0 spec so that `cvr` is the one import root and `fixtures/`, `templates/` and `eval/` hold only data and config, never code):

```
src/cvr/{text,models,eval,golden,template}/                     # exists (Phase 0)
src/cvr/parse/                                                  # exists (Phase 1, ticket 02)
src/cvr/verify/                                                 # exists (Phase 1, ticket 03)
src/cvr/transform/                                              # exists (Phase 1, ticket 04)
src/cvr/render/                                                 # exists (Phase 1, ticket 05)
src/cvr/label/                                                  # exists (Phase 1, ticket 07)
src/cvr/pipeline/                                               # exists (Phase 1, ticket 06)
src/cvr/api/                                                    # exists (Phase 1, ticket 11)
src/cvr/{graph,mcp}/                                            # Phase 2, Phase 3
templates/fictitious_recruitment.docx                           # exists; built by src/cvr/template/build.py, committed
fixtures/candidates/c01.json … c12.json                         # exists; ground truth, reviewed by hand
fixtures/generated/<id>__<layout>.docx + .manifest.json         # exists; 48 pairs written by cvr.golden.generate, committed
eval/thresholds.yaml                                            # exists; set by ticket 10 from three baseline runs
eval/baseline-2026-09-29.json                                   # exists; the three runs, their spread, the threshold arithmetic and notes
eval/report.{json,md}                                           # generated by cvr.eval.run, gitignored
.cache/eval-responses/                                          # the eval's LLM response cache, gitignored, never in the image
tests/{text,models,eval,golden,template,parse,verify,transform,render,label,pipeline,api}/ # exists; mirrors the package
tests/docker/                                                   # exists; the Dockerfile and .dockerignore checks that need no Docker
tests/docx_text.py                                              # exists; the dumb all_text/image_count helper the golden and template tests observe through
Dockerfile, .dockerignore                                       # exists (Phase 1, ticket 12)
scripts/check-image.sh                                          # exists; the checks of a built image (PULL=1: of a published one)
scripts/provision-azure.sh                                      # exists; the one-off Azure provisioning wizard (ticket 14)
scripts/smoke-deploy.sh                                         # exists; the post-deploy smoke test
tests/ci/                                                       # exists; the deploy job's static checks
.github/workflows/ci.yml                                        # exists
```

The golden set (brief §7) is fixture JSON treated as ground truth, not downloaded/scraped CVs — synthetic candidates rendered into messy `.docx` layouts by generator scripts, then committed.

## Working rules for Claude Code in this repo

- **Never let an LLM produce output text.** Any change that routes LLM-generated strings into the rendered document is a defect.
- Keep `transform`, `verify` and eval metrics as pure functions with unit tests. No LLM calls in unit tests.
- **Synthetic data only.** Never add real CVs, real names or real contact details.
- Do not add features outside the brief's §3 scope. If something seems necessary but isn't listed, stop and ask.
- Any change to the prompt, schema or model must be followed by an eval run, with the report diff shown.
- Small, reviewable commits. Explain the reasoning in PR descriptions — they are part of the evidence for this demo.
- Keep the Phase 1 pipeline's node boundaries identical to the LangGraph nodes planned for Phase 2.

## Environment

- Local Python is 3.14, but `.python-version` pins **3.12** so `uv` uses the same interpreter locally, in CI and (later) in the container. Do not bump it unless every dependency is confirmed on the newer version.
- Dependency management with `uv`; `uv.lock` is committed and CI syncs with `--locked`.
- Dev machine: Windows 11, Docker Desktop with WSL2.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
