# Phase 0 release 06–13

## Review before merging

- **Ticket 09: maintainer must review all eleven candidate fixtures (`fixtures/candidates/c02.json`–`c12.json`) before merging release.** The "Maintainer sign-off recorded in the PR" checkbox is deliberately unticked on PR #11. Orch spot-checked names/phones/emails/URLs/addresses: all synthetic (555 numbers, `example.*` domains, `-fictional` handles).
- Ticket 09 ⇄ 08: seven candidates' address lines had to be reworked (street / non-content road or suburb / postcode, no bare town or county line) because `pii_leak`'s address rule flags any address line that also appears as a work or education location. Design question for Phase 1: real CVs routinely say "Cork" in both places, so the zero PII gate may need a narrower address rule (e.g. only lines with a digit/postcode, or the full address in sequence) — the maintainer should decide before the Phase 1 baseline.
- Ticket 08: `pii_leak` blind spot — a one-word address line that is also a job location (e.g. `Cork`) will flag the location; the fixtures from ticket 09 should avoid plain place names as address lines (orch checks this on 09; see Decisions).
- Ticket 13 changed test semantics: an inapplicable corruption is now a **failure, not a skip**, and the apostrophe row falls back to a hyphen→en-dash swap from the confusable table on Candidates without an apostrophe (989 passed, 0 skipped). This constrains future Candidates (documented in the spec); confirm you agree with fail-over-skip.
- Ticket 13 edited `docs/project-brief.md` (status line and §10 Phase 0 checkboxes) and `.scratch/phase-0/spec.md` (appendix-row direction wording, future-Candidate constraint). The brief is the source of truth — check those edits.
- Ticket 07: the "straighten a curly apostrophe" corruption row runs only in the *curling* direction (no Candidate carries a curly apostrophe in a leaf, since confusables are a Layout decision), and is skipped for 3 Candidates with no apostrophe at all. The specified straightening direction is unexercised by the fake pipeline until a Candidate has a curly apostrophe in its expected content, or the real Phase 1 pipeline runs on the two-column/header-footer documents.
- Ticket 12: the header-footer date range is joined with ` to ` (`2022-03 to 2026-07`) rather than a dash, because a dash between dash-separated dates is ambiguous and an en dash is an off-column confusable. Confirm you are happy with that reading of the `2020-01` style.
- Ticket 13 rewrote `tests/golden/test_generate.py` to module-scoped generation fixtures (tests/golden ~4.5 min → ~12 s). Behaviourally equivalent per its report; worth a glance since it is the regression net for all 48 pairs. This resolves the O(n²) regeneration concern raised under ticket 12.
- Ticket 07 edited `.scratch/phase-0/spec.md` (one corruption-table row and a note, following ticket 05's precedent) — confirm that is acceptable.
- Ticket 11: "opens in Word" is evidenced with LibreOffice headless only (Word is not on the dev machine). Open `fixtures/generated/c01__text-box.docx` in Word once to confirm the two VML text boxes render.
- Ticket 10: the two-column docx SHAs were produced on Windows; the branch CI run on Linux (push run on `562c39c`) passed, which is the confirmation that the committed bytes are platform-stable.

## Per-ticket summary

### 13 integrate-and-verify — PR #16 (merged)
All 48 pairs regenerated in one run, byte-identical; spec's eight-row corruption table pinned as a literal against `CORRUPTIONS` (directions included); `NotApplicable` now fails instead of skipping, apostrophe row falls back to a confusable-table swap; golden regeneration test made module-scoped (full suite ~5 min → ~30 s); `CLAUDE.md` rewritten for "Phase 0 complete"; brief §10 Phase 0 boxes ticked. 989 passed, 0 skipped, ruff clean.


### 12 header-footer-layout — PR #15 (merged)
`HeaderFooterLayout` (`header-footer`): phone + email in the page header, address + URLs in the footer, `2020-01` dates, literal `–` bullets, education last, both sections reversed, ZWSP and curly apostrophes recorded via `Decisions.injected`; `text_by_part` walker in `tests/docx_text.py`; 33 tests including per-Candidate "each contact value in its home part and nowhere else"; twelve pairs committed; all 36 pre-existing pairs byte-identical. Sub-agent merged release (11) itself. 984 passed, 3 skipped, ruff clean.


### 11 text-box-layout — PR #14 (merged)
`TextBoxLayout` (`text-box`): contact block, skills and unplaceable fragments each in a VML text box written as raw `w:txbxContent` via lxml; `Jan '20` dates, literal `-` bullets, education after experience, experience rotated by one and education reversed; NBSP and soft-hyphen injection recorded on `Decisions`; 26 Layout tests; twelve pairs committed. One follow-up round to merge release (07 + 10) and put `LAYOUTS` in matrix order. 851 passed, 3 skipped, ruff clean.


### 07 provenance-and-punctuation-fidelity — PR #12 (merged)
`cvr.eval.provenance_violations` (canonicalised whole-unit substring of a source block, or whole-unit equality with a template unit or date-map rendered side) and `cvr.eval.punctuation_fidelity` (raw equality, findings name the differing code points); shared `findings` helper; fake pipeline gains `source_blocks`, `template_units`, `locate`, raw `pairs`; every corruption row now carries all eight metrics; two new rows. One follow-up round to merge release (08 + 09). 595 passed, 3 skipped, ruff clean.

### 10 two-column-layout — PR #13 (merged)
`TwoColumnLayout` (`two-column`): one two-cell table, photo + contact + Academic Background + referees + fragments left, everything else right; `MM/YYYY` dates, en dash ranges, literal `•`, experience reversed; curly apostrophes/double quotes injected via `Decisions.injected`; `placeholder_photo()` stdlib-only PNG with hand-rolled stored deflate for cross-platform byte stability; `image_count` test per pair. One follow-up round to merge release (09) and generate c02–c12 pairs; nothing in the Layout needed changing. 660 passed on branch; 715 after merge with 07. Orch resolved a `CLAUDE.md` conflict.


### 09 eleven-candidates-and-tags — PR #11 (merged)
Full 19-member `Tag` enum (14 computable predicates, 5 author-declared), fixtures c02–c12 per the spec allocation table, per-predicate and allocation tests, single-column pairs regenerated for c02–c12 (c01 byte-identical). One follow-up round: merged release and reworked seven addresses (see Decisions). 540 tests green, ruff clean. Maintainer sign-off deferred to the release PR.


### 08 pii-leak-and-image-leak — PR #10 (merged)
`cvr.eval.pii_leak` (per-class variant matching, one hit per occurrence, most specific rule wins, `PiiHit`), `cvr.eval.image_leak` (hash membership), `RemovalRule` ids and `PII`/`Referee`/`Personal` moved to `cvr.models` (re-exported by `cvr.golden`), two new corruption rows. 193 tests green on branch; 208 after merge with 06, ruff clean.


### 06 template-and-smoke-test — PR #9 (merged)
Template built by `python -m cvr.template.build` into `templates/fictitious_recruitment.docx`; `cvr.template.fill`, `template_text`/`template_tokens`; fake pipeline now uses real template tokens; smoke, determinism and no-image tests. 173 tests green, ruff clean.


## Decisions

- 13 · inapplicable corruption → fail rather than skip → the ticket says "over all twelve Candidates"; a skip narrows that silently (sub-agent).
- 13 · apostrophe row on Candidates with no apostrophe → hyphen→en-dash swap from the shared confusable table, not a Candidate content change → Candidates are maintainer-reviewed ground truth (sub-agent).
- 13 · fix the O(n²) golden regeneration test → yes, the checklist's regeneration item touches it (sub-agent; orch had flagged it as optional).
- 13 · "Designed in Word" exit criterion → ticked with an ADR-0006 note rather than reworded (sub-agent).
- 13 · spec table order vs `CORRUPTIONS` order → compared by row name; ADR-0007 rows stay grouped last (sub-agent).


- 12 · date-range join in the `2020-01` style → ` to ` (sub-agent; review topic above).
- 12 · fragment placement → `footer-end` (sub-agent).
- 12 · bullet `–` not recorded as an injected confusable → matrix names only ZWSP + curly apostrophes for this Layout; two-column likewise does not record its `•` (sub-agent).
- 12 · ZWSP placement → one after each bullet glyph, never inside emails/URLs, so PII stays an exact substring of its part (sub-agent).
- 12 · DOB/personal details go in the body under the name; referees before Qualifications → the ticket only places phone/email/address/URL in header/footer (sub-agent).
- 10/11/12 · each Layout keeps private paragraph helpers rather than a shared module → three-way duplication now exists; **follow-up ticket wanted** (review topic).


- 11 · text-box form → VML `w:pict`/`v:shape`/`v:textbox` rather than DrawingML with a VML fallback → the fallback form carries every string twice, which would double-count in every token metric; VML holds it once (sub-agent). Orch verified: c01 text-box has 2 `txbxContent`, 0 `AlternateContent`, the email appears once, no media.
- 11 · NBSP location → inside `format_date` so the manifest's `printed` string equals what the document carries (sub-agent).
- 11 · year-only date in `Jan '20` style → printed `2020`, not `'20` (sub-agent).
- 11 · fragments → a trailing text box, placement `text-box-end` (sub-agent).


- 07 · template-unit match semantics → whole-unit equality with a template unit, not substring → spec's Further Notes: whole-unit is what closes the template-word hole (sub-agent).
- 07 · empty/whitespace-only output unit → skipped by provenance (nothing rendered, nothing to prove), documented (sub-agent).
- 07 · swap-row punctuation column (blank in spec) → passes, because fidelity only sees located spans (ADR-0007); recorded in the spec table with a ticket-07 note (sub-agent).
- 07 · `source_blocks` for the fake pipeline → content leaves + PII values + unplaceable, i.e. what a Layout prints (sub-agent).
- 07 · 08's "re-emit email in header" row passes provenance because the header is not in `output_units` — matches the spec's intent that a leaked email is provenance-clean text (sub-agent, orch agrees).
- 10 · "curly quotes" scope → apostrophes (U+2019) and alternating double quotes (U+201C/U+201D); no Candidate has straight double quotes, so U+201C/D appear only in unit tests (sub-agent).
- 10 · `GENERATOR_VERSION` → left at 0.1.0 because no existing Layout's output changed (sub-agent). Same call made independently by 11.
- 10 · headings not in the matrix (Contact, Certifications, Other Information, Referees) → added, needed for source coverage (sub-agent).
- 10 · shared paragraph helpers duplicated between `single_column.py` and `two_column.py` → not extracted; 11 duplicated again → **follow-up PR wanted after 11/12 merge** (review topic).


- 09 · can `pii-in-bullet` / `inline-skills` be computed predicates? → author-declared → they describe how the *source* prints content; `CVContent` is the expected output, so content alone cannot prove them (sub-agent). Review topic: a Layout (or ticket 13) must actually print the phone inside c08's bullet for the trap to exist in a generated document.
- 09 · `concurrent-roles` → two experience entries ending Present; `empty-sections` → certifications and additional both empty; `date-in-body-text` → standalone 4-digit year in any body string (sub-agent).
- 09 · literal date sorting → `Summer 2020` carries `year: 2020` per the brief; `year-only-date` excludes literals (sub-agent).
- 09 · address lines colliding with job/education locations under 08's `pii_leak` → fixed on the fixture side (orch): town/county lines dropped in favour of street + non-content road/suburb + Eircode/postcode for c02, c03, c04, c06, c08, c11, c12; locations, tags and allocation table untouched (sub-agent executed). Why: 08 documented the blind spot as a fixture convention and the metric is deliberately over-sensitive for a zero gate; the Phase 1 question is logged above.
- 09 · real institutions are used (as c01 already does); all employers invented (sub-agent).
- 09 · `CONTEXT.md`'s Tag entry does not mention author-declared tags → left untouched; a one-line domain-doc update may be wanted (review topic).


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
- 12 into release (after 11): `src/cvr/golden/layouts/__init__.py` registry and `CLAUDE.md` status paragraph, resolved by the 12 sub-agent on its branch before opening the PR. Full regeneration produced zero diffs on the 36 pre-existing pairs.

- 11 into release (after 10): `src/cvr/golden/layouts/__init__.py` (import, `__all__`, `LAYOUTS` set to matrix order). Delegated to the 11 sub-agent; all 36 committed pairs byte-identical after regeneration; 851 green.

- 07 into release (after 08 + 09): `CLAUDE.md`, `tests/eval/corruptions.py` (6 hunks), `tests/eval/fake_pipeline.py` (3), `tests/eval/test_fake_pipeline.py` (1). Delegated to the 07 sub-agent (its context knew both sides); unions only, `Damage(candidate, result)` adopted for its rows; one lost `),` caught by ruff before commit.
- 10 into release (after 07): `CLAUDE.md` status paragraph only. Resolved locally by orch (union); full suite 715 passed, 3 skipped; pushed; PR #13 shows as merged.

- 09 into release (after 06 + 08): import block of `src/cvr/golden/candidate.py` (union, keeping the `PII`/`Referee`/`Personal` re-export). Resolved by the 09 sub-agent on its branch; 42 `pii_leak` row-0 failures then fixed on the fixture side. 540 green.


- 08 into release (after 06): `CLAUDE.md` status paragraph (union of both wordings) and `tests/eval/fake_pipeline.py` (kept 06's `template_tokens()`, added 08's `TEMPLATE_IMAGE_HASHES = []`). Resolved locally by orch, full suite 208 green, pushed; PR #10 shows as merged.


## Skipped / incomplete

- Nothing skipped. All eight tickets (06–13) merged into release.
- Deferred, not delivered (each logged above): maintainer sign-off on the eleven fixtures (ticket 09, by design); a Candidate with a curly apostrophe in a leaf so the straightening direction of the apostrophe row is exercised; a shared paragraph-helper module for the three newer Layouts; the Phase 1 question on the `pii_leak` address rule vs job locations.


## Run log

- 2026-09-13T10:57Z merged 13 (PR #16). Finish checks on release: uv sync, ruff check, ruff format --check, pytest — 989 passed. Worktrees and feature branches all removed. Opening release PR.

- 2026-09-13T10:44Z merged 12 (PR #15). Dispatching 13 alone.

- 2026-09-13T10:24Z merged 11 (PR #14). 12 running.

- 2026-09-13T10:16Z merged 07 (PR #12) and 10 (PR #13, local conflict resolution). 11 returned → follow-up round 1 (merge release with 10, reorder LAYOUTS). Dispatched 12.

- 2026-09-13T09:54Z 09 returned; conflict + 42 pii failures → follow-up round 1 to the 09 agent; merged 09 (PR #11). 07 returned with 4 conflicting files → follow-up round 1 to the 07 agent (merge release). 10 still running.

- 2026-09-13T09:44Z merged 08 (PR #10, local conflict resolution); dispatched 10.

- 2026-09-13T09:38Z merged 06 (PR #9); dispatched 07.
- 2026-09-13T09:26Z release branch created from main; dispatched 06, 09, 08 in parallel (cap 3).
