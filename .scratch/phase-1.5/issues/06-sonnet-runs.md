# 06: The Sonnet runs

**What to build:** Three full, uncached eval runs of `claude-sonnet-5-5` at effort `medium` on prompt 1.3.0, over all 48 documents, run the same way as ticket 02. This is the second candidate in the **Model comparison**, after Haiku failed widely (ticket 02). Effort `medium` matches the Opus reference, so Sonnet and Opus differ only in the model. Sonnet 5.5's API default is `high`, so effort has to be set explicitly.

The maintainer does this ticket because it needs `ANTHROPIC_API_KEY`. The price entry is in already: `claude-sonnet-5-5` costs $2 in and $10 out per million tokens, from https://claude.com/pricing, read 2026-10-19, and the page shows no long-prompt tier. The locked `langchain-anthropic` has no `claude-sonnet-5-5` profile, so `max_tokens` would fall back to 4,096. Set it to 128,000 through `CVR_LABEL_EXTRA`, as for Haiku.

Keep each run's reports in `.cache/phase-1.5-runs/sonnet-run-N/`. A `ProviderUnavailable`-only failure is re-run once. Any other failure is a result.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** 01 (Price Haiku 5.5 and write the run instructions), 02 (The Haiku runs)

**Status:** done

- [x] Smoke run done: config shows `claude-sonnet-5-5`, `medium`, `{'max_tokens': 128000}`, and cost is non-zero
- [x] Run 1 done, report kept in `sonnet-run-1/`
- [x] Run 2 done, report kept in `sonnet-run-2/`
- [x] Run 3 done, report kept in `sonnet-run-3/`
- [x] Each run's gate line, totals, cost and wall time posted as a comment below

## Comments

**2026-10-19, run instructions.** Use Git Bash at the repo root, with `ANTHROPIC_API_KEY` exported. Run the exports once per window, then check them before every run:

```
export CVR_LABEL_MODEL=claude-sonnet-5-5
export CVR_LABEL_EFFORT=medium
export CVR_LABEL_EXTRA='{"max_tokens": 128000}'
env | grep CVR_LABEL
```

Smoke run (one document, a few cents):

```
uv run python -m cvr.eval.run --candidate c04 --layout single-column --no-cache
```

Full run N (about $1.50 to $2 and about four minutes each). Copy the reports even when the run fails:

```
uv run python -m cvr.eval.run --no-cache
mkdir -p .cache/phase-1.5-runs/sonnet-run-1 && cp eval/report.json eval/report.md .cache/phase-1.5-runs/sonnet-run-1/
```

**2026-10-19, results (`claude-sonnet-5-5`, `medium`, `{"max_tokens": 128000}`, prompt 1.3.0, schema 1.0.0, 48 live calls each, no retries).** Every run passed the gate.

| Run | Gate | Structural P/R | Tunable P/R | Appendix | Input / output tokens | Cost | Wall time |
|---|---|---|---|---|---|---|---|
| 1 | PASS | 100 / 100 | 99.56 / 99.65 | 0.70% | 269,974 / 105,330 | $1.5932 | 163.3 s |
| 2 | PASS | 100 / 100 | 99.73 / 99.73 | 0.70% | 269,974 / 105,274 | $1.5927 | 138.8 s |
| 3 | PASS | 100 / 100 | 99.65 / 99.65 | 0.70% | 269,974 / 105,253 | $1.5925 | 138.5 s |

Every hard-gate count was zero: added, dropped, wrongful removals, provenance, PII, images, ordering, punctuation, labelling failures and errors. The tunable misses were all section choices, and no wording was lost:
- **c04:** Sonnet put the second profile paragraph, "Recently relocated to Dublin and available at short notice.", under Additional instead of Profile. That happened in 3 of 4 Layouts in runs 1 and 2, and in all 4 in run 3.
- **c10 text-box, run 1 only:** the profile was split between Profile and Additional.

Against the Opus reference (3 CI runs: tunable 99.91 to 100, appendix 0.70%, about $3.32, 214 to 238 s), Sonnet costs about 52% less and is about 35% faster. It is a little lower on tunable placement, but still well above the 98% threshold.
