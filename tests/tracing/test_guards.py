"""The guards: the tracer's own provider, the export filter and the mask hook.
A rogue span carrying a canary never reaches the exporter."""

import json
from uuid import uuid4

from opentelemetry import trace as otel_trace
from tracing_support import doc, exported, make_tracer

from cvr.pipeline import reformat
from cvr.tracing import ALLOWED_KEYS, REDACTED, mask

CANARY = "CANARY-9f3a71c2-candidate-text"


def _everything(spans) -> str:
    return json.dumps([dict(s.attributes) for s in spans] + [s.name for s in spans])


def test_the_global_tracer_provider_is_never_replaced():
    before = otel_trace.get_tracer_provider()
    make_tracer()
    assert otel_trace.get_tracer_provider() is before


def test_a_span_from_another_instrumented_library_never_reaches_the_exporter():
    tracer, exporter = make_tracer()
    # The global provider (what a library's instrumentation uses) is not ours.
    with otel_trace.get_tracer("opentelemetry.instrumentation.anthropic").start_span(
        CANARY
    ) as span:
        span.set_attribute("gen_ai.prompt.0.content", CANARY)
    # Even given our own provider, a foreign scope is filtered out.
    provider = tracer._client._resources.tracer_provider
    with provider.get_tracer("opentelemetry.instrumentation.openai").start_span(
        CANARY
    ) as span:
        span.set_attribute("gen_ai.prompt.0.content", CANARY)
    assert CANARY not in _everything(exported(tracer, exporter))


def test_a_stray_langfuse_span_without_our_marker_never_reaches_the_exporter():
    """What an ``observe``-decorated function would produce: the SDK's own
    scope, but not made by us."""
    tracer, exporter = make_tracer()
    stray = tracer._client.start_observation(name=CANARY, input={"text": CANARY})
    stray.update(output=CANARY, metadata={"text": CANARY})
    stray.end()
    assert exported(tracer, exporter) == []


def test_a_stray_span_inside_a_traced_run_does_not_export():
    tracer, exporter = make_tracer()
    d = doc()

    def labeller(blocks):
        stray = tracer._client.start_observation(name=CANARY, input=CANARY)
        stray.end()
        from oracle import Oracle

        return Oracle(d.candidate, d.manifest)(blocks)

    reformat(d.source, labeller, tracer=tracer)
    spans = exported(tracer, exporter)
    assert spans
    assert CANARY not in _everything(spans)


def test_the_mask_keeps_allowlisted_metadata_and_drops_the_rest():
    masked = mask(
        data={
            "block_count": 12,
            "reason": "unlocatable",
            "run_id": uuid4().hex,
            "quote": CANARY,
            "nested": {"block_count": 1},
            "listy": [CANARY],
        }
    )
    assert set(masked) == {"block_count", "reason", "run_id"}
    assert masked["block_count"] == 12


def test_the_mask_redacts_non_mapping_input_and_output():
    assert mask(data=CANARY) == REDACTED
    assert mask(data=[CANARY]) == REDACTED
    assert mask(data=12) == REDACTED


def test_input_output_and_metadata_set_by_hand_come_out_redacted():
    tracer, exporter = make_tracer()
    with tracer.trace(uuid4().hex) as run, run.node("parse") as node:
        node._observation.update(
            input=CANARY, output={"text": CANARY}, metadata={"quote": CANARY}
        )
    spans = exported(tracer, exporter)
    assert CANARY not in _everything(spans)
    assert any(REDACTED in json.dumps(dict(s.attributes)) for s in spans)


def test_the_allowlist_names_no_text_fields():
    assert not {"quote", "text", "name", "input", "output", "prompt"} & ALLOWED_KEYS
