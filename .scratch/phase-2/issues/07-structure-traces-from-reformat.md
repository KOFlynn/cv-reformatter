# 07: Structure traces from reformat

**What to build:** a Run can be traced in Langfuse with structure only: ids, counts, reasons, timings, tokens and cost, never candidate text. A new tracing package owns the Langfuse client (SDK pinned at its current major), its guards and one pure payload function. `reformat` gains an optional `tracer=` keyword; without it nothing is traced. The trace id is the run id. A trace holds one span per node visit and one generation per attempt, with the times measured around the model call and cost from the project's price table. The LangChain callback handler is never attached. This ticket does not wire tracing into the API or the eval (ticket 08) and has no full mode (ticket 09).

**Blocked by:** 02

**Status:** done

- [x] The pinned SDK version's docs confirm `span_exporter`, `tracer_provider`, `should_export_span` and the mask hook, and that a `uuid4().hex` is accepted as a trace id; findings noted on the ticket
- [x] Over an in-memory exporter with dummy keys, `reformat` with the oracle labeller exports one trace whose id is the run id, one span per node in order, and one generation carrying model, tokens, cost and start/end times taken around the call
- [x] The payload function emits only allowlisted fields (unit-tested); positive control: ids and counts are present
- [x] The client uses its own tracer provider (never the global one) and an export filter passing only our instrumentation scope; a rogue span (an instrumented call or a decorated function carrying a canary) never reaches the exporter (tested)
- [x] The mask hook redacts input and output and any metadata key off the allowlist (tested)
- [x] Ruff's banned-api rule forbids the Langfuse LangChain integration and its decorator; lint passes
- [x] With no keys the client is a no-op and `reformat` behaves exactly as before (existing tests unchanged)

## Comments

2026-10-21 (agent): built.

**SDK findings (Langfuse 5.0.4, read from the installed package).** `Langfuse(span_exporter=, tracer_provider=, should_export_span=, mask=)` all exist (`_client/client.py`). A `uuid4().hex` is a valid trace id (`create_trace_id` documents 32 lowercase hex; `trace_context={"trace_id": ...}` makes the root span carry it, confirmed on exported spans). Facts that shaped the design: (1) when no `tracer_provider` is passed the SDK calls `set_tracer_provider` on the global one, so we always pass our own; (2) the SDK keeps one client per public key per process, so tests use a fresh key each; (3) the mask hook is called with `data=` only, with no field name: it cannot tell input from output from metadata, and a dict is masked as a whole and then written per key; (4) metadata values are JSON-encoded in span attributes (`"cvr"` not `cvr`); (5) `start_observation` has no start-time argument, so a generation's start is when it is created: it is entered just before the labeller call and left just after, which is the measured time; (6) `should_export_span` is also asked when a span starts, before its metadata exists; (7) an `observe`-decorated function uses the SDK's own scope, so a scope filter alone would pass it. There is also a `mask_otel_spans` hook; not used.

**Built.** New package `src/cvr/tracing/` (`client.py`, `payload.py`); `reformat(..., tracer=None)`; `pyproject.toml` (`langfuse>=5.0,<6`, ruff `TID251` with `langfuse.langchain`, `langfuse.observe`, `langfuse.decorators`, `langfuse.openai` banned); `tests/tracing/` (27 tests); CLAUDE.md. Lock file: additions only (245 lines): langfuse, backoff, googleapis-common-protos, wrapt, protobuf and the OpenTelemetry api/sdk/semantic-conventions/exporter packages.

**Decisions beyond the ticket text.**
- Public names (the spec names none): `Tracer` (`from_env`, `create`, `disabled`, `trace(run_id)`, `flush`), `RunTrace.node(name)`, `NodeTrace.finish/generation/rejection`, `GenerationTrace.finish`, `node_payload(node, inputs, outputs)`, `generation_payload(label_run, attempt=)`, `rejection_payload`, `allowlisted`, `ALLOWED_KEYS`, `mask`, `should_export`, `REDACTED`. Settings: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` (the SDK's own names). Without both keys `from_env` returns a disabled tracer and never builds a client, so no warning.
- For ticket 09: the payload functions take the nodes' real inputs and outputs and return the span keyword arguments (`metadata` only today), so a `full` mode is a change to their output (adding `input`, `output`, more metadata) and to the allowlist/mask, nothing in the pipeline.
- The export filter requires the SDK's scope and a marker (`source: cvr` in metadata), so a stray `observe`-decorated span that reaches our client is dropped too. During the start-time question the filter answers on scope alone.
- The mask keeps only allowlisted keys with scalar values of a mapping and redacts anything that is not a mapping; structure mode sets no input or output at all.
- A rejection is one event under the verify span (path, block id, reason; never the quote); counts per reason on the verify span. Retry-decision events belong to the retry ticket.
- A failing node records `level=ERROR` and the exception type name only. Tracing failures are logged (no message) and swallowed: tracing never fails a Run.
- The generation is always emitted, with the attempt alone when the labeller records no `LabelRun` (the oracles). Cost is the `LabelRun.cost_usd` the price table gave, as `cost_details.total`.
- `reformat` now fixes the run id before the graph starts (the trace needs it); the Run is unchanged.
- Observed: this box's ruff also enforces BLE001 (existing code carries `# noqa: BLE001`); the new broad catches do the same.

**Results.** `pytest -q` 1337 passed, 1 skipped; `pytest -q -m slow` 914 passed; ruff check and format clean. Existing tests unchanged. The image check was not run (it needs Docker and a real model call); the Langfuse and OpenTelemetry packages add to the image, to be measured in ticket 08's PR.
