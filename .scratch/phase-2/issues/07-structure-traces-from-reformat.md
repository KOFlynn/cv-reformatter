# 07: Structure traces from reformat

**What to build:** a Run can be traced in Langfuse with structure only: ids, counts, reasons, timings, tokens and cost, never candidate text. A new tracing package owns the Langfuse client (SDK pinned at its current major), its guards and one pure payload function. `reformat` gains an optional `tracer=` keyword; without it nothing is traced. The trace id is the run id. A trace holds one span per node visit and one generation per attempt, with the times measured around the model call and cost from the project's price table. The LangChain callback handler is never attached. This ticket does not wire tracing into the API or the eval (ticket 08) and has no full mode (ticket 09).

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The pinned SDK version's docs confirm `span_exporter`, `tracer_provider`, `should_export_span` and the mask hook, and that a `uuid4().hex` is accepted as a trace id; findings noted on the ticket
- [ ] Over an in-memory exporter with dummy keys, `reformat` with the oracle labeller exports one trace whose id is the run id, one span per node in order, and one generation carrying model, tokens, cost and start/end times taken around the call
- [ ] The payload function emits only allowlisted fields (unit-tested); positive control: ids and counts are present
- [ ] The client uses its own tracer provider (never the global one) and an export filter passing only our instrumentation scope; a rogue span (an instrumented call or a decorated function carrying a canary) never reaches the exporter (tested)
- [ ] The mask hook redacts input and output and any metadata key off the allowlist (tested)
- [ ] Ruff's banned-api rule forbids the Langfuse LangChain integration and its decorator; lint passes
- [ ] With no keys the client is a no-op and `reformat` behaves exactly as before (existing tests unchanged)
