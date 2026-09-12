# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of truth

`docs/project-brief.md` is the original build spec this project started from. This file is a distilled summary of it for day-to-day work; consult the brief directly for full detail or if something here seems ambiguous or incomplete.

## Project status

**Phase 0 — spec, template, golden set. Nothing is built yet.** There is no source code, no `src/`, no tests, no Dockerfile, no CI, and no dependency manifest in this repo yet. Do not invent build/lint/test commands — there is nothing to build, lint, or test until Phase 0/1 work lands. Once code exists, this file should be updated with the actual commands (e.g. `uv run pytest`, `ruff check`, per the brief's proposed tooling).

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

Planned layout (brief §13):

```
src/cvr/{parse,label,verify,transform,render,graph,api,mcp}/
templates/fictitious_recruitment.docx
fixtures/candidates/*.json
fixtures/layouts/*.py
fixtures/generated/*.docx
eval/{run_eval.py,thresholds.yaml,report.json}
tests/
Dockerfile
.github/workflows/ci.yml
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

- Local Python is 3.14, but **pin the container and CI to Python 3.12** unless every dependency is confirmed on a newer version.
- Dependency management with `uv` (proposed in the brief; open to change).
- Dev machine: Windows 11, Docker Desktop with WSL2.
