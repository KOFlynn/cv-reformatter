"""The payload function emits allowlisted fields only: ids and counts yes,
candidate text never."""

from oracle import Oracle
from pipeline_support import document
from tracing_support import LABEL_RUN

from cvr.models import LabellingFailure
from cvr.parse import parse
from cvr.text import tokenise
from cvr.tracing import (
    ALLOWED_KEYS,
    allowlisted,
    generation_payload,
    node_payload,
    rejection_payload,
)
from cvr.transform import transform_content
from cvr.verify import Rejection, verify


def _stages():
    d = document("c04__single-column")
    parsed = parse(d.source)
    labelling = Oracle(d.candidate, d.manifest)(parsed.blocks)
    verified = verify(parsed.blocks, labelling)
    transformed = transform_content(verified.content)
    return d, parsed, labelling, verified, transformed


def test_allowlisted_drops_every_key_off_the_list():
    out = allowlisted({"block_count": 3, "quote": "x", "text": "y"})
    assert out == {"block_count": 3}


def test_every_node_payload_is_allowlisted_and_has_its_counts():
    d, parsed, labelling, verified, transformed = _stages()
    payloads = {
        "parse": node_payload("parse", {"source": d.source}, {"parsed": parsed}),
        "label": node_payload(
            "label", {"blocks": parsed.blocks}, {"labelling": labelling}
        ),
        "verify": node_payload("verify", {}, {"verified": verified}),
        "transform": node_payload("transform", {}, {"transformed": transformed}),
        "render": node_payload("render", {}, {"output": b"123"}),
    }
    for payload in payloads.values():
        assert set(payload["metadata"]) <= ALLOWED_KEYS
    # Positive controls: the counts are there.
    assert payloads["parse"]["metadata"]["block_count"] == len(parsed.blocks)
    assert payloads["parse"]["metadata"]["source_bytes"] == len(d.source)
    assert payloads["label"]["metadata"]["reference_count"] > 0
    assert payloads["label"]["metadata"]["label_failed"] is False
    assert payloads["verify"]["metadata"]["claim_count"] == len(verified.claims)
    assert payloads["verify"]["metadata"]["rejection_count"] == 0
    assert payloads["transform"]["metadata"]["date_count"] == len(transformed.date_map)
    assert payloads["render"]["metadata"]["output_bytes"] == 3


def test_no_source_token_appears_in_any_structure_payload():
    d, parsed, labelling, verified, transformed = _stages()
    payloads = [
        node_payload("parse", {"source": d.source}, {"parsed": parsed}),
        node_payload("label", {"blocks": parsed.blocks}, {"labelling": labelling}),
        node_payload("verify", {}, {"verified": verified}),
        node_payload("transform", {}, {"transformed": transformed}),
        generation_payload(LABEL_RUN, attempt=1),
        rejection_payload(
            Rejection("name", "body:1", "SECRET QUOTE", "unlocatable"), {"body:1"}
        ),
    ]
    # Values only: key names are ours and may coincide with a word of the CV.
    blob = repr([list(p["metadata"].values()) for p in payloads]).lower()
    source_tokens = {t for block in parsed.blocks for t in tokenise(block.text)}
    # Short or numeric tokens can occur in ids and counts; judge words.
    words = {t for t in source_tokens if len(t) >= 6 and t.isalpha()}
    assert words
    assert not {w for w in words if w in blob}


def test_a_failed_labelling_counts_zero_references():
    _, parsed, *_ = _stages()
    out = node_payload(
        "label", {"blocks": parsed.blocks}, {"labelling": LabellingFailure(reason="x")}
    )
    assert out["metadata"]["label_failed"] is True
    assert out["metadata"]["reference_count"] == 0


def test_a_rejection_carries_path_block_and_reason_but_not_the_quote():
    out = rejection_payload(
        Rejection("experience[0].bullets[1]", "body:7", "SECRET QUOTE", "conflict"),
        {"body:7"},
    )
    assert out["metadata"] == {
        "path": "experience[0].bullets[1]",
        "block_id": "body:7",
        "reason": "conflict",
    }


def test_the_generation_payload_has_model_tokens_and_cost_from_the_label_run():
    out = generation_payload(LABEL_RUN, attempt=2)
    assert out["model"] == "claude-sonnet-5-5"
    assert out["usage_details"] == {"input": 1234, "output": 567}
    assert out["cost_details"] == {"total": 0.0081}
    assert out["metadata"]["attempt"] == 2
    assert set(out["metadata"]) <= ALLOWED_KEYS


def test_the_generation_payload_without_a_label_run_is_the_attempt_alone():
    assert generation_payload(None, attempt=1) == {"metadata": {"attempt": 1}}
