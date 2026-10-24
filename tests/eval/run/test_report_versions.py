"""The report names the retry prompt and the additions schema it ran on, so a
model comparison can refuse runs made on different retry versions."""

import json
from dataclasses import replace

from run_support import ORACLE, oracle

from cvr.eval.run import main


def _versions(tmp_path, identity) -> dict:
    main(
        [
            "--candidate",
            "c04",
            "--layout",
            "single-column",
            "--out",
            str(tmp_path / "out"),
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
        labeller=(oracle, identity),
    )
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    return report["versions"]


def test_the_retry_hashes_are_in_the_versions_when_the_labeller_has_them(tmp_path):
    identity = replace(ORACLE, retry_prompt_hash="rr", additions_hash="aa")
    versions = _versions(tmp_path, identity)
    assert versions["retry_prompt"] == {"hash": "rr"}
    assert versions["additions_schema"] == {"hash": "aa"}


def test_a_labeller_with_no_retry_leaves_them_out(tmp_path):
    assert set(_versions(tmp_path, ORACLE)) == {"prompt", "schema"}
