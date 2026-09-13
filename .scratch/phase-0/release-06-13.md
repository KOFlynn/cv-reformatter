# Phase 0 release 06–13

## Review before merging

## Per-ticket summary

### 06 template-and-smoke-test — PR #9 (merged)
Template built by `python -m cvr.template.build` into `templates/fictitious_recruitment.docx`; `cvr.template.fill`, `template_text`/`template_tokens`; fake pipeline now uses real template tokens; smoke, determinism and no-image tests. 173 tests green, ruff clean.


## Decisions

- 06 · builder location → `src/cvr/template/build.py` rather than ADR-0006's `templates/build_template.py` → `cvr` is the one import root; ADR amended (sub-agent).
- 06 · where the candidate name goes → agency wordmark in page header, candidate name as body Title (sub-agent).
- 06 · single-date entries → printed without the dash, mirroring the Layouts' `_date_line` (sub-agent).
- 06 · byte-stable .docx → not attempted; only text/tags are asserted identical, since the zip stabiliser lives in `cvr.golden` which `template` may not import (sub-agent). Orch accepted: rebuild the template only when the script changes.


## Merge conflicts resolved

## Skipped / incomplete

## Run log

- 2026-09-13T09:38Z merged 06 (PR #9); dispatched 07.
- 2026-09-13T09:26Z release branch created from main; dispatched 06, 09, 08 in parallel (cap 3).
