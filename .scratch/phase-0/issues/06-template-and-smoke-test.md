# 06: Fictitious Recruitment template, built by script

**What to build:** The output template, produced by a committed python-docx script and never hand-edited (ADR-0006), with a smoke test that renders it through docxtpl. Sections in brief order; text wordmark, one accent colour, one font, no images; footer "References available on request"; the review appendix present only when `unplaced` is non-empty, headed by a large bold red "TEXT NOT PLACED — NEEDS HUMAN REVIEW" banner; profile present only when non-empty; paragraph-level loop tags so empty sections leave nothing behind. Entry layout: bold title (or qualification), then employer and location separated by a comma with location omitted if absent (or institution), then `MM/YYYY – MM/YYYY` omitted if both absent with `Present` as end, then bullets or detail lines. The template context mirrors `CVContent` plus `unplaced`. Finally, template tokens are extracted from the built template at run time (minus tags) and wired into the fake pipeline so `added_tokens` now sees real template text and row 0 still passes.

**Blocked by:** 04 (Multiset metrics and the fake pipeline)

**Status:** in-review

- [x] Builder script and built template both committed; a note in the builder says never hand-edit the output
- [x] Rebuilding produces identical text and tags
- [x] Smoke test renders with c01's content: opens; contains the name and one bullet; no `{{` or `{%` survives; profile heading absent when profile is empty; banner present iff `unplaced` non-empty; footer text present
- [x] A template-text extractor returns the template's fixed words minus Jinja tags, never a hardcoded list
- [x] Fake pipeline uses the extracted template tokens; row 0 and all existing corruptions still pass
- [x] The smoke test is written so Phase 1's render tests can reuse it unchanged

## Comments

**Implementation notes (ticket 06):** the builder lives at `src/cvr/template/build.py` (`python -m cvr.template.build`) rather than ADR-0006's `templates/build_template.py`, per the spec's one-import-root rule; ADR-0006 carries an amendment. The wordmark sits in the Word page header and the name is the body's Title paragraph. A single date (start or end alone) prints without the dash, mirroring the Layouts. The build is text-deterministic but not byte-stable (zip timestamps), so rebuild only when the script changes; `tests/template/test_build.py` fails when the committed file drifts.
