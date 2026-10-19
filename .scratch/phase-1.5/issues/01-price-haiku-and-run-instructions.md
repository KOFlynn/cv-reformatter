# 01: Price Haiku 5.5 and write the run instructions

**What to build:** An eval run on `claude-haiku-5-5` reports its real cost instead of $0, and the maintainer has a short, copy-paste procedure for the runs in ticket 02. Today the price table has no Haiku entry, and a model the table doesn't know is costed at zero, so a Haiku report would show no saving at all.

Take the input and output prices per million tokens from Anthropic's own pricing page, not from the third-party write-ups the spec mentions ($0.10 in and $0.50 out below 100K tokens; those figures are only a cross-check). Refresh the table's check date. Every golden-set prompt is far below Haiku's 100K-token long-prompt tier, so the base rates apply. The table stays a two-number lookup.

Write the run instructions as a comment on ticket 02. Keep the snippets short, because the maintainer pastes them into Git Bash with the key in their shell:
1. **A smoke run:** one Candidate, one Layout, `CVR_LABEL_MODEL=claude-haiku-5-5`, `CVR_LABEL_EFFORT=high`, `--no-cache`. It should show what success looks like: the gate result line, the config and a non-zero cost.
2. **Three full runs**, each with `--no-cache`. After each one, copy `report.json` and `report.md` into `.cache/phase-1.5-runs/run-N/`.
3. **What to send back** after each run: the gate line, the totals, the cost and the wall time.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `claude-haiku-5-5` is in the price table at Anthropic's published base rates, the check date is refreshed, and the source page and date are recorded in a ticket comment
- [ ] The price-table test asserts Haiku is present and that `estimate_cost` gives the expected dollars for one million tokens each way
- [ ] No other change to `label`. Prompt and schema hashes are unchanged, so the version check still passes
- [ ] The run instructions are a comment on ticket 02, with the smoke run first
- [ ] `uv run pytest -q`, `ruff check` and `ruff format --check` are green
