"""Ticket 10: the canary leak test, the evidence behind ADR-0013.

A copy of Candidate c11 is built at test time (nothing in ``fixtures/``
changes) in which every content leaf, PII value and unplaceable fragment is
a unique canary from a seeded generator, shaped like what it replaces (digit
strings for phones, a unique domain for emails, words for text); dates stay
real. It is rendered through all four Layouts and taken through the API and
through ``reformat`` in structure mode, with the real ``RealLabeller`` over a
fake chat model (no LLM, no network, an in-memory exporter, dummy keys). The
fake's answers include a flawed one (a quote and a block id the model made up)
and failures whose text carries canaries: a malformed answer, a schema-invalid
one, a refusal, a provider error and a defect. Three more scenarios script the
retry loop (ticket 16): a first answer that leaves a bullet unplaced and echoes a
made-up quote, then a retry that succeeds, one that makes no progress and one
whose answer is malformed and carries canaries.

Checked, for every canary and its normalised forms (case folded, spaces
removed, letters and digits only) and for each word of a canary:

* no canary in any exported span (``ReadableSpan.to_json``: names, attributes,
  events, status, resource attributes, links);
* no PII (nor model-echo) canary in the logs (standard output, standard error and every logger,
  at DEBUG), the API's error bodies, the exceptions that escape the labeller
  (with their cause and context chains) or the Run's failure reasons;
* the same for the retries: no canary in ``Run.retries``, nor a PII or model
  one in the logs, whatever a retry's answer said. The request the fake model
  *receives* is deliberately not among the channels checked: the retry prompt
  sends the unplaced text and the made-up quotes to the provider, by design
  (the provider boundary), while the Run, the logs and the structure traces
  (the log/trace boundary, ADR-0013) carry none of it; a positive control
  proves the fake did receive them;
* a second layer: no token of the source documents that is not the Layout's
  own text (a heading, a label, a date) in any exported span.

Positive controls keep that from passing blind: the spans hold the run id and
counts, the logs hold non-PII text, full mode holds every kind of canary
(including the PII ones), and the detector finds a canary that was spaced out
and recased.
"""

import contextlib
import io
import json
import logging
import random
import re
import traceback
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from oracle import Oracle
from retry_support import drop_first_bullets
from tracing_support import exported, make_tracer

import cvr.api.app as api_app
from cvr.api import DOCX_MEDIA_TYPE, RUN_ID_HEADER, create_app
from cvr.golden import LAYOUTS, Candidate, load_candidates
from cvr.label import RealLabeller
from cvr.label.errors import LabellerMisconfigured, ProviderUnavailable
from cvr.label.versions import CONTENT_HASH, PROMPT_HASH, SCHEMA_HASH
from cvr.models import Addition, Additions, Labelling, Reference
from cvr.parse import parse
from cvr.pipeline import reformat
from cvr.template import template_tokens
from cvr.text import tokenise
from cvr.tracing import ALLOWED_KEYS
from cvr.verify.backstops import HEADING_VOCABULARY

SEED = 20261021
API_KEY = "canary-test-api-key-0123456789"
BASE = "c11"  # has referees and unplaceable fragments; PII below is added to it

PII, CONTENT, MODEL = "pii", "content", "model"


# --- the canaries -----------------------------------------------------------

_CONSONANTS = "ghjklmnpqrstvwxz"  # no a-f: never a run of hex digits
_VOWELS = "aiou"


@dataclass
class Canaries:
    """Every canary of one test, with its class: ``pii`` (a value the system
    removes), ``content`` (a CV's text, which the output legitimately holds) or
    ``model`` (text a model, or an error, echoes back). A seeded generator, so
    the test is the same every time."""

    rng: random.Random = field(default_factory=lambda: random.Random(SEED))
    kinds: dict[str, str] = field(default_factory=dict)  # canary -> class
    needles: dict[str, str] = field(default_factory=dict)  # needle -> class
    words: set[str] = field(default_factory=set)

    def _register(self, kind: str, canary: str, *parts: str) -> str:
        assert canary not in self.kinds
        self.kinds[canary] = kind
        for needle in (canary, *parts):
            self.needles[needle] = kind
        return canary

    def _word(self) -> str:
        while True:
            word = "".join(
                self.rng.choice(_CONSONANTS) + self.rng.choice(_VOWELS)
                for _ in range(4)
            )
            if word not in self.words:
                self.words.add(word)
                return word

    def text(self, kind: str, words: int = 3) -> str:
        parts = [self._word() for _ in range(words)]
        return self._register(kind, " ".join(parts).capitalize(), *parts)

    def phone(self, kind: str = PII) -> str:
        digits = [str(self.rng.randint(0, 9)) for _ in range(13)]
        digits[0] = str(self.rng.randint(1, 9))
        number = "".join(digits)
        shaped = f"+{number[:3]} {number[3:5]} {number[5:9]} {number[9:]}"
        return self._register(kind, shaped, number)

    def email(self, kind: str = PII) -> str:
        local, domain = self._word() + self._word(), self._word() + self._word()
        return self._register(kind, f"{local}@{domain}.example.invalid", local, domain)

    def url(self, kind: str = PII) -> str:
        host, path = self._word() + self._word(), self._word() + self._word()
        return self._register(
            kind, f"https://www.{host}.example.invalid/{path}", host, path
        )

    def phones(self) -> list[str]:
        """The PII canaries shaped like a phone number (a leading ``+``)."""
        return [c for c, k in self.kinds.items() if k == PII and c.startswith("+")]

    def of_kind(self, *kinds: str) -> list[str]:
        return [n for n, k in self.needles.items() if k in kinds]


def _canary_candidate(canaries: Canaries) -> Candidate:
    """The base Candidate with every leaf replaced by a canary. Dates, the
    structure and the tags stay as they are; c11 has no date of birth or
    personal details, so a copy gets canaries for those too."""
    base = next(c for c in load_candidates() if c.id == BASE)
    data = base.model_dump(mode="json")
    content, pii = data["content"], data["pii"]

    content["name"] = canaries.text(CONTENT, 2)
    content["profile"] = [canaries.text(CONTENT, 6) for _ in content["profile"]]
    content["skills"] = [canaries.text(CONTENT, 2) for _ in content["skills"]]
    for entry in content["education"]:
        entry["institution"] = canaries.text(CONTENT, 3)
        entry["qualification"] = canaries.text(CONTENT, 3)
        entry["details"] = [canaries.text(CONTENT, 4) for _ in entry["details"]]
    for entry in content["experience"]:
        entry["title"] = canaries.text(CONTENT, 2)
        entry["employer"] = canaries.text(CONTENT, 2)
        entry["location"] = canaries.text(CONTENT, 1)
        entry["bullets"] = [canaries.text(CONTENT, 5) for _ in entry["bullets"]]
    content["certifications"] = [
        canaries.text(CONTENT, 3) for _ in content["certifications"]
    ]
    content["additional"] = [canaries.text(CONTENT, 4) for _ in content["additional"]]
    data["unplaceable"] = [canaries.text(CONTENT, 4) for _ in data["unplaceable"]]

    pii["phone"] = canaries.phone()
    pii["email"] = canaries.email()
    pii["address"] = [canaries.text(PII, 2) for _ in pii["address"]]
    pii["urls"] = [canaries.url() for _ in pii["urls"]]
    pii["dob"] = canaries.text(PII, 3)
    pii["personal"] = {
        "nationality": canaries.text(PII, 1),
        "marital_status": canaries.text(PII, 1),
    }
    for referee in pii["referees"]:
        referee["name"] = canaries.text(PII, 2)
        referee["role"] = canaries.text(PII, 2)
        referee["contact"] = [canaries.email(), canaries.phone()]
    return Candidate.model_validate(data)


def _forms(needle: str) -> tuple[str, str, str]:
    folded = needle.casefold()
    return folded, "".join(folded.split()), re.sub(r"[^0-9a-z]", "", folded)


def leaks(haystack: str, needles) -> list[str]:
    """The needles found in ``haystack``: as written, case folded, with
    whitespace removed, or as letters and digits only against the haystack
    reduced the same way (so ``Ko Va Zu`` and ``kova-zu`` are both found)."""
    folded = haystack.casefold()
    squashed = re.sub(r"[^0-9a-z]", "", folded)
    found = []
    for needle in needles:
        plain, spaceless, alnum = _forms(needle)
        if plain in folded or spaceless in "".join(folded.split()) or alnum in squashed:
            found.append(needle)
    return found


# --- the fake model ---------------------------------------------------------

_USAGE = {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500}
_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeChat:
    """``chat_model`` for ``RealLabeller``: ``with_structured_output`` gives a
    runnable answering with ``respond`` (a structured-output response dict, or
    an exception to raise), the oracle's labelling of the document's blocks
    being what a perfect model would say."""

    def __init__(
        self, respond: Callable[[Labelling], dict[str, Any]], oracle: Oracle, blocks
    ):
        self._respond, self._oracle, self._blocks = respond, oracle, blocks

    def with_structured_output(self, *args: Any, **kwargs: Any):
        return RunnableLambda(
            lambda _messages: self._respond(self._oracle(self._blocks))
        )


def _ok(labelling: Labelling) -> dict[str, Any]:
    raw = AIMessage(content=labelling.model_dump_json(), usage_metadata=_USAGE)
    return {"raw": raw, "parsed": labelling, "parsing_error": None}


def _malformed(said: str) -> dict[str, Any]:
    cause = json.JSONDecodeError(f"Expecting value {said}", said, 0)
    error = OutputParserException(f"Failed to parse: {said}", llm_output=said)
    error.__cause__ = cause
    raw = AIMessage(content=f"{{not json {said}", usage_metadata=_USAGE)
    return {"raw": raw, "parsed": None, "parsing_error": error}


def _with_title(labelling: Labelling, **update: str) -> Labelling:
    entry = labelling.content.experience[0]
    title = entry.title.model_copy(update=update)
    experience = [
        entry.model_copy(update={"title": title}),
        *labelling.content.experience[1:],
    ]
    content = labelling.content.model_copy(update={"experience": experience})
    return labelling.model_copy(update={"content": content})


def _echo(canaries: Canaries) -> tuple[str, str]:
    """The text a model or an error echoes: a ``model`` canary, and the same
    followed by the document's own phone."""
    echo = canaries.text(MODEL, 4)
    return echo, f"{echo} {canaries.phones()[0]}"


def _scenarios(
    echo: str, said: str
) -> dict[str, Callable[[Labelling], dict[str, Any]]]:
    """How the fake model answers, by scenario name."""

    def flawed(labelling: Labelling) -> dict[str, Any]:
        # A quote not in the source and a block id the model made up.
        return _ok(_with_title(labelling, quote=said, block_id=echo.replace(" ", "-")))

    def malformed(_: Labelling) -> dict[str, Any]:
        return _malformed(said)

    def schema_invalid(_: Labelling) -> dict[str, Any]:
        try:
            Labelling.model_validate(
                {"content": {"name": 7, said: said}, "removals": []}
            )
        except ValueError as error:
            raw = AIMessage(content=said, usage_metadata=_USAGE)
            return {"raw": raw, "parsed": None, "parsing_error": error}
        raise AssertionError("the answer was valid")

    def refusal(_: Labelling) -> dict[str, Any]:
        raw = AIMessage(
            content=said,
            response_metadata={"stop_reason": "refusal"},
            usage_metadata=_USAGE,
        )
        return {"raw": raw, "parsed": None, "parsing_error": None}

    def provider_down(_: Labelling) -> dict[str, Any]:
        raise anthropic.InternalServerError(
            f"overloaded: {said}",
            response=httpx.Response(500, request=_REQUEST),
            body={"echo": said},
        )

    def defect(_: Labelling) -> dict[str, Any]:
        raise RuntimeError(f"a bug that mentions {said}")

    return {
        "ok": _ok,
        "flawed": flawed,
        "malformed": malformed,
        "schema-invalid": schema_invalid,
        "refusal": refusal,
        "provider-down": provider_down,
        "defect": defect,
    }


class RetryChat:
    """``chat_model`` for the retry scenarios: one step per model call, whatever
    schema it is bound to (the last step repeats, so a loop that retries more
    often than the script says still gets an answer). ``requests`` keeps the
    messages of every call as the provider received them, canaries and all."""

    def __init__(self, steps, oracle: Oracle, blocks):
        self._steps, self._oracle, self._blocks = steps, oracle, blocks
        self.requests: list[tuple[str, list[Any]]] = []

    def with_structured_output(self, schema: type, *args: Any, **kwargs: Any):
        def invoke(messages: list[Any]) -> dict[str, Any]:
            step = self._steps[min(len(self.requests), len(self._steps) - 1)]
            self.requests.append((schema.__name__, messages))
            return step(self._oracle(self._blocks))

        return RunnableLambda(invoke)


@dataclass
class RetryScenario:
    """Steps (each: the perfect labelling in, a response dict out) the fake
    model takes in turn."""

    steps: list[Callable[[Labelling], dict[str, Any]]]


def _retry_scenarios(echo: str, said: str) -> dict[str, RetryScenario]:
    def first(labelling: Labelling) -> dict[str, Any]:
        # The first bullet of the first job is left unplaced, and a skill
        # whose quote the model made up is rejected (so a hint to the retry).
        damaged = drop_first_bullets(1)(labelling)
        block_id = labelling.content.experience[0].bullets[0].block_id
        made_up = Reference(block_id=block_id, quote=said)
        content = damaged.content.model_copy(
            update={"skills": [*damaged.content.skills, made_up]}
        )
        return _ok(damaged.model_copy(update={"content": content}))

    def fixed(labelling: Labelling) -> dict[str, Any]:
        bullet = labelling.content.experience[0].bullets[0]
        placed = Addition(
            path="experience[0].bullets",
            reference=Reference(block_id=bullet.block_id, quote=bullet.quote),
        )
        # An addition whose quote is made up is rejected too.
        invented = Addition(
            path="skills",
            reference=Reference(block_id=bullet.block_id, quote=said),
        )
        return _ok(Additions(additions=[placed, invented]))

    def bad_path(labelling: Labelling) -> dict[str, Any]:
        # Model-authored ids: a path that is free text, and one that echoes a
        # PII-shaped string; and a block id the model made up. None may be
        # recorded anywhere a reader can see.
        bullet = labelling.content.experience[0].bullets[0]
        real = Reference(block_id=bullet.block_id, quote=bullet.quote)
        return _ok(
            Additions(
                additions=[
                    Addition(path=echo, reference=real),
                    Addition(path=said, reference=real),
                    Addition(
                        path="skills",
                        reference=Reference(
                            block_id=echo.replace(" ", "-"), quote=bullet.quote
                        ),
                    ),
                ]
            )
        )

    def no_progress(_: Labelling) -> dict[str, Any]:
        return _ok(Additions(additions=[]))

    def malformed(_: Labelling) -> dict[str, Any]:
        return _malformed(said)

    return {
        "retry-fixed": RetryScenario([first, fixed, no_progress]),
        "retry-no-progress": RetryScenario([first, no_progress]),
        "retry-bad-path": RetryScenario([first, bad_path, no_progress]),
        "retry-malformed": RetryScenario([first, malformed]),
    }


def _chat(respond, oracle: Oracle, blocks):
    if isinstance(respond, RetryScenario):
        return RetryChat(respond.steps, oracle, blocks)
    return FakeChat(respond, oracle, blocks)


# --- what was observed ------------------------------------------------------


@dataclass
class Channels:
    """Everything one scenario put where a reader could see it."""

    spans: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    bodies: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    retries: list[str] = field(default_factory=list)  # Run.retries, as JSON
    reasons_after_retry: list[str] = field(default_factory=list)  # the retries'
    # What the fake model received on its retry calls. No leak assertion reads
    # it: see the module docstring.
    requests: list[str] = field(default_factory=list)
    run_ids: list[str] = field(default_factory=list)

    def join(self, name: str) -> str:
        return "\n".join(getattr(self, name))


@contextlib.contextmanager
def _captured() -> Iterator[Callable[[], str]]:
    """Standard output, standard error and every logger at DEBUG, as one text."""
    out, err, logged = io.StringIO(), io.StringIO(), io.StringIO()
    handler = logging.StreamHandler(logged)
    handler.setLevel(logging.DEBUG)
    names = ["", "langfuse", "opentelemetry", "cvr", "httpx", "httpcore"]
    loggers = [logging.getLogger(name) for name in names]
    saved = [(lg, lg.level) for lg in loggers]
    for lg in loggers:
        lg.setLevel(logging.DEBUG)
        lg.addHandler(handler)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            yield lambda: f"{out.getvalue()}\n{err.getvalue()}\n{logged.getvalue()}"
    finally:
        for lg, level in saved:
            lg.removeHandler(handler)
            lg.setLevel(level)


def _spans_json(tracer, exporter) -> list[str]:
    return [span.to_json() for span in exported(tracer, exporter)]


def _exception_text(error: BaseException) -> str:
    chain, seen, current = [], set(), error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(
            "".join(traceback.format_exception(current))
            + repr(current)
            + repr(current.args)
        )
        current = current.__cause__ or current.__context__
    return "\n".join(chain)


@dataclass
class Harvest:
    canaries: Canaries
    sources: dict[str, bytes]
    channels: dict[
        tuple[str, str, str], Channels
    ]  # (layout, scenario, path) -> observed
    full: Channels
    bullets: list[str]  # each job's first bullet: the retry tests leave one unplaced
    benign: list[str]


def _requests(chat) -> list[str]:
    """The retry calls' messages as text (the first call is not a retry's)."""
    return [
        str(messages[1].content)  # the human message: one JSON object
        for schema, messages in getattr(chat, "requests", [])
        if schema == "Additions"
    ]


def _run_api(source, respond, oracle) -> Channels:
    tracer, exporter = make_tracer("structure", tags=["env=local"])
    blocks = parse(source).blocks
    chat = _chat(respond, oracle, blocks)
    labeller = RealLabeller(chat_model=chat)
    client = TestClient(create_app(labeller, tracer=tracer))
    observed = Channels()
    with _captured() as logs:
        response = client.post(
            "/reformat",
            files={"file": ("cv.docx", source, DOCX_MEDIA_TYPE)},
            headers={"X-API-Key": API_KEY},
        )
    observed.logs.append(logs())
    observed.requests += _requests(chat)
    observed.run_ids.append(response.headers[RUN_ID_HEADER])
    observed.spans += _spans_json(tracer, exporter)
    if response.status_code != 200:
        observed.bodies.append(response.text)
    return observed


def _run_direct(source, respond, oracle, run_id, mode="structure") -> Channels:
    tracer, exporter = make_tracer(mode)
    chat = _chat(respond, oracle, parse(source).blocks)
    labeller = RealLabeller(chat_model=chat)
    observed = Channels()
    with _captured() as logs:
        try:
            _, run = reformat(source, labeller, run_id=run_id, tracer=tracer)
        except (ProviderUnavailable, LabellerMisconfigured) as error:
            observed.exceptions.append(_exception_text(error))
        else:
            if run.label is not None and run.label.failure_reason:
                observed.reasons.append(run.label.failure_reason)
            observed.reasons_after_retry += [
                r.label.failure_reason
                for r in run.retries
                if r.label is not None and r.label.failure_reason
            ]
            observed.retries += [r.model_dump_json() for r in run.retries]
    observed.logs.append(logs())
    observed.requests += _requests(chat)
    observed.spans += _spans_json(tracer, exporter)
    observed.run_ids.append(run_id)
    return observed


@pytest.fixture(scope="module")
def harvest() -> Iterator[Harvest]:
    canaries = Canaries()
    candidate = _canary_candidate(canaries)
    echo, said = _echo(canaries)
    scenarios = {**_scenarios(echo, said), **_retry_scenarios(echo, said)}

    # Deterministic run ids, so the collision check below covers every id the
    # test will see; the API issues its own with ``uuid4`` (patched here).
    id_rng = random.Random(SEED + 1)
    run_ids = [
        "".join(id_rng.choice("0123456789abcdef") for _ in range(32))
        for _ in range(200)
    ]
    issued = iter(run_ids)

    channels: dict[tuple[str, str, str], Channels] = {}
    sources: dict[str, bytes] = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("CVR_API_KEY", API_KEY)
        patch.setattr(api_app, "uuid4", lambda: SimpleNamespace(hex=next(issued)))
        for layout in LAYOUTS:
            generated = layout.generate(candidate)
            source = sources[layout.name] = generated.document
            oracle = Oracle(candidate, generated.manifest)
            for name, respond in scenarios.items():
                channels[layout.name, name, "api"] = _run_api(source, respond, oracle)
                channels[layout.name, name, "direct"] = _run_direct(
                    source, respond, oracle, next(issued)
                )
        # Full mode, once, as the positive control that the canaries are
        # visible to the detector in a trace that does carry text.
        generated = LAYOUTS[0].generate(candidate)
        full = _run_direct(
            generated.document,
            scenarios["flawed"],
            Oracle(candidate, generated.manifest),
            next(issued),
            mode="full",
        )

    benign = [
        *run_ids,
        PROMPT_HASH,
        SCHEMA_HASH,
        CONTENT_HASH,
        *sorted(ALLOWED_KEYS),
        *template_tokens(),
        *HEADING_VOCABULARY,
        "unlocatable conflict removed reformat parse label verify transform render",
    ]
    # Which job comes first depends on the Layout, so any job's first bullet
    # may be the one the first answer leaves out.
    bullets = [entry.bullets[0] for entry in candidate.content.experience]
    yield Harvest(canaries, sources, channels, full, bullets, benign)


def _everywhere(harvest: Harvest, name: str) -> str:
    return "\n".join(c.join(name) for c in harvest.channels.values())


# --- the canaries are sound -------------------------------------------------


def test_the_canaries_collide_with_nothing_they_could_be_mistaken_for(harvest):
    haystack = "\n".join(harvest.benign)
    assert leaks(haystack, harvest.canaries.needles) == []
    assert len(harvest.canaries.needles) > 100  # the canaries were built


def test_the_detector_finds_a_canary_spaced_out_and_recased():
    detector = Canaries()
    name = detector.text(CONTENT, 2)
    phone = detector.phone()
    spaced = " ".join(name.upper())
    assert leaks(f"x {spaced} y", [name]) == [name]
    assert leaks("tel " + phone.replace(" ", ""), [phone])
    assert leaks("tel " + phone.replace(" ", "-"), [phone])
    assert leaks("unrelated text", detector.needles) == []


def test_the_source_documents_hold_the_canaries(harvest):
    # The Layouts print them (a confusable or case change would make the
    # canaries blind); every class is in every Layout's source.
    for layout, source in harvest.sources.items():
        text = "\n".join(block.text for block in parse(source).blocks)
        for kind in (PII, CONTENT):
            hits = {
                c
                for c in harvest.canaries.kinds
                if harvest.canaries.kinds[c] == kind and leaks(text, [c])
            }
            assert hits, (layout, kind)
        # The phone the Layout printed is among the PII canaries.
        assert leaks(
            text,
            harvest.canaries.phones(),
        )


# --- the structure-mode traces ----------------------------------------------


def test_no_canary_is_in_any_exported_span(harvest):
    spans = _everywhere(harvest, "spans")
    assert spans  # the control below checks what is in it
    assert leaks(spans, harvest.canaries.needles) == []


def test_the_spans_still_hold_ids_and_counts(harvest):
    for (layout, scenario, path), observed in harvest.channels.items():
        spans = [json.loads(s) for s in observed.spans]
        assert spans, (layout, scenario, path)
        trace_ids = {s["context"]["trace_id"] for s in spans}
        assert trace_ids == {"0x" + observed.run_ids[0]}, (layout, scenario, path)
        by_name = {s["name"]: s["attributes"] for s in spans}
        blocks = len(parse(harvest.sources[layout]).blocks)
        assert (
            json.loads(by_name["parse"]["langfuse.observation.metadata.block_count"])
            == blocks
        )
        if scenario == "ok":
            verify = by_name["verify"]
            assert json.loads(verify["langfuse.observation.metadata.claim_count"]) > 0
            assert (
                json.loads(verify["langfuse.observation.metadata.rejection_count"]) == 0
            )
            root = by_name["reformat"]
            assert (
                json.loads(root["langfuse.observation.metadata.run_id"])
                == observed.run_ids[0]
            )
        if scenario == "flawed":
            events = [s for s in spans if s["name"] == "rejection"]
            assert len(events) == 1
            attributes = events[0]["attributes"]
            assert (
                json.loads(attributes["langfuse.observation.metadata.reason"])
                == "unlocatable"
            )
            assert (
                json.loads(attributes["langfuse.observation.metadata.block_id"])
                == "unknown"
            )
        if scenario in {"malformed", "schema-invalid", "refusal"}:
            label = by_name["label"]
            assert (
                json.loads(label["langfuse.observation.metadata.label_failed"]) is True
            )


def test_the_source_tokens_that_are_not_the_layouts_own_text_are_in_no_span(harvest):
    """The layer under the canaries: it reads the tokens of the documents as
    the parser found them (so a Layout's confusable or recasing cannot make a
    canary blind) and asks that none of them, but the Layout's own headings,
    labels and dates, reaches a span."""
    spans_tokens = set(tokenise(_everywhere(harvest, "spans")))
    own = {
        t for text in (*template_tokens(), *HEADING_VOCABULARY) for t in tokenise(text)
    }
    for layout, source in harvest.sources.items():
        tokens = {
            t for b in parse(source).blocks for t in tokenise(b.text) if len(t) >= 4
        }
        content = tokens - own
        assert content, layout  # the canaries are what is left
        assert not (content & spans_tokens), (layout, sorted(content & spans_tokens))


# --- the logs, the bodies, the exceptions, the reasons ----------------------


def test_no_pii_canary_is_in_the_logs(harvest):
    logs = _everywhere(harvest, "logs")
    assert leaks(logs, harvest.canaries.of_kind(PII, MODEL)) == []


def test_the_logs_still_hold_non_pii_text_and_the_run_id(harvest):
    for (layout, scenario, path), observed in harvest.channels.items():
        logs = observed.join("logs")
        if path == "api":
            assert observed.run_ids[0] in logs, (layout, scenario)
    ok = [
        o
        for (layout, scenario, path), o in harvest.channels.items()
        if (scenario, path) == ("ok", "api")
    ]
    for observed in ok:
        assert leaks(observed.join("logs"), harvest.canaries.of_kind(CONTENT)), (
            "no content text in the logs"
        )


def test_the_log_capture_sees_the_loggers_and_not_only_standard_output(harvest):
    # A library logs the request through ``logging``: a capture that missed
    # the loggers would pass blind.
    for layout in harvest.sources:
        logs = harvest.channels[layout, "defect", "api"].join("logs")
        assert "HTTP Request: POST" in logs  # httpx's logger, not our stdout lines


def test_no_canary_is_in_an_error_body_an_exception_or_a_failure_reason(harvest):
    for name in ("bodies", "exceptions", "reasons", "reasons_after_retry"):
        text = _everywhere(harvest, name)
        assert text, name  # each is exercised
        assert leaks(text, harvest.canaries.needles) == [], name


def test_the_failures_were_exercised_and_stayed_fixed_in_kind(harvest):
    for layout in sorted(harvest.sources):
        assert "misconfigured" in harvest.channels[layout, "defect", "api"].join(
            "bodies"
        )
        assert "unavailable" in harvest.channels[layout, "provider-down", "api"].join(
            "bodies"
        )
        reasons = {
            scenario: harvest.channels[layout, scenario, "direct"].reasons
            for scenario in ("malformed", "schema-invalid", "refusal")
        }
        assert reasons["malformed"] == ["invalid JSON"]
        assert reasons["schema-invalid"][0].startswith("schema mismatch")
        assert reasons["refusal"] == ["the model refused to answer"]
        assert harvest.channels[layout, "defect", "direct"].exceptions


# --- full mode: the positive control -----------------------------------------


def test_full_mode_carries_every_kind_of_canary(harvest):
    spans = harvest.full.join("spans")
    canaries = harvest.canaries
    for kind in (PII, CONTENT, MODEL):
        assert leaks(spans, canaries.of_kind(kind)), kind


# --- the retries (ticket 16) --------------------------------------------------

RETRY_SCENARIOS = (
    "retry-fixed",
    "retry-no-progress",
    "retry-malformed",
    "retry-bad-path",
)


def _retry_channels(harvest: Harvest):
    return [
        (key, observed)
        for key, observed in harvest.channels.items()
        if key[1] in RETRY_SCENARIOS
    ]


def _records(observed: Channels) -> list[dict]:
    return [json.loads(record) for record in observed.retries]


def test_the_fake_model_received_the_unplaced_canaries_in_its_retry_request(harvest):
    """The positive control of the retry tests: the provider is sent the text
    that the Run, the logs and the traces are not."""
    cases = _retry_channels(harvest)
    assert len(cases) == len(RETRY_SCENARIOS) * len(LAYOUTS) * 2
    for key, observed in cases:
        assert observed.requests, key
        for number, request in enumerate(observed.requests):
            feedback = json.loads(request)["feedback"]
            unplaced = " ".join(run["text"] for run in feedback["unplaced"])
            # c11's unplaceable fragments stay unplaced in every retry; the
            # bullet the first answer dropped is there in the first retry
            assert leaks(unplaced, harvest.canaries.of_kind(CONTENT)), key
            if number == 0:
                assert leaks(unplaced, harvest.bullets), key
                # the made-up quote of the first answer comes back as a hint
                hints = " ".join(h.get("quote", "") for h in feedback["unlocatable"])
                assert leaks(hints, harvest.canaries.of_kind(MODEL)), key
            elif "fixed" in key[1]:
                assert not leaks(unplaced, harvest.bullets), key  # placed since


def test_the_retries_were_exercised_in_each_kind(harvest):
    for layout in sorted(harvest.sources):
        fixed = harvest.channels[layout, "retry-fixed", "direct"]
        # the first retry places the dropped bullet; the document's own
        # unplaceable fragments are what keeps the loop going once more
        progress = _records(fixed)
        assert len(progress) == 2
        assert progress[0]["unplaced_chars"] > 0
        assert fixed.reasons == [] and fixed.reasons_after_retry == []

        # no progress: the loop stops after the retry that placed nothing
        stuck = _records(harvest.channels[layout, "retry-no-progress", "direct"])
        assert len(stuck) == 1
        assert stuck[0]["unplaced_chars"] > 0

        broken = harvest.channels[layout, "retry-malformed", "direct"]
        assert _records(broken)
        assert all(r["label"]["label_failed"] for r in _records(broken))
        assert set(broken.reasons_after_retry) == {"invalid JSON"}

        for name in RETRY_SCENARIOS:
            spans = [
                json.loads(s) for s in harvest.channels[layout, name, "direct"].spans
            ]
            assert any(s["name"] == "retry_decision" for s in spans), name


def test_no_canary_is_in_a_runs_retries(harvest):
    # ``Run.retries`` holds feedback (ids, offsets, paths), rejections (reason
    # only) and the attempts' records. What the fake model received is not
    # checked here, on purpose: it is the provider boundary, and the retry
    # prompt hands the provider the unplaced text by design (ADR-0013), while
    # this is the log/trace boundary.
    retries = _everywhere(harvest, "retries")
    assert retries
    assert leaks(retries, harvest.canaries.needles) == []


def test_a_model_written_path_or_block_id_in_an_addition_is_recorded_nowhere(harvest):
    """A retry whose additions carry a canary as their ``path`` (and one a
    canary block id) is rejected, and the Run, the logs, the structure-mode
    spans, the exceptions and the failure reasons hold none of it; the paths
    are recorded as ``unknown``. (The request to the fake model is excluded, as
    the module docstring explains.)"""
    for layout in sorted(harvest.sources):
        for path in ("direct", "api"):
            observed = harvest.channels[layout, "retry-bad-path", path]
            for name in ("spans", "logs", "retries", "exceptions", "reasons"):
                assert leaks(observed.join(name), harvest.canaries.of_kind(MODEL)) == []
        recorded = _records(harvest.channels[layout, "retry-bad-path", "direct"])
        rejections = [r for record in recorded for r in record["rejections"]]
        assert {r["path"] for r in rejections if r["reason"] == "bad_path"} == {
            "unknown"
        }
        assert {r["block_id"] for r in rejections} >= {"unknown"}
        events = [
            json.loads(span)
            for span in harvest.channels[layout, "retry-bad-path", "direct"].spans
        ]
        assert any(e["name"] == "rejection" for e in events)
