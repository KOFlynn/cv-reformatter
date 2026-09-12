# 04: Multiset metrics and the fake pipeline

**What to build:** The first three metrics and the harness that proves them. `Finding` (what, count, where; sorted), `added_tokens`, `dropped_tokens` and `appendix_rate`, all pure functions over token lists, with hand-made test cases kept apart from the Candidates. Then the fake pipeline: a function from a Candidate to metric inputs (output units = content leaves; output tokens = tokenised leaves plus template tokens, an empty list until the template exists; date map pairs each `expected` with itself; removed tokens = PII values; appendix = `unplaceable`). Row 0 asserts zero findings over every loaded Candidate. Three corruptions each declare a blast radius over the metrics that exist so far, and the test asserts every metric inside fails and every metric outside passes. After this ticket, inserting a word into a bullet is caught and dropping a bullet is caught, and each is caught by the right metric.

**Blocked by:** 02 (Content model, Candidate model, loader, and c01)

**Status:** in-review

- [x] `Finding` carries what, count and where; every metric returns findings sorted
- [x] `added_tokens(source, output, template, date_map)`: output minus source, template and mapped dates as a multiset
- [x] `dropped_tokens(source, output, removed, appendix)`: source tokens not in output, removal log or appendix
- [x] `appendix_rate(appendix_tokens, source_content_tokens)`: source content tokens are source minus rule-removed
- [x] Hand-made cases live under the eval tests directory, never under the candidates directory; per metric: clean, one per finding kind, empty inputs, sorted output
- [x] Fake pipeline maps a Candidate to every metric input; parametrised over all loaded Candidates
- [x] Row 0: zero findings and appendix rate equal to the unplaceable share for every Candidate
- [x] Corruptions with blast radii: insert a word (added), drop a bullet (dropped), move one job's bullets into the appendix (appendix); each fails only its declared metrics
- [x] The corruption table is data so later tickets add rows and columns without rewriting the test

## Comments

**2026-09-12 (Claude Code):** Implemented on branch `phase-0/04-multiset-metrics-and-fake-pipeline`, PR #3 (https://github.com/KOFlynn/cv-reformatter/pull/3). `cvr.eval` gains `Finding` (`finding.py`), `added_tokens`/`dropped_tokens` (`multiset.py`, Counter arithmetic with multiplicity) and `appendix_rate` (`appendix.py`); it imports only `cvr.text`. The harness is test-side: `tests/eval/fake_pipeline.py` (honest pipeline, `metric_inputs`, `leaves`, `pii_values`, `unplaceable_share`) and `tests/eval/corruptions.py` (`CHECKS` columns, `CORRUPTIONS` rows, each row writing out both `fails` and `passes` in full so a new metric must be placed in every row on purpose; the test asserts the two partition `CHECKS`). Decisions beyond the ticket text, each flagged for the maintainer: `Finding` sorts by `where`, then `what`, then `count` (groups by location; construction is keyword-only so call sites still read what/count/where); `appendix_rate` defines 0/0 as `0.0` and n/0 as `1.0` rather than raising; the appendix check in Phase 0 is "rate equals the Candidate's unplaceable share" since no threshold exists yet, with the share computed from the Candidate alone so the oracle is independent of the metric; a Candidate with no job with bullets skips the corruption rows (visible as `s`) rather than failing; the test helpers are sibling modules imported by pytest's rootdir path insertion, not a package. Two-axis review found no hard violations; follow-ups applied (empty candidates directory fails row 0 loudly, dead `count > 0` guard removed, `Damage` type alias). 109 tests, ruff clean.
