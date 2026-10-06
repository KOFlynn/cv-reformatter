"""The API through FastAPI's test client, with the oracle labeller injected:
the document and its headers on success, ``X-Run-Id`` on every response
including 4xx and 5xx, ``/reformat`` refused without the key or over the
size cap before any labeller is called, ``/health`` without a key or a
labeller, the real labeller built once and only when a document needs it,
and no route but the two."""

import json

import pytest
from api_support import API_KEY, AUTH
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from oracle import Oracle
from pipeline_support import document

import cvr.api.app as api_app
from cvr.api import DOCX_MEDIA_TYPE as DOCX
from cvr.api import RUN_ID_HEADER, create_app
from cvr.api.app import (
    API_KEY_HEADER,
    MAX_UPLOAD_BYTES,
    content_disposition,
    output_filename,
)
from cvr.eval.adapter import adapt
from cvr.label import LabellerMisconfigured, ProviderUnavailable
from cvr.models import LabellingFailure, LabelRun

STEM = "c04__single-column"


def _post(client: TestClient, filename: str, body: bytes):
    return client.post(
        "/reformat", files={"file": (filename, body, DOCX)}, headers=AUTH
    )


def _never(blocks):
    pytest.fail("the labeller was called")


def _summary(out: str) -> dict:
    lines = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    (summary,) = [line for line in lines if line["line"] == "summary"]
    return summary


# --- Success


def test_a_golden_set_document_comes_back_reformatted(monkeypatch, capsys):
    doc = document(STEM)
    runs = []
    reformat = api_app.reformat

    def recording(*args, **kwargs):
        output, run = reformat(*args, **kwargs)
        runs.append(run)
        return output, run

    monkeypatch.setattr(api_app, "reformat", recording)
    client = TestClient(create_app(Oracle(doc.candidate, doc.manifest)))
    response = _post(client, "candidate CV.docx", doc.source)

    assert response.status_code == 200
    assert response.headers["content-type"] == DOCX
    assert response.content.startswith(b"PK")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="candidate CV-reformatted.docx"'
    )
    (run,) = runs
    assert response.headers[RUN_ID_HEADER] == run.run_id
    assert _summary(capsys.readouterr().out)["run_id"] == run.run_id


def test_every_request_has_its_own_run_id():
    doc = document(STEM)
    client = TestClient(create_app(Oracle(doc.candidate, doc.manifest)))
    ids = {_post(client, "cv.docx", doc.source).headers[RUN_ID_HEADER] for _ in "ab"}
    assert len(ids) == 2


def test_a_labelling_failure_is_still_a_document_under_the_banner():
    doc = document(STEM)
    client = TestClient(create_app(lambda blocks: LabellingFailure(reason="refused")))
    response = _post(client, "cv.docx", doc.source)
    assert response.status_code == 200
    assert RUN_ID_HEADER in response.headers
    assert adapt(response.content).appendix  # every block's text, under the banner


# --- Failures carry the run id too


def test_a_pdf_upload_is_a_4xx_with_a_run_id(capsys):
    client = TestClient(create_app(_never))
    response = client.post(
        "/reformat",
        files={"file": ("cv.pdf", b"%PDF-1.7\n", "application/pdf")},
        headers=AUTH,
    )
    assert response.status_code == 415
    run_id = response.headers[RUN_ID_HEADER]
    summary = _summary(capsys.readouterr().out)
    assert summary["run_id"] == run_id
    assert summary["status"] == 415


def test_a_docx_name_on_something_else_is_a_4xx_with_a_run_id():
    client = TestClient(create_app(_never))
    response = _post(client, "cv.docx", b"not a zip at all")
    assert response.status_code == 415
    assert RUN_ID_HEADER in response.headers


def test_a_request_with_no_file_is_a_4xx_with_a_run_id():
    client = TestClient(create_app(_never))
    response = client.post("/reformat", headers=AUTH)
    assert 400 <= response.status_code < 500
    assert RUN_ID_HEADER in response.headers


def test_a_labeller_that_raises_is_a_5xx_with_a_run_id(capsys):
    def raising(blocks):
        raise RuntimeError("a defect in the labeller")

    doc = document(STEM)
    client = TestClient(create_app(raising))
    response = _post(client, "cv.docx", doc.source)
    assert response.status_code == 500
    run_id = response.headers[RUN_ID_HEADER]
    summary = _summary(capsys.readouterr().out)
    assert summary["run_id"] == run_id
    assert summary["status"] == 500
    assert "RuntimeError" in summary["error"]


def test_a_failure_after_labelling_still_logs_what_the_labelling_cost(
    monkeypatch, capsys
):
    label_run = LabelRun(
        config={"model": "stand-in"},
        prompt_version="p",
        prompt_hash="ph",
        schema_version="s",
        schema_hash="sh",
        content_hash="ch",
        input_tokens=1200,
        cost_usd=0.02,
    )

    class Recording:
        last_run = None

        def __call__(self, blocks):
            self.last_run = label_run
            return LabellingFailure(reason="stand-in")

    def failing_after_the_labeller(source, labeller, *, run_id):
        labeller([])
        raise RuntimeError("render failed")

    monkeypatch.setattr(api_app, "reformat", failing_after_the_labeller)
    response = _post(
        TestClient(create_app(Recording())), "cv.docx", document(STEM).source
    )
    assert response.status_code == 500
    summary = _summary(capsys.readouterr().out)
    assert summary["run_id"] == response.headers[RUN_ID_HEADER]
    assert summary["label"]["input_tokens"] == 1200
    assert summary["label"]["cost_usd"] == 0.02


def test_a_log_that_cannot_be_written_still_returns_the_run_id(monkeypatch):
    def broken(lines):
        raise OSError("stdout closed")

    monkeypatch.setattr(api_app, "write_lines", broken)
    doc = document(STEM)
    client = TestClient(create_app(Oracle(doc.candidate, doc.manifest)))
    response = _post(client, "cv.docx", doc.source)
    assert response.status_code == 200
    assert RUN_ID_HEADER in response.headers


@pytest.mark.parametrize(
    ("error", "status"),
    [(ProviderUnavailable("overloaded"), 503), (LabellerMisconfigured("bad key"), 500)],
)
def test_a_labeller_error_is_its_5xx_with_a_run_id(error, status):
    def raising(blocks):
        raise error

    doc = document(STEM)
    response = _post(TestClient(create_app(raising)), "cv.docx", doc.source)
    assert response.status_code == status
    assert RUN_ID_HEADER in response.headers


def test_an_unknown_route_is_a_404_with_a_run_id():
    response = TestClient(create_app(_never)).get("/docs")
    assert response.status_code == 404
    assert RUN_ID_HEADER in response.headers


# --- The key and the size cap: refused before the body or the labeller


def test_the_key_header_is_x_api_key():
    assert API_KEY_HEADER == "X-API-Key"


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-API-Key": "wrong"}, {"X-API-Key": ""}, {"X-API-Key": API_KEY + "x"}],
    ids=["missing", "wrong", "empty", "longer"],
)
def test_reformat_without_the_key_is_a_401_with_a_run_id(headers, capsys):
    client = TestClient(create_app(_never))
    response = client.post(
        "/reformat",
        files={"file": ("cv.docx", document(STEM).source, DOCX)},
        headers=headers,
    )
    assert response.status_code == 401
    run_id = response.headers[RUN_ID_HEADER]
    summary = _summary(capsys.readouterr().out)
    assert summary["run_id"] == run_id
    assert summary["status"] == 401
    assert summary["error"]


def test_the_key_is_checked_before_the_size_or_the_body():
    # No key and a body over the cap: refused for the key, unread.
    client = TestClient(create_app(_never))
    response = client.post(
        "/reformat", files={"file": ("cv.docx", b"x" * (MAX_UPLOAD_BYTES + 1), DOCX)}
    )
    assert response.status_code == 401


def test_neither_key_is_ever_logged(capsys, caplog):
    client = TestClient(create_app(_never))
    client.post(
        "/reformat",
        files={"file": ("cv.docx", document(STEM).source, DOCX)},
        headers={"X-API-Key": "a-wrong-key-sent-by-a-caller"},
    )
    doc = document(STEM)
    TestClient(create_app(Oracle(doc.candidate, doc.manifest))).post(
        "/reformat", files={"file": ("cv.docx", doc.source, DOCX)}, headers=AUTH
    )
    captured = capsys.readouterr()
    logged = captured.out + captured.err + caplog.text
    assert '"status":401' in logged and '"status":200' in logged
    assert API_KEY not in logged
    assert "a-wrong-key-sent-by-a-caller" not in logged


@pytest.mark.parametrize("configured", [None, ""], ids=["unset", "empty"])
def test_with_no_key_configured_reformat_refuses_everyone(
    configured, monkeypatch, capsys
):
    if configured is None:
        monkeypatch.delenv("CVR_API_KEY")
    else:
        monkeypatch.setenv("CVR_API_KEY", configured)
    client = TestClient(create_app(_never))
    for headers in ({}, {"X-API-Key": ""}, AUTH):
        response = client.post(
            "/reformat",
            files={"file": ("cv.docx", document(STEM).source, DOCX)},
            headers=headers,
        )
        assert response.status_code == 503
        assert RUN_ID_HEADER in response.headers
    summaries = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    assert [s["status"] for s in summaries] == [503, 503, 503]
    assert all("CVR_API_KEY" in s["error"] for s in summaries)


def test_an_upload_over_the_cap_is_a_413_with_a_run_id(capsys):
    client = TestClient(create_app(_never))
    response = client.post(
        "/reformat",
        files={"file": ("cv.docx", b"x" * (MAX_UPLOAD_BYTES + 1), DOCX)},
        headers=AUTH,
    )
    assert response.status_code == 413
    run_id = response.headers[RUN_ID_HEADER]
    summary = _summary(capsys.readouterr().out)
    assert summary["run_id"] == run_id
    assert summary["status"] == 413


def test_an_upload_of_unstated_length_is_a_411():
    # Without Content-Length the size is unknown until the body is read.
    def chunks():
        yield b"x" * 10

    client = TestClient(create_app(_never))
    response = client.post(
        "/reformat",
        content=chunks(),
        headers={**AUTH, "Content-Type": "multipart/form-data; boundary=b"},
    )
    assert response.status_code == 411
    assert RUN_ID_HEADER in response.headers


def test_the_cap_is_far_above_every_golden_set_document():
    assert MAX_UPLOAD_BYTES == 5 * 1024 * 1024
    assert len(document("c11__two-column").source) * 20 < MAX_UPLOAD_BYTES


def test_health_needs_no_key_even_when_none_is_configured(monkeypatch):
    monkeypatch.delenv("CVR_API_KEY")
    response = TestClient(create_app(_never)).get("/health")
    assert response.status_code == 200


# --- Health, and the real labeller


class CountingLabeller:
    """Stands in for ``RealLabeller``: counts constructions, labels nothing."""

    constructed = 0

    def __init__(self, config=None):
        type(self).constructed += 1

    def __call__(self, blocks):
        return LabellingFailure(reason="stand-in")


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    CountingLabeller.constructed = 0
    monkeypatch.setattr(api_app, "RealLabeller", CountingLabeller)


def test_health_is_live_with_no_key_and_no_labeller_constructed(no_key):
    with TestClient(create_app()) as client:  # startup and shutdown run too
        response = client.get("/health")  # no key sent
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert RUN_ID_HEADER in response.headers
    assert CountingLabeller.constructed == 0


def test_the_real_labeller_is_constructed_once(no_key):
    doc = document(STEM)
    with TestClient(create_app()) as client:
        for _ in range(2):
            assert _post(client, "cv.docx", doc.source).status_code == 200
    assert CountingLabeller.constructed == 1


# --- Routes


def test_no_route_but_reformat_and_health():
    app = create_app(_never)
    routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert routes == {("/reformat", "POST"), ("/health", "GET")}
    assert [route for route in app.routes if not isinstance(route, APIRoute)] == []


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/runs"])
def test_no_documentation_or_run_endpoint_is_served(path):
    assert TestClient(create_app(_never)).get(path).status_code == 404


# --- The derived filename


@pytest.mark.parametrize(
    ("upload", "expected"),
    [
        ("cv.docx", "cv-reformatted.docx"),
        ("CV.DOCX", "CV-reformatted.docx"),
        ("C:\\Users\\a\\cv.v2.docx", "cv.v2-reformatted.docx"),
        ("folder/cv.docx", "cv-reformatted.docx"),
    ],
)
def test_the_output_filename_is_the_uploads_stem_reformatted(upload, expected):
    assert output_filename(upload) == expected


def test_a_filename_header_is_always_safe_ascii():
    assert content_disposition("cv.docx") == 'attachment; filename="cv.docx"'
    assert content_disposition('a"b.docx') == (
        "attachment; filename=\"a_b.docx\"; filename*=UTF-8''a%22b.docx"
    )
    assert content_disposition("Zoë.docx") == (
        "attachment; filename=\"Zo_.docx\"; filename*=UTF-8''Zo%C3%AB.docx"
    )
