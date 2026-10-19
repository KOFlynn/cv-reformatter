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
