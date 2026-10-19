# 02: The Haiku runs

**What to build:** Three full, uncached eval runs of `claude-haiku-5-5` at effort `high` on prompt 1.3.0, over all 48 documents. They're the candidate side of the **Model comparison**. A one-document smoke run comes first, so a wrong model id or a rejected effort setting costs a fraction of a cent rather than a full run.

The maintainer does this ticket: it needs `ANTHROPIC_API_KEY`, and there's no code. Follow the instructions ticket 01 leaves in a comment below. Keep each run's `report.json` and `report.md` in `.cache/phase-1.5-runs/run-N/`, because the next run overwrites `eval/report.*`.

If a run fails only because the provider was unavailable (`ProviderUnavailable`), re-run it once and note it here. That says nothing about the model's labelling. Any other failure is a result. Record it, and the maintainer decides what follows, with the agent's advice.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** 01 (Price Haiku 5.5 and write the run instructions)

**Status:** done

- [x] Smoke run done: the model id and effort `high` were accepted, and the report shows the Haiku config and a non-zero cost
- [x] Run 1 done, report kept in `run-1/`
- [x] Run 2 done, report kept in `run-2/`
- [x] Run 3 done, report kept in `run-3/`
- [x] Each run's gate line, totals, cost and wall time posted as a comment below, with any provider-only re-run noted

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

**2026-10-19, first attempt.**
- **The smoke run failed, but the failure is in the harness, not Haiku's labelling.**
  - The cached answer shows `output_tokens: 4096` exactly, and the JSON stops before `removals`. That's a parse failure, so a `LabellingFailure`. The banner document then put everything in the appendix, which shows up as the PII, placement and appendix failures.
  - The cause: the labeller never sets `max_tokens`. The locked `langchain-anthropic` has a model profile for `claude-opus-5-5` (128K output) but none for `claude-haiku-5-5`, so it falls back to its default of 4,096. At effort `high`, thinking counts against that cap.
  - Anthropic's models overview (platform.claude.com, read 2026-10-19) gives Haiku 5.5 the same 128K maximum output as Opus 5.5. Setting `max_tokens` to 128,000 through `CVR_LABEL_EXTRA` therefore gives Haiku exactly the cap Opus ran with.
- **The three "full runs" were Opus.** The `CVR_LABEL_*` variables had been set inline on the smoke-run line only, so the next commands used the default config (`claude-opus-5-5`, `medium`). They cost about $3.32 each, and the reports were not kept. The last one (PASS, 48 documents, $3.3247, 217.8 s) is saved in `.cache/phase-1.5-runs/opus-2026-10-19/`, as a fourth Opus reference on prompt 1.3.0.
- **Corrected procedure:** export the variables once per Git Bash window, and check them before every full run.

```
export CVR_LABEL_MODEL=claude-haiku-5-5
export CVR_LABEL_EFFORT=high
export CVR_LABEL_EXTRA='{"max_tokens": 128000}'
env | grep CVR_LABEL
```
- **Follow-up for ticket 04:** if Haiku becomes the default, the 128K cap has to live in the code, either as a labeller default or through a `langchain-anthropic` that knows the model. Otherwise production would cut off at 4,096 tokens.

**2026-10-19, results (run 1 to 3, `claude-haiku-5-5`, `high`, `{"max_tokens": 128000}`, prompt 1.3.0, 48 live calls each, reports in `.cache/phase-1.5-runs/run-N/`).** Every run FAILs the gate.

| Run | Hard-gate failures | Structural P/R | Tunable P/R | Appendix | Cost | Wall time |
|---|---|---|---|---|---|---|
| 1 | 2 wrongful removals (`RM_REFEREE`, c04 "with a reference available") | 100 / 100 | 98.94 / 99.02 | 1.30% | $0.1407 | 201.0 s |
| 2 | 4 wrongful removals (`RM_PERSONAL` c07 "EU citizen"; `RM_REFEREE` c04 ×3); structural misses c05, c08, c12 | 99.72 / 99.72 | 98.41 / 98.49 | 1.34% | $0.1418 | 200.1 s |
| 3 | 3 wrongful removals (`RM_PERSONAL` c07; `RM_REFEREE` c04 ×2); structural misses c08, c12 | 99.81 / 99.81 | 98.59 / 98.94 | 1.09% | $0.1403 | 202.2 s |

No added or dropped text, no provenance, PII or image leak, no ordering or labelling failure. Haiku also clips quotes at commas and clause ends (", Moylish", ", Bray", " (hybrid)", sentence tails into the appendix). No provider-only re-run was needed.

**Verdict (maintainer, 2026-10-19):** a wide gap; Haiku as configured is out, and Phase 1.5 moves to Sonnet 5.5 at effort `medium` (ticket 06). A Haiku-specific prompt approach may be worth trying later; it is not planned.
