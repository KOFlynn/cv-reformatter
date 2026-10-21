# 04: Catch-all 500 and a local-only traceback flag

**What to build:** any exception that escapes the app becomes a generic 500 with `X-Run-Id`, and one summary log line that records the exception's type name only. Uvicorn never prints a traceback with its message. Full tracebacks are available only behind a debug setting that is off by default and never set in production. Container Apps ships standard error to Log Analytics too, so "local only" has to be enforced by the setting, not by where the output goes.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] An exception carrying a canary in its message, raised inside `/reformat`, returns a generic 500 body with no canary, sets `X-Run-Id`, and logs one summary line with the type name and no canary (stdout and stderr captured)
- [x] With the debug setting on, the same request writes the full traceback to standard error; off is the default (tested)
- [x] Existing status mappings (401, 411, 413, 415, 503, 500, 200 banner) are unchanged
- [x] The setting is documented in the development docs and absent from the deploy configuration

## Comments

2026-10-21: Done. The spec names no variable for the debug setting, so it is `CVR_DEBUG_TRACEBACKS` (`1`, `true` or `yes`; read once when the app is created, like `CVR_API_KEY`; off when unset). The middleware's catch-all now logs `run <id> failed: <TypeName>` and sets the summary's `error` to the type name alone (it was `Type: message`); the traceback goes to standard error only with the flag on. The log-write failure handler likewise logs the type name only. Labeller errors with their own mapping (`ProviderUnavailable`, `LabellerMisconfigured`) are unchanged, including their summary `error`, which ticket 05 strips. Documented in `docs/development.md`; a static test in `tests/ci/test_workflow.py` asserts no workflow, script or the Dockerfile mentions it. Changes are in `src/cvr/api/app.py` only; `log.py` untouched.
