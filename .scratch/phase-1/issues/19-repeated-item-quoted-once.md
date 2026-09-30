# 19: A repeated item is quoted once

**What to build:** The labeller references every occurrence of a content item, including one that repeats an earlier item word for word. Ticket 10's baseline found this as the only structural miss across all three runs. c06 (tag `duplicate-skill`) lists "Microsoft Excel" twice among its skills on purpose. The labeller quotes it once and leaves the repeat unreferenced, so the repeat goes to the review appendix. The miss was in 2, 4 and 3 of c06's four Layouts in the three runs, and `c06__single-column` and `c06__header-footer` missed it every time. The cached answers show it plainly: one `skills` reference to "Microsoft Excel", none to the second block that holds it. No text is lost, since the appendix keeps it for a reviewer. But the design is that the output keeps the candidate's wording as written, repeats included; deduplicating is an edit, and the ground truth expects both.

The prompt says nothing about repeats today, and the model reads a repeated skill as redundant. The rule to add is that every occurrence is its own reference: an item that repeats an earlier one is quoted again with its own block id, never skipped as a duplicate. Before changing the prompt, check how `verify` treats two identical quotes. Two different blocks are simply two references. Two occurrences inside one block, such as an inline skills line, would need a second reference with the same block id and the same quote. Whether the ledger claims the next unclaimed occurrence or reports a double claim decides whether the prompt alone is enough.

**Blocked by:** 10 (Baseline and thresholds)

**Status:** ready-for-agent

- [ ] How `verify` resolves a second identical quote in the same block is established by a test, and the ticket comment says whether the prompt alone can fix both cases
- [ ] The prompt's rule added (and `verify` changed only if the test shows it must be); `versions.json` bumped
- [ ] A live eval run over all 48 documents: c06's skills recall 8/8 in every Layout, and every hard gate and threshold held. Report diff against ticket 10's best run (run 1) and the cost in the PR description, per the eval-run rule
- [ ] If the change moves the baseline materially, say whether ticket 10's thresholds still hold; they are not loosened to fit
