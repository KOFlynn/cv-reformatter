# 05: Tracing for MCP Runs

**What to build:** every `reformat_cv` call is traced in Langfuse with the run id as the trace id, under environment `local` and tagged `surface=mcp`, so MCP runs can be told apart from API and eval runs. Always in structure mode.

**Blocked by:** 03

**Status:** done

- [x] `python -m cvr.mcp` builds `Tracer.from_env(tags=["env=local", "surface=mcp"])`, with Langfuse's Environment field `local`, flushes after each call and shuts down on exit
- [x] With no Langfuse keys the server runs untraced and silent
- [x] `CVR_TRACE_MODE=full` logs a warning to stderr, and the server still traces in structure mode only
- [x] Tests over the injected test tracer show one trace per call whose id is the run id, carrying the tags and identical in shape to an API Run's trace (prior art: the API's tracing tests)
- [x] A refused call (ticket 04) produces no trace, or one that carries no path

## Comments

2026-11-05, done on a branch off `phase-3/release-01-07`. `tests/mcp/test_mcp_tracing.py` (14 tests, one slow subprocess) and `tests/tracing/test_from_env_mode_override.py` (5), over an in-memory exporter, dummy keys and the oracle.

Decisions made here:

- **Where the tracer is built.** In `create_server` when none is injected, mirroring `create_app`, so `__main__` is unchanged and a test of `create_server` covers it. `TRACE_ENVIRONMENT` (`local`) and `TRACE_TAGS` (`env=local`, `surface=mcp`) are exported constants.
- **Structure only.** `Tracer.from_env` gained a keyword `mode` that replaces `CVR_TRACE_MODE` (the variable is still validated, so a typo fails at start-up); the server passes `structure` and logs a warning when the variable says `full`. The API's choice (trace in full, warn) was not copied: the MCP server handles the user's own documents.
- **Shutdown.** A FastMCP lifespan shuts down the tracer the server built, never an injected one (tests open one session per call, and ticket 06 reuses a tracer).
- **Refused calls.** Everything before `reformat` (outside the Workspace, not found, not a docx, too large) starts no trace, tested with a marker in the path. `exists` is raised after the Run, so its trace exists, under the run id, with no path or file name in any span (tested). An error inside the pipeline is traced as an API failure is.
- **Shape.** The span names of a call equal those of a direct `reformat` over the same document and oracle.
- **Review, acted on:** the `from_env` local renamed `env_mode`; `own_tracer` tested once. **Left as is:** the shape test compares span names with a direct `reformat` Run (the API runs the same function; its own tests cover the API), not tags or attributes; the full-mode warning goes through `logging` (stderr via the last-resort handler, covered by the subprocess test); shutdown is in the lifespan after `yield`, so a crash skips it, as the API's does; `surface=mcp` is a literal beside `env_tag` since only one surface needs it; `make_tracer` is repeated in the test file because `tests/tracing` helpers are not on the MCP tests' path.
