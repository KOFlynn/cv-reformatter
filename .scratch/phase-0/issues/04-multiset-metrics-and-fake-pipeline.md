# 04: Multiset metrics and the fake pipeline

**What to build:** The first three metrics and the harness that proves them. `Finding` (what, count, where; sorted), `added_tokens`, `dropped_tokens` and `appendix_rate`, all pure functions over token lists, with hand-made test cases kept apart from the Candidates. Then the fake pipeline: a function from a Candidate to metric inputs (output units = content leaves; output tokens = tokenised leaves plus template tokens, an empty list until the template exists; date map pairs each `expected` with itself; removed tokens = PII values; appendix = `unplaceable`). Row 0 asserts zero findings over every loaded Candidate. Three corruptions each declare a blast radius over the metrics that exist so far, and the test asserts every metric inside fails and every metric outside passes. After this ticket, inserting a word into a bullet is caught and dropping a bullet is caught, and each is caught by the right metric.

**Blocked by:** 02 (Content model, Candidate model, loader, and c01)

**Status:** ready-for-agent

- [ ] `Finding` carries what, count and where; every metric returns findings sorted
- [ ] `added_tokens(source, output, template, date_map)`: output minus source, template and mapped dates as a multiset
- [ ] `dropped_tokens(source, output, removed, appendix)`: source tokens not in output, removal log or appendix
- [ ] `appendix_rate(appendix_tokens, source_content_tokens)`: source content tokens are source minus rule-removed
- [ ] Hand-made cases live under the eval tests directory, never under the candidates directory; per metric: clean, one per finding kind, empty inputs, sorted output
- [ ] Fake pipeline maps a Candidate to every metric input; parametrised over all loaded Candidates
- [ ] Row 0: zero findings and appendix rate equal to the unplaceable share for every Candidate
- [ ] Corruptions with blast radii: insert a word (added), drop a bullet (dropped), move one job's bullets into the appendix (appendix); each fails only its declared metrics
- [ ] The corruption table is data so later tickets add rows and columns without rewriting the test
