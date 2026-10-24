"""A retried Run's trace (ticket 14): the extra node visits, one generation per
attempt, one event per retry decision carrying its reason and counts only."""

import json

from pipeline_support import document
from retry_support import (
    bullet_additions,
    damaged,
    drop_first_bullets,
    perfect,
    scripted,
)
from tracing_support import exported, make_tracer

from cvr.pipeline import reformat

STEM = "c04__single-column"
NODES = {"parse", "label", "verify", "transform", "render"}


def meta(span, key):
    return json.loads(span.attributes["langfuse.observation.metadata." + key])


def _trace(*script):
    tracer, exporter = make_tracer()
    labeller, _ = scripted(*script)
    _, run = reformat(document(STEM).source, labeller, tracer=tracer)
    return run, exported(tracer, exporter)


def _by_start(spans, name):
    return sorted((s for s in spans if s.name == name), key=lambda s: s.start_time)


def _generations(spans):
    return sorted(
        (s for s in spans if s.attributes["langfuse.observation.type"] == "generation"),
        key=lambda s: s.start_time,
    )


def _fixed_by_a_retry():
    full = perfect(STEM)
    return _trace(damaged(STEM, drop_first_bullets(1)), bullet_additions(full, 0))


def test_a_retried_run_shows_the_extra_node_visits_and_generations():
    run, spans = _fixed_by_a_retry()

    ordered = sorted(spans, key=lambda s: s.start_time)
    assert [s.name for s in ordered if s.name in NODES] == [
        "parse",
        "label",
        "verify",
        "label",
        "verify",
        "transform",
        "render",
    ]
    generations = _generations(spans)
    assert [meta(g, "attempt") for g in generations] == [1, 2]
    assert len(run.retries) == 1
    # each generation sits under its own label visit
    for generation, label in zip(generations, _by_start(spans, "label"), strict=True):
        assert generation.parent.span_id == label.context.span_id


def test_one_event_per_retry_decision_with_its_reason_and_counts_only():
    _, spans = _fixed_by_a_retry()
    events = _by_start(spans, "retry_decision")
    assert [
        (meta(e, "retry"), meta(e, "reason"), meta(e, "attempt")) for e in events
    ] == [
        (True, "unplaced_text", 1),
        (False, "nothing_unplaced", 2),
    ]
    assert meta(events[0], "unplaced_chars") > 0
    assert meta(events[1], "unplaced_chars") == 0
    # each sits under its verify visit
    verifies = _by_start(spans, "verify")
    assert [e.parent.span_id for e in events] == [v.context.span_id for v in verifies]


def test_an_outage_on_a_retry_is_an_error_generation_and_a_stop_event():
    _, spans = _trace(damaged(STEM, drop_first_bullets(1)), "outage")
    events = _by_start(spans, "retry_decision")
    assert [meta(e, "reason") for e in events] == ["unplaced_text", "outage"]
    first, second = _generations(spans)
    assert first.attributes.get("langfuse.observation.level") != "ERROR"
    assert second.attributes["langfuse.observation.level"] == "ERROR"


def test_a_perfect_run_has_one_decision_event_and_no_retry():
    _, spans = _trace(perfect(STEM))
    (event,) = _by_start(spans, "retry_decision")
    assert (meta(event, "retry"), meta(event, "reason")) == (False, "nothing_unplaced")
    assert len(_by_start(spans, "label")) == 1


def test_label_visits_report_their_attempt_and_count_a_retrys_additions():
    _, spans = _fixed_by_a_retry()
    first, second = _by_start(spans, "label")
    assert (meta(first, "attempt"), meta(second, "attempt")) == (1, 2)
    assert meta(second, "reference_count") == 1  # the one addition
    assert meta(second, "label_failed") is False
    assert _by_start(spans, "verify")[-1].attributes
    assert meta(_by_start(spans, "verify")[-1], "unplaced_count") == 0
