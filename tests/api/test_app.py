"""The API through FastAPI's test client, with the oracle labeller injected:
the document and its headers on success, ``X-Run-Id`` on every response
including 4xx and 5xx, ``/health`` without a labeller, the real labeller
built once and only when a document needs it, and no route but the two."""

import json

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from oracle import Oracle
from pipeline_support import document

import cvr.api.app as api_app
from cvr.api import RUN_ID_HEADER, create_app
from cvr.api.app import content_disposition, output_filename
from cvr.eval.adapter import adapt
from cvr.label import LabellerMisconfigured, ProviderUnavailable
from cvr.models import LabellingFailure

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
STEM = "c04__single-column"


def _post(client: TestClient, filename: str, body: bytes):
    return client.post("/reformat", files={"file": (filename, body, DOCX)})


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
        "/reformat", files={"file": ("cv.pdf", b"%PDF-1.7\n", "application/pdf")}
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
    response = client.post("/reformat")
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
        response = client.get("/health")
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
