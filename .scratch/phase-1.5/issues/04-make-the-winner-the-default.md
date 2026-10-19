# 04: Make the winner the default

**What to build:** The labeller's default configuration becomes the winning model and its effort: Haiku 5.5 at `high`, if ticket 03's verdict says so. CI's eval, the deployed app and local runs then all use it, and the decision is recorded where a reviewer will find it. Nothing outside the code pins the model: the app's environment holds only the two keys, and no workflow, Dockerfile or script sets `CVR_LABEL_*`. So the default is the one place to change it.

Write ADR-0011 as the decision record. It covers the chosen model and effort, the alternatives (Opus stays, Sonnet), the comparison's numbers with a pointer to the committed comparison file, the trade-off (cost and wall time against margins above the gate), and the fact that the thresholds were left unchanged on purpose, because they're the product's bar, not a description of Opus.

Update every place that describes the current default as Opus: CLAUDE.md (the `label` entry, the cost of a full uncached run, the project status), the development guide, and the thresholds file's header. The header must keep saying the thresholds were derived from the Opus Baseline, and add that the default has since moved, with a pointer to ADR-0011. The pull request's merge runs the gate's live eval on the new default. Record its result and cost here.

This ticket runs only if ticket 03's verdict and the maintainer's decision are to switch. If Sonnet wins instead, the same ticket applies to Sonnet.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** 03 (The comparison record and the verdict)

**Status:** ready-for-agent

- [ ] The default model and effort are changed. The configuration test that pins the default is updated to the decided values, and a default-effort assertion is added if one is missing
- [ ] ADR-0011 is written and cross-linked from ADR-0009
- [ ] CLAUDE.md, the development guide and the thresholds header are updated. The thresholds' numbers are unchanged
- [ ] `uv run pytest -q`, the slow suite, `ruff check` and `ruff format --check` are green
- [ ] After the merge: the `main` push's live eval passed on the new default, with its cost recorded here
