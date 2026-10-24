"""The API with the retry loop (ticket 14): the summary line's cost and tokens
equal the sum over the attempts and it states the retry count; an outage on
the first attempt is still a 503; a retry that fails is still a 200; no line
exceeds the size limit; a bad ``CVR_RETRY_MAX`` stops the app at start-up."""

import json

import pytest
from api_support import AUTH
from fastapi.testclient import TestClient
from pipeline_support import document
from retry_support import (
    bullet_additions,
    damaged,
    drop_first_bullets,
    perfect,
    scripted,
)

from cvr.api import DOCX_MEDIA_TYPE as DOCX
from cvr.api import RUN_ID_HEADER, create_app
from cvr.api.log import MAX_LINE_BYTES
from cvr.label.pricing import estimate_cost

STEM = "c04__single-column"
MODEL = "claude-sonnet-5-5"


def _post(labeller, capsys):
    doc = document(STEM)
    client = TestClient(create_app(labeller))
    capsys.readouterr()
    response = client.post(
        "/reformat", files={"file": ("cv.docx", doc.source, DOCX)}, headers=AUTH
    )
    lines = capsys.readouterr().out.splitlines()
    return response, lines


def _summary(lines):
    (summary,) = [json.loads(x) for x in lines if json.loads(x)["line"] == "summary"]
    return summary


def test_the_summary_sums_cost_and_tokens_over_every_attempt(capsys):
    full = perfect(STEM)
    labeller, chat = scripted(
        damaged(STEM, drop_first_bullets(2)),
        bullet_additions(full, 0),
        bullet_additions(full, 1),
    )
    response, lines = _post(labeller, capsys)

    assert response.status_code == 200
    assert len(chat.calls) == 3
    summary = _summary(lines)
    assert summary["retries"] == 2
    # 1000 in, 100 out on each of the three calls
    assert summary["attempts"]["input_tokens"] == 3000
    assert summary["attempts"]["output_tokens"] == 300
    assert summary["attempts"]["cost_usd"] == pytest.approx(
        3 * estimate_cost(MODEL, 1000, 100)
    )
    # the label section is the first attempt alone, as the Run keeps it
    assert summary["label"]["input_tokens"] == 1000
    assert summary["run_id"] == response.headers[RUN_ID_HEADER]


def test_a_run_without_a_retry_states_zero(capsys):
    labeller, _ = scripted(perfect(STEM))
    _, lines = _post(labeller, capsys)
    summary = _summary(lines)
    assert summary["retries"] == 0
    assert summary["attempts"]["input_tokens"] == 1000


def test_no_line_exceeds_the_size_limit_with_retries(capsys):
    full = perfect(STEM)
    labeller, _ = scripted(
        damaged(STEM, drop_first_bullets(2)),
        bullet_additions(full, 0),
        bullet_additions(full, 1),
    )
    _, lines = _post(labeller, capsys)
    assert max(len(line.encode()) for line in lines) < MAX_LINE_BYTES


def test_an_outage_on_the_first_attempt_is_still_a_503(capsys):
    labeller, _ = scripted("outage")
    response, lines = _post(labeller, capsys)
    assert response.status_code == 503
    assert _summary(lines)["status"] == 503


def test_an_outage_on_a_retry_is_a_200_with_the_previous_document(capsys):
    labeller, _ = scripted(damaged(STEM, drop_first_bullets(1)), "outage")
    response, lines = _post(labeller, capsys)
    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    summary = _summary(lines)
    assert summary["retries"] == 1
    assert summary["attempts"]["input_tokens"] == 1000  # the outage cost nothing


def test_a_bad_retry_max_stops_the_app_at_start_up(monkeypatch):
    monkeypatch.setenv("CVR_RETRY_MAX", "-1")
    with pytest.raises(ValueError, match="CVR_RETRY_MAX"):
        create_app(scripted(perfect(STEM))[0])
