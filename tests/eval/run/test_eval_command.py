"""The eval command end to end with the oracle labellers in place of the real
one: exit code, the report's shape and order, and a summary that names the
failing metric and candidate."""

import contextlib
import io
import json

import pytest
from pipeline.oracle import omit_first_bullet, unlocatable_title
from run_support import C04, ORACLE, imperfect, oracle, thresholds_file

from cvr.eval.run import main

BREAKDOWNS = ["totals", "per_layout", "per_tag", "per_candidate"]
AFTER = ["config", "versions", "tokens", "cost_usd", "wall_time_seconds"]


def _main(tmp_path, labeller, *extra: str) -> int:
    return main(
        [
            "--candidate",
            "c04",
            "--out",
            str(tmp_path / "out"),
            "--cache-dir",
            str(tmp_path / "cache"),
            *extra,
        ],
        labeller=(labeller, ORACLE),
    )


def _report(tmp_path) -> dict:
    return json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def perfect(tmp_path_factory):
    """The perfect oracle over c04's four documents, at the tightest
    thresholds: its exit code, standard output, and the report directory."""
    tmp_path = tmp_path_factory.mktemp("perfect")
    thresholds = thresholds_file(tmp_path, placement_min=100, appendix_max=0)
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = _main(tmp_path, oracle, "--thresholds", str(thresholds))
    return code, out.getvalue(), tmp_path


def test_the_perfect_oracle_over_four_documents_passes_with_every_breakdown(
    perfect,
):
    code, out, tmp_path = perfect
    assert code == 0
    report = _report(tmp_path)

    keys = list(report)
    assert keys[: len(BREAKDOWNS) + len(AFTER)] == BREAKDOWNS + AFTER
    assert report["totals"]["documents"] == 4
    assert sorted(report["per_layout"]) == [stem.split("__")[1] for stem in C04]
    assert list(report["per_candidate"]) == ["c04"]
    assert report["per_tag"]
    assert all(t["documents"] == 4 for t in report["per_tag"].values())
    assert report["config"] == dict(ORACLE.config)
    assert report["versions"] == {
        "prompt": {"version": "oracle", "hash": "oracle"},
        "schema": {"version": "oracle", "hash": "oracle"},
    }
    assert report["gate"] == {"passed": True, "failures": []}
    assert [doc["document"] for doc in report["documents"]] == C04
    totals = report["totals"]
    assert totals["structural"]["precision"] == totals["structural"]["recall"] == 100
    assert totals["tunable"]["precision"] == totals["tunable"]["recall"] == 100
    assert totals["appendix_rate"] == 0
    assert out.startswith("PASS")


def test_the_markdown_renders_the_same_report_with_the_totals_table_first(perfect):
    _, _, tmp_path = perfect
    markdown = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Totals",
        "## Per layout",
        "## Per tag",
        "## Per candidate",
        "## Labeller and usage",
        "## Gate",
    ]
    first_table = next(line for line in markdown.splitlines() if line.startswith("|"))
    assert "Added" in first_table and "Appendix %" in first_table
    for layout in _report(tmp_path)["per_layout"]:
        assert f"| {layout} |" in markdown


def test_an_omitted_leaf_under_a_placement_minimum_of_100_fails_naming_it(
    tmp_path, capsys
):
    thresholds = thresholds_file(tmp_path, placement_min=100)
    code = _main(
        tmp_path, imperfect(omit_first_bullet), "--thresholds", str(thresholds)
    )
    assert code == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL")
    (failure,) = _report(tmp_path)["gate"]["failures"]
    assert failure["metric"] == "placement_accuracy (tunable)"
    assert failure["detail"].startswith("recall")
    assert failure["candidates"] == ["c04"]
    assert failure["documents"] == C04
    assert "placement_accuracy (tunable): recall" in out
    assert "(c04)" in out
    markdown = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "**FAIL**" in markdown
    assert "placement_accuracy (tunable): recall" in markdown


ONE = ("--layout", "single-column")


def test_the_same_omission_passes_the_placeholder_thresholds(tmp_path):
    assert _main(tmp_path, imperfect(omit_first_bullet), *ONE) == 0


def test_a_structural_miss_fails_whatever_the_thresholds(tmp_path, capsys):
    assert _main(tmp_path, imperfect(unlocatable_title), *ONE) == 1
    metrics = [f["metric"] for f in _report(tmp_path)["gate"]["failures"]]
    assert metrics == ["placement_accuracy (structural)"]
    assert "placement_accuracy (structural)" in capsys.readouterr().out


def test_an_unknown_filter_is_an_error_not_an_empty_pass(tmp_path):
    with pytest.raises(SystemExit) as exit:
        main(["--layout", "three-column"], labeller=(oracle, ORACLE))
    assert exit.value.code == 2


def test_a_second_command_replays_the_cache_and_no_cache_bypasses_it(tmp_path):
    runs = [(), (), ("--no-cache",)]
    caches = []
    for extra in runs:
        assert _main(tmp_path, oracle, *ONE, *extra) == 0
        caches.append(_report(tmp_path)["cache"])
    assert [(c["hits"], c["live_calls"], c["read"]) for c in caches] == [
        (0, 1, True),
        (1, 0, True),
        (0, 1, False),
    ]
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1


@pytest.mark.slow
def test_the_perfect_oracle_over_every_generated_document_passes(tmp_path):
    # Two Candidates carry unplaceable fragments, so the appendix is not
    # empty even for a perfect labeller; every other gate is at its tightest.
    thresholds = thresholds_file(tmp_path, placement_min=100, appendix_max=1)
    code = main(
        [
            "--out",
            str(tmp_path),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--thresholds",
            str(thresholds),
        ],
        labeller=(oracle, ORACLE),
    )
    report = _report_in(tmp_path)
    assert (code, report["totals"]["documents"]) == (0, 48)
    assert len(report["per_candidate"]) == 12 and len(report["per_layout"]) == 4


def _report_in(directory) -> dict:
    return json.loads((directory / "report.json").read_text(encoding="utf-8"))
