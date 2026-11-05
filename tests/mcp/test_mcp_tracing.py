"""Every ``reformat_cv`` call is traced like an API Run: the trace id is the
run id, the spans are the same, the tags say ``surface=mcp``, and nothing a
span carries is the path, the file name or CV text. A refused call starts no
trace. The server builds its own tracer from the environment (structure mode
only, shut down when it stops) when none is injected. In-memory exporter,
dummy keys, the oracle: no network, no model."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from mcp_support import call
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from oracle import Oracle
from pipeline_support import document

import cvr.mcp.server as mcp_server
from cvr.mcp import create_server
from cvr.pipeline import reformat
from cvr.tracing import Tracer

STEM = "c04__single-column"
MARKER = "ZXQMARKERPATH"


def make_tracer(mode="structure", tags=()):
    exporter = InMemorySpanExporter()
    tracer = Tracer.create(
        public_key=f"pk-lf-{uuid4().hex}",
        secret_key="sk-lf-dummy",
        base_url="http://127.0.0.1:1",
        span_exporter=exporter,
        tags=tags,
        mode=mode,
    )
    return tracer, exporter


@pytest.fixture
def doc():
    return document(STEM)


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


def _oracle(doc):
    return Oracle(doc.candidate, doc.manifest)


def _trace_ids(spans):
    return {format(s.context.trace_id, "032x") for s in spans}


def _everything(spans) -> str:
    """Every attribute of every span, as one string to search."""
    return json.dumps(
        [{"name": s.name, "attributes": dict(s.attributes or {})} for s in spans],
        default=str,
    )


def _tags(span) -> set[str]:
    return set((span.attributes or {}).get("langfuse.trace.tags") or ())


def test_one_trace_per_call_whose_id_is_the_run_id_with_the_tags(doc, workspace):
    tracer, exporter = make_tracer(tags=mcp_server.TRACE_TAGS)
    (workspace / "cv.docx").write_bytes(doc.source)
    server = create_server(_oracle(doc), tracer=tracer, workspace=workspace)

    first = call(server, path="cv.docx")
    second = call(server, path="cv.docx")

    ids = {
        first.structuredContent["run_id"],
        second.structuredContent["run_id"],
    }
    assert len(ids) == 2
    spans = list(exporter.get_finished_spans())  # flushed by the call itself
    assert _trace_ids(spans) == ids
    assert any({"env=local", "surface=mcp"} <= _tags(s) for s in spans)


def test_the_trace_has_the_shape_of_an_api_run(doc, workspace):
    mcp_tracer, mcp_exporter = make_tracer()
    (workspace / "cv.docx").write_bytes(doc.source)
    call(
        create_server(_oracle(doc), tracer=mcp_tracer, workspace=workspace),
        path="cv.docx",
    )
    direct_tracer, direct_exporter = make_tracer()
    reformat(doc.source, _oracle(doc), tracer=direct_tracer)
    direct_tracer.flush()

    def shape(exporter):
        return sorted(s.name for s in exporter.get_finished_spans())

    assert shape(mcp_exporter) == shape(direct_exporter)
    assert len(shape(mcp_exporter)) > 5


def test_no_span_carries_the_path_the_file_name_or_cv_text(doc, workspace):
    tracer, exporter = make_tracer(tags=mcp_server.TRACE_TAGS)
    folder = workspace / f"{MARKER}-dir"
    folder.mkdir()
    (folder / f"{MARKER}-cv.docx").write_bytes(doc.source)
    call(
        create_server(_oracle(doc), tracer=tracer, workspace=workspace),
        path=f"{MARKER}-dir/{MARKER}-cv.docx",
    )
    everything = _everything(exporter.get_finished_spans())
    assert everything != "[]"
    assert MARKER not in everything
    assert str(workspace) not in everything
    assert doc.candidate.content.name.split()[0] not in everything


@pytest.mark.parametrize(
    "path",
    [f"{MARKER}/missing.docx", f"../{MARKER}.docx", f"{MARKER}.txt", "."],
)
def test_a_refused_call_starts_no_trace(path, doc, workspace):
    tracer, exporter = make_tracer()
    (workspace / f"{MARKER}.txt").write_text("x")
    result = call(
        create_server(_oracle(doc), tracer=tracer, workspace=workspace), path=path
    )
    assert result.isError
    assert list(exporter.get_finished_spans()) == []


def test_a_name_already_taken_is_traced_without_the_path(doc, workspace, monkeypatch):
    run_id = "ab" * 16
    monkeypatch.setattr(mcp_server, "uuid4", lambda: type("U", (), {"hex": run_id}))
    tracer, exporter = make_tracer(tags=mcp_server.TRACE_TAGS)
    (workspace / f"{MARKER}.docx").write_bytes(doc.source)
    (workspace / f"{MARKER}-reformatted-{run_id[:8]}.docx").write_bytes(b"earlier")

    result = call(
        create_server(_oracle(doc), tracer=tracer, workspace=workspace),
        path=f"{MARKER}.docx",
    )

    assert result.isError
    spans = list(exporter.get_finished_spans())
    assert _trace_ids(spans) == {run_id}
    assert MARKER not in _everything(spans)


# --- the tracer the server builds


class _Spy:
    """Stands in for ``Tracer.from_env``: records how it was called and hands
    back a test tracer that records its shutdown."""

    def __init__(self, monkeypatch):
        self.kwargs = None
        self.shutdowns = 0
        self.tracer, self.exporter = make_tracer(tags=mcp_server.TRACE_TAGS)
        original = self.tracer.shutdown

        def shutdown():
            self.shutdowns += 1
            original()

        self.tracer.shutdown = shutdown
        spy = self

        def from_env(environ=None, **kwargs):
            spy.kwargs = kwargs
            return spy.tracer

        monkeypatch.setattr(Tracer, "from_env", staticmethod(from_env))


def test_without_a_tracer_the_server_builds_env_local_surface_mcp(
    doc, workspace, monkeypatch
):
    spy = _Spy(monkeypatch)
    (workspace / "cv.docx").write_bytes(doc.source)
    server = create_server(_oracle(doc), workspace=workspace)

    result = call(server, path="cv.docx")

    assert spy.kwargs == {
        "tags": ("env=local", "surface=mcp"),
        "environment": "local",
        "mode": "structure",
    }
    assert _trace_ids(spy.exporter.get_finished_spans()) == {
        result.structuredContent["run_id"]
    }


def test_the_server_shuts_down_its_own_tracer_but_not_an_injected_one(
    doc, workspace, monkeypatch
):
    spy = _Spy(monkeypatch)
    (workspace / "cv.docx").write_bytes(doc.source)
    call(create_server(_oracle(doc), workspace=workspace), path="cv.docx")
    assert spy.shutdowns == 1

    injected, _ = make_tracer()
    shutdowns = []
    injected.shutdown = lambda: shutdowns.append(1)
    call(
        create_server(_oracle(doc), tracer=injected, workspace=workspace),
        path="cv.docx",
    )
    assert shutdowns == []


def test_without_keys_the_server_is_untraced_and_silent(
    doc, workspace, monkeypatch, capsys
):
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "CVR_TRACE_MODE"):
        monkeypatch.delenv(name, raising=False)
    (workspace / "cv.docx").write_bytes(doc.source)
    capsys.readouterr()
    call(create_server(_oracle(doc), workspace=workspace), path="cv.docx")
    err = capsys.readouterr().err
    assert all(line.startswith("{") for line in err.splitlines() if line.strip())


def test_full_mode_is_ignored_with_a_warning_and_traces_structure_only(
    doc, workspace, monkeypatch, caplog
):
    monkeypatch.setenv("CVR_TRACE_MODE", "full")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-mcp-full-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-dummy")
    built = {}
    real_create = Tracer.create.__func__

    def create(cls, **kwargs):
        exporter = InMemorySpanExporter()
        built.update(mode=kwargs["mode"], environment=kwargs["environment"])
        built["exporter"] = exporter
        return real_create(
            cls,
            **{**kwargs, "span_exporter": exporter, "base_url": "http://127.0.0.1:1"},
        )

    monkeypatch.setattr(Tracer, "create", classmethod(create))
    (workspace / "cv.docx").write_bytes(doc.source)
    with caplog.at_level("WARNING", logger="cvr.mcp.server"):
        server = create_server(_oracle(doc), workspace=workspace)
    assert any("CVR_TRACE_MODE=full" in r.getMessage() for r in caplog.records)
    assert built["mode"] == "structure"
    assert built["environment"] == "local"

    call(server, path="cv.docx")
    assert doc.candidate.content.name.split()[0] not in _everything(
        built["exporter"].get_finished_spans()
    )


def test_an_unknown_trace_mode_stops_the_server_at_start_up(
    doc, workspace, monkeypatch
):
    monkeypatch.setenv("CVR_TRACE_MODE", "nope")
    with pytest.raises(ValueError, match="CVR_TRACE_MODE"):
        create_server(_oracle(doc), workspace=workspace)


# --- the process


@pytest.mark.slow
def test_the_process_warns_on_stderr_when_full_mode_is_set(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CVR_", "ANTHROPIC_", "LANGFUSE_", "AZURE_"))
    }
    env.update(
        CVR_MCP_ROOT=str(tmp_path),
        CVR_TRACE_MODE="full",
        LANGFUSE_PUBLIC_KEY="pk-lf-process-test",
        LANGFUSE_SECRET_KEY="sk-lf-dummy",
        LANGFUSE_BASE_URL="http://127.0.0.1:1",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "cvr.mcp"],
        input="",
        capture_output=True,
        text=True,
        cwd=repo,
        env=env,
        timeout=90,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert proc.stdout == ""
    assert "CVR_TRACE_MODE=full" in proc.stderr
