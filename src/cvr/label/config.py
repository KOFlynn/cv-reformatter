"""``LabellerConfig``: provider, model, effort, optional temperature and any
other sampling knob, read from the environment and printed in every report.
Temperature is sent only when set, because Opus 5 rejected an explicit value;
``LabellerConfig.temperature`` is ``None`` unless the caller set it, and
nothing downstream ever invents a default for it.

Environment variables (all optional; unset means the default, ADR-0011):

======================  ===========================================
``CVR_LABEL_PROVIDER``  LangChain provider id (default ``anthropic``)
``CVR_LABEL_MODEL``     model name (default ``claude-sonnet-5-5``)
``CVR_LABEL_EFFORT``    reasoning effort: ``low | medium | high | xhigh | max``
                        (default ``medium``)
``CVR_LABEL_TEMPERATURE``  a float; unset or empty means "do not send
                        temperature at all"
``CVR_LABEL_EXTRA``     a JSON object of any other provider sampling kwarg
                        (for example ``{"top_p": 0.9}``)
======================  ===========================================

Azure OpenAI (``CVR_LABEL_PROVIDER=azure_openai``, ticket 17) also reads:

===============================  =========================================
``CVR_LABEL_AZURE_ENDPOINT``     the resource endpoint (required), for
                                 example ``https://<name>.openai.azure.com/``
``CVR_LABEL_AZURE_DEPLOYMENT``   the deployment name (default: the model
                                 name)
``CVR_LABEL_AZURE_API_VERSION``  the data-plane API version (default
                                 ``DEFAULT_AZURE_API_VERSION``)
``CVR_LABEL_AZURE_SCOPE``        the token scope (default
                                 ``https://ai.azure.com/.default``)
===============================  =========================================

There is no key variable: the service authenticates with the default Azure
credential (a managed identity in Container Apps), and a configuration that
carries an API key for Azure is refused.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AZURE_MODEL",
    "DEFAULT_AZURE_API_VERSION",
    "DEFAULT_AZURE_SCOPE",
    "DEFAULT_EFFORT",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "ENV_AZURE_API_VERSION",
    "ENV_AZURE_DEPLOYMENT",
    "ENV_AZURE_ENDPOINT",
    "ENV_AZURE_SCOPE",
    "ENV_EFFORT",
    "ENV_EXTRA",
    "ENV_MODEL",
    "ENV_PROVIDER",
    "ENV_TEMPERATURE",
    "KNOWN_MODELS",
    "LabellerConfig",
]

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"
# The Azure OpenAI model (ticket 01: ``gpt-5.4`` version 2026-03-05). Not a
# default: it is chosen with CVR_LABEL_PROVIDER=azure_openai.
AZURE_MODEL = "gpt-5.4"
# What the subscription can deploy today (2026-10-24): `cvr_sub` has no default
# gpt-5.4 quota, and the Data Zone Standard chat model it has is gpt-5.4-mini
# (version 2026-03-17), so that is the Azure model compared with Sonnet.
AZURE_MINI_MODEL = "gpt-5.4-mini"
# Its DataZoneStandard quota request (swedencentral, version 2026-07-09) was refused
# on 2026-10-29 for region capacity; it stays accepted and priced in case quota
# appears later, so a run on it would cost what it says.
AZURE_TERRA_MODEL = "gpt-5.6-terra"
# Every model the project has configured or compared; each must have a price.
KNOWN_MODELS = (
    DEFAULT_MODEL,
    "claude-opus-5-5",
    "claude-haiku-5-5",
    AZURE_MODEL,
    AZURE_MINI_MODEL,
    AZURE_TERRA_MODEL,
)

# The token scope Microsoft's current managed-identity guide uses (ticket 01);
# the older ``https://cognitiveservices.azure.com/.default`` is the fallback if
# the live proof returns 401. The API version is a dated preview that carries
# ``reasoning_effort``, ``max_completion_tokens`` and strict structured outputs.
DEFAULT_AZURE_SCOPE = "https://ai.azure.com/.default"
DEFAULT_AZURE_API_VERSION = "2025-04-01-preview"

ENV_PROVIDER = "CVR_LABEL_PROVIDER"
ENV_MODEL = "CVR_LABEL_MODEL"
ENV_EFFORT = "CVR_LABEL_EFFORT"
ENV_TEMPERATURE = "CVR_LABEL_TEMPERATURE"
ENV_EXTRA = "CVR_LABEL_EXTRA"
ENV_AZURE_ENDPOINT = "CVR_LABEL_AZURE_ENDPOINT"
ENV_AZURE_DEPLOYMENT = "CVR_LABEL_AZURE_DEPLOYMENT"
ENV_AZURE_API_VERSION = "CVR_LABEL_AZURE_API_VERSION"
ENV_AZURE_SCOPE = "CVR_LABEL_AZURE_SCOPE"


@dataclass(frozen=True, slots=True)
class LabellerConfig:
    """One configuration object for the labeller. A change to any field
    counts as a model change under the eval-run rule, so every field is
    printed into the report through the ``Run`` it rides on."""

    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    temperature: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)
    # Azure OpenAI only; ``None`` elsewhere and then absent from ``as_dict``,
    # so an Anthropic configuration (and its eval cache keys) is unchanged.
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    azure_api_version: str | None = None
    azure_scope: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Every field as plain values, for the Run's label section. The
        Azure endpoint is left out on purpose: it names the resource, and
        this dict ends up in reports and traces."""
        azure = {
            "azure_deployment": self.azure_deployment,
            "azure_api_version": self.azure_api_version,
            "azure_scope": self.azure_scope,
        }
        return {
            "provider": self.provider,
            "model": self.model,
            "effort": self.effort,
            "temperature": self.temperature,
            "extra": dict(self.extra),
            **{key: value for key, value in azure.items() if value is not None},
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LabellerConfig:
        """Read every field from its documented environment variable, or the
        spec's default when unset."""
        source: Mapping[str, str] = os.environ if env is None else env
        temperature_raw = source.get(ENV_TEMPERATURE)
        extra_raw = source.get(ENV_EXTRA)
        return cls(
            provider=source.get(ENV_PROVIDER, DEFAULT_PROVIDER),
            model=source.get(ENV_MODEL, DEFAULT_MODEL),
            effort=source.get(ENV_EFFORT, DEFAULT_EFFORT),
            temperature=(
                float(temperature_raw) if temperature_raw not in (None, "") else None
            ),
            extra=json.loads(extra_raw) if extra_raw else {},
            azure_endpoint=source.get(ENV_AZURE_ENDPOINT) or None,
            azure_deployment=source.get(ENV_AZURE_DEPLOYMENT) or None,
            azure_api_version=source.get(ENV_AZURE_API_VERSION) or None,
            azure_scope=source.get(ENV_AZURE_SCOPE) or None,
        )
