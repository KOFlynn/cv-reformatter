# Phase 0 release 06–13

## Review before merging

- Ticket 08: `pii_leak` blind spot — a one-word address line that is also a job location (e.g. `Cork`) will flag the location; the fixtures from ticket 09 should avoid plain place names as address lines (orch checks this on 09; see Decisions).


## Per-ticket summary

### 08 pii-leak-and-image-leak — PR #10 (merged)
`cvr.eval.pii_leak` (per-class variant matching, one hit per occurrence, most specific rule wins, `PiiHit`), `cvr.eval.image_leak` (hash membership), `RemovalRule` ids and `PII`/`Referee`/`Personal` moved to `cvr.models` (re-exported by `cvr.golden`), two new corruption rows. 193 tests green on branch; 208 after merge with 06, ruff clean.


### 06 template-and-smoke-test — PR #9 (merged)
Template built by `python -m cvr.template.build` into `templates/fictitious_recruitment.docx`; `cvr.template.fill`, `template_text`/`template_tokens`; fake pipeline now uses real template tokens; smoke, determinism and no-image tests. 173 tests green, ruff clean.


## Decisions

- 08 · `eval` may not import `golden` but `pii_leak` takes `PII` → `PII`/`Referee`/`Personal` moved to `cvr.models`, re-exported by `cvr.golden` → keeps the dependency direction and every existing import (sub-agent).
- 08 · shape of `output_text` → mapping of docx part name (body/header/footer) to text; `where` on a hit is the part (sub-agent).
- 08 · image leak "by count and hash" (spec) vs "not in the template's set" (ticket) → set membership; a repeated template logo is not a leak; ADR-0007 amended (sub-agent).
- 08 · national-form phone with unknown country → matched behind any of the four golden-set country codes; over-sensitive on purpose for a zero gate (sub-agent).
- 08 · `TEMPLATE_IMAGE_HASHES` → `[]`, because ticket 06's template has no images (asserted by `tests/template`) (orch, at merge).


- 06 · builder location → `src/cvr/template/build.py` rather than ADR-0006's `templates/build_template.py` → `cvr` is the one import root; ADR amended (sub-agent).
- 06 · where the candidate name goes → agency wordmark in page header, candidate name as body Title (sub-agent).
- 06 · single-date entries → printed without the dash, mirroring the Layouts' `_date_line` (sub-agent).
- 06 · byte-stable .docx → not attempted; only text/tags are asserted identical, since the zip stabiliser lives in `cvr.golden` which `template` may not import (sub-agent). Orch accepted: rebuild the template only when the script changes.


## Merge conflicts resolved

- 08 into release (after 06): `CLAUDE.md` status paragraph (union of both wordings) and `tests/eval/fake_pipeline.py` (kept 06's `template_tokens()`, added 08's `TEMPLATE_IMAGE_HASHES = []`). Resolved locally by orch, full suite 208 green, pushed; PR #10 shows as merged.


## Skipped / incomplete

## Run log

- 2026-09-13T09:44Z merged 08 (PR #10, local conflict resolution); dispatched 10.

- 2026-09-13T09:38Z merged 06 (PR #9); dispatched 07.
- 2026-09-13T09:26Z release branch created from main; dispatched 06, 09, 08 in parallel (cap 3).
