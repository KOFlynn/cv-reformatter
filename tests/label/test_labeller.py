"""The real labeller's provider-agnostic machinery, exercised without any
network call: the Anthropic-specific request options (temperature sent only
when set), and turning a structured-output response into a labelling
result or a labelling failure without ever raising."""

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from cvr.label.config import LabellerConfig
from cvr.label.labeller import anthropic_kwargs, label_blocks
from cvr.label.versions import (
    CONTENT_HASH,
    PROMPT_HASH,
    PROMPT_VERSION,
    SCHEMA_HASH,
    SCHEMA_VERSION,
)
from cvr.models import (
    ContentReferences,
    Labelling,
    LabellingFailure,
    LabelRun,
    Reference,
    SourceBlock,
)

BLOCKS = [
    SourceBlock(id="body:0", text="Padraig Lonergan", kind="body"),
    SourceBlock(id="body:1", text="Software Engineer at Acme", kind="body"),
]


def _valid_labelling() -> Labelling:
    return Labelling(
        content=ContentReferences(
            name=Reference(block_id="body:0", quote="Padraig Lonergan"),
            profile=[],
            skills=[],
            education=[],
            experience=[],
            certifications=[],
            additional=[],
        ),
        removals=[],
    )


def _fake_structured_model(response: dict[str, Any]) -> RunnableLambda:
    """Stands in for ``chat_model.with_structured_output(..., include_raw=True)``:
    a Runnable returning the same ``{raw, parsed, parsing_error}`` shape
    Claude's structured output produces, with no network involved."""
    return RunnableLambda(lambda _messages: response)


# --- Anthropic-specific request options ------------------------------------


def test_temperature_absent_from_kwargs_when_unset():
    config = LabellerConfig(temperature=None)
    kwargs = anthropic_kwargs(config)
    assert "temperature" not in kwargs
    assert kwargs["reasoning_effort"] == config.effort


def test_temperature_present_in_kwargs_when_set():
    config = LabellerConfig(temperature=0.3)
    kwargs = anthropic_kwargs(config)
    assert kwargs["temperature"] == 0.3


def test_other_sampling_knobs_pass_through():
    config = LabellerConfig(extra={"top_p": 0.9})
    kwargs = anthropic_kwargs(config)
    assert kwargs["top_p"] == 0.9


# --- Canned-response handling: a fake chat model, no network ---------------


def test_valid_answer_becomes_a_labelling_result():
    config = LabellerConfig()
    raw = AIMessage(
        content="",
        usage_metadata={"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
    )
    model = _fake_structured_model(
        {"raw": raw, "parsed": _valid_labelling(), "parsing_error": None}
    )

    result, run = label_blocks(BLOCKS, model, config)

    assert isinstance(result, Labelling)
    assert result.content.name.quote == "Padraig Lonergan"
    assert run == LabelRun(
        config=config.as_dict(),
        prompt_version=PROMPT_VERSION,
        prompt_hash=PROMPT_HASH,
        schema_version=SCHEMA_VERSION,
        schema_hash=SCHEMA_HASH,
        content_hash=CONTENT_HASH,
        input_tokens=120,
        output_tokens=40,
        cost_usd=run.cost_usd,
        label_failed=False,
        failure_reason=None,
    )
    assert run.cost_usd > 0


def test_malformed_answer_becomes_a_labelling_failure_without_raising():
    config = LabellerConfig()
    raw = AIMessage(
        content="{not valid json",
        usage_metadata={"input_tokens": 80, "output_tokens": 10, "total_tokens": 90},
    )
    model = _fake_structured_model(
        {"raw": raw, "parsed": None, "parsing_error": ValueError("bad json")}
    )

    result, run = label_blocks(BLOCKS, model, config)

    assert isinstance(result, LabellingFailure)
    assert "bad json" in result.reason
    assert run.label_failed is True
    assert run.failure_reason == result.reason
    assert run.input_tokens == 80
    assert run.output_tokens == 10


def test_a_request_that_raises_becomes_a_labelling_failure_without_raising():
    config = LabellerConfig()

    def _explode(_messages: Any) -> dict[str, Any]:
        raise RuntimeError("rate limited")

    result, run = label_blocks(BLOCKS, RunnableLambda(_explode), config)

    assert isinstance(result, LabellingFailure)
    assert "rate limited" in result.reason
    assert run.label_failed is True
    assert run.input_tokens == 0
    assert run.output_tokens == 0
    assert run.cost_usd == 0.0


def test_every_run_carries_the_prompt_and_schema_identity():
    config = LabellerConfig()
    raw = AIMessage(
        content="",
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )
    model = _fake_structured_model(
        {"raw": raw, "parsed": _valid_labelling(), "parsing_error": None}
    )
    _, run = label_blocks(BLOCKS, model, config)
    assert run.prompt_version == PROMPT_VERSION
    assert run.schema_version == SCHEMA_VERSION
    assert run.content_hash == CONTENT_HASH
