"""The eval runner traces each document's Run: one trace per document tagged
``env=eval``, a cache hit marked cached with zero cost, and with no Langfuse
keys the runner is untraced and unchanged. In-memory exporter, dummy keys,
oracle labellers: no network, no model."""

import json
import time
from typing import ClassVar
from uuid import uuid4

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from run_support import ORACLE, oracle

from cvr.eval.run import main
from cvr.models import LabelExchange, LabelRun
from cvr.tracing import Tracer

LABEL_RUN = LabelRun(
    config={"provider": "anthropic", "model": "claude-sonnet-5-5"},
    prompt_version="1.3.0",
    prompt_hash="p" * 8,
    schema_version="1.0.0",
    schema_hash="s" * 8,
    content_hash="c" * 8,
    input_tokens=1000,
    output_tokens=500,
    cost_usd=0.0123,
)


class WithLabelRun:
    """The oracle with a ``LabelRun`` recorded on ``last_run``, as the real
    labeller does."""

    def __init__(self, inner):
        self._inner = inner
        self.last_run = None

    def __call__(self, blocks):
        self.last_run = None
        result = self._inner(blocks)
        self.last_run = LABEL_RUN
        return result


def live(document):
    return WithLabelRun(oracle(document))


def _tracer(tags=("env=eval",)):
    exporter = InMemorySpanExporter()
    tracer = Tracer.create(
        public_key=f"pk-lf-{uuid4().hex}",
        secret_key="sk-lf-dummy",
        base_url="http://127.0.0.1:1",
        span_exporter=exporter,
        tags=list(tags),
    )
    return tracer, exporter


def _main(tmp_path, tracer=None, *extra):
    return main(
        [
            "--candidate",
            "c04",
            "--out",
            str(tmp_path / "out"),
            "--cache-dir",
            str(tmp_path / "cache"),
            *extra,
        ],
        labeller=(live, ORACLE),
        tracer=tracer,
    )


def _meta(span, key):
    return json.loads(span.attributes["langfuse.observation.metadata." + key])


def _roots(exporter):
    return [s for s in exporter.get_finished_spans() if s.name == "reformat"]


def test_one_trace_per_document_tagged_env_eval(tmp_path):
    tracer, exporter = _tracer()
    assert _main(tmp_path, tracer) == 0
    spans = list(exporter.get_finished_spans())
    roots = _roots(exporter)
    assert len(roots) == 4  # c04 in each of the four Layouts
    trace_ids = {format(s.context.trace_id, "032x") for s in spans}
    assert len(trace_ids) == 4
    for root in roots:
        assert list(root.attributes["langfuse.trace.tags"]) == ["env=eval"]
        assert _meta(root, "run_id") == format(root.context.trace_id, "032x")


def test_a_live_generation_carries_the_cost_and_is_not_cached(tmp_path):
    tracer, exporter = _tracer()
    _main(tmp_path, tracer)
    gens = [
        s
        for s in exporter.get_finished_spans()
        if s.attributes["langfuse.observation.type"] == "generation"
    ]
    assert len(gens) == 4
    for gen in gens:
        assert json.loads(gen.attributes["langfuse.observation.cost_details"]) == {
            "total": LABEL_RUN.cost_usd
        }
        assert _meta(gen, "cached") is False


def test_a_cache_hit_is_traced_marked_cached_with_zero_cost(tmp_path):
    first, _ = _tracer()
    _main(tmp_path, first)
    tracer, exporter = _tracer()
    assert _main(tmp_path, tracer) == 0
    assert len(_roots(exporter)) == 4
    gens = [
        s
        for s in exporter.get_finished_spans()
        if s.attributes["langfuse.observation.type"] == "generation"
    ]
    assert len(gens) == 4
    for gen in gens:
        assert _meta(gen, "cached") is True
        assert json.loads(gen.attributes["langfuse.observation.cost_details"]) == {
            "total": 0.0
        }
        usage = json.loads(gen.attributes["langfuse.observation.usage_details"])
        assert usage == {"input": 0, "output": 0}


def test_the_runner_flushes_and_shuts_the_client_down(tmp_path):
    tracer, _ = _tracer()
    calls = []
    real_flush = tracer.flush
    tracer.flush = lambda: (calls.append("flush"), real_flush())
    tracer.shutdown = lambda: calls.append("shutdown")
    _main(tmp_path, tracer)
    assert calls[-2:] == ["flush", "shutdown"]


def test_without_keys_the_runner_is_untraced_and_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    built = []
    monkeypatch.setattr(
        Tracer, "create", classmethod(lambda cls, **kw: built.append(kw))
    )
    assert _main(tmp_path) == 0
    assert built == []
    assert (tmp_path / "out" / "report.json").exists()


def test_with_keys_the_runner_tags_eval_whatever_cvr_trace_env_says(
    tmp_path, monkeypatch
):
    created = {}
    exporter = InMemorySpanExporter()
    real_create = Tracer.create.__func__

    def create(cls, **kwargs):
        created.update(kwargs)
        return real_create(cls, **{**kwargs, "span_exporter": exporter})

    monkeypatch.setattr(Tracer, "create", classmethod(create))
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", f"pk-lf-{uuid4().hex}")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-dummy")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("CVR_TRACE_ENV", "prod")
    assert _main(tmp_path) == 0
    assert list(created["tags"]) == ["env=eval"]
    assert len(_roots(exporter)) == 4


class MarkedExchange(WithLabelRun):
    """Keeps a ``last_exchange`` naming the blocks it was called with, so a
    trace can be matched to the labelling that made it. A pause makes the
    four concurrent labellings overlap."""

    instances: ClassVar[list] = []

    def __init__(self, inner):
        super().__init__(inner)
        self.last_exchange = None
        MarkedExchange.instances.append(self)

    def __call__(self, blocks):
        self.last_exchange = None
        time.sleep(0.05)
        result = super().__call__(blocks)
        self.last_exchange = LabelExchange(
            messages=[{"role": "human", "content": blocks[0].text}],
            answer="answer for " + blocks[0].text,
        )
        return result


def _full_tracer():
    exporter = InMemorySpanExporter()
    tracer = Tracer.create(
        public_key=f"pk-lf-{uuid4().hex}",
        secret_key="sk-lf-dummy",
        base_url="http://127.0.0.1:1",
        span_exporter=exporter,
        tags=["env=eval"],
        mode="full",
    )
    return tracer, exporter


def test_concurrent_full_traces_each_carry_their_own_labellings_exchange(tmp_path):
    """The runner labels four documents at once; each labelling has its own
    labeller instance, so a trace's prompt and answer are never another
    document's (``last_run`` and ``last_exchange`` are per instance)."""
    MarkedExchange.instances = []
    tracer, exporter = _full_tracer()
    code = main(
        [
            "--candidate",
            "c04",
            "--out",
            str(tmp_path / "out"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
        labeller=(lambda d: MarkedExchange(oracle(d)), ORACLE),
        tracer=tracer,
    )
    assert code == 0
    assert len({id(i) for i in MarkedExchange.instances}) == 4
    gens = [
        s
        for s in exporter.get_finished_spans()
        if s.attributes["langfuse.observation.type"] == "generation"
    ]
    assert len(gens) == 4
    for gen in gens:
        sent = json.loads(gen.attributes["langfuse.observation.input"])
        got = json.loads(gen.attributes["langfuse.observation.output"])
        assert got["answer"] == "answer for " + sent["messages"][0]["content"]
