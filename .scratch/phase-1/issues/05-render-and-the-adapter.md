# 05: Render and the adapter

**What to build:** The `render` node and its inverse. Render fills the committed template through `cvr.template.fill` from transformed content projected to strings plus the unplaced list in source order; it composes composite lines exactly as the template does (employer and location with a comma, location omitted if absent; the date line with an en dash, omitted if both dates absent); the appendix and profile render only when non-empty. The adapter walks a rendered document back to leaves by field type, using the template's headings and paragraph styles and the same composite-line conventions, so the Phase 0 metrics are fed from real output without changing. The renderer round-trip test proves the pair: known content in, document out, adapter back, leaves equal and in order; a composite line assembled in the wrong order is caught here and nowhere else, which the ADR states. On the eval side, the fake pipeline gains a `split_map` input and `provenance_violations` permits a unit iff it equals its logged slices joined, each a substring of its block, in ascending order; the corruption table gains "join two slices out of source order" failing provenance only.

**Blocked by:** 04 (Transform)

**Status:** in-review

- [x] `render(content, unplaced) -> bytes` over the committed template; no `{{` or `{%` survives in any output
- [x] Adapter returns leaves by field type (name, profile, skills, education entries, experience entries, certifications, additional, appendix) from a rendered document
- [x] Round-trip over every Candidate's content: adapter(render(content)) equals the content's leaves, in order, including composite lines split back into employer/location and start/end
- [x] Round-trip with unplaced text: banner present and the appendix leaves equal the unplaced list in order; without unplaced text the banner is absent
- [x] Profile absent → no profile heading; empty certifications and additional → no stray paragraphs (extends the Phase 0 smoke test)
- [x] `provenance_violations` accepts a `split_map`; a multi-span unit whose slices are ascending substrings of one block passes; one whose slices are joined out of source order fails
- [x] Corruption row "join two slices out of source order" added with blast radius provenance only, asserted over every Candidate
- [x] `punctuation_fidelity` receives raw pairs for every piece of a multi-span unit, not the joined text

## Comments

### 2026-09-24: built, in review (branch `phase-1/05-render-and-the-adapter`)

**What was built.** `src/cvr/render/render.py`: `render(content: TransformedContent,
unplaced: list[Span]) -> bytes`, which turns transform's output into the
`CVContent` shape `cvr.template.fill` already takes (`_to_cv_content`: every
plain date string wrapped as `DateValue(expected=...)`, a rejected leaf's
`None` becomes `""`) and calls `fill` unchanged, so every composite line is
still composed by the template's own Jinja and nothing here invents
wording. `src/cvr/render/adapter.py`: `adapt(document: bytes) -> Adapted`
(`content: TransformedContent`, `appendix: list[str]`), a python-docx walk
keyed on the template's own headings (`Heading 1`), the `Title`/`List
Bullet` styles and bold runs to find entry boundaries, recomposing the
employer/location and date-range composite lines in reverse. `src/cvr/render/__init__.py`
re-exports `render`, `adapt`, `Adapted`. Tests:
`tests/render/test_render.py` (extends the Phase 0 template smoke test:
same assertions against `render` instead of `fill`, plus empty
certifications/additional), `tests/render/test_roundtrip.py`
(`adapt(render(content, unplaced)) == (content, appendix)` over every one of
the 12 Candidates, plus explicit composite-line and unplaced/banner cases),
`tests/render/render_support.py` (`to_transformed_content`: a Candidate's
`CVContent` down to the `TransformedContent` shape `render` takes, using
each `DateValue.expected` directly since that is transform's own hand-written
answer for that date). On the eval side: `provenance_violations` gained an
optional `split_map` argument (`src/cvr/eval/provenance.py`) — a unit it
names is checked only through its ordered raw slices (each a canonicalised
substring of one common block, the next found strictly after the last), never
the whole-unit substring rule, because a multi-span unit's joined text is
never itself a contiguous substring of its block. `tests/eval/fake_pipeline.py`
gained `PipelineResult.split_map` and `MetricInputs.split_map`, and
`punctuation_fidelity`'s pairs are now built per slice for a split_map unit.
`tests/eval/corruptions.py` gained the row "join two slices out of source
order" (declares the first bulleted job's first bullet a two-slice join of
its own halves in the wrong order; nothing printed changes), asserted over
every Candidate with blast radius provenance only. `docs/adr/0007-provenance-check-and-blind-spots.md`
amended for both (the split_map check, and why the renderer round-trip test
rather than the eval gate is what catches a composite line assembled in the
wrong order). 1718 tests pass in about 40s, 1 skipped (the labeller spike
test, no API key); ruff and format clean.

**Decisions beyond the ticket text.**

- **`render` depends on `cvr.transform` for `TransformedContent`, not just
  `models` and `text`.** The Phase 1 spec's dependency table (written before
  ticket 04 landed) says "`transform` and `render` on `models` and `text`",
  but ticket 04 actually placed `TransformedContent` inside `cvr.transform`,
  and `render(content, unplaced)`'s `content` has to be *something* — the
  ticket names no other candidate shape, and duplicating an identical
  dataclass inside `render` just to avoid the import felt like ceremony the
  brief's "no scope creep" rule would flag, not a real architectural
  boundary. My own task briefing's layering rule for this ticket names the
  forbidden dependencies explicitly (`eval`, `golden`, `verify`, `parse`,
  `label`) and does not forbid `transform`, so I read that as the
  authoritative, ticket-04-aware statement and took it. **For the
  maintainer:** if this reading is wrong and `render` should stay off every
  other node package, the fix is a small local shadow type in `render` (as
  ticket 04 did for `verify`'s ledger/residue shapes in `transform`), not a
  redesign of `render` itself.
- **`fill()` and the committed template are untouched; `render` adapts
  `TransformedContent` into a `CVContent` and calls `fill` unchanged.**
  `fill`'s existing contract (`content: CVContent`, dates as `DateValue`
  with `.expected`) is exercised directly by the Phase 0 smoke test and by
  `tests/eval/fake_pipeline.py`, both of which the ticket says must keep
  working; changing the template's date-line Jinja to take a plain string
  would break both. `_to_cv_content` is therefore the one adaptation layer:
  a normalised date string becomes `DateValue(expected=...)` with every
  other field left at its default (nothing else in the template reads
  them), and a rejected leaf's `None` becomes `""` rather than the literal
  word "None" Jinja would otherwise print for a bare `None`.
- **The adapter's return type is `TransformedContent` plus a separate
  `appendix: list[str]` (`Adapted`), not a reconstructed `CVContent`.** A
  `CVContent.DateValue` carries `month`/`year` as structured ints; the
  adapter can only ever recover the string that was printed, so
  reconstructing a `DateValue` would mean inventing month/year fields no
  rendered text states. Returning the same shape `render` takes makes the
  round-trip test a direct equality assertion and needs no new comparison
  logic; wiring an adapter output into the Phase 0 structural metrics
  (`eval.leaves`/`eval.alignment`, which do want `CVContent`) is the eval
  runner's job (ticket 09), not this one — the ticket's own checklist item
  only asks for "leaves by field type", not for `CVContent` specifically.
- **Two composite-line reads in the adapter are heuristics, not general
  parsers, in the same stated-not-mitigated spirit as ADR-0008's text-box
  order.** The employer/location line is split on the first `", "`, because
  the template inserts exactly one such separator and no employer name in
  the golden set contains a comma of its own (checked against all 12
  Candidates). The date line is told apart from an education entry's
  "details" paragraph, which shares its plain style, by shape: it either
  joins two pieces with the template's own `" – "` or is itself one of
  `transform.dates`' three formatted outputs (`MM/YYYY`, `YYYY`, `Present`);
  experience needs no such check since its bullets carry their own `List
  Bullet` style. Checked against every Candidate, including c03's lone
  `"2011"` end date and c04's real-date-plus-literal `"01/2018 – Summer
  2020"`; a lone literal date sitting where it could be confused for a
  details line is the one shape this does not attempt to recognise, and no
  Candidate produces it. Recorded in the adapter's module docstring and the
  ADR-0007 amendment, not mitigated, because nothing in the golden set
  exercises the case that would need it.
- **`provenance_violations`'s `split_map` lookup is by exact rendered-unit
  string, not canonicalised, matching how `date_map` is already keyed.**
  transform's own `split_map` uses the identical joined string as both the
  dict key and the content that ends up in `output_units`, so an exact
  lookup is what a real Run actually produces; canonicalising the key would
  only risk two distinct multi-span units colliding.
- **The ascending-order check is a sequential `str.find` per slice within
  one candidate block, not a positional (start/end) comparison.** Eval
  metrics are pure functions over plain strings by design (no `Span`
  anywhere in `cvr.eval`), so there are no real offsets to compare; walking
  forward through a block and requiring each slice to be found after the
  last is the string-only equivalent of "ascending, non-overlapping,
  same block", and it is what actually catches the new corruption row
  (searching for the true second half first finds it at its real,
  later position; searching for the true first half afterward finds
  nothing, since it only occurs earlier).
- **The corruption row changes nothing printed — only `split_map`'s claimed
  order — precisely so its blast radius is provenance alone.** Every other
  row that touches content moves at least one other metric (placement,
  added/dropped, ...); this row had to leave the rendered bullet exactly as
  row 0's so that only the metric reading `split_map` at all could react,
  which is also the strongest form of the "no single check would have been
  enough" argument ADR-0007 already makes for the other two rows.
- **ADR-0007, not a new ADR number, for both the `split_map` check and the
  round-trip test.** ADR-0010 is reserved for ticket 14's deployment
  decision, and there is no ADR number set aside for `render`. ADR-0007 is
  already the running record of provenance's blind spots and the checks
  that close each one (a leaked-but-copied PII value, a photo, a
  template word used as filler, a straightened apostrophe); a multi-span
  unit's joined text having no single contiguous source location, and a
  composite line's field-order bug having no token-level signature at all,
  are two more instances of exactly that pattern, so I amended it rather
  than opening a fourth ADR for a one-paragraph point each.
- **`tests/render/support.py` renamed to `tests/render/render_support.py`
  before the first commit.** Same collision ticket 04 hit and documented:
  every `tests/<package>/` directory is an import root with no
  `__init__.py`, so a bare `support.py` name collides with
  `tests/verify/support.py` at collection time. Followed ticket 04's fix
  (`transform_support.py`) rather than rediscovering it.

PR: none yet.
