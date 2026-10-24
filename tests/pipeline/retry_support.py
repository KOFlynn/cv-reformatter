"""The scripted fake for the retry loop: the real ``RealLabeller`` over a fake
chat model that answers from a script, one step per model call, whatever
schema it is bound to. So the real parsing, exception wrapping and prompt
choice run, and a test says what the model "said" on each attempt.

A step is a parsed answer (``Labelling`` or ``Additions``), the string
``"malformed"`` (an answer that does not parse), ``"outage"`` (the provider
is down) or a ready-made response dict. A call past the end of the script
fails the test: a retry the test did not expect.
"""

import json
from typing import Any

import anthropic
import httpx
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from oracle import Imperfect, Oracle
from pipeline_support import document

from cvr.label import RealLabeller
from cvr.label.config import LabellerConfig
from cvr.models import (
    Addition,
    Additions,
    Labelling,
    LabellingResult,
    Reference,
    SourceBlock,
)
from cvr.parse import parse

USAGE = {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}
_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

Step = Labelling | Additions | str | dict[str, Any]


def ok(parsed: Labelling | Additions) -> dict[str, Any]:
    raw = AIMessage(content=parsed.model_dump_json(), usage_metadata=USAGE)
    return {"raw": raw, "parsed": parsed, "parsing_error": None}


def malformed() -> dict[str, Any]:
    error = OutputParserException("Failed to parse", llm_output="{not json")
    raw = AIMessage(content="{not json", usage_metadata=USAGE)
    return {"raw": raw, "parsed": None, "parsing_error": error}


def outage() -> Exception:
    return anthropic.InternalServerError(
        "overloaded",
        response=httpx.Response(500, request=_REQUEST),
        body={"error": "overloaded"},
    )


class ScriptedChat:
    """``chat_model`` for ``RealLabeller``. ``calls`` records, per model call,
    the schema it was bound to and its messages."""

    def __init__(self, script: list[Step]):
        self.script = list(script)
        self.calls: list[tuple[type, list[Any]]] = []

    def with_structured_output(self, schema: type, **kwargs: Any):
        def invoke(messages: list[Any]) -> dict[str, Any]:
            self.calls.append((schema, messages))
            if not self.script:
                raise AssertionError(
                    "the labeller made a call the script has no step for"
                )
            step = self.script.pop(0)
            if step == "malformed":
                return malformed()
            if step == "outage":
                raise outage()
            if isinstance(step, dict):
                return step
            return ok(step)

        return RunnableLambda(invoke)

    @property
    def schemas(self) -> list[type]:
        return [schema for schema, _ in self.calls]

    def payload(self, call: int) -> dict[str, Any]:
        """The JSON the human message of call ``call`` held (a retry's)."""
        return json.loads(self.calls[call][1][1].content)


def scripted(*script: Step) -> tuple[RealLabeller, ScriptedChat]:
    chat = ScriptedChat(list(script))
    return RealLabeller(LabellerConfig(), chat_model=chat), chat


def perfect(stem: str) -> LabellingResult:
    doc = document(stem)
    return Oracle(doc.candidate, doc.manifest)(_blocks(doc))


def damaged(stem: str, damage) -> Labelling:
    doc = document(stem)
    return Imperfect(Oracle(doc.candidate, doc.manifest), damage)(_blocks(doc))


def _blocks(doc) -> list[SourceBlock]:
    return parse(doc.source).blocks


def drop_first_bullets(count: int):
    """Leave the first ``count`` bullets of the first experience entry
    unreferenced, as a labeller that missed them."""

    def damage(labelling: Labelling) -> Labelling:
        entry = labelling.content.experience[0]
        experience = [
            entry.model_copy(update={"bullets": entry.bullets[count:]}),
            *labelling.content.experience[1:],
        ]
        content = labelling.content.model_copy(update={"experience": experience})
        return labelling.model_copy(update={"content": content})

    return damage


def bullet_additions(full: Labelling, *indices: int) -> Additions:
    """Additions placing the first entry's bullets ``indices`` of the perfect
    answer ``full``."""
    bullets = full.content.experience[0].bullets
    return Additions(
        additions=[
            Addition(
                path="experience[0].bullets",
                reference=Reference(
                    block_id=bullets[i].block_id, quote=bullets[i].quote
                ),
            )
            for i in indices
        ]
    )
