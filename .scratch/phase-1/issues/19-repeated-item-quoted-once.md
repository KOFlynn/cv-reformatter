# 19: A repeated item is quoted once

**What to build:** The labeller references every occurrence of a content item, including one that repeats an earlier item word for word. Ticket 10's baseline found this as the only structural miss across all three runs. c06 (tag `duplicate-skill`) lists "Microsoft Excel" twice among its skills on purpose. The labeller quotes it once and leaves the repeat unreferenced, so the repeat goes to the review appendix. The miss was in 2, 4 and 3 of c06's four Layouts in the three runs, and `c06__single-column` and `c06__header-footer` missed it every time. The cached answers show it plainly: one `skills` reference to "Microsoft Excel", none to the second block that holds it. No text is lost, since the appendix keeps it for a reviewer. But the design is that the output keeps the candidate's wording as written, repeats included; deduplicating is an edit, and the ground truth expects both.

The prompt says nothing about repeats today, and the model reads a repeated skill as redundant. The rule to add is that every occurrence is its own reference: an item that repeats an earlier one is quoted again with its own block id, never skipped as a duplicate. Before changing the prompt, check how `verify` treats two identical quotes. Two different blocks are simply two references. Two occurrences inside one block, such as an inline skills line, would need a second reference with the same block id and the same quote. Whether the ledger claims the next unclaimed occurrence or reports a double claim decides whether the prompt alone is enough.

**Blocked by:** 10 (Baseline and thresholds)

**Status:** in-progress

- [x] How `verify` resolves a second identical quote in the same block is established by a test, and the ticket comment says whether the prompt alone can fix both cases
- [x] The prompt's rule added (and `verify` changed only if the test shows it must be); `versions.json` bumped
- [ ] A live eval run over all 48 documents: c06's skills recall 8/8 in every Layout, and every hard gate and threshold held. Report diff against ticket 10's best run (run 1) and the cost in the PR description, per the eval-run rule
- [ ] If the change moves the baseline materially, say whether ticket 10's thresholds still hold; they are not loosened to fit

## Comments

**2026-10-02.** How `verify` treats a repeated quote, and why the prompt alone is enough.

- **Two occurrences in one block** were already pinned by ticket 03's `test_two_identical_quotes_place_at_two_occurrences` and `test_a_third_identical_quote_against_two_occurrences_is_rejected`. The ledger gives a second identical reference the next occurrence not yet claimed by content. It reports a `conflict` only when every occurrence is already held.
- **Two different blocks** is the case c06 actually hits, in every Layout. The two "Microsoft Excel" lines are always separate blocks: `body:13`/`body:17` in single-column, `table:0:r0:c1:6`/`:10` in two-column, `textbox:5:0:2`/`:6` in text-box, `body:6`/`body:10` in header-footer. `test_the_same_quote_in_two_blocks_places_once_in_each` pins that two references place once in each block. `test_a_repeat_left_unreferenced_is_unplaced` pins today's miss: the repeat is unplaced, not rejected.
- So `verify` is unchanged, and the prompt alone can fix both cases.

Prompt rule added after the skills rule: "Every occurrence is its own reference, repeats included". It covers both cases, and the same-block one explicitly ("two references with the same block id and the same quote").

The prompt version is **1.3.0** (hash `f326caf4f478e95d`), not 1.2.0. The unmerged ticket 15 demo branch already reports prompt 1.2.0 (`0489b6aa8b86424e`), and two prompts under one label would make reports ambiguous.

Boxes 3 and 4 wait on the maintainer's live run. The prompt hash is in the eval cache key, so a plain `python -m cvr.eval.run` misses the cache on all 48 documents.
