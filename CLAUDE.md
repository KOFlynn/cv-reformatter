# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of truth

`docs/project-brief.md` is the original build spec this project started from. This file is a distilled summary of it for day-to-day work; consult the brief directly for full detail or if something here seems ambiguous or incomplete.

## Project status

**Phase 0 (spec, template, golden set, eval metrics) is complete. Phase 1 (the pipeline) is in progress: `parse`, `verify`, `transform` and `label` exist.** The other pipeline packages (render, api, and the pipeline function itself) do not exist yet; nothing here opens a `.docx` inside a metric. `label` is the one package that calls an LLM, and only through `RealLabeller`; no unit test does.

What exists, by package under `src/cvr/`:

- `text`: `CONFUSABLES`, `canonicalise`, `tokenise`. Standard library only; the one normalisation every metric and every Layout shares.
- `models`: `CVContent`, `ExperienceEntry`, `EducationEntry`, `DateValue`; `PII`, `Referee`, `Personal` and the `RemovalRule` ids; the source side, `SourceBlock`, `Span`, `Image`, `Removal` and `Normalisation` (the `NORM_INVISIBLE` event); the labelling result, `Labelling` (a `ContentReferences` tree of `Reference`s plus `RemovalReference`s under the closed `TextRemovalRule`) or `LabellingFailure`, whose JSON schema is strict-compatible; the verified side, `VerifiedContent` of `Unit`s (one or more `Span`s of one block); the `Run` and its transform log, one section per node (`LabelRun` from label; normalisations, removals, `LedgerEntry` ledgers, `Residue` and `label_failed` from parse and verify; `date_map`/`split_map` from transform), assembled by the pipeline function, JSON-round-trippable, `unplaced` derived from the residue.
- `golden`: `Candidate`, `Tag` (closed vocabulary, one predicate each), `load_candidates` over `fixtures/candidates/` (twelve Candidates, the spec's allocation table); the `Layout` base and its `Manifest`; the four Layouts of the style matrix (`single-column`, `two-column`, `text-box`, `header-footer`); `python -m cvr.golden.generate` writing the 48 committed `fixtures/generated/<id>__<layout>.docx` + `.manifest.json` pairs.
- `eval`: the nine metrics as pure functions with sorted `Finding`s: `added_tokens`, `dropped_tokens`, `provenance_violations`, `punctuation_fidelity`, `pii_leak`, `image_leak`, `placement_accuracy`, `ordering_report`, `appendix_rate`; entry alignment in `eval.alignment`, leaves by field type in `eval.leaves`. The runner, thresholds and report are Phase 1.
- `parse`: `parse(bytes) -> ParsedDocument`, the pipeline's first node: ordered `SourceBlock`s with address ids (body, table cells, headers and footers by type, text boxes at their anchor), invisibles stripped under `NORM_INVISIBLE`, every image collected by content hash and removed under `RM_PHOTO`. Proven over all 48 generated documents against `tests/docx_text.py`.
- `verify`: `verify(blocks, labelling) -> VerifiedDocument`, the pipeline's third node: one claim ledger per block filled removals → regex backstop → content in tree-walk order → heading backstop → coverage (asserted by a test); matching on canonical text through the offset map, slicing raw. Out: the `VerifiedContent` tree, the flat `(path, Span)` claims, `Removal`s under their rules, `Rejection`s with reasons, `Residue` split into separator and unplaced, the ledgers, `label_failed`. The backstops in `verify.backstops`, the ledger in `verify.ledger`. ADR-0008.
- `transform`: the pipeline's fourth node, pure over `VerifiedContent` (`models`/`text` only, never `verify`). `transform_content` projects every `Unit` to the string the renderer prints (a multi-span unit joined by one space of template text, logged in `split_map`), splits each entry's `dates` reference into a normalised start/end (`transform.dates.split_dates`: whole-as-one-date tried before splitting on a range separator; accepted formats to `MM/YYYY`/`YYYY`/`Present`, else a verbatim literal; a lone date is the entry's `end`, logged in `date_map`), and reorders experience/education entries (`transform.order`: end date descending, Present first, then start descending, then source order). `date_map` and `split_map` are transform's section of the `Run`.
- `template`: `python -m cvr.template.build` writing `templates/fictitious_recruitment.docx` (committed, never hand-edited, ADR-0006); `fill(content, unplaced)` through docxtpl; `template_text`/`template_tokens` read from the built file for the eval whitelist.
- `label`: `RealLabeller`, a `blocks -> labelling result` callable built from `LabellerConfig` (provider, model, effort, optional temperature and any other sampling knob, read from `CVR_LABEL_*`); `init_chat_model` plus `with_structured_output(Labelling, method="json_schema")`, Anthropic-specific options isolated in `anthropic_kwargs`. `prompt.md`; `versions.json` records the prompt and schema versions with the hash each stands for, and import fails with `VersionMismatch` naming the fix if `prompt.md` or the `Labelling` schema changed without a bump; `PROMPT_HASH`, `SCHEMA_HASH` and `CONTENT_HASH` (both together); each call fills a `LabelRun` (the Run's label section, in `models`) with all of that plus tokens and cost (`PRICE_TABLE` in `label.pricing`, one place, checked 2026-09-23). A malformed, schema-invalid or refused answer returns a `LabellingFailure` value; a provider still unavailable after the client's two retries raises `ProviderUnavailable`, a request rejected as configured raises `LabellerMisconfigured` (`label.errors`), anything else propagates. One spike test reaches the real model and is skipped without `ANTHROPIC_API_KEY`; the eval is the labeller's real test. ADR-0009.
- `tests/eval/fake_pipeline.py` and `tests/eval/corruptions.py`: the "test the test" harness, an honest pipeline over every Candidate plus the eight-row corruption table with declared blast radii and directions, asserted equal to the spec's table over every committed Candidate (so a new Candidate must carry what every row damages: a job with bullets, two jobs, an email, an apostrophe or a hyphen).

Where the detail is: the Phase 0 spec and its tickets under `.scratch/phase-0/` (`spec.md`, `issues/NN-*.md`), the vocabulary in `CONTEXT.md`, the decisions in `docs/adr/0001`–`0009`, and the exit criteria in the brief §10.

## Commands

```
uv sync                       # install, using the Python 3.12 pinned in .python-version
uv run pytest -q              # unit tests (tests/), about half a minute
uv run pytest tests/text      # one directory
uv run ruff check .           # lint (defaults + import sorting)
uv run ruff format .          # format (CI runs --check)
uv run python -m cvr.golden.generate    # regenerate fixtures/generated/ after a Candidate or Layout change; commit the result
uv run python -m cvr.template.build     # rebuild templates/fictitious_recruitment.docx after a build.py change; commit the result
```

CI (`.github/workflows/ci.yml`) runs sync, lint, format check and tests on every push and pull request. Both generators are byte-stable, and `tests/golden/test_generate.py` and `tests/template/test_build.py` fail if a committed artefact differs from a fresh generation. The fuller command reference (dependency management, venv activation, useful pytest flags) is `docs/development.md`.

Package layout under `src/cvr/`: `text` and `models` sit at the bottom; `eval`, `golden`, `template`, `parse`, `verify`, `transform` and `label` depend on them and never on each other. `cvr.text` is standard library only. `label` additionally depends on LangChain (`langchain`, `langchain-anthropic`) and is the only pipeline package that reaches the network. `golden` and `eval` are excluded from the runtime image later; nothing production-facing imports either.

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
src/cvr/label/                                                  # exists (Phase 1, ticket 07)
src/cvr/{render,graph,api,mcp}/                                 # Phase 1+
templates/fictitious_recruitment.docx                           # exists; built by src/cvr/template/build.py, committed
fixtures/candidates/c01.json … c12.json                         # exists; ground truth, reviewed by hand
fixtures/generated/<id>__<layout>.docx + .manifest.json         # exists; 48 pairs written by cvr.golden.generate, committed
eval/{thresholds.yaml,report.json}                              # Phase 1: config, and the gitignored generated report
tests/{text,models,eval,golden,template,parse,verify,transform,label}/ # exists; mirrors the package
tests/docx_text.py                                              # exists; the dumb all_text/image_count helper the golden and template tests observe through
Dockerfile                                                      # Phase 1
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
