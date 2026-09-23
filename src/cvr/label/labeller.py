"""The real labeller: blocks in, a labelling result and a ``LabelRun`` out.
``init_chat_model`` with provider and model from ``LabellerConfig``, then
``with_structured_output(Labelling, method="json_schema")`` so Claude's
native structured-output feature is used instead of a forced tool call,
which would be incompatible with adaptive thinking. Anthropic-specific
options (adaptive-thinking effort, and temperature only when set) are
isolated in :func:`anthropic_kwargs`, the one provider-configuration
function; everything else in this module is provider-agnostic.

A malformed or schema-invalid answer, or any error raised while reaching
the provider, becomes a :class:`~cvr.models.LabellingFailure` value; this
module never raises out of :func:`label_blocks` or :meth:`RealLabeller.__call__`.
Retries are Phase 2.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from cvr.label.config import LabellerConfig
from cvr.label.pricing import estimate_cost
from cvr.label.versions import CONTENT_HASH, PROMPT_TEXT, PROMPT_VERSION, SCHEMA_VERSION
from cvr.models import Labelling, LabellingFailure, LabellingResult, SourceBlock

__all__ = [
    "LabelRun",
    "RealLabeller",
    "anthropic_kwargs",
    "build_chat_model",
    "label_blocks",
]


@dataclass(frozen=True, slots=True)
class LabelRun:
    """What the labeller itself knows about one request: the configuration
    used, the prompt and schema identity, tokens and cost, and whether the
    answer was usable. The pipeline's ``Run`` (ticket 06) folds this in
    alongside the ledger, removals and residue that only exist once the
    result has been verified."""

    config: LabellerConfig
    prompt_version: str
    schema_version: str
    content_hash: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    label_failed: bool
    failure_reason: str | None = None


def anthropic_kwargs(config: LabellerConfig) -> dict[str, Any]:
    """Anthropic-specific request options, isolated here so no other
    function in this module knows Anthropic's field names. Adaptive
    thinking is enabled implicitly by setting ``reasoning_effort``; a
    temperature is included only when the caller set one, because Opus 5
    rejects an explicit temperature."""
    kwargs: dict[str, Any] = {"reasoning_effort": config.effort}
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    kwargs.update(config.extra)
    return kwargs


def build_chat_model(config: LabellerConfig) -> BaseChatModel:
    """``init_chat_model`` with the provider and model from ``config``.
    Provider-specific options are added by the one provider-configuration
    function for that provider; today there is only ``anthropic_kwargs``."""
    if config.provider != "anthropic":
        raise ValueError(
            f"unsupported labeller provider {config.provider!r}: only "
            "'anthropic' has a provider-configuration function"
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


def label_blocks(
    blocks: Sequence[SourceBlock],
    structured_model: Runnable[Any, dict[str, Any]],
    config: LabellerConfig,
) -> tuple[LabellingResult, LabelRun]:
    """Invoke ``structured_model`` (a chat model already bound to the
    labelling schema with ``include_raw=True``) over ``blocks`` and turn its
    answer into a usable :class:`Labelling` or a
    :class:`~cvr.models.LabellingFailure`. Never raises: a malformed
    response, a schema mismatch, or a request that fails outright all
    become a labelling failure value, and the run's tokens and cost are
    whatever could be recovered (zero if the request itself failed)."""
    reason: str | None = None
    parsed: Any = None
    input_tokens = 0
    output_tokens = 0
    try:
        response = structured_model.invoke(_messages(blocks))
        raw = response.get("raw")
        error = response.get("parsing_error")
        parsed = response.get("parsed")
        usage = getattr(raw, "usage_metadata", None) or {}
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        if error is not None:
            reason = str(error)
    except Exception as exc:  # noqa: BLE001 - a provider failure is a labelling failure, never a crash
        reason = str(exc)

    label_failed = reason is not None or not isinstance(parsed, Labelling)
    if label_failed and reason is None:
        reason = "response did not match the schema"

    result: LabellingResult = (
        LabellingFailure(reason=reason) if label_failed else parsed
    )
    run = LabelRun(
        config=config,
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
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
    to fold into its ``Run``.
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
        result, run = label_blocks(blocks, self._structured_model, self.config)
        self.last_run = run
        return result


LabellerFn = Callable[[Sequence[SourceBlock]], LabellingResult]
