# 15: The retry in the eval, and ADR-0012

**What to build:** the eval runs the retry and shows what it costs and earns. The cache key includes a hash of the feedback, so each attempt is cached separately and a cached run replays the retries exactly. The report gains three columns: retries fired, characters placed by a retry, and retry cost. Cost totals sum all attempts, and thresholds are unchanged. A live eval on the deployed provider shows the expected pattern: the eight documents with deliberate unplaceable fragments (c09 and c11 in every Layout) make one retry each with no progress, and documents placed fully on the first attempt make none. ADR-0012 records the graph and its bounded, additions-only retry.

**Blocked by:** 14

**Status:** ready-for-agent

- [ ] Runner tests: the feedback hash changes the cache key; a cached rerun reproduces the same retries without a call
- [ ] Report tests: the three columns, per layout, tag and candidate; totals summed over attempts
- [ ] A live eval run's report is shown in the PR with the expected retry pattern, every hard gate at zero and the thresholds met; any deviation from the pattern is explained
- [ ] ADR-0012 written, including "what would change" (neighbouring-block feedback; leaner feedback, measurable on a failure-prone model such as Haiku and then confirmed on the deployed one)
- [ ] CLAUDE.md, the README and the brief's §10 graph box updated
