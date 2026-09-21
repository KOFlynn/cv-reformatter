# 04: Transform: dates, entry order, multi-span units and the transform log

**What to build:** The `transform` node: pure functions from `VerifiedContent` to the content the renderer projects, plus the `Run` record. Date normalisation touches entry date fields only, on canonicalised text: accepted `Jan 2020`, `January 2020`, `01/2020`, `1/2020`, `2020-01`, `Jan '20`, `2020`, and `Present | Current | to date | now` case-folded; output `MM/YYYY`, `YYYY` or `Present`, never an invented month. The range block is tried as a single date first, then split on ` - `, ` – `, ` — `, ` to `, so `2020-01 - 2021-06` is a range and `2020-01` alone is a date. Anything else is a literal: verbatim, sorted by its first four-digit year, else undated; undated entries last in source order. Entry order: end date descending, Present first, then start date descending, then source order. `date_map` (normalised string → source slice) and `split_map` (rendered multi-span text → ordered slices) are emitted for provenance. Multi-span units are joined by one space, which is template text. Removed Spans never reach content. The `Run` record is assembled: run id, labeller configuration, prompt and schema label and hash, tokens and cost, per-block ledger, removals, `NORM_INVISIBLE` events, `date_map`, `split_map`, residue (all of it), unplaced text, `label_failed`.

**Blocked by:** 03 (Verify)

**Status:** ready-for-agent

- [ ] One test case per accepted format, each in straight and curly-apostrophe form where an apostrophe exists, all yielding the same normalised string
- [ ] `2020-01 - 2021-06` parses as a range; `2020-01` alone as a single date; `January 2020 - June 2026`, `01/2020 – 06/2026`, `2022-03 to 2026-07` (the three Layout range styles) all split correctly
- [ ] `Summer 2020` is a literal passed through verbatim with sort year 2020; a literal with no year sorts last in source order
- [ ] A date inside a certification's text is never touched
- [ ] Entry order cases: Present first; two roles both Present ordered by start descending; concurrent roles with equal dates keep source order; year-only dates sort as January of that year for ordering only, never printed with a month
- [ ] `date_map` holds one pair per normalised date, mapping back to a raw slice of the range block; `split_map` holds one entry per multi-span unit with slices ascending
- [ ] `Run` record type defined; a `Run` from a hand-made `VerifiedContent` serialises to JSON and back unchanged
- [ ] No LLM, no clock, no network in any function; every function is deterministic over its inputs
