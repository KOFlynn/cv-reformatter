# 04: Catch-all 500 and a local-only traceback flag

**What to build:** any exception that escapes the app becomes a generic 500 with `X-Run-Id`, and one summary log line that records the exception's type name only. Uvicorn never prints a traceback with its message. Full tracebacks are available only behind a debug setting that is off by default and never set in production. Container Apps ships standard error to Log Analytics too, so "local only" has to be enforced by the setting, not by where the output goes.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] An exception carrying a canary in its message, raised inside `/reformat`, returns a generic 500 body with no canary, sets `X-Run-Id`, and logs one summary line with the type name and no canary (stdout and stderr captured)
- [ ] With the debug setting on, the same request writes the full traceback to standard error; off is the default (tested)
- [ ] Existing status mappings (401, 411, 413, 415, 503, 500, 200 banner) are unchanged
- [ ] The setting is documented in the development docs and absent from the deploy configuration
