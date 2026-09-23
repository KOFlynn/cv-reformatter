"""``LabellerConfig``: provider, model, effort, optional temperature and any
other sampling knob, read from the environment and printed in every report.
Temperature is sent only when set, because Opus 5 rejects an explicit value;
``LabellerConfig.temperature`` is ``None`` unless the caller set it, and
nothing downstream ever invents a default for it.

Environment variables (all optional; unset means the spec's baseline):

======================  ===========================================
``CVR_LABEL_PROVIDER``  LangChain provider id (default ``anthropic``)
``CVR_LABEL_MODEL``     model name (default ``claude-opus-5``)
``CVR_LABEL_EFFORT``    reasoning effort: ``low | medium | high | xhigh | max``
                        (default ``medium``)
``CVR_LABEL_TEMPERATURE``  a float; unset or empty means "do not send
                        temperature at all"
``CVR_LABEL_EXTRA``     a JSON object of any other provider sampling kwarg
                        (for example ``{"top_p": 0.9}``)
======================  ===========================================
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DEFAULT_EFFORT",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "ENV_EFFORT",
    "ENV_EXTRA",
    "ENV_MODEL",
    "ENV_PROVIDER",
    "ENV_TEMPERATURE",
    "LabellerConfig",
]

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "medium"

ENV_PROVIDER = "CVR_LABEL_PROVIDER"
ENV_MODEL = "CVR_LABEL_MODEL"
ENV_EFFORT = "CVR_LABEL_EFFORT"
ENV_TEMPERATURE = "CVR_LABEL_TEMPERATURE"
ENV_EXTRA = "CVR_LABEL_EXTRA"


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
                float(temperature_raw)
                if temperature_raw not in (None, "")
                else None
            ),
            extra=json.loads(extra_raw) if extra_raw else {},
        )
