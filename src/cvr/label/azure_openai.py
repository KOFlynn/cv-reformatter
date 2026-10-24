"""The Azure OpenAI provider's configuration and error classes (ticket 17),
isolated here as ``anthropic_kwargs`` and ``anthropic_error`` are isolated in
``cvr.label.labeller``, so nothing else in the package knows Azure's argument
names or its exception types.

No key path exists. The chat model is given ``azure_ad_token_provider``, built
from the default Azure credential (a managed identity in Container Apps, the
developer's sign-in locally) with the scope ticket 01 found, and the key
arguments are passed as an explicit ``None`` so that ``AzureChatOpenAI`` does
not fall back to ``AZURE_OPENAI_API_KEY`` or ``OPENAI_API_KEY`` in the
environment. A configuration that carries a key or a token of its own, or an argument that
could redirect the token (``base_url``, ``openai_api_base``, ``azure_endpoint``,
``default_headers``), through ``CVR_LABEL_EXTRA`` is refused as
``LabellerMisconfigured``. The credential excludes the environment credential,
so a client secret in the environment is not a way in.
"""

from __future__ import annotations

from typing import Any

import openai
from azure.core import exceptions as azure_exceptions
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from cvr.label.config import (
    DEFAULT_AZURE_API_VERSION,
    DEFAULT_AZURE_SCOPE,
    ENV_AZURE_ENDPOINT,
    LabellerConfig,
)
from cvr.label.errors import LabellerError, LabellerMisconfigured, ProviderUnavailable

__all__ = [
    "AZURE_EFFORTS",
    "AZURE_PROVIDER",
    "azure_error",
    "azure_failure_reason",
    "azure_kwargs",
]

AZURE_PROVIDER = "azure_openai"

# gpt-5.4's accepted reasoning_effort values on Chat Completions, a subset of
# the labeller's own vocabulary: Azure's reasoning guide (checked 2026-10-24)
# lists ``max`` for GPT-6 and GPT-5.6 on the Responses API only, and ``none``
# is not an effort the labeller offers.
AZURE_EFFORTS = ("low", "medium", "high", "xhigh")


def _is_credential_argument(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    return "api_key" in lowered or lowered.startswith(
        ("azure_ad_token", "azure_ad_async_token")
    )


_REDIRECTIONS = frozenset(
    {"base_url", "openai_api_base", "azure_endpoint", "default_headers"}
)


def _is_redirection(name: str) -> bool:
    """An argument that would send the token to another host or add headers
    of the caller's own."""
    return name.lower().replace("-", "_") in _REDIRECTIONS


def azure_kwargs(
    config: LabellerConfig, *, max_retries: int, max_tokens: int
) -> dict[str, Any]:
    """Arguments for ``init_chat_model(..., model_provider="azure_openai")``.

    ``azure_endpoint`` is required. The deployment defaults to the model name.
    Raises :class:`LabellerMisconfigured` for a missing endpoint, an effort
    Azure does not accept, or any credential argument in ``config.extra``.
    """
    if not config.azure_endpoint:
        raise LabellerMisconfigured(
            f"the azure_openai labeller provider needs {ENV_AZURE_ENDPOINT} "
            "(the resource endpoint)"
        )
    if config.effort not in AZURE_EFFORTS:
        raise LabellerMisconfigured(
            f"effort {config.effort!r} is not accepted by the azure_openai "
            f"provider: use one of {', '.join(AZURE_EFFORTS)}"
        )
    refused = sorted(name for name in config.extra if _is_credential_argument(name))
    if refused:
        raise LabellerMisconfigured(
            "the azure_openai labeller provider is keyless (managed identity): "
            f"CVR_LABEL_EXTRA must not carry {', '.join(refused)}"
        )
    redirected = sorted(name for name in config.extra if _is_redirection(name))
    if redirected:
        raise LabellerMisconfigured(
            "the azure_openai labeller provider sends a bearer token, so "
            "CVR_LABEL_EXTRA must not redirect it: it must not carry "
            f"{', '.join(redirected)}"
        )

    token_provider = get_bearer_token_provider(
        # No environment credential: an AZURE_CLIENT_SECRET (or certificate)
        # in the environment must not become a way to authenticate. The chain
        # is the managed identity in Container Apps and the developer's
        # sign-in (CLI, VS Code, PowerShell) locally.
        DefaultAzureCredential(exclude_environment_credential=True),
        config.azure_scope or DEFAULT_AZURE_SCOPE,
    )
    kwargs: dict[str, Any] = {
        "azure_endpoint": config.azure_endpoint,
        "azure_deployment": config.azure_deployment or config.model,
        "api_version": config.azure_api_version or DEFAULT_AZURE_API_VERSION,
        "azure_ad_token_provider": token_provider,
        # Explicit None: without it AzureChatOpenAI reads AZURE_OPENAI_API_KEY,
        # OPENAI_API_KEY and AZURE_OPENAI_AD_TOKEN from the environment.
        "api_key": None,
        "azure_ad_token": None,
        "reasoning_effort": config.effort,
        "max_retries": max_retries,
        # Reasoning models take max_completion_tokens, not max_tokens.
        "max_completion_tokens": max_tokens,
    }
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    kwargs.update(config.extra)
    return kwargs


def azure_failure_reason(chain: list[BaseException]) -> str | None:
    """The labelling-failure reason for an exception chain that is the model's
    answer failing, not the provider or the configuration: the OpenAI client
    raises ``LengthFinishReasonError`` when the answer hit the token limit
    (truncated JSON, so ``invalid JSON`` as for Anthropic's ``max_tokens``) and
    ``ContentFilterFinishReasonError`` when Azure's content filter stopped it
    (``the model refused to answer``, as for a refusal). Fixed categories; no
    message is carried."""
    if any(isinstance(e, openai.ContentFilterFinishReasonError) for e in chain):
        return "the model refused to answer"
    if any(isinstance(e, openai.LengthFinishReasonError) for e in chain):
        return "invalid JSON"
    return None


def azure_error(exc: Exception, retries: int) -> LabellerError | None:
    """The labeller error an OpenAI-client or Azure-credential exception
    stands for, or ``None`` when it is not a provider failure at all. As for
    Anthropic, the message is withheld: it can echo model text."""
    detail = (
        f"{type(exc).__name__}, status {exc.status_code}"
        if isinstance(exc, openai.APIStatusError)
        else type(exc).__name__
    )
    if isinstance(
        exc,
        openai.AuthenticationError
        | openai.PermissionDeniedError
        | openai.NotFoundError
        | openai.BadRequestError
        | openai.UnprocessableEntityError
        | azure_exceptions.ClientAuthenticationError,
    ):
        return LabellerMisconfigured(
            f"the labelling provider rejected the request as configured "
            f"({detail}); check the CVR_LABEL_AZURE_* settings, the model "
            "deployment and the identity's Cognitive Services OpenAI User "
            "role. Retrying will not help."
        )
    if isinstance(
        exc, openai.APIConnectionError | azure_exceptions.ServiceRequestError
    ) or (
        isinstance(exc, openai.APIStatusError)
        and (exc.status_code in (408, 409, 429) or exc.status_code >= 500)
    ):
        return ProviderUnavailable(
            f"the labelling provider was unavailable after {retries} "
            f"retries ({detail}); try again later."
        )
    return None
