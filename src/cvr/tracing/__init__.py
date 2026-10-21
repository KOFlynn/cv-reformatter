"""Traces of a Run (structure by default, full text only by setting) in Langfuse (Phase 2, ticket 07).

``Tracer`` is what ``cvr.pipeline.reformat(..., tracer=)`` takes; with no
Langfuse keys it is disabled and traces nothing. ``node_payload`` and its
siblings (``cvr.tracing.payload``) are the one place that decides which
fields a span carries; ``mask`` and ``should_export`` are the guards under
it. Depends on ``models`` and the Langfuse SDK only; ``pipeline`` may
depend on this package, the nodes never.
"""

from cvr.tracing.client import (
    DEFAULT_TRACE_ENV,
    ENV_TRACE_ENV,
    ENV_TRACE_MODE,
    REDACTED,
    TRACE_ENVS,
    GenerationTrace,
    NodeTrace,
    RunTrace,
    Tracer,
    UnknownTraceMode,
    env_tag,
    make_mask,
    mask,
    should_export,
    trace_env,
)
from cvr.tracing.payload import (
    ALLOWED_KEYS,
    FULL_KEYS,
    Mode,
    allowed_keys,
    allowlisted,
    generation_payload,
    node_payload,
    rejection_payload,
)

__all__ = [
    "ALLOWED_KEYS",
    "DEFAULT_TRACE_ENV",
    "ENV_TRACE_ENV",
    "ENV_TRACE_MODE",
    "FULL_KEYS",
    "REDACTED",
    "TRACE_ENVS",
    "GenerationTrace",
    "Mode",
    "NodeTrace",
    "RunTrace",
    "Tracer",
    "UnknownTraceMode",
    "allowed_keys",
    "allowlisted",
    "env_tag",
    "generation_payload",
    "make_mask",
    "mask",
    "node_payload",
    "rejection_payload",
    "should_export",
    "trace_env",
]
