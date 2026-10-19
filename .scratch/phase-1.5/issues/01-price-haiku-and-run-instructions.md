# 01: Price Haiku 5.5 and write the run instructions

**What to build:** An eval run on `claude-haiku-5-5` reports its real cost instead of $0, and the maintainer has a short, copy-paste procedure for the runs in ticket 02. Today the price table has no Haiku entry, and a model the table doesn't know is costed at zero, so a Haiku report would show no saving at all.

Take the input and output prices per million tokens from Anthropic's own pricing page, not from the third-party write-ups the spec mentions ($0.10 in and $0.50 out below 100K tokens; those figures are only a cross-check). Refresh the table's check date. Every golden-set prompt is far below Haiku's 100K-token long-prompt tier, so the base rates apply. The table stays a two-number lookup.

Write the run instructions as a comment on ticket 02. Keep the snippets short, because the maintainer pastes them into Git Bash with the key in their shell:
1. **A smoke run:** one Candidate, one Layout, `CVR_LABEL_MODEL=claude-haiku-5-5`, `CVR_LABEL_EFFORT=high`, `--no-cache`. It should show what success looks like: the gate result line, the config and a non-zero cost.
2. **Three full runs**, each with `--no-cache`. After each one, copy `report.json` and `report.md` into `.cache/phase-1.5-runs/run-N/`.
3. **What to send back** after each run: the gate line, the totals, the cost and the wall time.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** in-review

- [x] `claude-haiku-5-5` is in the price table at Anthropic's published base rates, the check date is refreshed, and the source page and date are recorded in a ticket comment
- [x] The price-table test asserts Haiku is present and that `estimate_cost` gives the expected dollars for one million tokens each way
- [x] No other change to `label`. Prompt and schema hashes are unchanged, so the version check still passes
- [x] The run instructions are a comment on ticket 02, with the smoke run first
- [x] `uv run pytest -q`, `ruff check` and `ruff format --check` are green

## Comments

**2026-10-19.** Added `claude-haiku-5-5` to `PRICE_TABLE` at $0.10 in and $0.50 out per million tokens, the base tier (prompts up to 100K tokens; the page lists $0.50 and $2.50 above that, which no golden-set prompt reaches). Source: Anthropic's own pricing page, https://claude.com/pricing, fetched 2026-10-19 (the fetch tool did not report a post-redirect URL). The third-party figures matched and were used only as a cross-check. The existing Opus 5.5 entry ($4 in, $20 out) still matches the page, so it is unchanged. `PRICE_TABLE_CHECKED` and the module docstring are now 2026-10-19; the Opus 5 and Sonnet 5 entries were not re-read on the page this time and keep their earlier check. The table is still a two-number lookup. The test asserts Haiku is present and that one million tokens each way costs input plus output. Nothing else in `label` changed. The run instructions are the comment on ticket 02.

**2026-10-19, review.** I re-read https://claude.com/pricing for every entry in the table: Haiku 5.5 $0.10/$0.50 (long-prompt tier $0.50/$2.50 above 100K), Opus 5.5 $4/$20, Opus 5 $5/$25 and Sonnet 5 $2/$10 (the last two are listed as legacy). All match, so `PRICE_TABLE_CHECKED` now holds for the whole table.
