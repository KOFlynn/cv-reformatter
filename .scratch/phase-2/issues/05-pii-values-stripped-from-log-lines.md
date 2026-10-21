# 05: PII values stripped from log lines

**What to build:** the API's log lines keep the transform log's text, which stays inside our own tenant, but never a PII value. The log writer strips PII wherever it occurs: text removals under a PII rule, ledger claims under a PII rule, residue overlapping such a removal, and any error field. A stripped removal keeps its rule, block, offsets, length and character class, so an over-eager rule is still visible. Headings removed under RM_HEADING are not PII and stay. The Run itself is unchanged, so the eval's `removal_precision`, which reads the in-memory Run, is unaffected.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] A document built at test time with a unique email-shaped canary (e.g. `canary-7f3@example.invalid`) and a unique digit-string phone goes through the API with the oracle labeller; neither value, nor its normalised forms (spaces removed, case folded), appears in the captured log output
- [x] Positive control: a non-PII content string from the same document does appear in the block lines
- [x] Stripped removals log rule, block, offsets, length and class (tested)
- [x] The Run returned by `reformat` still holds the removal text; the `removal_precision` tests pass unchanged
- [x] Every line stays under the existing size limit for the golden set (existing test)
- [x] The log module's docstring states the rule

## Comments

**2026-10-21.** Done in `src/cvr/api/log.py`. A text removal under any rule but RM_HEADING (and RM_PHOTO, which is an image) logs `{block_id, start, end, length, class}` and no text; `class` is a per-character shape (`a` letter, `9` digit, `_` whitespace, `#` other). Residue overlapping such a removal is logged the same way. Ledger claims already hold only offsets and the claimant, so they are unchanged. The `error` field has emails, phones and URLs (the verify backstop patterns) and the text of the Run's PII removals replaced by `[pii]`; ticket 04 reduces errors to type names, which makes this a second layer. The canary test builds c04 with a canary email, phone and address through all four Layouts. Finding: the block lines hold no content text at all (the ledger is offsets), so the positive control is the removed headings, the only non-PII text there. `test_the_lines_hold_the_whole_run` was adapted on purpose: it reads stripped spans back with placeholder text and compares with the Run as the log is expected to hold it. `removal_precision` tests pass unchanged.
