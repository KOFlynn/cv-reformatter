# 04: Make the winner the default

**What to build:** The labeller's default configuration becomes the winning model and its effort: Sonnet 5.5 at `medium`, the maintainer's decision after Haiku 5.5 at `high` failed every gate run. CI's eval, the deployed app and local runs then all use it, and the decision is recorded where a reviewer will find it. Nothing outside the code pins the model: the app's environment holds only the two keys, and no workflow, Dockerfile or script sets `CVR_LABEL_*`. So the default is the one place to change it.

Write ADR-0011 as the decision record. It covers the chosen model and effort, the alternatives (Opus stays, Haiku), the comparison's numbers with a pointer to the committed comparison file, the trade-off (cost and wall time against margins above the gate), and the fact that the thresholds were left unchanged on purpose, because they're the product's bar, not a description of Opus.

Update every place that describes the current default as Opus: CLAUDE.md (the `label` entry, the cost of a full uncached run, the project status), the development guide, and the thresholds file's header. The header must keep saying the thresholds were derived from the Opus Baseline, and add that the default has since moved, with a pointer to ADR-0011. The pull request's merge runs the gate's live eval on the new default. Record its result and cost here.

This ticket applies to Sonnet 5.5 (Haiku failed); the comparison file is `eval/model-comparison-2026-10-19.json`.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** 03 (The comparison record and the verdict)

**Status:** in-review

- [x] The default model and effort are changed. The configuration test that pins the default is updated to the decided values, and a default-effort assertion is added if one is missing
- [x] ADR-0011 is written and cross-linked from ADR-0009
- [x] CLAUDE.md, the development guide and the thresholds header are updated. The thresholds' numbers are unchanged
- [x] `uv run pytest -q`, the slow suite, `ruff check` and `ruff format --check` are green
- [ ] After the merge: the `main` push's live eval passed on the new default, with its cost recorded here

## Comments

**2026-10-19:** Default changed to `claude-sonnet-5-5` at `medium`; ADR-0011 written and linked from ADR-0009; CLAUDE.md, README, development guide, thresholds header and cost comments updated (thresholds' numbers untouched). Extra finding: `langchain-anthropic` has no profile for the model and caps output at 4096, so `anthropic_kwargs` now sends `max_tokens` 128000 from a constant (`MAX_OUTPUT_TOKENS`), applied before `config.extra` so `CVR_LABEL_EXTRA` can override it. A constant, not a config field, so reports and cache keys do not list it and `CVR_LABEL_EXTRA` merges with it instead of replacing it. Prompt and schema hashes untouched. The post-merge live eval is still to record.
