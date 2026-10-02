# 19: A repeated item is quoted once

**What to build:** The labeller references every occurrence of a content item, including one that repeats an earlier item word for word. Ticket 10's baseline found this as the only structural miss across all three runs. c06 (tag `duplicate-skill`) lists "Microsoft Excel" twice among its skills on purpose. The labeller quotes it once and leaves the repeat unreferenced, so the repeat goes to the review appendix. The miss was in 2, 4 and 3 of c06's four Layouts in the three runs, and `c06__single-column` and `c06__header-footer` missed it every time. The cached answers show it plainly: one `skills` reference to "Microsoft Excel", none to the second block that holds it. No text is lost, since the appendix keeps it for a reviewer. But the design is that the output keeps the candidate's wording as written, repeats included; deduplicating is an edit, and the ground truth expects both.

The prompt says nothing about repeats today, and the model reads a repeated skill as redundant. The rule to add is that every occurrence is its own reference: an item that repeats an earlier one is quoted again with its own block id, never skipped as a duplicate. Before changing the prompt, check how `verify` treats two identical quotes. Two different blocks are simply two references. Two occurrences inside one block, such as an inline skills line, would need a second reference with the same block id and the same quote. Whether the ledger claims the next unclaimed occurrence or reports a double claim decides whether the prompt alone is enough.

**Blocked by:** 10 (Baseline and thresholds)

**Status:** in-review

- [x] How `verify` resolves a second identical quote in the same block is established by a test, and the ticket comment says whether the prompt alone can fix both cases
- [x] The prompt's rule added (and `verify` changed only if the test shows it must be); `versions.json` bumped
- [x] A live eval run over all 48 documents: c06's skills recall 8/8 in every Layout, and every hard gate and threshold held. Report diff against ticket 10's best run (run 1) and the cost in the PR description, per the eval-run rule
- [x] If the change moves the baseline materially, say whether ticket 10's thresholds still hold; they are not loosened to fit

## Comments

**2026-10-02.** How `verify` treats a repeated quote, and why the prompt alone is enough.

- **Two occurrences in one block** were already pinned by ticket 03's `test_two_identical_quotes_place_at_two_occurrences` and `test_a_third_identical_quote_against_two_occurrences_is_rejected`. The ledger gives a second identical reference the next occurrence not yet claimed by content. It reports a `conflict` only when every occurrence is already held.
- **Two different blocks** is the case c06 actually hits, in every Layout. The two "Microsoft Excel" lines are always separate blocks: `body:13`/`body:17` in single-column, `table:0:r0:c1:6`/`:10` in two-column, `textbox:5:0:2`/`:6` in text-box, `body:6`/`body:10` in header-footer. `test_the_same_quote_in_two_blocks_places_once_in_each` pins that two references place once in each block. `test_a_repeat_left_unreferenced_is_unplaced` pins today's miss: the repeat is unplaced, not rejected.
- So `verify` is unchanged, and the prompt alone can fix both cases.

Prompt rule added after the skills rule: "Every occurrence is its own reference, repeats included". It covers both cases, and the same-block one explicitly ("two references with the same block id and the same quote").

The prompt version is **1.3.0** (hash `f326caf4f478e95d`), not 1.2.0. The unmerged ticket 15 demo branch already reports prompt 1.2.0 (`0489b6aa8b86424e`), and two prompts under one label would make reports ambiguous.

Boxes 3 and 4 wait on the maintainer's live run. The prompt hash is in the eval cache key, so a plain `python -m cvr.eval.run` misses the cache on all 48 documents.

**2026-10-02, the eval.** The maintainer's live runs on prompt 1.3.0 (`f326caf4f478e95d`), reports kept in the gitignored `.cache/ticket-19-runs/`:

- `--candidate c06` first: PASS, 4 live calls, $0.2553. Skills 8/8 (precision and recall 100%) in all four Layouts, empty appendix.
- Then the full run: **PASS**, 48 documents, 44 live calls plus c06's 4 cached answers. The labellings cost $3.3124, of which this run spent $3.0571. Wall time 203.7 s, no retries.

Diff against ticket 10's run 1 (prompt 1.1.0, the best of the three):

| | Run 1 (1.1.0) | 1.3.0 |
|---|---|---|
| Hard gates (added, dropped, wrongful removals, provenance, PII, images, ordering, errors, label fails) | all 0 | all 0 |
| Structural P/R | 100 / 100 (1072/1072) | 100 / 100 |
| Tunable P/R | 100 / 99.82 (1126 of 1128) | **100 / 100 (1128 of 1128)** |
| Appendix | 0.73% (96 of 13108 tokens) | **0.70% (92 of 13108)** |
| Punctuation | 0 | 0 |
| Tokens in / out | 263398 / 111000 | 269974 / 111625 |
| Cost (48 labellings) | $3.2736 | $3.3124 |

- The two tunable misses in run 1 were the repeated "Microsoft Excel", and the four appendix tokens it no longer has are those two repeats.
- What remains in the appendix is what the golden set puts there on purpose. c09 has a page number and a motto (tag `unplaceable`). c11 has the declaration line and a page number. The appendix text is identical in all four Layouts, and the per-candidate rates match run 1 exactly (3.09%, 5.73%).
- Precision held at 100%, so the rule made the model quote nothing twice that it shouldn't.
- The prompt is about 2.5% more input tokens, about 1% more cost.

Box 4: the baseline moved only by closing the gap ticket 10 recorded. Tunable recall goes 99.82 → 100, and the appendix rate falls 0.73 → 0.70, both improvements. Ticket 10's thresholds (tunable ≥ 98, appendix ≤ 2, punctuation hard) still hold, with the same margins or better, and are not changed. One run cannot re-derive a spread, so `thresholds.yaml` and the baseline file stay as they are.
