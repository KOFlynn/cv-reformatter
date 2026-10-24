"""The retry through the real labeller, over a fake chat model (ticket 12):
no feedback is the first attempt (the first prompt, ``Labelling``); feedback
is the retry (the retry prompt, ``Additions``, with the blocks, the first
answer and the feedback text in the messages), classified like the first."""

import json
from typing import Any

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from cvr.label import RealLabeller
from cvr.label.config import LabellerConfig
from cvr.label.errors import LabellerMisconfigured, ProviderUnavailable
from cvr.label.labeller import _reference_at, retry_messages
from cvr.label.versions import (
    ADDITIONS_HASH,
    ADDITIONS_VERSION,
    CONTENT_HASH,
    PROMPT_TEXT,
    RETRY_HASH,
    RETRY_TEXT,
    RETRY_VERSION,
)
from cvr.models import (
    Addition,
    Additions,
    ContentReferences,
    ExperienceReference,
    Labelling,
    LabellingFailure,
    Reference,
    RemovalReference,
    SourceBlock,
)
from cvr.models.feedback import Feedback, UnlocatableHint, UnplacedRun

CANARY = "CANARY-retry-model-text"

BLOCKS = [
    SourceBlock(id="body:0", text="Padraig Lonergan", kind="body"),
    SourceBlock(id="body:1", text="Software Engineer at Acme", kind="body"),
    SourceBlock(id="body:2", text="Led the Cork team; Python, SQL", kind="body"),
]
USAGE = {"input_tokens": 300, "output_tokens": 20, "total_tokens": 320}


def _first() -> Labelling:
    return Labelling(
        content=ContentReferences(
            name=Reference(block_id="body:0", quote="Padraig Lonergan"),
            profile=[],
            skills=[Reference(block_id="body:2", quote="Pythn")],
            education=[],
            experience=[
                ExperienceReference(
                    title=Reference(block_id="body:1", quote="Software Enginer"),
                    employer=None,
                    location=None,
                    dates=None,
                    bullets=[Reference(block_id="body:2", quote="Led the Cork tam")],
                )
            ],
            certifications=[],
            additional=[],
        ),
        removals=[RemovalReference(rule="RM_PHONE", block_id="body:2", quote="0871")],
    )


FEEDBACK = Feedback(
    unplaced=[UnplacedRun(block_id="body:1", start=21, end=25)],
    unlocatable=[
        UnlocatableHint(path="skills[0]", block_id="body:2"),
        UnlocatableHint(path="experience[0].title", block_id="body:1"),
        UnlocatableHint(path="experience[0].bullets[0]", block_id="body:2"),
        UnlocatableHint(path="removals[0]", block_id="body:2"),
        UnlocatableHint(path="experience[7].title", block_id="body:2"),
    ],
)


def _additions() -> Additions:
    return Additions(
        additions=[
            Addition(
                path="skills", reference=Reference(block_id="body:2", quote="Python")
            )
        ]
    )


class _FakeChat:
    """Records the schema each ``with_structured_output`` was bound to and the
    messages each runnable got; answers by schema."""

    def __init__(self, answers: dict[type, dict[str, Any]]):
        self.answers = answers
        self.bound: list[type] = []
        self.calls: list[tuple[type, list[Any]]] = []

    def with_structured_output(self, schema: type, **kwargs: Any):
        self.bound.append(schema)
        assert kwargs == {"include_raw": True, "method": "json_schema"}

        def invoke(messages: list[Any]) -> dict[str, Any]:
            self.calls.append((schema, messages))
            answer = self.answers[schema]
            if isinstance(answer, Exception):
                raise answer
            return answer

        return RunnableLambda(invoke)


def _ok(parsed: Any) -> dict[str, Any]:
    return {
        "raw": AIMessage(content=parsed.model_dump_json(), usage_metadata=USAGE),
        "parsed": parsed,
        "parsing_error": None,
    }


def _labeller(additions: Any = None) -> tuple[RealLabeller, _FakeChat]:
    chat = _FakeChat(
        {Labelling: _ok(_first()), Additions: additions or _ok(_additions())}
    )
    return RealLabeller(LabellerConfig(), chat_model=chat), chat


# --- routing ---------------------------------------------------------------


def test_no_feedback_is_the_first_attempt():
    labeller, chat = _labeller()
    result = labeller(BLOCKS)

    assert isinstance(result, Labelling)
    assert [schema for schema, _ in chat.calls] == [Labelling]
    system, human = chat.calls[0][1]
    assert system.content == PROMPT_TEXT
    assert json.loads(human.content)[0] == {
        "block_id": "body:0",
        "text": "Padraig Lonergan",
    }
    assert labeller.last_run.prompt_version == "1.3.0"


def test_feedback_is_the_retry_prompt_and_additions():
    labeller, chat = _labeller()
    result = labeller(BLOCKS, feedback=FEEDBACK, first=_first())

    assert isinstance(result, Additions)
    assert result == _additions()
    assert [schema for schema, _ in chat.calls] == [Additions]
    system, human = chat.calls[0][1]
    assert system.content == RETRY_TEXT
    payload = json.loads(human.content)
    assert [b["block_id"] for b in payload["blocks"]] == ["body:0", "body:1", "body:2"]
    assert payload["blocks"][1]["text"] == "Software Engineer at Acme"
    assert payload["first_answer"] == _first().model_dump(mode="json")
    assert payload["feedback"]["unusable"] is False


def test_the_feedback_reaches_the_provider_with_its_text():
    messages = retry_messages(BLOCKS, _first(), FEEDBACK)
    feedback = json.loads(messages[1].content)["feedback"]

    # The unplaced run's text, sliced from its block.
    assert feedback["unplaced"] == [
        {"block_id": "body:1", "start": 21, "end": 25, "text": "Acme"}
    ]
    # Each unlocatable hint's rejected quote, looked up by path in the first
    # answer; a path naming nothing there keeps no quote.
    assert feedback["unlocatable"] == [
        {"path": "skills[0]", "block_id": "body:2", "quote": "Pythn"},
        {
            "path": "experience[0].title",
            "block_id": "body:1",
            "quote": "Software Enginer",
        },
        {
            "path": "experience[0].bullets[0]",
            "block_id": "body:2",
            "quote": "Led the Cork tam",
        },
        {"path": "removals[0]", "block_id": "body:2", "quote": "0871"},
        {"path": "experience[7].title", "block_id": "body:2"},
    ]


def test_an_unusable_first_answer_asks_for_everything_as_additions():
    labeller, chat = _labeller()
    labeller(BLOCKS, feedback=Feedback(unusable=True))

    payload = json.loads(chat.calls[0][1][1].content)
    assert payload["first_answer"] is None
    assert payload["feedback"] == {
        "unusable": True,
        "unplaced": [],
        "unlocatable": [],
    }
    assert "unusable" in RETRY_TEXT
    assert "empty tree" in RETRY_TEXT


def test_an_unusable_flag_wins_over_a_first_answer_passed_anyway():
    messages = retry_messages(BLOCKS, _first(), Feedback(unusable=True))
    payload = json.loads(messages[1].content)
    assert payload["first_answer"] is None


def test_a_retry_without_a_first_answer_unless_unusable_is_a_defect():
    labeller, chat = _labeller()
    with pytest.raises(ValueError, match="first answer"):
        labeller(BLOCKS, feedback=FEEDBACK)
    assert chat.calls == []


def test_the_oracle_style_call_still_works_with_one_argument():
    labeller, _ = _labeller()
    assert isinstance(labeller(BLOCKS), Labelling)


@pytest.mark.parametrize(
    ("path", "quote"),
    [
        ("name", "Padraig Lonergan"),
        ("skills[0]", "Pythn"),
        ("experience[0].title", "Software Enginer"),
        ("experience[0].employer", None),
        ("experience[0].bullets[0]", "Led the Cork tam"),
        ("experience[0].bullets[1]", None),
        ("education[0].details[0]", None),
        ("removals[0]", "0871"),
        ("removals[1]", None),
        ("profile[0]", None),
        ("nonsense", None),
        ("experience[0].__class__", None),
    ],
)
def test_a_hint_path_finds_its_reference(path: str, quote: str | None):
    reference = _reference_at(_first(), path)
    assert (reference.quote if reference else None) == quote


# --- the retry's own Run section ---------------------------------------------


def test_a_retry_fills_its_own_label_run_and_exchange():
    labeller, _ = _labeller()
    labeller(BLOCKS)
    first_run = labeller.last_run
    labeller(BLOCKS, feedback=FEEDBACK, first=_first())
    run = labeller.last_run

    assert run is not first_run
    assert run.prompt_version == RETRY_VERSION
    assert run.prompt_hash == RETRY_HASH
    assert run.schema_version == ADDITIONS_VERSION
    assert run.schema_hash == ADDITIONS_HASH
    assert run.content_hash == CONTENT_HASH
    assert (run.input_tokens, run.output_tokens) == (300, 20)
    assert run.cost_usd > 0
    assert run.label_failed is False

    exchange = labeller.last_exchange
    assert [m["role"] for m in exchange.messages] == ["system", "human"]
    assert exchange.messages[0]["content"] == RETRY_TEXT
    assert "Acme" in exchange.messages[1]["content"]
    assert exchange.answer == _additions().model_dump_json()
    # The Run keeps no text.
    assert "Acme" not in run.model_dump_json()


# --- the same failure classification as the first attempt ---------------------


def _schema_error(data: dict[str, Any]) -> Exception:
    try:
        Additions.model_validate(data)
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a validation error")


def _retry_with(response: dict[str, Any]):
    labeller, _ = _labeller(response)
    result = labeller(BLOCKS, feedback=FEEDBACK, first=_first())
    return result, labeller.last_run


def test_a_schema_invalid_retry_names_where_but_never_what():
    bad = {
        "additions": [
            {"path": "skills", "reference": {"block_id": "body:0", "quote": 7}},
            {CANARY: CANARY},
        ],
        CANARY: 1,
    }
    result, run = _retry_with(
        {
            "raw": AIMessage(content=CANARY, usage_metadata=USAGE),
            "parsed": None,
            "parsing_error": _schema_error(bad),
        }
    )

    assert isinstance(result, LabellingFailure)
    assert result.reason.startswith("schema mismatch at ")
    assert "additions.0.reference.quote" in result.reason
    assert CANARY not in result.reason
    assert run.label_failed is True
    assert run.failure_reason == result.reason
    assert run.prompt_version == RETRY_VERSION
    assert (run.input_tokens, run.output_tokens) == (300, 20)
    assert CANARY not in run.model_dump_json()


def test_a_malformed_retry_is_invalid_json():
    result, run = _retry_with(
        {
            "raw": AIMessage(content=CANARY),
            "parsed": None,
            "parsing_error": json.JSONDecodeError(CANARY, CANARY, 0),
        }
    )
    assert result == LabellingFailure(reason="invalid JSON")
    assert run.label_failed is True


def test_a_refused_retry_is_a_labelling_failure():
    raw = AIMessage(
        content="", response_metadata={"stop_reason": "refusal"}, usage_metadata=USAGE
    )
    result, run = _retry_with({"raw": raw, "parsed": None, "parsing_error": None})
    assert result == LabellingFailure(reason="the model refused to answer")
    assert run.label_failed is True


def test_a_labelling_where_additions_were_expected_is_a_schema_mismatch():
    result, _ = _retry_with(
        {"raw": AIMessage(content=""), "parsed": _first(), "parsing_error": None}
    )
    assert result == LabellingFailure(reason="schema mismatch")


def test_a_parser_error_raised_by_the_retry_call_is_a_labelling_failure():
    labeller, _ = _labeller(OutputParserException(f"bad {CANARY}", llm_output=CANARY))
    result = labeller(BLOCKS, feedback=FEEDBACK, first=_first())
    assert result == LabellingFailure(reason="invalid JSON")
    assert CANARY not in repr(result)


def test_a_defect_in_the_retry_call_raises_without_the_message():
    labeller, _ = _labeller(RuntimeError(f"bug {CANARY}"))
    with pytest.raises(LabellerMisconfigured) as raised:
        labeller(BLOCKS, feedback=FEEDBACK, first=_first())
    assert "RuntimeError" in str(raised.value)
    assert CANARY not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


def test_a_provider_error_in_the_retry_is_provider_unavailable():
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.RateLimitError(
        f"echoed {CANARY}", response=httpx.Response(429, request=request), body=None
    )
    labeller, _ = _labeller(exc)
    with pytest.raises(ProviderUnavailable) as raised:
        labeller(BLOCKS, feedback=FEEDBACK, first=_first())
    assert CANARY not in str(raised.value)
    assert raised.value.__cause__ is None
