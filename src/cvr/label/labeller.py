"""The real labeller: blocks in, a labelling result and the Run's label
section (``cvr.models.LabelRun``) out.
``init_chat_model`` with provider and model from ``LabellerConfig``, then
``with_structured_output(Labelling, method="json_schema")`` so Claude's
native structured-output feature is used instead of a forced tool call,
which would be incompatible with adaptive thinking. Anthropic-specific
options (adaptive-thinking effort, temperature only when set, the client's
retries) are isolated in :func:`anthropic_kwargs`, and Anthropic's error
types in :func:`anthropic_error`; everything else in this module is
provider-agnostic.

Every exception at the labeller boundary is classified, and none of them
carries the model's text or the library's message (pydantic, LangChain's
output parser and the provider SDKs all echo the model's output in theirs):

- the provider was unavailable after the client's retries (connection,
  timeout, 408, 409, 429, 5xx): :class:`ProviderUnavailable`;
- the provider rejected the request as configured (401, 403, 404, 400, 422)
  or the provider is unsupported: :class:`LabellerMisconfigured`;
- anything else that escapes the model call that is not about the model's
  output (a parser or validation error is, and is a labelling failure below):
  :class:`LabellerMisconfigured` with a fixed message naming only the
  exception's type (maintainer decision, ticket 03). The API answers 500,
  the defect stays loud and nothing retries it as a model failure;
- the model answered but unusably: a :class:`~cvr.models.LabellingFailure`
  value, and the job completes with every block in the review appendix. Its
  reason is a fixed category (``the model refused to answer``,
  ``invalid JSON`` or ``schema mismatch``) plus, for a schema mismatch, the
  error locations reduced to the schema's own field names and integers.

Every raised error is raised outside the ``except`` block: the original
exception, whose message may echo text, is on neither ``__cause__`` nor
``__context__`` for a logger or tracer to print.
Retrying a labelling failure is Phase 2.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

import anthropic
from langchain.chat_models import init_chat_model
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from cvr.label.config import LabellerConfig
from cvr.label.errors import LabellerError, LabellerMisconfigured, ProviderUnavailable
from cvr.label.pricing import estimate_cost
from cvr.label.versions import (
    CONTENT_HASH,
    PROMPT_HASH,
    PROMPT_TEXT,
    PROMPT_VERSION,
    SCHEMA_HASH,
    SCHEMA_VERSION,
)
from cvr.models import (
    LabelExchange,
    Labelling,
    LabellingFailure,
    LabellingResult,
    LabelRun,
    SourceBlock,
)

__all__ = [
    "FAILURE_LOCATIONS",
    "MAX_OUTPUT_TOKENS",
    "PROVIDER_RETRIES",
    "RealLabeller",
    "anthropic_error",
    "anthropic_kwargs",
    "build_chat_model",
    "label_blocks",
]


# The provider client's own retries, with its backoff, before a transient
# error becomes ``ProviderUnavailable``: connection errors, timeouts, 429s
# and 5xx are retried; anything else is not.
PROVIDER_RETRIES = 2

# The output cap sent with every request: Sonnet 5.5's and Opus 5.5's documented
# maximum. langchain-anthropic has no model profile for claude-sonnet-5-5, so
# without this it falls back to 4096 tokens; adaptive thinking counts against
# the cap, answers are truncated and become LabellingFailures (ADR-0011).
# ``CVR_LABEL_EXTRA`` can override it.
MAX_OUTPUT_TOKENS = 128_000


def anthropic_kwargs(config: LabellerConfig) -> dict[str, Any]:
    """Anthropic-specific request options, isolated here so no other
    function in this module knows Anthropic's field names. Adaptive
    thinking is enabled implicitly by setting ``reasoning_effort``; a
    temperature is included only when the caller set one, because Opus 5
    rejects an explicit temperature."""
    kwargs: dict[str, Any] = {
        "reasoning_effort": config.effort,
        "max_retries": PROVIDER_RETRIES,
        "max_tokens": MAX_OUTPUT_TOKENS,
    }
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    kwargs.update(config.extra)
    return kwargs


def build_chat_model(config: LabellerConfig) -> BaseChatModel:
    """``init_chat_model`` with the provider and model from ``config``.
    Provider-specific options are added by the one provider-configuration
    function for that provider; today there is only ``anthropic_kwargs``."""
    if config.provider != "anthropic":
        raise LabellerMisconfigured(
            f"unsupported labeller provider {config.provider!r}: only "
            "'anthropic' is supported; set CVR_LABEL_PROVIDER=anthropic"
        )
    return init_chat_model(
        model=config.model,
        model_provider=config.provider,
        **anthropic_kwargs(config),
    )


def _messages(blocks: Sequence[SourceBlock]) -> list[SystemMessage | HumanMessage]:
    """The prompt as the system message; the blocks as the human message,
    each with its id and raw text so a quote can be checked against it."""
    payload = [{"block_id": block.id, "text": block.text} for block in blocks]
    return [
        SystemMessage(content=PROMPT_TEXT),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
    ]


def _structured_model(chat_model: BaseChatModel) -> Runnable[Any, dict[str, Any]]:
    """``chat_model`` bound to the labelling schema through Claude's native
    structured-output feature, never a forced tool call. ``include_raw``
    keeps the raw message (for usage metadata) beside the parsed result (or
    the parsing error) even when parsing fails."""
    return chat_model.with_structured_output(
        Labelling, include_raw=True, method="json_schema"
    )


def anthropic_error(exc: Exception) -> LabellerError | None:
    """The labeller error an Anthropic client exception stands for, or
    ``None`` when it is not a provider failure at all (the caller then
    classifies it as a labelling failure). Isolated here so no other function knows Anthropic's error
    types. Raised only after the client's own retries are spent."""
    # The exception's message is left out on purpose: it can echo model text.
    detail = (
        f"{type(exc).__name__}, status {exc.status_code}"
        if isinstance(exc, anthropic.APIStatusError)
        else type(exc).__name__
    )
    if isinstance(
        exc,
        anthropic.CredentialsError
        | anthropic.AuthenticationError
        | anthropic.PermissionDeniedError
        | anthropic.NotFoundError
        | anthropic.BadRequestError
        | anthropic.UnprocessableEntityError,
    ):
        return LabellerMisconfigured(
            f"the labelling provider rejected the request as configured "
            f"({detail}); check ANTHROPIC_API_KEY and CVR_LABEL_MODEL. "
            "Retrying will not help."
        )
    if isinstance(exc, anthropic.APIConnectionError) or (
        isinstance(exc, anthropic.APIStatusError)
        and (exc.status_code in (408, 409, 429) or exc.status_code >= 500)
    ):
        return ProviderUnavailable(
            f"the labelling provider was unavailable after {PROVIDER_RETRIES} "
            f"retries ({detail}); try again later."
        )
    return None


def _provider_error(config: LabellerConfig, exc: Exception) -> LabellerError | None:
    if config.provider == "anthropic":
        return anthropic_error(exc)
    return None


def _field_names(schema: Any) -> set[str]:
    """Every property name anywhere in a JSON schema."""
    names: set[str] = set()
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
        for value in schema.values():
            names |= _field_names(value)
    elif isinstance(schema, list):
        for value in schema:
            names |= _field_names(value)
    return names


FAILURE_LOCATIONS: frozenset[str] = frozenset(
    _field_names(Labelling.model_json_schema())
)
"""The only non-integer segments a failure reason may name: the
``Labelling`` schema's own field names."""

_MAX_LOCATIONS = 10


def _safe_location(loc: tuple[Any, ...]) -> str | None:
    """``loc`` as a dotted path of allowlisted field names and integers; any
    other segment (a key the model invented, a union branch's class name) is
    dropped. ``None`` when nothing is left."""
    kept = [
        str(segment)
        for segment in loc
        if (isinstance(segment, int) and not isinstance(segment, bool))
        or segment in FAILURE_LOCATIONS
    ]
    return ".".join(kept) or None


def _causes(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def failure_reason(exc: BaseException) -> str | None:
    """A fixed-category reason for ``exc``, never any of its message. Walks
    the cause chain (LangChain's output parser wraps pydantic's and json's
    errors): a validation error is a schema mismatch with its allowlisted
    locations, a JSON decode error or a bare parser error is invalid JSON,
    anything else is ``None``: not a labelling failure."""
    chain = _causes(exc)
    for error in chain:
        if isinstance(error, ValidationError):
            locations = sorted(
                {
                    location
                    for item in error.errors(include_input=False, include_url=False)
                    if (location := _safe_location(tuple(item["loc"]))) is not None
                }
            )[:_MAX_LOCATIONS]
            if not locations:
                return "schema mismatch"
            return "schema mismatch at " + ", ".join(locations)
    if any(isinstance(e, json.JSONDecodeError | OutputParserException) for e in chain):
        return "invalid JSON"
    return None


def _unexpected(exc: BaseException) -> LabellerMisconfigured:
    """The fixed-message error for a defect: the exception's type name only."""
    return LabellerMisconfigured(
        f"unexpected {type(exc).__name__} while labelling; this is a defect, "
        "not a provider or CV problem (the exception's message is withheld "
        "because it may contain model text)"
    )


def label_blocks(
    blocks: Sequence[SourceBlock],
    structured_model: Runnable[Any, dict[str, Any]],
    config: LabellerConfig,
) -> tuple[LabellingResult, LabelRun]:
    """Invoke ``structured_model`` (a chat model already bound to the
    labelling schema with ``include_raw=True``) over ``blocks`` and turn its
    answer into a usable :class:`Labelling` or a
    :class:`~cvr.models.LabellingFailure` (malformed, schema-invalid,
    or refused, with whatever tokens and cost the answer reported).

    Raises :class:`ProviderUnavailable` or :class:`LabellerMisconfigured`
    when the request itself fails for one of those reasons, and
    :class:`LabellerMisconfigured` naming only the type for any other
    exception. See the module docstring: no message or cause of any
    exception is carried onward."""
    error: LabellerError | None = None
    try:
        response = structured_model.invoke(_messages(blocks))
    except Exception as exc:  # noqa: BLE001 - the boundary classifies everything
        error = _provider_error(config, exc)
        if error is None and failure_reason(exc) is None:
            error = _unexpected(exc)
        # A parser or validation error raised by the call is about the
        # model's output: handled below like one returned with the answer.
        response = {"raw": None, "parsed": None, "parsing_error": exc}
    if error is not None:
        # Raised outside the ``except`` block, so the SDK exception (whose
        # message can echo model text) is neither __cause__ nor __context__.
        raise error

    raw = response.get("raw")
    parsed = response.get("parsed")
    usage = getattr(raw, "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    stop_reason = (getattr(raw, "response_metadata", None) or {}).get("stop_reason")

    reason: str | None = None
    if stop_reason == "refusal":
        reason = "the model refused to answer"
    elif response.get("parsing_error") is not None:
        reason = failure_reason(response["parsing_error"])
        if reason is None:
            raise _unexpected(response["parsing_error"])
    elif not isinstance(parsed, Labelling):
        reason = "schema mismatch"
    label_failed = reason is not None

    result: LabellingResult = (
        LabellingFailure(reason=reason) if label_failed else parsed
    )
    run = LabelRun(
        config=config.as_dict(),
        prompt_version=PROMPT_VERSION,
        prompt_hash=PROMPT_HASH,
        schema_version=SCHEMA_VERSION,
        schema_hash=SCHEMA_HASH,
        content_hash=CONTENT_HASH,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=estimate_cost(config.model, input_tokens, output_tokens),
        label_failed=label_failed,
        failure_reason=reason if label_failed else None,
    )
    return result, run


def _answer_text(raw: Any) -> str | None:
    """The text of a raw model message (its text blocks only: thinking is
    not an answer), or ``None`` when there is none."""
    content = getattr(raw, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else str(part.get("text", ""))
            for part in content
            if isinstance(part, str)
            or (isinstance(part, dict) and part.get("type") == "text")
        )
    return None


class _Recording:
    """Wraps the structured model so the exchange is kept for the full-text
    trace without touching ``label_blocks``: ``invoke`` passes the messages and
    the response through unchanged and notes both."""

    def __init__(self, inner: Runnable[Any, dict[str, Any]]) -> None:
        self._inner = inner
        self.exchange: LabelExchange | None = None

    def invoke(self, messages: Any) -> dict[str, Any]:
        self.exchange = None
        response = self._inner.invoke(messages)
        self.exchange = LabelExchange(
            messages=[
                {"role": message.type, "content": str(message.content)}
                for message in messages
            ],
            answer=_answer_text(response.get("raw")),
        )
        return response


class RealLabeller:
    """A callable from blocks to a labelling result, matching the pipeline's
    labeller seam (``blocks -> labelling result``). Each call's full
    :class:`LabelRun` (tokens, cost, prompt and schema identity) is recorded
    on :attr:`last_run` immediately afterwards, for the pipeline (ticket 06)
    to put in its ``Run`` as the label section.
    """

    def __init__(
        self,
        config: LabellerConfig | None = None,
        *,
        chat_model: BaseChatModel | None = None,
    ) -> None:
        self.config = config or LabellerConfig.from_env()
        model = chat_model or build_chat_model(self.config)
        self._recording = _Recording(_structured_model(model))
        self.last_run: LabelRun | None = None
        # The last call's prompt messages and raw answer, candidate text
        # included, for the full-text trace only; never in the Run (ticket 09).
        self.last_exchange: LabelExchange | None = None

    def __call__(self, blocks: Sequence[SourceBlock]) -> LabellingResult:
        self.last_run = None
        self.last_exchange = None
        result, run = label_blocks(blocks, self._recording, self.config)
        self.last_run = run
        self.last_exchange = self._recording.exchange
        return result


LabellerFn = Callable[[Sequence[SourceBlock]], LabellingResult]
