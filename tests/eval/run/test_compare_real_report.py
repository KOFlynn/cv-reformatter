"""Key drift: the aggregator reads the report the eval run really writes (the
oracle in place of the model, no LLM), not a hand-built one."""

import json
from dataclasses import replace

from run_support import ORACLE, oracle

from cvr.eval.compare import compare
from cvr.eval.run import main


def _report(tmp_path, label: str, model: str) -> tuple[str, str, dict]:
    out = tmp_path / label
    identity = replace(
        ORACLE,
        config={"provider": "oracle", "model": model},
        retry_prompt_hash="r",
        additions_hash="x",
    )
    main(
        [
            "--candidate",
            "c04",
            "--layout",
            "single-column",
            "--out",
            str(out),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--no-cache",
        ],
        labeller=(oracle, identity),
    )
    path = out / "report.json"
    return label, str(path), json.loads(path.read_text(encoding="utf-8"))


def test_a_real_report_is_accepted_by_the_aggregator(tmp_path):
    runs = [_report(tmp_path, "a", "one"), _report(tmp_path, "b", "two")]

    record = compare(runs, date="d")

    assert record["documents_per_run"] == 1
    assert record["reference"]["gates_passed"] == 1
    assert record["versions"]["retry_prompt"] == {"hash": "r"}
    assert "retries_fired" in record["candidates"]["b"]["runs"][0]["totals"]
