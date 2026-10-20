# The labeller's default is Sonnet 5.5 at effort `medium`, chosen by running the same gate on three models

ADR-0009 built the labeller and the eval gate, and the spec's baseline was Opus 5.5 at `medium`, about $3.30 and four minutes a full run. Phase 1.5 asked whether a cheaper model passes the same gate unchanged. The eval's live runs are the only evidence this project accepts for a model change, so each candidate ran all 48 documents against `eval/thresholds.yaml`, three times, on prompt 1.3.0. The numbers are in `eval/model-comparison-2026-10-19.json`.

**Decision.** `DEFAULT_MODEL` is `claude-sonnet-5-5` and `DEFAULT_EFFORT` stays `medium`. CI's eval, the deployed app and local runs all take the default; nothing else pins the model.

| Configuration | Runs | Gate | Tunable placement (precision / recall, %) | Structural | Appendix | Cost per run | Wall time |
|---|---|---|---|---|---|---|---|
| Opus 5.5 `medium` (reference) | 3 CI runs | PASS x3 | 99.91-100 | 100 | 0.70% | $3.32-3.33 | 214-238 s |
| Haiku 5.5 `high` | 3 local runs | FAIL x3 | 98.41-98.94 | 99.72-100 | 1.09-1.34% | about $0.14 | about 200 s |
| Sonnet 5.5 `medium` | 3 local runs | PASS x3 | 99.56-99.73 | 100 | 0.70% | $1.593 | 139-163 s |

Input is 269,974 tokens on every run; output is about 105K for Sonnet and about 112K for Opus.

**Why not Haiku.** It is far cheaper, but it failed the gate on all three runs. It removed lines wrongly under `RM_REFEREE` and `RM_PERSONAL` (the hard `removal_precision` gate), and it missed structural leaves because its quotes were clipped at commas (the structural 100% gate). A Haiku-specific prompt is not pursued now: the prompt is shared, a second one is a second thing to keep honest, and Sonnet already passes.

**Why not stay on Opus.** It passes, but Sonnet passes the same gate for about 52% less money ($1.59 against $3.32) and about 35% less wall time. Sonnet's one systematic difference from Opus is that it files c04's second profile paragraph ("Recently relocated to Dublin and available at short notice.") under Additional rather than Profile. No wording was lost and the hard gates held; it costs a little tunable placement (99.56-99.73% against 99.91-100%), which is still well above the 98% gate.

**The thresholds are unchanged, on purpose.** They were derived from the Opus baseline (`eval/baseline-2026-09-29.json`), but they are the product's bar, not a description of Opus. Loosening them to fit a cheaper model would be fitting the test to the change. The header of `eval/thresholds.yaml` says the default has moved and points here; the numbers are untouched.

**The output cap is set in code.** `langchain-anthropic` as locked has no model profile for `claude-sonnet-5-5`, so it silently falls back to `max_tokens` 4096. Adaptive thinking counts against that cap, so answers were truncated and became `LabellingFailure`s. The comparison's runs worked around it with `CVR_LABEL_EXTRA='{"max_tokens": 128000}'`; production has no such variable, so `anthropic_kwargs` now sets `max_tokens` to `MAX_OUTPUT_TOKENS` (128000, Sonnet 5.5's documented maximum, the same as Opus 5.5's profile) before it merges `LabellerConfig.extra`, so `CVR_LABEL_EXTRA` can still override it. It is a constant in the request, not a field of `LabellerConfig`: the config printed in every report and hashed into the eval cache key therefore does not list it, and the cache keys of the comparison runs (which carried it in `extra`) differ from the default's. The cap changes nothing about what the model is asked, only how much it may write. Tests pin both the default and the override; none calls the API.

**Considered options:** Opus stays (rejected: about twice the cost and a longer run for no gate-relevant gain). Haiku 5.5 at `high` (rejected: failed every run on hard gates). A Haiku-specific prompt (not pursued now; a possible later experiment, which would need its own version and gate runs). Putting `max_tokens` in `LabellerConfig.extra` by default (rejected: `CVR_LABEL_EXTRA` would then replace the cap instead of merging with it, and every report would list a knob that is not a choice).

**Consequence:** a full uncached eval is about $1.6 and two and a half minutes, so the gate on every pull request and `main` push costs about half as much. Sonnet 5.5 and Haiku 5.5 are in `PRICE_TABLE` (checked 2026-10-19). Any later model change repeats this process: three runs, the same thresholds, an ADR.
