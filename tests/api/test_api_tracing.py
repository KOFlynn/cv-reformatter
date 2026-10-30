"""The API traces every ``/reformat`` Run: the response's ``X-Run-Id`` is the
exported trace id and is on every log line; the trace is tagged with the
environment (``CVR_TRACE_ENV``, read once when the app is created); spans are
flushed before the response is gone; with no Langfuse keys the API is
untraced and unchanged. In-memory exporter, dummy keys, the oracle: no
network, no model."""

import json
from uuid import uuid4

import pytest
from api_support import AUTH
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from oracle import Oracle
from pipeline_support import document

from cvr.api import DOCX_MEDIA_TYPE as DOCX
from cvr.api import RUN_ID_HEADER, create_app
from cvr.tracing import Tracer

STEM = "c04__single-column"


def _tracer(tags=()):
    exporter = InMemorySpanExporter()
    tracer = Tracer.create(
        public_key=f"pk-lf-{uuid4().hex}",
        secret_key="sk-lf-dummy",
        base_url="http://127.0.0.1:1",
        span_exporter=exporter,
        tags=tags,
    )
    return tracer, exporter


def _post(app, doc, headers=AUTH):
    return TestClient(app).post(
        "/reformat", files={"file": ("cv.docx", doc.source, DOCX)}, headers=headers
    )


def _app(tracer=None, **kwargs):
    doc = document(STEM)
    return create_app(Oracle(doc.candidate, doc.manifest), tracer=tracer, **kwargs), doc


def test_x_run_id_is_the_exported_trace_id_and_the_log_lines_carry_it(capsys):
    tracer, exporter = _tracer()
    app, doc = _app(tracer)
    capsys.readouterr()
    response = _post(app, doc)
    assert response.status_code == 200
    run_id = response.headers[RUN_ID_HEADER]
    # No explicit flush here: the API flushes before it answers.
    spans = list(exporter.get_finished_spans())
    assert spans
    assert {format(s.context.trace_id, "032x") for s in spans} == {run_id}
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines
    assert {line["run_id"] for line in lines} == {run_id}


def test_every_request_is_its_own_trace():
    tracer, exporter = _tracer()
    app, doc = _app(tracer)
    ids = {_post(app, doc).headers[RUN_ID_HEADER] for _ in range(2)}
    assert len(ids) == 2
    assert {
        format(s.context.trace_id, "032x") for s in exporter.get_finished_spans()
    } == ids


def test_a_refused_upload_starts_no_trace():
    tracer, exporter = _tracer()
    app, doc = _app(tracer)
    assert _post(app, doc, headers={}).status_code == 401
    assert list(exporter.get_finished_spans()) == []


def test_a_failing_run_is_still_flushed(monkeypatch):
    tracer, exporter = _tracer()

    def boom(blocks):
        raise RuntimeError("boom")

    doc = document(STEM)
    app = create_app(boom, tracer=tracer)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/reformat", files={"file": ("cv.docx", doc.source, DOCX)}, headers=AUTH
    )
    assert response.status_code == 500
    run_id = response.headers[RUN_ID_HEADER]
    spans = list(exporter.get_finished_spans())
    assert {format(s.context.trace_id, "032x") for s in spans} == {run_id}


def _env_app(monkeypatch, env: str | None):
    exporter = InMemorySpanExporter()
    created = {}
    real_create = Tracer.create.__func__

    def create(cls, **kwargs):
        created.update(kwargs)
        return real_create(cls, **{**kwargs, "span_exporter": exporter})

    monkeypatch.setattr(Tracer, "create", classmethod(create))
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", f"pk-lf-{uuid4().hex}")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-dummy")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://127.0.0.1:1")
    if env is None:
        monkeypatch.delenv("CVR_TRACE_ENV", raising=False)
    else:
        monkeypatch.setenv("CVR_TRACE_ENV", env)
    app, doc = _app()
    return app, doc, exporter, created


def _environments(exporter):
    spans = list(exporter.get_finished_spans())
    assert spans
    return {s.attributes["langfuse.environment"] for s in spans}


@pytest.mark.parametrize("env", ["prod", "eval", "local"])
def test_the_spans_carry_the_native_environment(monkeypatch, env):
    app, doc, exporter, _ = _env_app(monkeypatch, env)
    assert _post(app, doc).status_code == 200
    assert _environments(exporter) == {env}


@pytest.mark.parametrize("env", [None, "", "staging"])
def test_the_native_environment_defaults_to_local(monkeypatch, env):
    app, doc, exporter, _ = _env_app(monkeypatch, env)
    assert _post(app, doc).status_code == 200
    assert _environments(exporter) == {"local"}


def test_a_stray_langfuse_variable_does_not_override_cvr_trace_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "other")
    app, doc, exporter, _ = _env_app(monkeypatch, "prod")
    assert _post(app, doc).status_code == 200
    assert _environments(exporter) == {"prod"}


def _tags(exporter):
    (root,) = [s for s in exporter.get_finished_spans() if s.name == "reformat"]
    return list(root.attributes["langfuse.trace.tags"])


@pytest.mark.parametrize("env", ["prod", "eval", "local"])
def test_the_trace_is_tagged_with_the_environment(monkeypatch, env):
    app, doc, exporter, _ = _env_app(monkeypatch, env)
    assert _post(app, doc).status_code == 200
    assert _tags(exporter) == [f"env={env}"]


@pytest.mark.parametrize("env", [None, "", "staging"])
def test_the_environment_defaults_to_local(monkeypatch, env):
    app, doc, exporter, _ = _env_app(monkeypatch, env)
    assert _post(app, doc).status_code == 200
    assert _tags(exporter) == ["env=local"]


def test_the_environment_is_read_once_when_the_app_is_created(monkeypatch):
    app, doc, exporter, _ = _env_app(monkeypatch, "prod")
    monkeypatch.setenv("CVR_TRACE_ENV", "local")
    _post(app, doc)
    assert _tags(exporter) == ["env=prod"]


def test_without_keys_the_api_runs_untraced(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    built = []
    monkeypatch.setattr(
        Tracer, "create", classmethod(lambda cls, **kw: built.append(kw))
    )
    app, doc = _app()
    response = _post(app, doc)
    assert response.status_code == 200
    assert response.headers[RUN_ID_HEADER]
    assert built == []


def test_the_client_is_shut_down_when_the_app_stops():
    tracer, _ = _tracer()
    calls = []
    tracer.shutdown = lambda: calls.append("shutdown")
    app, _doc = _app(tracer)
    with TestClient(app):
        assert calls == []
    assert calls == ["shutdown"]


def test_full_mode_in_the_api_is_logged_as_a_warning(caplog):
    tracer, _ = _tracer()
    tracer.mode = "full"
    with caplog.at_level("WARNING", logger="cvr.api.app"):
        _app(tracer)
    assert any("full mode" in r.getMessage() for r in caplog.records)


def test_structure_mode_in_the_api_logs_no_warning(caplog):
    tracer, _ = _tracer()
    with caplog.at_level("WARNING", logger="cvr.api.app"):
        _app(tracer)
    assert not caplog.records
