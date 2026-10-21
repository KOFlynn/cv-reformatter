"""Ticket 09: full-text mode. One setting, ``CVR_TRACE_MODE`` (``structure`` by
default, or ``full``), changes only what the payload functions return, so the
spans and the number of generations are the same in both modes."""

import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from oracle import UNLOCATABLE, Oracle, unlocatable_title
from tracing_support import LABEL_RUN, exported, make_tracer

from cvr.golden import load_candidates
from cvr.golden.layouts import SingleColumnLayout
from cvr.label.labeller import RealLabeller, _messages
from cvr.models import LabelExchange, SourceBlock
from cvr.pipeline import reformat
from cvr.tracing import (
    ENV_TRACE_MODE,
    REDACTED,
    Tracer,
    UnknownTraceMode,
    make_mask,
)

CANARY_NAME = "Qzxv Canaryname-7a41"
CANARY_PROFILE = "Canaryprofile-93bd line of a profile that no one wrote."


def _canary_document():
    """Candidate c04 with a canary for its name and its first profile line,
    rendered through a Layout at test time; nothing in the fixtures changes."""
    candidate = next(c for c in load_candidates() if c.id == "c04")
    profile = [CANARY_PROFILE, *candidate.content.profile[1:]]
    content = candidate.content.model_copy(
        update={"name": CANARY_NAME, "profile": profile}
    )
    candidate = candidate.model_copy(update={"content": content})
    return candidate, SingleColumnLayout().generate(candidate)


class ExchangeOracle:
    """The oracle with a ``last_run`` and the ``last_exchange`` a
    ``RealLabeller`` keeps: the rendered prompt and the answer as JSON."""

    def __init__(self, oracle, damage=None):
        self._oracle = oracle
        self._damage = damage
        self.last_run = None
        self.last_exchange = None

    def __call__(self, blocks):
        self.last_run = None
        self.last_exchange = None
        result = self._oracle(blocks)
        if self._damage is not None:
            result = self._damage(result)
        self.last_run = LABEL_RUN.model_copy()
        self.last_exchange = LabelExchange(
            messages=[
                {"role": m.type, "content": str(m.content)} for m in _messages(blocks)
            ],
            answer=result.model_dump_json(),
        )
        return result


def _trace(mode, damage=None):
    candidate, generated = _canary_document()
    tracer, exporter = make_tracer(mode)
    labeller = ExchangeOracle(Oracle(candidate, generated.manifest), damage)
    _, run = reformat(generated.document, labeller, run_id=uuid4().hex, tracer=tracer)
    return run, exported(tracer, exporter)


def _text(spans) -> str:
    """Every attribute, name and event of the exported spans."""
    return json.dumps(
        [dict(s.attributes) for s in spans]
        + [s.name for s in spans]
        + [[(e.name, dict(e.attributes)) for e in s.events] for s in spans],
        ensure_ascii=False,
    )


def _generations(spans):
    return [
        s for s in spans if s.attributes["langfuse.observation.type"] == "generation"
    ]


def _attr(span, key):
    return span.attributes[f"langfuse.observation.{key}"]


# --- the setting ---------------------------------------------------------


def test_the_mode_defaults_to_structure():
    assert Tracer.from_env({}).mode == "structure"
    assert Tracer.from_env({ENV_TRACE_MODE: ""}).mode == "structure"
    assert Tracer.disabled().mode == "structure"


def test_full_is_read_from_the_environment():
    keys = {"LANGFUSE_PUBLIC_KEY": f"pk-lf-{uuid4().hex}", "LANGFUSE_SECRET_KEY": "x"}
    tracer = Tracer.from_env({**keys, ENV_TRACE_MODE: "full"})
    assert tracer.enabled and tracer.mode == "full"
    assert Tracer.from_env({ENV_TRACE_MODE: "full"}).mode == "full"


@pytest.mark.parametrize("value", ["FULL", "verbose", "on", "structure "])
def test_an_unknown_mode_fails_at_startup_with_a_named_error(value):
    with pytest.raises(UnknownTraceMode, match=ENV_TRACE_MODE) as error:
        Tracer.from_env({ENV_TRACE_MODE: value})
    assert isinstance(error.value, ValueError)


def test_an_unknown_mode_fails_even_with_keys():
    keys = {"LANGFUSE_PUBLIC_KEY": f"pk-lf-{uuid4().hex}", "LANGFUSE_SECRET_KEY": "x"}
    with pytest.raises(UnknownTraceMode):
        Tracer.from_env({**keys, ENV_TRACE_MODE: "nope"})


# --- the content boundary ------------------------------------------------


def test_structure_mode_carries_no_canary():
    _, spans = _trace("structure", unlocatable_title)
    everything = _text(spans)
    for canary in (CANARY_NAME, CANARY_PROFILE, UNLOCATABLE):
        assert canary not in everything


def test_full_mode_carries_the_canaries_in_the_generation_and_the_spans():
    _, spans = _trace("full", unlocatable_title)
    (generation,) = _generations(spans)
    # The rendered prompt (the blocks as the model saw them) and the raw answer.
    prompt = _attr(generation, "input")
    assert CANARY_NAME in prompt and CANARY_PROFILE in prompt
    assert "system" in prompt
    assert UNLOCATABLE in _attr(generation, "output")
    by_name = {s.name: s for s in spans}
    # The blocks: what parse found, and what label was given.
    assert CANARY_NAME in _attr(by_name["parse"], "output")
    assert CANARY_PROFILE in _attr(by_name["label"], "input")
    # A rejection's quote.
    (rejection,) = [s for s in spans if s.name == "rejection"]
    assert (
        json.loads(rejection.attributes["langfuse.observation.metadata.quote"])
        == UNLOCATABLE
    )


def test_the_two_modes_export_the_same_spans_and_generations():
    _, structure = _trace("structure", unlocatable_title)
    _, full = _trace("full", unlocatable_title)

    def shape(spans):
        ordered = sorted(spans, key=lambda s: s.name)
        return [
            (s.name, s.attributes["langfuse.observation.type"], len(s.events))
            for s in ordered
        ]

    assert shape(structure) == shape(full)
    assert len(_generations(structure)) == len(_generations(full)) == 1


def test_full_mode_changes_no_output_or_run():
    candidate, generated = _canary_document()
    outcomes = []
    for mode in ("structure", "full"):
        tracer, _ = make_tracer(mode)
        labeller = ExchangeOracle(Oracle(candidate, generated.manifest))
        output, run = reformat(
            generated.document, labeller, run_id="a" * 32, tracer=tracer
        )
        outcomes.append((output, run.model_dump_json()))
    assert outcomes[0] == outcomes[1]


def test_a_labeller_that_keeps_no_exchange_gets_a_generation_without_text():
    candidate, generated = _canary_document()
    tracer, exporter = make_tracer("full")
    reformat(generated.document, Oracle(candidate, generated.manifest), tracer=tracer)
    (generation,) = _generations(exported(tracer, exporter))
    assert "langfuse.observation.input" not in generation.attributes


# --- the mask, per mode --------------------------------------------------


def test_the_full_mask_passes_text_under_its_keys_and_redacts_the_rest():
    mask = make_mask("full")
    assert mask(data="bare") == REDACTED
    kept = mask(data={"blocks": [{"text": "t"}], "answer": "a", "other": "x"})
    assert kept == {"blocks": [{"text": "t"}], "answer": "a"}


def test_the_structure_mask_still_drops_the_full_keys():
    mask = make_mask("structure")
    assert mask(data={"blocks": "t", "quote": "q", "block_count": 3}) == {
        "block_count": 3
    }


# --- the labeller keeps what the trace needs -----------------------------


class _FakeChat:
    def __init__(self, response):
        self._response = response

    def with_structured_output(self, *args, **kwargs):
        return RunnableLambda(lambda _messages: self._response)


def test_the_real_labeller_keeps_the_rendered_messages_and_the_raw_answer():
    raw = AIMessage(
        content=[
            {"type": "thinking", "thinking": "private reasoning"},
            {"type": "text", "text": '{"answer": "raw"}'},
        ]
    )
    labeller = RealLabeller(
        chat_model=_FakeChat(
            {"raw": raw, "parsed": None, "parsing_error": ValueError()}
        )
    )
    block = SourceBlock(id="body:0", text="Canary text", kind="body")
    assert labeller.last_exchange is None
    labeller([block])
    exchange = labeller.last_exchange
    assert [m["role"] for m in exchange.messages] == ["system", "human"]
    assert "Canary text" in exchange.messages[1]["content"]
    assert exchange.answer == '{"answer": "raw"}'
    # It is not part of the Run's label section.
    assert "Canary" not in labeller.last_run.model_dump_json()
