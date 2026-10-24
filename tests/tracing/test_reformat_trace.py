"""``reformat`` with a tracer: one trace, id = run id, one span per node in
order, one generation with the measured times, tokens and cost."""

import json
from uuid import uuid4

from oracle import UNLOCATABLE, Imperfect, Oracle, unlocatable_title
from tracing_support import LABEL_RUN, RecordingOracle, doc, exported, make_tracer

from cvr.models import RemovalRule
from cvr.pipeline import reformat
from cvr.tracing import Tracer

NODES = ["parse", "label", "verify", "transform", "render"]


def meta(span, key):
    """One metadata key of a span (the SDK writes each JSON-encoded)."""
    return json.loads(span.attributes["langfuse.observation.metadata." + key])


def _run():
    tracer, exporter = make_tracer()
    d = doc()
    run_id = uuid4().hex
    _, run = reformat(d.source, RecordingOracle(d), run_id=run_id, tracer=tracer)
    return run_id, run, exported(tracer, exporter)


def _generations(spans):
    return [
        s for s in spans if s.attributes["langfuse.observation.type"] == "generation"
    ]


def test_one_trace_whose_id_is_the_run_id():
    run_id, run, spans = _run()
    assert run.run_id == run_id
    assert {format(s.context.trace_id, "032x") for s in spans} == {run_id}


def test_one_span_per_node_in_order_under_a_root():
    _, _, spans = _run()
    root = next(s for s in spans if s.name == "reformat")
    nodes = [s for s in spans if s.name in NODES]
    assert [s.name for s in sorted(nodes, key=lambda s: s.start_time)] == NODES
    assert all(s.parent.span_id == root.context.span_id for s in nodes)


def test_one_generation_with_model_tokens_cost_and_measured_times():
    _, _, spans = _run()
    (gen,) = _generations(spans)
    attrs = gen.attributes
    assert attrs["langfuse.observation.model.name"] == "claude-sonnet-5-5"
    assert json.loads(attrs["langfuse.observation.usage_details"]) == {
        "input": LABEL_RUN.input_tokens,
        "output": LABEL_RUN.output_tokens,
    }
    assert json.loads(attrs["langfuse.observation.cost_details"]) == {
        "total": LABEL_RUN.cost_usd
    }
    # The pause is inside the labeller call, so the generation lasts at least it.
    assert (gen.end_time - gen.start_time) >= 0.02 * 1e9
    label = next(s for s in spans if s.name == "label")
    assert gen.parent.span_id == label.context.span_id
    assert label.start_time <= gen.start_time and gen.end_time <= label.end_time


def test_node_spans_carry_ids_and_counts():
    run_id, run, spans = _run()
    verify = next(s for s in spans if s.name == "verify")
    text_removals = [r for r in run.removals if r.rule is not RemovalRule.PHOTO]
    assert meta(verify, "removal_count") == len(text_removals)
    assert meta(verify, "unplaced_count") == len(run.unplaced)
    root = next(s for s in spans if s.name == "reformat")
    assert meta(root, "run_id") == run_id


def test_a_labeller_without_last_run_still_gets_one_generation():
    tracer, exporter = make_tracer()
    d = doc()
    reformat(d.source, Oracle(d.candidate, d.manifest), tracer=tracer)
    assert len(_generations(exported(tracer, exporter))) == 1


def test_a_disabled_tracer_changes_nothing():
    d = doc()
    plain, plain_run = reformat(d.source, Oracle(d.candidate, d.manifest), run_id="r")
    off, off_run = reformat(
        d.source, Oracle(d.candidate, d.manifest), run_id="r", tracer=Tracer.disabled()
    )
    assert plain_run == off_run
    assert plain  # a document came out
    assert off


def test_from_env_without_keys_is_disabled():
    assert not Tracer.from_env({}).enabled
    assert not Tracer.from_env({"LANGFUSE_PUBLIC_KEY": "pk"}).enabled
    keys = {"LANGFUSE_PUBLIC_KEY": f"pk-{uuid4().hex}", "LANGFUSE_SECRET_KEY": "sk"}
    assert Tracer.from_env(keys).enabled


def test_an_exception_is_recorded_by_type_name_only():
    tracer, exporter = make_tracer()
    d = doc()

    def boom(blocks):
        raise RuntimeError("CANARY-text-from-the-model")

    try:
        reformat(d.source, boom, tracer=tracer)
    except RuntimeError:
        pass
    spans = exported(tracer, exporter)
    assert "CANARY" not in repr([dict(s.attributes) for s in spans])
    label = next(s for s in spans if s.name == "label")
    assert label.attributes["langfuse.observation.status_message"] == "RuntimeError"


def test_a_rejection_is_an_event_under_verify_without_its_quote():
    tracer, exporter = make_tracer()
    d = doc()
    labeller = Imperfect(Oracle(d.candidate, d.manifest), unlocatable_title)
    reformat(d.source, labeller, tracer=tracer)
    spans = exported(tracer, exporter)
    verify = next(s for s in spans if s.name == "verify")
    events = [s for s in spans if s.name == "rejection"]
    assert len(events) == 1
    assert events[0].parent.span_id == verify.context.span_id
    assert meta(events[0], "reason") == "unlocatable"
    assert meta(verify, "rejected_unlocatable") == 1
    assert UNLOCATABLE not in json.dumps([dict(s.attributes) for s in spans])
