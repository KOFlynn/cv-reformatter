# 02: The Haiku runs

**What to build:** Three full, uncached eval runs of `claude-haiku-5-5` at effort `high` on prompt 1.3.0, over all 48 documents. They're the candidate side of the **Model comparison**. A one-document smoke run comes first, so a wrong model id or a rejected effort setting costs a fraction of a cent rather than a full run.

The maintainer does this ticket: it needs `ANTHROPIC_API_KEY`, and there's no code. Follow the instructions ticket 01 leaves in a comment below. Keep each run's `report.json` and `report.md` in `.cache/phase-1.5-runs/run-N/`, because the next run overwrites `eval/report.*`.

If a run fails only because the provider was unavailable (`ProviderUnavailable`), re-run it once and note it here. That says nothing about the model's labelling. Any other failure is a result. Record it, and the maintainer decides what follows, with the agent's advice.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** 01 (Price Haiku 5.5 and write the run instructions)

**Status:** ready-for-human

- [ ] Smoke run done: the model id and effort `high` were accepted, and the report shows the Haiku config and a non-zero cost
- [ ] Run 1 done, report kept in `run-1/`
- [ ] Run 2 done, report kept in `run-2/`
- [ ] Run 3 done, report kept in `run-3/`
- [ ] Each run's gate line, totals, cost and wall time posted as a comment below, with any provider-only re-run noted

## Comments

**2026-10-19, run instructions (from ticket 01).** Paste into Git Bash at the repo root, with `ANTHROPIC_API_KEY` already exported. Prices are in, so cost is no longer $0.

**1. Smoke run (one document, a fraction of a cent):**

```
CVR_LABEL_MODEL=claude-haiku-5-5 CVR_LABEL_EFFORT=high uv run python -m cvr.eval.run --candidate c04 --layout single-column --no-cache
```

Success looks like: the run finishes without a `LabellerMisconfigured` error (a wrong model id or a rejected effort would show there), the gate line starts `PASS: 1 documents` (a `FAIL` on one document is still a valid smoke result; it only matters that the call worked), `eval/report.md` shows the config with model `claude-haiku-5-5` and effort `high`, and the cost is non-zero (a few thousandths of a dollar at most). If cost shows 0, stop and tell me.

**2. Three full runs, one at a time (about four minutes each, well under the $3.3 an Opus run costs):**

```
CVR_LABEL_MODEL=claude-haiku-5-5 CVR_LABEL_EFFORT=high uv run python -m cvr.eval.run --no-cache
mkdir -p .cache/phase-1.5-runs/run-1 && cp eval/report.json eval/report.md .cache/phase-1.5-runs/run-1/
```

Then the same two lines again with `run-2`, and with `run-3`. Do the copy even if the run exits 1, since a failure is a result; the next run overwrites `eval/report.*`.

**3. Post back after each run:** the gate line (the `PASS`/`FAIL` line, plus the failure lines if any), the totals, the cost and the wall time, all from `eval/report.md`. A run that failed only with `ProviderUnavailable` is re-run once; note that here and keep the re-run's report in that `run-N/`. Any other failure is a result: record it and do not re-run.
