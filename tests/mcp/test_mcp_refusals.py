"""Every way a ``reformat_cv`` call goes wrong is a tool error in one of the
eight fixed categories, with its fixed message and never an exception's text;
a labelling failure is not an error (ticket 04). Refusals happen before the
labeller is built or called, and a failed call logs its summary alone."""

import os
from pathlib import Path

import pytest
from mcp_support import call, log_lines
from oracle import Imperfect, Oracle, schema_invalid
from pipeline_support import document
from retry_support import (
    bullet_additions,
    damaged,
    drop_first_bullets,
    perfect,
    scripted,
)

import cvr.mcp.server as mcp_server
from cvr.label.errors import LabellerMisconfigured, ProviderUnavailable
from cvr.mcp import create_server
from cvr.mcp.server import MESSAGES
from cvr.runlog import MAX_UPLOAD_BYTES, ErrorCategory

STEM = "c04__single-column"
SECRET = "Jane Doe secret text"


@pytest.fixture
def doc():
    return document(STEM)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    return root


def never(blocks):
    pytest.fail("the labeller was called")


def _refused(result, category: ErrorCategory) -> str:
    assert result.isError
    text = "\n".join(block.text for block in result.content)
    assert f"{category.value}: {MESSAGES[category]}" in text
    return text


def _outputs(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


# --- outside_workspace


def test_an_absolute_path_outside_the_workspace_is_refused(doc, workspace, tmp_path):
    outside = tmp_path / "outside.docx"
    outside.write_bytes(doc.source)

    result = call(create_server(never, workspace=workspace), path=str(outside))

    text = _refused(result, ErrorCategory.OUTSIDE_WORKSPACE)
    assert "outside.docx" not in text
    assert _outputs(tmp_path) == ["outside.docx", "workspace"]


def test_dot_dot_out_of_a_subdirectory_is_refused(doc, workspace, tmp_path):
    (workspace / "sub").mkdir()
    (workspace / "sub" / ".." / ".." / "x.docx").resolve().write_bytes(doc.source)

    result = call(create_server(never, workspace=workspace), path="sub/../../x.docx")

    _refused(result, ErrorCategory.OUTSIDE_WORKSPACE)


def test_a_symlink_escaping_the_workspace_is_refused(doc, workspace, tmp_path):
    target = tmp_path / "target.docx"
    target.write_bytes(doc.source)
    try:
        os.symlink(target, workspace / "link.docx")
    except (OSError, NotImplementedError):
        pytest.skip("this platform cannot create a symlink here")

    result = call(create_server(never, workspace=workspace), path="link.docx")

    _refused(result, ErrorCategory.OUTSIDE_WORKSPACE)


# --- not_found


def test_a_missing_path_is_not_found(workspace):
    result = call(create_server(never, workspace=workspace), path="absent.docx")

    text = _refused(result, ErrorCategory.NOT_FOUND)
    assert "absent" not in text


def test_a_directory_is_not_found(workspace):
    (workspace / "folder.docx").mkdir()

    result = call(create_server(never, workspace=workspace), path="folder.docx")

    _refused(result, ErrorCategory.NOT_FOUND)
    assert _outputs(workspace) == ["folder.docx"]


# --- not_docx


@pytest.mark.parametrize("name", ["cv.pdf", "cv.docx.txt", "cv", "cv.doc"])
def test_a_file_that_is_not_a_docx_is_refused(doc, workspace, name):
    (workspace / name).write_bytes(doc.source)

    result = call(create_server(never, workspace=workspace), path=name)

    _refused(result, ErrorCategory.NOT_DOCX)
    assert _outputs(workspace) == [name]


@pytest.mark.parametrize("name", ["cv.DOCX", "cv.DocX"])
def test_the_docx_suffix_is_matched_in_any_case(doc, workspace, name):
    (workspace / name).write_bytes(doc.source)

    result = call(
        create_server(Oracle(doc.candidate, doc.manifest), workspace=workspace),
        path=name,
    )

    assert not result.isError


def test_not_found_is_reported_before_not_docx(workspace):
    result = call(create_server(never, workspace=workspace), path="absent.pdf")

    _refused(result, ErrorCategory.NOT_FOUND)


# --- too_large


def test_a_file_over_the_limit_is_refused_before_it_is_read(
    doc, workspace, monkeypatch
):
    big = workspace / "big.docx"
    with big.open("wb") as file:
        file.truncate(MAX_UPLOAD_BYTES + 1)

    def no_read(self, *args, **kwargs):
        pytest.fail("the file was read")

    monkeypatch.setattr(Path, "read_bytes", no_read)
    result = call(create_server(never, workspace=workspace), path="big.docx")

    _refused(result, ErrorCategory.TOO_LARGE)
    assert _outputs(workspace) == ["big.docx"]


def test_a_file_of_exactly_the_limit_is_not_too_large(doc, workspace):
    exact = workspace / "exact.docx"
    with exact.open("wb") as file:
        file.truncate(MAX_UPLOAD_BYTES)

    # Not a real document, so the pipeline fails: but not as too_large.
    result = call(
        create_server(Oracle(doc.candidate, doc.manifest), workspace=workspace),
        path="exact.docx",
    )

    assert "too_large" not in "\n".join(b.text for b in result.content)


# --- exists


def test_an_existing_output_name_is_refused_and_not_retried(
    doc, workspace, monkeypatch, capsys
):
    run_id = "cd" * 16
    monkeypatch.setattr(mcp_server, "uuid4", lambda: type("U", (), {"hex": run_id}))
    (workspace / "cv.docx").write_bytes(doc.source)
    taken = workspace / f"cv-reformatted-{run_id[:8]}.docx"
    taken.write_bytes(b"an earlier result")
    calls = []
    oracle = Oracle(doc.candidate, doc.manifest)

    def counting(blocks):
        calls.append(1)
        return oracle(blocks)

    result = call(create_server(counting, workspace=workspace), path="cv.docx")

    _refused(result, ErrorCategory.EXISTS)
    assert taken.read_bytes() == b"an earlier result"
    assert _outputs(workspace) == [taken.name, "cv.docx"]
    assert len(calls) == 1


# --- refusals come before the labeller


@pytest.mark.parametrize("path", ["../x.docx", "absent.docx", "cv.txt", "big.docx"])
def test_a_refusal_never_builds_or_calls_the_labeller(
    doc, workspace, monkeypatch, path
):
    (workspace / "cv.txt").write_bytes(doc.source)
    with (workspace / "big.docx").open("wb") as file:
        file.truncate(MAX_UPLOAD_BYTES + 1)

    def unbuildable(config):
        pytest.fail("the real labeller was built")

    monkeypatch.setattr(mcp_server, "RealLabeller", unbuildable)

    assert call(create_server(workspace=workspace), path=path).isError


# --- the labeller's two errors, and anything else


class Raising:
    """A labeller that raises ``error`` on its first call."""

    def __init__(self, error: BaseException):
        self.error = error

    def __call__(self, blocks):
        raise self.error


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ProviderUnavailable("down"), ErrorCategory.PROVIDER_UNAVAILABLE),
        (LabellerMisconfigured("bad key"), ErrorCategory.MISCONFIGURED),
    ],
)
def test_the_labellers_errors_have_their_fixed_messages(
    doc, workspace, error, category, capsys
):
    (workspace / "cv.docx").write_bytes(doc.source)
    capsys.readouterr()

    result = call(create_server(Raising(error), workspace=workspace), path="cv.docx")

    text = _refused(result, category)
    assert str(error) not in text.replace(MESSAGES[category], "")
    assert [p.name for p in workspace.iterdir()] == ["cv.docx"]
    (summary,) = log_lines(capsys.readouterr().err)
    assert summary["status"] == category.value
    assert summary["error"] == type(error).__name__


def test_anything_else_is_internal_logged_by_type_name_only(doc, workspace, capsys):
    (workspace / "cv.docx").write_bytes(doc.source)
    capsys.readouterr()
    result = call(
        create_server(Raising(RuntimeError(SECRET)), workspace=workspace),
        path="cv.docx",
    )

    text = _refused(result, ErrorCategory.INTERNAL)
    assert SECRET not in text
    err = capsys.readouterr().err
    assert SECRET not in err
    (summary,) = log_lines(err)
    assert summary["status"] == "internal"
    assert summary["error"] == "RuntimeError"


def test_an_outage_or_defect_on_a_retry_logs_every_attempt_paid_for(
    doc, workspace, capsys
):
    full = perfect(STEM)
    labeller, chat = scripted(
        damaged(STEM, drop_first_bullets(2)),
        bullet_additions(full, 0),
        RuntimeError(SECRET),
    )
    (workspace / "cv.docx").write_bytes(doc.source)
    capsys.readouterr()

    result = call(create_server(labeller, workspace=workspace), path="cv.docx")

    _refused(result, ErrorCategory.MISCONFIGURED)
    assert len(chat.calls) == 3
    err = capsys.readouterr().err
    assert SECRET not in err
    (summary,) = log_lines(err)
    assert summary["status"] == "misconfigured"
    assert summary["attempts"]["input_tokens"] == 2000
    assert summary["attempts"]["output_tokens"] == 200
    assert [p.name for p in workspace.iterdir()] == ["cv.docx"]


def test_an_outage_on_a_retry_keeps_the_previous_result(doc, workspace):
    labeller, _ = scripted(damaged(STEM, drop_first_bullets(1)), "outage")
    (workspace / "cv.docx").write_bytes(doc.source)

    result = call(create_server(labeller, workspace=workspace), path="cv.docx")

    assert not result.isError
    assert len(_outputs(workspace)) == 2


def test_an_outage_on_the_first_attempt_is_provider_unavailable(doc, workspace):
    labeller, _ = scripted("outage")
    (workspace / "cv.docx").write_bytes(doc.source)

    result = call(create_server(labeller, workspace=workspace), path="cv.docx")

    _refused(result, ErrorCategory.PROVIDER_UNAVAILABLE)


# --- a labelling failure is not an error


def test_a_labelling_failure_writes_the_banner_document_and_is_not_an_error(
    doc, workspace
):
    (workspace / "cv.docx").write_bytes(doc.source)
    labeller = Imperfect(Oracle(doc.candidate, doc.manifest), schema_invalid)

    result = call(create_server(labeller, workspace=workspace), path="cv.docx")

    assert not result.isError
    content = result.structuredContent
    assert content["status"] == "labelling_failed"
    assert content["unplaced"]["spans"] > 0
    assert content["unplaced"]["characters"] > 0
    assert content["appendix"] is not None
    assert content["run_id"]
    assert (workspace / Path(content["output_path"]).name).is_file()


def test_every_category_has_a_message():
    assert set(MESSAGES) == set(ErrorCategory)
    assert all(MESSAGES[c] for c in ErrorCategory)
