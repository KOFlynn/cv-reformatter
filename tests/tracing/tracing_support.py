"""A real Langfuse client over an in-memory OpenTelemetry exporter, dummy
keys, no network. The SDK keeps one client per public key in the process, so
every tracer gets a key of its own."""

import time
from uuid import uuid4

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from oracle import Oracle
from pipeline_support import document

from cvr.models import LabelRun
from cvr.tracing import Tracer


def make_tracer() -> tuple[Tracer, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    tracer = Tracer.create(
        public_key=f"pk-lf-{uuid4().hex}",
        secret_key="sk-lf-dummy",
        base_url="http://127.0.0.1:1",
        span_exporter=exporter,
    )
    return tracer, exporter


def exported(tracer: Tracer, exporter: InMemorySpanExporter):
    tracer.flush()
    return list(exporter.get_finished_spans())


LABEL_RUN = LabelRun(
    config={"provider": "anthropic", "model": "claude-sonnet-5-5", "effort": "medium"},
    prompt_version="1.3.0",
    prompt_hash="p" * 8,
    schema_version="1.0.0",
    schema_hash="s" * 8,
    content_hash="c" * 8,
    input_tokens=1234,
    output_tokens=567,
    cost_usd=0.0081,
)


class RecordingOracle:
    """The oracle with a ``last_run`` like ``RealLabeller``'s, and a pause so
    the measured time around the call is visible."""

    def __init__(self, doc, pause: float = 0.02):
        self._oracle = Oracle(doc.candidate, doc.manifest)
        self._pause = pause
        self.last_run = None

    def __call__(self, blocks):
        self.last_run = None
        time.sleep(self._pause)
        result = self._oracle(blocks)
        self.last_run = LABEL_RUN
        return result


def doc(name: str = "c04__single-column"):
    return document(name)
