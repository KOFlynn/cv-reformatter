# 05: Tracing for MCP Runs

**What to build:** every `reformat_cv` call is traced in Langfuse with the run id as the trace id, under environment `local` and tagged `surface=mcp`, so MCP runs can be told apart from API and eval runs. Always in structure mode.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] `python -m cvr.mcp` builds `Tracer.from_env(tags=["env=local", "surface=mcp"])`, with Langfuse's Environment field `local`, flushes after each call and shuts down on exit
- [ ] With no Langfuse keys the server runs untraced and silent
- [ ] `CVR_TRACE_MODE=full` logs a warning to stderr, and the server still traces in structure mode only
- [ ] Tests over the injected test tracer show one trace per call whose id is the run id, carrying the tags and identical in shape to an API Run's trace (prior art: the API's tracing tests)
- [ ] A refused call (ticket 04) produces no trace, or one that carries no path
