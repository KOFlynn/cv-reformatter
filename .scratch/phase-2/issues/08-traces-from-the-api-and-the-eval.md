# 08: Traces from the API and the eval

**What to build:** real Runs appear in Langfuse Cloud (EU, Hobby, private project). The API builds the client once per process from the environment and passes it to `reformat`. Every response's `X-Run-Id` is the trace id, and every log line keeps carrying the run id. The eval runner traces each document's Run. Traces are tagged `env=prod`, `env=eval` or `env=local`, and eval cache hits are marked cached with zero cost. The keys live in GitHub secrets (the eval job) and Container Apps secrets (the app), never in the image.

**Blocked by:** 07

**Status:** in-progress

- [x] API tests (injected in-memory client) show the response's `X-Run-Id` equal to the exported trace id, and the log lines carrying the same id
- [x] Eval runner tests show one trace per document with `env=eval`, and a cache hit tagged cached with zero cost
- [x] With the keys missing, the API and the eval still run, untraced (tested)
- [x] The CI eval job and the deploy configuration receive the Langfuse keys as secrets; the workflow's static tests cover it
- [ ] The image check is run and pasted (the size added by the OpenTelemetry packages noted); the runtime-import test still holds
- [ ] The maintainer sees one CI eval run's traces in Langfuse (noted on the ticket); usage checked against the Hobby allowance
- [x] The development docs and CLAUDE.md list the new environment variables

## Comments

2026-10-21 (agent): built; in progress until the maintainer's boxes (image check, CI traces in Langfuse, Hobby usage) are done.

**Maintainer, 2026-10-21 (via the orchestrator):** the GitHub repository secrets `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL` (EU cloud) are set. `ci.yml`'s eval job therefore reads all three as `secrets.*`.

**Built.** `create_app(labeller=None, tracer=None)`: the tracer is `Tracer.from_env(tags=[env=<CVR_TRACE_ENV>])` built once at app creation (`prod`/`eval`/`local`, anything else `local`; `cvr.tracing.trace_env`/`env_tag`), passed to `reformat` with the middleware's run id as the trace id, flushed in a `finally` after every Run (also a failing one) and shut down in the app's lifespan. When the tracer is disabled `reformat` is called exactly as before (an existing test monkeypatches it with a signature without `tracer`). The eval runner: `main(..., tracer=)` builds `Tracer.from_env(tags=[env=eval])` (never reads `CVR_TRACE_ENV`), passes it through `evaluate`/`run_documents` to `reformat`, and flushes and shuts down in a `finally`. A cache hit: `CachedLabeller.cached` (and `_Unlocked` forwarding it) is read by `label_node`; `generation_payload(..., cached=)` writes metadata `cached` (allowlisted), zero tokens and `cost_details.total` 0.0. `Tracer.shutdown()` added. A provider retry in the eval makes a new trace per attempt (the failed attempts stay as ERROR traces). Wizard (`scripts/provision-azure.sh`, stage 7): idempotent step for `langfuse-public-key`/`langfuse-secret-key` Container Apps secrets (kept and read back on a re-run, skippable with Enter), env `LANGFUSE_*` by secretref, `LANGFUSE_BASE_URL`, `CVR_TRACE_ENV=prod`, and the GitHub secrets. The deploy job is unchanged (it keeps the app's settings). Tests: `tests/api/test_api_tracing.py`, `tests/eval/run/test_run_tracing.py`, additions to `tests/ci/`. Image: the runtime-import and Dockerfile tests hold (`cvr.tracing` ships via the `src/` allowlist; no key reaches the image); the image was not built (Docker daemon not running) nor checked.

**Results.** `pytest -q` 1399 passed, 2 skipped; `-m slow` 914 passed; ruff clean. One flaky failure of `test_a_raising_client_leaves_the_run_unchanged` was seen once in a combined run and not reproduced.

**Merge with ticket 09 (2026-10-21).** Merged `phase-2/release-01-10` (full mode) keeping both: `Tracer` carries tags and mode, `generation_payload`/`GenerationTrace.finish` take `cached` and `exchange` together. In the eval, `CachedLabeller` and the runner's `_Unlocked`/`_Counted` wrappers forward `last_exchange` (`None` on a cache hit, so a replayed generation has no text, as it has no cost). Each labelling gets its own labeller instance (`live(document)` per attempt, wrapper per attempt), so `last_run`/`last_exchange` are never shared across the four concurrent threads; `test_concurrent_full_traces_each_carry_their_own_labellings_exchange` pins it. **API stance on `CVR_TRACE_MODE=full`:** a logged warning at app creation (the app still starts); the deploy never setting it stays pinned by the static test from ticket 09, and the wizard never mentions it. Failing closed was not chosen: a misconfigured full mode on the deployed app is caught by that test and the warning in Log Analytics, and refusing to start would take the demo down.

**Two failures fixed on the release head.** (1) `RealLabeller`: whatever comes back in the structured output's `parsing_error` slot is a labelling failure, `invalid JSON` unless it is a validation error (ticket 03's decision); the label test that expected `LabellerMisconfigured` for a `RuntimeError` there was replaced by one expecting `invalid JSON` for several exception types. (2) `test_a_raising_client_leaves_the_run_unchanged` (and its two siblings) compared two rendered `.docx` byte for byte; every zip entry carries the render time to the 2 seconds a zip stores, so they differ whenever a 2-second boundary falls between the baseline and the traced render (reproduced: same parts, entry times 21:15:40 vs 21:15:42). Not Langfuse state. The tests now compare each zip entry's content.
