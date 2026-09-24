# 04: Transform: dates, entry order, multi-span units and the transform log

**What to build:** The `transform` node: pure functions from `VerifiedContent` to the content the renderer projects, plus the `Run` record. Date normalisation touches entry date fields only, on canonicalised text: accepted `Jan 2020`, `January 2020`, `01/2020`, `1/2020`, `2020-01`, `Jan '20`, `2020`, and `Present | Current | to date | now` case-folded; output `MM/YYYY`, `YYYY` or `Present`, never an invented month. The range block is tried as a single date first, then split on ` - `, ` – `, ` — `, ` to `, so `2020-01 - 2021-06` is a range and `2020-01` alone is a date. Anything else is a literal: verbatim, sorted by its first four-digit year, else undated; undated entries last in source order. Entry order: end date descending, Present first, then start date descending, then source order. `date_map` (normalised string → source slice) and `split_map` (rendered multi-span text → ordered slices) are emitted for provenance. Multi-span units are joined by one space, which is template text. Removed Spans never reach content. The `Run` record is assembled: run id, labeller configuration, prompt and schema label and hash, tokens and cost, per-block ledger, removals, `NORM_INVISIBLE` events, `date_map`, `split_map`, residue (all of it), unplaced text, `label_failed`.

**Blocked by:** 03 (Verify)

**Status:** in-review

- [x] One test case per accepted format, each in straight and curly-apostrophe form where an apostrophe exists, all yielding the same normalised string
- [x] `2020-01 - 2021-06` parses as a range; `2020-01` alone as a single date; `January 2020 - June 2026`, `01/2020 – 06/2026`, `2022-03 to 2026-07` (the three Layout range styles) all split correctly
- [x] `Summer 2020` is a literal passed through verbatim with sort year 2020; a literal with no year sorts last in source order
- [x] A date inside a certification's text is never touched
- [x] Entry order cases: Present first; two roles both Present ordered by start descending; concurrent roles with equal dates keep source order; year-only dates sort as January of that year for ordering only, never printed with a month
- [x] `date_map` holds one pair per normalised date, mapping back to a raw slice of the range block; `split_map` holds one entry per multi-span unit with slices ascending
- [x] `Run` record type defined; a `Run` from a hand-made `VerifiedContent` serialises to JSON and back unchanged
- [x] No LLM, no clock, no network in any function; every function is deterministic over its inputs

## Comments

### 2026-09-21: built, in review (branch `phase-1/04-transform-dates-order-multi-span-log`)

**What was built.** `src/cvr/transform/dates.py`: `NormalisedDate` (value,
year, month, present, literal) and two pure functions — `parse_date(text)`
classifies one fragment (present-family words, then the seven accepted
numeric/month-name formats, else a verbatim literal sorted by its first
four-digit year) and `split_dates(span)` decides whether a range block's
`Span` is one date or two, trying the whole text as a single date before
searching for a range separator (`canonicalise` maps every dash variant onto
`-`, so one regex, ` - | to `, catches all three Layout styles), and traces
each side back to its own raw slice via the offset map `cvr.text` already
builds. `src/cvr/transform/order.py`: `Ranked[T]` and `order()`, one rank
function shared by both keys (end, start) and both entry kinds, so Present
outranks every date, a date ranks by `(year, month or 1)`, and nothing
sortable ranks last with source order as the final tiebreak.
`src/cvr/transform/__init__.py`: `transform_content(VerifiedContent) ->
TransformResult(content, date_map, split_map)` walks the tree once,
projecting every `Unit` to the string the renderer prints (multi-span units
joined by one space, logged into `split_map`), routing only each entry's
`dates` reference through `split_dates`, and reordering experience/education
via `order()`; `TransformedContent`/`TransformedExperience`/
`TransformedEducation` are the string-shaped output. `LedgerLine` and `Run`
are the transform-log types; `transform(content, run_id, **metadata) ->
(TransformedContent, Run)` assembles a `Run` from explicit, all-optional
arguments. 1638 tests pass in about 31s; ruff and format clean.

**Decisions beyond the ticket text.**

- **A lone (non-range) date is assigned to the entry's `end`, with `start`
  left `None`.** The ticket and spec never say which side a single date
  belongs to when the range block holds only one (`"2020-01"` alone, or
  `"Summer 2020"`). The only such case in the fixtures (c03's education
  entry, `"end": {"year": 2011}, "start": null`) is end-only, and a
  solitary date on a CV entry conventionally reads as a completion date, so
  every lone date — structured or literal — becomes `end`. **For the
  maintainer:** if a future Candidate needs a genuine start-only entry
  (`"since 2020"`), this convention gets it wrong; nothing in the ticket
  or spec resolves the ambiguity, so I flagged it rather than guessing
  further.
- **`Run` and `LedgerLine` live in `cvr.transform`, not `cvr.models`.**
  `Run` needs a per-block ledger and residue, which are `cvr.verify`
  concepts (`LedgerEntry`, `Residue`), but the package rule is `transform`
  depends on `models` and `text` only — it must never import `verify`. So
  `Run.ledger` takes a `dict[str, list[LedgerLine]]` of a small local type
  structurally like `verify.ledger.LedgerEntry` (a raw range, a claimant, a
  removal-or-content kind) rather than the real one, and `Run.residue`/
  `Run.unplaced` are plain `list[Span]` (the separator/non-separator split
  itself is not carried into the log — see below). Ticket 06's pipeline
  function, which imports every node, is where a real `VerifiedDocument`
  gets translated into these plain values before `transform()` is called;
  `transform()` itself never sees a `VerifiedDocument`, only the
  `VerifiedContent` tree plus whatever log pieces its caller hands it. This
  follows ticket 03's own precedent (`VerifiedContent` lives in `models`
  because both `label` and `verify` need it; `VerifiedDocument` stays local
  to `verify` because only the pipeline reads it) one step further: a type
  a *sibling* package's return value would otherwise leak into stays local
  and gets a plain-data shadow instead.
- **`Run.residue` is "all of it" as an unfiltered `list[Span]`, not
  `Residue` objects with the separator flag.** The ticket's own field list
  for `Run` doesn't mention rejections at all (only ticket 03's
  `VerifiedDocument` has those), and residue's separator/unplaced split is
  already fully recoverable from having both `residue` (everything) and
  `unplaced` (the non-separator subset) as two fields — the per-line
  boolean would be redundant. Kept `Run` free of any `verify`-typed value.
- **A multi-span `dates` unit (a removal clipping the middle of a range
  block) is never split into start/end.** No golden-set Candidate produces
  one — a PII value never sits inside a date range's own text — but the
  function must not crash on it. Without the source blocks (`transform`
  only sees `VerifiedContent`, not the parsed document), there is no way to
  recover the raw text *between* two spans of the same block, so no
  reliable contiguous raw slice exists for either side. The whole thing is
  therefore treated as one value (assigned to `end`, per the lone-date
  convention above), still classified by `parse_date` (so a freak but
  genuinely well-formed multi-span date still normalises), recorded in
  `split_map` for provenance, but never in `date_map`. Pinned by
  `test_multi_span_dates_are_not_split_but_are_logged`.
- **Literal dates rank exactly like structured dates for ordering: by
  `(year, month or 1)`, tier below Present.** The ticket only states this
  for the *undated* literal ("sorts last in source order"); a literal that
  does carry a year (`"Summer 2020"`) is not mentioned for entry order at
  all. Treating it the same as a structured date of that year is the
  natural reading of "sorted by its first four-digit year" and keeps one
  rank function for every case; pinned by
  `test_literal_with_a_year_sorts_by_it` /
  `test_literal_with_no_year_sorts_last_like_an_undated_entry`.
- **Two-digit years in `Jan '20`-style dates are read as `20YY`.** Not
  stated in the ticket; every CV in scope is recent enough that this is
  never ambiguous in practice.
- Module split: `cvr.transform.dates` (one fragment, one range block),
  `cvr.transform.order` (the rank function, generic over the entry type via
  a PEP 695 type parameter as `PlannedEntry` already does in `cvr.golden`),
  and `cvr.transform` itself (the tree walk, the projected content types,
  `Run`, and the two public entry points `transform_content`/`transform`).
- `tests/transform/support.py` collided at import time with
  `tests/verify/support.py` (both test directories are import roots with no
  `__init__.py`, so `import support` is ambiguous once both are collected);
  renamed to `tests/transform/transform_support.py`.

PR: none yet (release branch `release/phase-1-04-07`, not opened).


### 2026-09-23: maintainer review, on the release branch

- **Lone date is the entry's `end`**: accepted.
- **One Run, in `models`** (commit `01b1d73`): tickets 04 and 07 were built in parallel, so transform had its own `Run` with copies of verify's ledger and residue shapes, and label had its own `LabelRun`. `Run`, `LabelRun`, `LedgerEntry`, `LedgerKind` and `Residue` now live in `cvr.models`; each node fills its own section and verify uses the shared types directly. Transform no longer builds a `Run`: `transform_content` returns `date_map` and `split_map`, transform's section, and the pipeline function (ticket 06) assembles the `Run`. `unplaced` is derived from the residue rather than stored twice. `LedgerLine` and `transform()` are gone; the Run round-trip test moved to `tests/models/test_run.py`, still over a hand-made `VerifiedContent` through `transform_content`.
- **Multi-span dates left unsplit**: accepted as a rare edge case.
- **Two-digit years** (commit `46729a5`): `'00`–`'26` read as 20YY, `'27`–`'99` as 19YY, so `Jan '98` is 1998, not 2098. The pivot is the constant `TWO_DIGIT_YEAR_PIVOT = 26`, not today's date, because no transform function reads the clock.

Release PR: #21.
