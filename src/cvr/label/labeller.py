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

Failures come in four kinds (``cvr.label.errors``). The model answered but
unusably (malformed, schema-invalid, refused): a
:class:`~cvr.models.LabellingFailure` value, and the job completes with
every block in the review appendix. The provider was unavailable after the
client's retries: :class:`ProviderUnavailable`. The provider rejected the
request as configured: :class:`LabellerMisconfigured`. Anything else is a
defect and propagates. Retrying a labelling failure is Phase 2.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

import anthropic
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

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
    Labelling,
    LabellingFailure,
    LabellingResult,
    LabelRun,
    SourceBlock,
)

__all__ = [
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


def anthropic_kwargs(config: LabellerConfig) -> dict[str, Any]:
    """Anthropic-specific request options, isolated here so no other
    function in this module knows Anthropic's field names. Adaptive
    thinking is enabled implicitly by setting ``reasoning_effort``; a
    temperature is included only when the caller set one, because Opus 5
    rejects an explicit temperature."""
    kwargs: dict[str, Any] = {
        "reasoning_effort": config.effort,
        "max_retries": PROVIDER_RETRIES,
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
    ``None`` when it is not a provider failure at all (a defect, left to
    propagate). Isolated here so no other function knows Anthropic's error
    types. Raised only after the client's own retries are spent."""
    detail = f"{type(exc).__name__}: {exc}"
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


def label_blocks(
    blocks: Sequence[SourceBlock],
    structured_model: Runnable[Any, dict[str, Any]],
    config: LabellerConfig,
) -> tuple[LabellingResult, LabelRun]:
    """Invoke ``structured_model`` (a chat model already bound to the
    labelling schema with ``include_raw=True``) over ``blocks`` and turn its
    answer into a usable :class:`Labelling` or a
    :class:`~cvr.models.LabellingFailure` (malformed, schema-invalid or
    refused, with whatever tokens and cost the answer reported).

    Raises :class:`ProviderUnavailable` or :class:`LabellerMisconfigured`
    when the request itself fails for one of those reasons; anything else
    raised is a defect and propagates unchanged."""
    try:
        response = structured_model.invoke(_messages(blocks))
    except Exception as exc:
        error = _provider_error(config, exc)
        if error is None:
            raise
        raise error from exc

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
        reason = str(response["parsing_error"])
    elif not isinstance(parsed, Labelling):
        reason = "response did not match the schema"
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
        self._structured_model = _structured_model(model)
        self.last_run: LabelRun | None = None

    def __call__(self, blocks: Sequence[SourceBlock]) -> LabellingResult:
        self.last_run = None
        result, run = label_blocks(blocks, self._structured_model, self.config)
        self.last_run = run
        return result


LabellerFn = Callable[[Sequence[SourceBlock]], LabellingResult]
