"""Review fixes for ticket 07: model-controlled ids, tracing never failing a
Run, the untraced path, the mode, the stale ``last_run``."""

import json
from dataclasses import dataclass

import pytest
from oracle import Imperfect, Oracle, unlocatable_title
from tracing_support import (
    LABEL_RUN,
    RecordingOracle,
    doc,
    docx_parts,
    exported,
    make_tracer,
)

import cvr.tracing.client as client_module
from cvr.models import Labelling, LabelRun
from cvr.pipeline import reformat
from cvr.tracing import Tracer, make_mask, rejection_payload
from cvr.verify import Rejection

CANARY = "CANARY-block-id-5d1e"


def _bogus_block_id(labelling: Labelling):
    entry = labelling.content.experience[0]
    title = entry.title.model_copy(update={"block_id": CANARY})
    return labelling.model_copy(
        update={
            "content": labelling.content.model_copy(
                update={
                    "experience": [
                        entry.model_copy(update={"title": title}),
                        *labelling.content.experience[1:],
                    ]
                }
            )
        }
    )


def test_a_model_made_block_id_never_reaches_the_exporter():
    tracer, exporter = make_tracer()
    d = doc()
    labeller = Imperfect(Oracle(d.candidate, d.manifest), _bogus_block_id)
    reformat(d.source, labeller, tracer=tracer)
    spans = exported(tracer, exporter)
    events = [s for s in spans if s.name == "rejection"]
    assert len(events) == 1  # the positive control: the rejection was traced
    assert CANARY not in json.dumps([dict(s.attributes) for s in spans])
    assert json.loads(
        events[0].attributes["langfuse.observation.metadata.block_id"]
    ) == ("unknown")


def test_a_parsed_block_id_is_kept():
    rejection = Rejection("name", "body:1", "q", "unlocatable")
    assert rejection_payload(rejection, {"body:1"})["metadata"]["block_id"] == "body:1"
    assert rejection_payload(rejection, set())["metadata"]["block_id"] == "unknown"


def _baseline(d):
    return reformat(d.source, Oracle(d.candidate, d.manifest), run_id="r")


def test_a_raising_payload_function_leaves_the_run_unchanged(monkeypatch):
    d = doc()
    expected_bytes, expected_run = _baseline(d)

    def boom(*args, **kwargs):
        raise RuntimeError("payload")

    for name in ("node_payload", "generation_payload", "rejection_payload"):
        monkeypatch.setattr(client_module, name, boom)
    tracer, _ = make_tracer()
    out, run = reformat(
        d.source, Oracle(d.candidate, d.manifest), run_id="r", tracer=tracer
    )
    assert (docx_parts(out), run) == (docx_parts(expected_bytes), expected_run)


def test_a_raising_client_leaves_the_run_unchanged():
    d = doc()
    expected_bytes, expected_run = _baseline(d)
    tracer, _ = make_tracer()

    class Broken:
        def __getattr__(self, name):
            raise RuntimeError("client")

    tracer._client = Broken()
    out, run = reformat(
        d.source, Oracle(d.candidate, d.manifest), run_id="r", tracer=tracer
    )
    assert (docx_parts(out), run) == (docx_parts(expected_bytes), expected_run)


def test_a_raising_propagate_attributes_leaves_the_run_unchanged(monkeypatch):
    d = doc()
    expected_bytes, expected_run = _baseline(d)

    def boom(**kwargs):
        raise RuntimeError("propagate")

    monkeypatch.setattr(client_module, "propagate_attributes", boom)
    tracer, _ = make_tracer()
    tracer._tags = ["env=test"]
    out, run = reformat(
        d.source, Oracle(d.candidate, d.manifest), run_id="r", tracer=tracer
    )
    assert (docx_parts(out), run) == (docx_parts(expected_bytes), expected_run)


def test_propagate_attributes_is_not_entered_without_tags(monkeypatch):
    def boom(**kwargs):
        raise AssertionError("entered")

    monkeypatch.setattr(client_module, "propagate_attributes", boom)
    tracer, _ = make_tracer()
    with tracer.trace("a" * 32):
        pass


def test_the_untraced_path_builds_no_payload(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("payload built without a tracer")

    for name in ("node_payload", "generation_payload", "rejection_payload"):
        monkeypatch.setattr(client_module, name, boom)
    d = doc()
    reformat(d.source, Imperfect(Oracle(d.candidate, d.manifest), unlocatable_title))


def test_the_mode_defaults_to_structure_and_unknown_modes_are_refused():
    # Ticket 07 accepted only structure; ticket 09 adds full (test_full_mode.py).
    assert Tracer.disabled().mode == "structure"
    with pytest.raises(ValueError):
        Tracer(None, mode="verbose")
    with pytest.raises(ValueError):
        make_mask("verbose")
    assert make_mask("structure")(data="x") == "[redacted]"


def test_the_sdk_scope_constant_is_the_sdks():
    from langfuse._client.constants import LANGFUSE_TRACER_NAME

    assert client_module.SDK_SCOPE == LANGFUSE_TRACER_NAME


def test_generation_finish_requires_the_attempt():
    tracer, _ = make_tracer()
    with (
        tracer.trace("b" * 32) as run,
        run.node("label") as node,
        node.generation() as generation,
        pytest.raises(TypeError),
    ):
        generation.finish(None)


@dataclass
class _Stale:
    """A labeller that records a LabelRun on its first call only."""

    inner: Oracle
    calls: int = 0
    last_run: LabelRun | None = None

    def __call__(self, blocks):
        self.calls += 1
        if self.calls == 1:
            self.last_run = LABEL_RUN
        return self.inner(blocks)


def test_a_stale_last_run_is_not_recorded_for_a_later_call():
    d = doc()
    labeller = _Stale(Oracle(d.candidate, d.manifest))
    labeller.last_run = LABEL_RUN  # left over from an earlier call
    tracer, exporter = make_tracer()
    reformat(d.source, labeller, tracer=tracer)
    spans = exported(tracer, exporter)
    (gen,) = [
        s for s in spans if s.attributes["langfuse.observation.type"] == "generation"
    ]
    assert "langfuse.observation.model.name" not in gen.attributes


def test_a_fresh_last_run_is_recorded():
    d = doc()
    tracer, exporter = make_tracer()
    reformat(d.source, RecordingOracle(d), tracer=tracer)
    (gen,) = [
        s
        for s in exported(tracer, exporter)
        if s.attributes["langfuse.observation.type"] == "generation"
    ]
    assert "langfuse.observation.model.name" in gen.attributes
