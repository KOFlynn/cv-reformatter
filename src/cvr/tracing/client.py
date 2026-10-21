"""The Langfuse client, its guards, and the thin objects the pipeline uses.

The guards (ticket 07, spec "Tracing"):

* The client gets its **own** ``TracerProvider`` and never sets it as the
  global one, so an OpenTelemetry-instrumented library elsewhere in the
  process cannot reach our exporter, nor ours its.
* ``should_export_span`` passes only spans from the Langfuse SDK's own
  instrumentation scope **that we created** (they carry a marker in their
  metadata), so a stray decorated function that reaches the same client
  still does not export.
* ``mask`` is the second layer under the payload function's allowlist: any
  metadata key off the allowlist is dropped, and anything that is not a
  mapping (an input or an output; structure mode sets none) is redacted.
* The LangChain callback handler and the ``observe`` decorator are never
  used (ruff's banned-api rule enforces it).

With no keys, :meth:`Tracer.from_env` returns a disabled tracer whose every
method does nothing, so ``reformat`` behaves as it always did.
"""

import json
import logging
import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from types import TracebackType
from typing import Any

from langfuse import Langfuse, propagate_attributes
from langfuse._client.constants import LANGFUSE_TRACER_NAME
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter

from cvr.models import LabelRun
from cvr.tracing.payload import (
    ALLOWED_KEYS,
    generation_payload,
    node_payload,
    rejection_payload,
)

__all__ = [
    "MARKER_ATTRIBUTE",
    "REDACTED",
    "GenerationTrace",
    "NodeTrace",
    "RunTrace",
    "Tracer",
    "mask",
    "should_export",
]

logger = logging.getLogger(__name__)

ENV_PUBLIC_KEY = "LANGFUSE_PUBLIC_KEY"
ENV_SECRET_KEY = "LANGFUSE_SECRET_KEY"
ENV_BASE_URL = "LANGFUSE_BASE_URL"

REDACTED = "[redacted]"
_MARKER = {"source": "cvr"}
# How the SDK writes one metadata key onto a span: the value JSON-encoded.
MARKER_ATTRIBUTE = "langfuse.observation.metadata.source"
_MARKER_VALUE = json.dumps(_MARKER["source"])


def should_export(span: ReadableSpan) -> bool:
    """Export only spans the Langfuse SDK's own scope made for us: the scope
    is the SDK's, the marker is ours. The SDK also asks when a span starts,
    before our metadata is on it; that early question is answered on scope
    alone and only decides its app-root bookkeeping, since nothing exports
    until a span ends."""
    scope = span.instrumentation_scope
    if scope is None or scope.name != LANGFUSE_TRACER_NAME:
        return False
    if span.end_time is None:
        return True
    return (span.attributes or {}).get(MARKER_ATTRIBUTE) == _MARKER_VALUE


def mask(*, data: Any, **_: Any) -> Any:
    """The SDK's mask hook, called on every input, output and metadata value
    before it is written. A mapping keeps only allowlisted keys with scalar
    (or list-of-scalar) values; anything else is redacted."""
    if not isinstance(data, Mapping):
        return REDACTED
    return {
        key: value
        for key, value in data.items()
        if key in ALLOWED_KEYS and _scalar_or_scalars(value)
    }


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, bool | int | float | str)


def _scalar_or_scalars(value: Any) -> bool:
    if isinstance(value, list | tuple):
        return all(_scalar(item) for item in value)
    return _scalar(value)


def _guard(action: str) -> None:
    """Log (type name only: an SDK error may echo what it was given) and go on:
    tracing must never fail a Run."""
    logger.warning("tracing: %s failed", action)


class _Observation:
    """The shared part: one Langfuse observation, ended exactly once, errors
    recorded as the exception's type name only."""

    def __init__(self, observation: Any | None) -> None:
        self._observation = observation

    def _update(self, **fields: Any) -> None:
        if self._observation is None:
            return
        try:
            self._observation.update(**fields)
        except Exception:  # noqa: BLE001 - tracing never fails a Run
            _guard("update")

    def _end(self, error: BaseException | None) -> None:
        if self._observation is None:
            return
        try:
            if error is not None:
                self._observation.update(
                    level="ERROR", status_message=type(error).__name__
                )
            self._observation.end()
        except Exception:  # noqa: BLE001 - tracing never fails a Run
            _guard("end")

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._end(exc)


class GenerationTrace(_Observation):
    """One labelling attempt. It starts when it is entered and ends when it is
    left, so enter it immediately before the model call and leave it
    immediately after: its start and end are the measured times around the
    call."""

    def finish(self, label_run: LabelRun | None, *, attempt: int = 1) -> None:
        """Record what the attempt used, from the labeller's own ``LabelRun``."""
        self._update(**generation_payload(label_run, attempt=attempt))


class NodeTrace(_Observation):
    """One visit of one node."""

    def __init__(self, name: str, observation: Any | None) -> None:
        super().__init__(observation)
        self._name = name

    def finish(self, inputs: Mapping[str, Any], outputs: Mapping[str, Any]) -> None:
        """Record what the node did, through the payload function."""
        self._update(**node_payload(self._name, inputs, outputs))

    def generation(self) -> GenerationTrace:
        if self._observation is None:
            return GenerationTrace(None)
        try:
            return GenerationTrace(
                self._observation.start_observation(
                    name="labelling", as_type="generation", metadata=dict(_MARKER)
                )
            )
        except Exception:  # noqa: BLE001 - tracing never fails a Run
            _guard("start generation")
            return GenerationTrace(None)

    def rejection(self, rejection: Any) -> None:
        """An event under this span for one rejected reference."""
        if self._observation is None:
            return
        try:
            self._observation.create_event(
                name="rejection",
                metadata={**_MARKER, **rejection_payload(rejection)["metadata"]},
            )
        except Exception:  # noqa: BLE001 - tracing never fails a Run
            _guard("create event")


class RunTrace:
    """The trace of one Run: the root span plus its node spans."""

    def __init__(self, root: Any | None) -> None:
        self._root = root

    def node(self, name: str) -> NodeTrace:
        if self._root is None:
            return NodeTrace(name, None)
        try:
            observation = self._root.start_observation(
                name=name, metadata=dict(_MARKER)
            )
        except Exception:  # noqa: BLE001 - tracing never fails a Run
            _guard("start span")
            return NodeTrace(name, None)
        return NodeTrace(name, observation)


class Tracer:
    """What ``reformat(..., tracer=)`` takes. Disabled (``client`` None) it
    traces nothing."""

    def __init__(self, client: Langfuse | None = None, *, tags: Sequence[str] = ()):
        self._client = client
        self._tags = list(tags)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @classmethod
    def disabled(cls) -> "Tracer":
        return cls(None)

    @classmethod
    def create(
        cls,
        *,
        public_key: str,
        secret_key: str,
        base_url: str | None = None,
        span_exporter: SpanExporter | None = None,
        tags: Sequence[str] = (),
    ) -> "Tracer":
        """A tracer over a Langfuse client with its own tracer provider (never
        the global one), the export filter and the mask hook. ``span_exporter``
        replaces the network exporter (tests)."""
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
            tracer_provider=TracerProvider(),
            should_export_span=should_export,
            mask=mask,
            span_exporter=span_exporter,
        )
        return cls(client, tags=tags)

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None, *, tags: Sequence[str] = ()
    ) -> "Tracer":
        """From ``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY`` and
        optionally ``LANGFUSE_BASE_URL``. Without both keys: disabled, quietly."""
        source = os.environ if environ is None else environ
        public_key = source.get(ENV_PUBLIC_KEY, "")
        secret_key = source.get(ENV_SECRET_KEY, "")
        if not public_key or not secret_key:
            return cls.disabled()
        return cls.create(
            public_key=public_key,
            secret_key=secret_key,
            base_url=source.get(ENV_BASE_URL) or None,
            tags=tags,
        )

    @contextmanager
    def trace(self, run_id: str) -> Iterator[RunTrace]:
        """The trace of one Run, whose id is ``run_id`` (a ``uuid4().hex`` is
        a valid trace id)."""
        if self._client is None:
            yield RunTrace(None)
            return
        try:
            root_context = self._client.start_as_current_observation(
                name="reformat",
                trace_context={"trace_id": run_id},
                metadata={**_MARKER, "run_id": run_id},
            )
            root = root_context.__enter__()
        except Exception:  # noqa: BLE001 - tracing never fails a Run
            _guard("start trace")
            yield RunTrace(None)
            return
        error: BaseException | None = None
        try:
            with propagate_attributes(tags=self._tags or None):
                yield RunTrace(root)
        except BaseException as exc:
            error = exc
            raise
        finally:
            try:
                if error is not None:
                    root.update(level="ERROR", status_message=type(error).__name__)
                root_context.__exit__(None, None, None)
            except Exception:  # noqa: BLE001 - tracing never fails a Run
                _guard("end trace")

    def flush(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:  # noqa: BLE001 - tracing never fails a Run
                _guard("flush")
