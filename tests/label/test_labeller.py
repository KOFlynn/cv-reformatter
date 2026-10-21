"""The real labeller's machinery, exercised without any network call: the
Anthropic-specific request options (temperature sent only when set, the
client's retries), turning a structured-output response into a labelling
result or a labelling failure, and the four kinds of failure."""

import json
from typing import Any

import anthropic
import httpx
import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from cvr.label.config import LabellerConfig
from cvr.label.errors import LabellerMisconfigured, ProviderUnavailable
from cvr.label.labeller import (
    FAILURE_LOCATIONS,
    MAX_OUTPUT_TOKENS,
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

CANARY = "CANARY-7f3a-model-text"

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


def test_output_cap_is_sent_by_default():
    # langchain-anthropic has no model profile for claude-sonnet-5-5 and would
    # fall back to 4096 tokens, truncating answers (thinking counts against it).
    assert MAX_OUTPUT_TOKENS == 128_000
    assert anthropic_kwargs(LabellerConfig())["max_tokens"] == 128_000


def test_extra_overrides_the_output_cap():
    config = LabellerConfig(extra={"max_tokens": 64_000})
    assert anthropic_kwargs(config)["max_tokens"] == 64_000


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
        {
            "raw": raw,
            "parsed": None,
            "parsing_error": json.JSONDecodeError(CANARY, CANARY, 0),
        }
    )

    result, run = label_blocks(BLOCKS, model, config)

    assert isinstance(result, LabellingFailure)
    assert result.reason == "invalid JSON"
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
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


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
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_anything_else_raises_misconfigured_naming_only_its_type():
    with pytest.raises(LabellerMisconfigured) as raised:
        label_blocks(
            BLOCKS, _raising(RuntimeError(f"a bug {CANARY}")), LabellerConfig()
        )
    assert "RuntimeError" in str(raised.value)
    assert CANARY not in str(raised.value)
    assert CANARY not in repr(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


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


# --- No model text in any failure (ticket 03) -------------------------------


def _schema_error(data: dict[str, Any]) -> Exception:
    try:
        Labelling.model_validate(data)
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a validation error")


def _parser_error_around(cause: Exception) -> OutputParserException:
    try:
        raise OutputParserException(f"Failed to parse: {CANARY}", llm_output=CANARY)
    except OutputParserException as exc:
        exc.__cause__ = cause
        return exc


def _failure_from(parsing_error: Exception):
    raw = AIMessage(content=CANARY)
    model = _fake_structured_model(
        {"raw": raw, "parsed": None, "parsing_error": parsing_error}
    )
    return label_blocks(BLOCKS, model, LabellerConfig())


def _assert_canary_nowhere(result: Any, run: LabelRun) -> None:
    assert CANARY not in repr(result)
    assert CANARY not in run.model_dump_json()


def test_a_schema_invalid_answer_names_where_but_never_what():
    bad = {
        "content": {"name": {"block_id": "body:0", "quote": 7}, CANARY: CANARY},
        "removals": [],
    }
    result, run = _failure_from(_schema_error(bad))

    assert isinstance(result, LabellingFailure)
    assert result.reason.startswith("schema mismatch")
    assert "content.name.quote" in result.reason
    assert run.failure_reason == result.reason
    _assert_canary_nowhere(result, run)


def test_a_malformed_answer_reports_only_the_category():
    cause = json.JSONDecodeError(f"Expecting value {CANARY}", CANARY, 0)
    result, run = _failure_from(_parser_error_around(cause))

    assert result.reason == "invalid JSON"
    _assert_canary_nowhere(result, run)


def test_a_parser_error_around_a_schema_error_is_a_schema_mismatch():
    bad = {"content": {"name": 3}, "removals": []}
    result, run = _failure_from(_parser_error_around(_schema_error(bad)))

    assert result.reason.startswith("schema mismatch")
    assert "content.name" in result.reason
    _assert_canary_nowhere(result, run)


def test_a_bare_parser_error_is_invalid_json():
    result, run = _failure_from(_parser_error_around(ValueError(CANARY)))

    assert result.reason == "invalid JSON"
    _assert_canary_nowhere(result, run)


@pytest.mark.parametrize("error", [RuntimeError, ValueError, KeyError, TypeError])
def test_any_exception_in_the_parsing_error_slot_is_invalid_json(error):
    # Ticket 03's decision: what the structured output returns as a parsing
    # error is about the model's answer, whatever its type. Only an exception
    # raised by the call that is not about parsing is a misconfiguration.
    result, run = _failure_from(error(CANARY))

    assert result.reason == "invalid JSON"
    _assert_canary_nowhere(result, run)


def test_a_parsed_value_of_the_wrong_type_is_a_schema_mismatch():
    raw = AIMessage(content=CANARY)
    model = _fake_structured_model(
        {"raw": raw, "parsed": {"x": CANARY}, "parsing_error": None}
    )
    result, run = label_blocks(BLOCKS, model, LabellerConfig())

    assert result.reason == "schema mismatch"
    _assert_canary_nowhere(result, run)


def test_error_locations_keep_schema_field_names_and_integers_only():
    bad = {
        "content": {
            "name": {"block_id": "body:0", "quote": "x"},
            "experience": [{"title": 5}],
            CANARY: {CANARY: 1},
        },
        CANARY: 1,
        "removals": [{"rule": CANARY, "block_id": "body:0", "quote": "x"}],
    }
    result, _ = _failure_from(_schema_error(bad))

    locations = result.reason.removeprefix("schema mismatch at ").split(", ")
    assert locations
    for location in locations:
        for segment in location.split("."):
            assert segment.isdigit() or segment in FAILURE_LOCATIONS
    assert CANARY not in result.reason
    assert any("experience.0" in location for location in locations)


def test_a_segment_outside_the_allowlist_is_dropped():
    from cvr.label.labeller import _safe_location

    assert _safe_location(("content", CANARY, "experience", 0, "Reference")) == (
        "content.experience.0"
    )
    assert _safe_location((CANARY,)) is None


@pytest.mark.parametrize(
    ("cls", "status"),
    [
        (anthropic.RateLimitError, 429),
        (anthropic.AuthenticationError, 401),
        (anthropic.BadRequestError, 400),
    ],
    ids=["unavailable", "misconfigured-auth", "misconfigured-bad-request"],
)
def test_a_provider_error_that_embeds_model_text_does_not_carry_it(cls, status):
    exc = cls(
        f"echoed: {CANARY}",
        response=httpx.Response(status, request=_REQUEST),
        body={"error": CANARY},
    )
    with pytest.raises((ProviderUnavailable, LabellerMisconfigured)) as raised:
        label_blocks(BLOCKS, _raising(exc), LabellerConfig())
    assert CANARY not in str(raised.value)
    assert CANARY not in repr(raised.value)
    # Not in the chain either: logger.exception prints __cause__ and __context__.
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_a_parser_error_raised_by_the_call_is_a_labelling_failure():
    exc = OutputParserException(f"Failed to parse: {CANARY}", llm_output=CANARY)

    result, run = label_blocks(BLOCKS, _raising(exc), LabellerConfig())

    assert result == LabellingFailure(reason="invalid JSON")
    assert run.label_failed is True
    _assert_canary_nowhere(result, run)


def test_a_validation_error_raised_by_the_call_is_a_schema_mismatch():
    exc = _schema_error({"content": {"name": 3}, "removals": [], CANARY: CANARY})

    result, run = label_blocks(BLOCKS, _raising(exc), LabellerConfig())

    assert result.reason.startswith("schema mismatch")
    _assert_canary_nowhere(result, run)
