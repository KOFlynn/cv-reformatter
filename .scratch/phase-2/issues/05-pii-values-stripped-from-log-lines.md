# 05: PII values stripped from log lines

**What to build:** the API's log lines keep the transform log's text, which stays inside our own tenant, but never a PII value. The log writer strips PII wherever it occurs: text removals under a PII rule, ledger claims under a PII rule, residue overlapping such a removal, and any error field. A stripped removal keeps its rule, block, offsets, length and character class, so an over-eager rule is still visible. Headings removed under RM_HEADING are not PII and stay. The Run itself is unchanged, so the eval's `removal_precision`, which reads the in-memory Run, is unaffected.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A document built at test time with a unique email-shaped canary (e.g. `canary-7f3@example.invalid`) and a unique digit-string phone goes through the API with the oracle labeller; neither value, nor its normalised forms (spaces removed, case folded), appears in the captured log output
- [ ] Positive control: a non-PII content string from the same document does appear in the block lines
- [ ] Stripped removals log rule, block, offsets, length and class (tested)
- [ ] The Run returned by `reformat` still holds the removal text; the `removal_precision` tests pass unchanged
- [ ] Every line stays under the existing size limit for the golden set (existing test)
- [ ] The log module's docstring states the rule
