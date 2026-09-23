"""The real labeller's machinery, exercised without any network call: the
Anthropic-specific request options (temperature sent only when set, the
client's retries), turning a structured-output response into a labelling
result or a labelling failure, and the four kinds of failure."""

from typing import Any

import anthropic
import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from cvr.label.config import LabellerConfig
from cvr.label.errors import LabellerMisconfigured, ProviderUnavailable
from cvr.label.labeller import (
    PROVIDER_RETRIES,
    anthropic_kwargs,
    build_chat_model,
    label_blocks,
)
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


def _raising(exc: Exception) -> RunnableLambda:
    def _raise(_messages: Any) -> dict[str, Any]:
        raise exc

    return RunnableLambda(_raise)


_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> Exception:
    return cls(
        "provider said no", response=httpx.Response(status, request=_REQUEST), body=None
    )


@pytest.mark.parametrize(
    "exc",
    [
        _status_error(anthropic.RateLimitError, 429),
        _status_error(anthropic.InternalServerError, 500),
        _status_error(anthropic.OverloadedError, 529),
        anthropic.APIConnectionError(request=_REQUEST),
        anthropic.APITimeoutError(request=_REQUEST),
    ],
    ids=["rate-limit", "server-error", "overloaded", "connection", "timeout"],
)
def test_a_transient_provider_error_is_provider_unavailable(exc: Exception):
    with pytest.raises(ProviderUnavailable, match="try again later") as raised:
        label_blocks(BLOCKS, _raising(exc), LabellerConfig())
    assert raised.value.__cause__ is exc


@pytest.mark.parametrize(
    "exc",
    [
        _status_error(anthropic.AuthenticationError, 401),
        _status_error(anthropic.PermissionDeniedError, 403),
        _status_error(anthropic.NotFoundError, 404),
        _status_error(anthropic.BadRequestError, 400),
    ],
    ids=["bad-key", "no-access", "unknown-model", "bad-request"],
)
def test_a_rejected_request_is_labeller_misconfigured(exc: Exception):
    with pytest.raises(LabellerMisconfigured, match="ANTHROPIC_API_KEY") as raised:
        label_blocks(BLOCKS, _raising(exc), LabellerConfig())
    assert raised.value.__cause__ is exc


def test_anything_else_is_a_defect_and_propagates_unchanged():
    with pytest.raises(RuntimeError, match="a bug"):
        label_blocks(BLOCKS, _raising(RuntimeError("a bug")), LabellerConfig())


def test_a_refusal_is_a_labelling_failure():
    raw = AIMessage(
        content="",
        response_metadata={"stop_reason": "refusal"},
        usage_metadata={"input_tokens": 50, "output_tokens": 2, "total_tokens": 52},
    )
    model = _fake_structured_model({"raw": raw, "parsed": None, "parsing_error": None})

    result, run = label_blocks(BLOCKS, model, LabellerConfig())

    assert isinstance(result, LabellingFailure)
    assert result.reason == "the model refused to answer"
    assert run.label_failed is True
    assert run.input_tokens == 50


def test_an_unsupported_provider_is_labeller_misconfigured():
    with pytest.raises(LabellerMisconfigured, match="CVR_LABEL_PROVIDER"):
        build_chat_model(LabellerConfig(provider="openai"))


def test_the_client_retries_before_giving_up():
    assert anthropic_kwargs(LabellerConfig())["max_retries"] == PROVIDER_RETRIES == 2


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
