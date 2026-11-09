"""The MCP server through the SDK's in-memory client session, with the oracle
labeller and a temporary Workspace injected: one ``reformat_cv`` call writes
the reformatted document next to its source under a name holding the run id,
and returns a Tool result whose fields agree with the Run and carry no
candidate text; the tool as a client lists it; a path outside the Workspace
refused; the real labeller built once and only when a document needs it;
calls one at a time; each Run logged to standard error without its path."""

import json
import threading
import time
import zipfile

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp_support import call, list_tools, log_lines, summaries
from oracle import Imperfect, Oracle, omit_first_bullet
from pipeline_support import document

import cvr.mcp.server as mcp_server
from cvr.eval.adapter import adapt
from cvr.mcp import ENV_WORKSPACE, TOOL_NAME, WorkspaceMissing, create_server
from cvr.models import LabelRun
from cvr.runlog import request_lines

STEM = "c04__single-column"


class Paid(Oracle):
    """The oracle with a labelling record, as ``RealLabeller`` keeps one."""

    last_run = LabelRun(
        config={"model": "oracle"},
        prompt_version="p",
        prompt_hash="ph",
        schema_version="s",
        schema_hash="sh",
        content_hash="ch",
        input_tokens=1200,
        output_tokens=340,
        cost_usd=0.0125,
    )


@pytest.fixture
def doc():
    return document(STEM)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    return root


@pytest.fixture
def runs(monkeypatch):
    """Every Run the server's ``reformat`` returns, in call order."""
    recorded = []
    reformat = mcp_server.reformat

    def recording(*args, **kwargs):
        output, run = reformat(*args, **kwargs)
        recorded.append(run)
        return output, run

    monkeypatch.setattr(mcp_server, "reformat", recording)
    return recorded


def _source(workspace, doc, name="cv.docx"):
    path = workspace / name
    path.write_bytes(doc.source)
    return path


def _server(doc, workspace, labeller=None):
    return create_server(
        labeller or Oracle(doc.candidate, doc.manifest), workspace=workspace
    )


def _text(result) -> str:
    return "\n".join(block.text for block in result.content)


# --- Success


def test_the_output_is_written_next_to_the_source_named_with_the_run_id(
    doc, workspace, runs
):
    source = _source(workspace, doc)
    result = call(_server(doc, workspace), path=str(source))

    assert not result.isError
    (run,) = runs
    output = workspace / f"cv-reformatted-{run.run_id[:8]}.docx"
    assert result.structuredContent["output_path"] == str(output)
    assert result.structuredContent["run_id"] == run.run_id
    assert zipfile.is_zipfile(output)
    # Our template's document: the adapter reads the candidate's name back.
    assert adapt(output.read_bytes()).content.name == doc.candidate.content.name
    assert source.read_bytes() == doc.source
    assert sorted(p.name for p in workspace.iterdir()) == sorted(
        ["cv.docx", output.name]
    )


def test_a_relative_path_is_taken_from_the_workspace(doc, workspace, runs):
    (workspace / "cvs").mkdir()
    _source(workspace, doc, "cvs/cv.docx")
    result = call(_server(doc, workspace), path="cvs/cv.docx")

    assert not result.isError
    (run,) = runs
    assert result.structuredContent["output_path"] == str(
        workspace / "cvs" / f"cv-reformatted-{run.run_id[:8]}.docx"
    )


def test_a_docx_suffix_in_any_case_is_dropped_from_the_output_name(
    doc, workspace, runs
):
    _source(workspace, doc, "CV.DOCX")
    result = call(_server(doc, workspace), path="CV.DOCX")
    (run,) = runs
    assert result.structuredContent["output_path"].endswith(
        f"CV-reformatted-{run.run_id[:8]}.docx"
    )


def test_every_call_has_its_own_run_and_output(doc, workspace, runs):
    server = _server(doc, workspace)
    _source(workspace, doc)
    first = call(server, path="cv.docx").structuredContent
    second = call(server, path="cv.docx").structuredContent
    assert first["run_id"] != second["run_id"]
    assert first["output_path"] != second["output_path"]


def test_the_tool_result_agrees_with_the_run(doc, workspace, runs):
    _source(workspace, doc)
    result = call(_server(doc, workspace), path="cv.docx").structuredContent
    (run,) = runs

    counts: dict[str, int] = {}
    for removal in run.removals:
        counts[removal.rule.value] = counts.get(removal.rule.value, 0) + 1
    assert counts  # c04 has PII to remove
    assert result["status"] == "ok"
    assert result["retries"] == len(run.retries) == 0
    assert result["removals"] == counts
    assert result["unplaced"] == {"spans": 0, "characters": 0}
    assert result["appendix"] is None


def test_unplaced_text_is_counted_and_the_appendix_named(doc, workspace, runs):
    _source(workspace, doc)
    labeller = Imperfect(Oracle(doc.candidate, doc.manifest), omit_first_bullet)
    result = call(_server(doc, workspace, labeller), path="cv.docx")
    (run,) = runs

    assert run.unplaced
    assert result.structuredContent["unplaced"] == {
        "spans": len(run.unplaced),
        "characters": sum(span.end - span.start for span in run.unplaced),
    }
    assert "appendix" in result.structuredContent["appendix"]
    # The sentence is fixed: it names no unplaced text.
    assert all(
        span.text not in result.structuredContent["appendix"] for span in run.unplaced
    )


def test_tokens_and_cost_are_summed_over_every_attempt(doc, workspace, runs):
    _source(workspace, doc)
    result = call(
        _server(doc, workspace, Paid(doc.candidate, doc.manifest)), path="cv.docx"
    ).structuredContent
    (run,) = runs
    assert result["input_tokens"] == sum(r.input_tokens for r in run.label_runs)
    assert result["output_tokens"] == sum(r.output_tokens for r in run.label_runs)
    assert result["cost_usd"] == pytest.approx(sum(r.cost_usd for r in run.label_runs))
    assert (result["input_tokens"], result["output_tokens"]) == (1200, 340)


def test_the_text_rendering_states_the_same_fields(doc, workspace, runs):
    _source(workspace, doc)
    result = call(_server(doc, workspace), path="cv.docx")
    text = _text(result)
    fields = result.structuredContent
    assert fields["output_path"] in text
    assert fields["run_id"] in text
    for rule, count in fields["removals"].items():
        assert f"{rule}: {count}" in text


def test_no_candidate_text_reaches_the_tool_result(doc, workspace, runs):
    _source(workspace, doc)
    result = call(_server(doc, workspace), path="cv.docx")
    (run,) = runs
    said = json.dumps(result.structuredContent) + _text(result)
    content = doc.candidate.content
    texts = [content.name, *content.profile, *content.skills]
    texts += [bullet for entry in content.experience for bullet in entry.bullets]
    texts += [r.subject.text for r in run.removals if hasattr(r.subject, "text")]
    assert texts
    leaked = [t for t in texts if len(t) >= 4 and t in said]
    assert leaked == []


# --- The tool as a client lists it


def test_exactly_one_tool_with_its_schema_description_and_annotations(doc, workspace):
    (tool,) = list_tools(_server(doc, workspace))
    assert tool.name == "reformat_cv"
    assert tool.inputSchema["required"] == ["path"]
    assert tool.inputSchema["properties"]["path"]["type"] == "string"
    assert set(tool.outputSchema["properties"]) == {
        "output_path",
        "run_id",
        "status",
        "retries",
        "removals",
        "unplaced",
        "appendix",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    }
    description = tool.description.lower()
    assert "workspace" in description
    assert "-reformatted-" in description
    assert "no cv text" in description
    assert "output path" in description
    annotations = tool.annotations
    assert annotations.readOnlyHint is False
    assert annotations.destructiveHint is False
    assert annotations.idempotentHint is False
    assert annotations.openWorldHint is True


# --- The Workspace


def test_a_path_escaping_the_workspace_is_refused_before_the_labeller(
    doc, workspace, tmp_path
):
    (tmp_path / "outside.docx").write_bytes(doc.source)

    def never(blocks):
        pytest.fail("the labeller was called")

    result = call(create_server(never, workspace=workspace), path="../outside.docx")

    assert result.isError
    text = _text(result)
    assert "outside_workspace" in text
    assert "outside.docx" not in text
    assert sorted(p.name for p in tmp_path.iterdir()) == ["outside.docx", "workspace"]


def test_the_workspace_is_read_from_the_environment_when_the_server_is_created(
    doc, workspace, runs, monkeypatch
):
    monkeypatch.setenv(ENV_WORKSPACE, str(workspace))
    server = create_server(Oracle(doc.candidate, doc.manifest))
    monkeypatch.setenv(ENV_WORKSPACE, str(workspace.parent))
    _source(workspace, doc)
    assert not call(server, path="cv.docx").isError


@pytest.mark.parametrize("value", [None, "", "missing"])
def test_no_workspace_is_a_named_error(value, monkeypatch, tmp_path):
    if value is None:
        monkeypatch.delenv(ENV_WORKSPACE, raising=False)
    else:
        monkeypatch.setenv(ENV_WORKSPACE, str(tmp_path / value) if value else "")
    with pytest.raises(WorkspaceMissing, match=ENV_WORKSPACE):
        create_server(lambda blocks: None)


# --- The labeller


def test_the_tool_is_listed_without_a_model_key_or_a_labeller(workspace, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def unbuildable(*args, **kwargs):
        pytest.fail("the real labeller was built")

    monkeypatch.setattr(mcp_server, "RealLabeller", unbuildable)
    (tool,) = list_tools(create_server(workspace=workspace))
    assert tool.name == "reformat_cv"


def test_the_real_labeller_is_built_once_on_the_first_call(
    doc, workspace, runs, monkeypatch
):
    built = []

    def building(config):
        built.append(config)
        return Oracle(doc.candidate, doc.manifest)

    monkeypatch.setattr(mcp_server, "RealLabeller", building)
    server = create_server(workspace=workspace)
    assert built == []
    _source(workspace, doc)
    for _ in range(2):
        assert not call(server, path="cv.docx").isError
    assert len(built) == 1


def test_calls_run_one_at_a_time(doc, workspace, runs):
    oracle = Oracle(doc.candidate, doc.manifest)
    state = {"active": 0, "most": 0}
    guard = threading.Lock()

    def slow(blocks):
        with guard:
            state["active"] += 1
            state["most"] = max(state["most"], state["active"])
        time.sleep(0.2)
        with guard:
            state["active"] -= 1
        return oracle(blocks)

    server = create_server(slow, workspace=workspace)
    _source(workspace, doc)

    async def main():
        async with create_connected_server_and_client_session(server) as client:
            results = []

            async def one():
                results.append(await client.call_tool(TOOL_NAME, {"path": "cv.docx"}))

            async with anyio.create_task_group() as group:
                for _ in range(3):
                    group.start_soon(one)
            return results

    results = anyio.run(main)
    assert [r.isError for r in results] == [False] * 3
    assert state["most"] == 1


# --- The log


def test_each_run_is_logged_to_stderr_with_the_api_summarys_keys(
    doc, workspace, runs, capsys
):
    _source(workspace, doc, "Jane Doe CV.docx")
    result = call(_server(doc, workspace), path="Jane Doe CV.docx")
    captured = capsys.readouterr()
    (run,) = runs

    assert captured.out == ""
    (summary,) = summaries(captured.err)
    assert summary["run_id"] == result.structuredContent["run_id"] == run.run_id
    api_keys = json.loads(request_lines(run.run_id, 200, run=run)[0]).keys()
    assert summary.keys() == api_keys
    blocks = [line for line in log_lines(captured.err) if line["line"] == "block"]
    assert len(blocks) == summary["blocks"] > 0
    assert "Jane Doe" not in captured.err
    assert "CV.docx" not in captured.err
    assert workspace.name not in captured.err


def test_a_refused_call_logs_its_summary_alone_without_the_path(
    doc, workspace, tmp_path, capsys
):
    (tmp_path / "Jane Doe CV.docx").write_bytes(doc.source)
    call(_server(doc, workspace), path="../Jane Doe CV.docx")
    captured = capsys.readouterr()

    assert captured.out == ""
    (summary,) = log_lines(captured.err)
    assert summary["line"] == "summary"
    assert summary["status"] == "outside_workspace"
    assert "Jane Doe" not in captured.err


def test_a_call_failing_after_the_run_still_logs_what_the_labelling_cost(
    doc, workspace, runs, capsys, monkeypatch
):
    run_id = "ab" * 16
    monkeypatch.setattr(mcp_server, "uuid4", lambda: type("U", (), {"hex": run_id}))
    _source(workspace, doc)
    taken = workspace / f"cv-reformatted-{run_id[:8]}.docx"
    taken.write_bytes(b"an earlier result")
    capsys.readouterr()

    result = call(
        _server(doc, workspace, Paid(doc.candidate, doc.manifest)), path="cv.docx"
    )

    assert result.isError
    assert taken.read_bytes() == b"an earlier result"
    (summary,) = log_lines(capsys.readouterr().err)
    assert summary["status"] == "exists"
    assert summary["attempts"]["input_tokens"] == 1200
    assert summary["attempts"]["cost_usd"] == pytest.approx(0.0125)
