# 05: Placement accuracy and ordering

**What to build:** The two structural metrics. `placement_accuracy(actual, expected)` aligns entries in two passes (experience on canonicalised employer plus structured start year/month, education on canonicalised institution plus qualification; then greedy best Jaccard overlap over canonicalised leaves with cutoff 0.5; unmatched after both means every leaf misses), compares scalar leaves directly and list leaves by canonicalised text with multiplicity, and returns a `PlacementReport` with precision and recall overall and per field type, `unaligned_entries` per section, and `aligned_by` per entry. `ordering_report(actual, expected)` compares the sequence of alignment keys over the matched subsequence per section and reports the unmatched count separately. After this ticket, a swapped title and employer reads as one miss on the fallback pass rather than eight, and reversing experience order fails ordering and nothing else.

**Blocked by:** 04 (Multiset metrics and the fake pipeline)

**Status:** ready-for-agent

- [ ] Two-pass alignment with the keys and cutoff as specified; `aligned_by` distinguishes key, fallback, unmatched
- [ ] Precision and recall reported separately, overall and per field type; structural vs tunable field types are distinguishable in the report
- [ ] `unaligned_entries` per section is a first-class number
- [ ] Ordering computed over matched entries only; unmatched count reported alongside; tiebreak end desc, start desc, source order is respected
- [ ] Hand-made cases: swapped title/employer aligns on fallback and costs one leaf; lost entry is unaligned; promotion (same employer, two starts) aligns on key; duplicate skill counted with multiplicity; concurrent roles with equal dates keep source order
- [ ] Fake-pipeline corruption: reverse experience order fails ordering only, placement passes
- [ ] Direction assertions added to the ticket-04 corruptions: insert a word lowers precision only; drop a bullet lowers recall only; bullets to appendix lowers recall
