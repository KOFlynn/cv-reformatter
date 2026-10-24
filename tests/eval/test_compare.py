"""The comparison record: synthetic ``report.json`` files in, the dated record
out, and every way the runs can be incomparable refused."""

import copy
import json

import pytest

from cvr.eval.compare import CompareError, compare, main

VERSIONS = {
    "prompt": {"version": "1.3.0", "hash": "p"},
    "schema": {"version": "1.0.0", "hash": "s"},
    "retry_prompt": {"hash": "r"},
    "additions_schema": {"hash": "a"},
}
THRESHOLDS = {
    "placement_accuracy": {"min": 98.0},
    "appendix_rate": {"max": 2.0},
    "punctuation_fidelity": {"hard": True},
}
TALLY = {"precision": 100.0, "recall": 100.0, "hits": 10, "actual": 10, "expected": 10}


def report(
    *,
    model="m",
    cost=1.5,
    seconds=100.0,
    passed=True,
    tunable=99.0,
    stems=("c01__a", "c01__b"),
    versions=VERSIONS,
    hits=0,
) -> dict:
    totals = {
        "documents": len(stems),
        "added": 0,
        "dropped": 0,
        "wrongful_removals": 0,
        "provenance": 0,
        "pii": 0,
        "images": 0,
        "ordering_failures": 0,
        "structural": TALLY,
        "tunable": {**TALLY, "precision": tunable, "recall": tunable},
        "punctuation": 0,
        "appendix_rate": 0.7,
        "label_failures": 0,
        "errors": 0,
        "retries": 0,
        "retries_fired": 2,
        "retry_chars_placed": 25,
        "retry_cost_usd": 0.01,
        "input_tokens": 1000,
        "output_tokens": 500,
    }
    return {
        "totals": totals,
        "per_layout": {"single-column": totals},
        "config": {"provider": "p", "model": model, "effort": "medium"},
        "versions": copy.deepcopy(versions),
        "tokens": {"input": 1000, "output": 500},
        "cost_usd": {"labelling": cost, "this_run": cost},
        "wall_time_seconds": seconds,
        "cache": {"enabled": True, "read": False, "hits": hits, "live_calls": 2},
        "retries": 0,
        "thresholds": THRESHOLDS,
        "gate": {"passed": passed, "failures": [] if passed else [{"metric": "x"}]},
        "documents": [{"document": stem} for stem in stems],
    }


def three(label, **kw):
    return [(label, f"{label}-{n}.json", report(**kw)) for n in (1, 2, 3)]


def test_the_record_holds_both_sides_with_runs_spread_and_totals():
    runs = three("sonnet", model="s", cost=1.6) + [
        ("gpt", "g1.json", report(model="g", cost=1.0, seconds=90.0, passed=False)),
        ("gpt", "g2.json", report(model="g", cost=1.2, seconds=95.0)),
    ]
    record = compare(runs, date="2026-11-01")

    assert record["date"] == "2026-11-01"
    assert record["versions"] == VERSIONS
    assert record["documents_per_run"] == 2
    assert record["thresholds_applied"] == THRESHOLDS
    reference, gpt = record["reference"], record["candidates"]["gpt"]
    assert reference["label"] == "sonnet"
    assert reference["config"]["model"] == "s"
    assert [run["run"] for run in reference["runs"]] == [1, 2, 3]
    assert reference["runs"][0]["source"] == "sonnet-1.json"
    assert reference["gates_passed"] == 3
    assert gpt["gates_passed"] == 1
    assert gpt["runs"][0]["gate"]["failures"] == [{"metric": "x"}]
    assert gpt["spread"]["cost_usd"] == {
        "runs": [1.0, 1.2],
        "min": 1.0,
        "max": 1.2,
        "range": 0.2,
    }
    assert gpt["spread"]["wall_time_seconds"]["runs"] == [90.0, 95.0]
    assert gpt["spread"]["retries_fired"]["runs"] == [2, 2]
    assert gpt["total_cost_usd"] == 2.2
    assert record["total_cost_usd"] == {"sonnet": 4.8, "gpt": 2.2}
    assert gpt["runs"][0]["totals"]["retry_cost_usd"] == 0.01
    json.dumps(record)


@pytest.mark.parametrize(
    "change",
    [
        {"prompt": {"version": "1.4.0", "hash": "p2"}},
        {"retry_prompt": {"hash": "other"}},
        {"additions_schema": {"hash": "other"}},
    ],
)
def test_runs_on_different_versions_are_refused(change):
    other = report(versions={**VERSIONS, **change})
    runs = three("a") + [("b", "b.json", other)]
    with pytest.raises(CompareError, match="versions differ"):
        compare(runs, date="d")


def test_a_run_without_the_retry_versions_is_refused_beside_one_with_them():
    old = {k: v for k, v in VERSIONS.items() if k in ("prompt", "schema")}
    runs = three("a") + [("b", "b.json", report(versions=old))]
    with pytest.raises(CompareError, match="versions differ"):
        compare(runs, date="d")


def test_a_different_golden_set_is_refused():
    runs = three("a") + [("b", "b.json", report(stems=("c01__a", "c02__a")))]
    with pytest.raises(CompareError, match="documents differ"):
        compare(runs, date="d")


def test_a_mixed_configuration_within_a_side_is_refused():
    runs = [
        ("a", "1.json", report(model="x")),
        ("a", "2.json", report(model="y")),
        ("b", "3.json", report(model="z")),
    ]
    with pytest.raises(CompareError, match="configurations within 'a'"):
        compare(runs, date="d")


def test_a_run_that_replayed_the_cache_is_refused_naming_it():
    runs = three("a") + [("b", "cached.json", report(hits=3))]
    with pytest.raises(CompareError, match="cached.json replayed 3"):
        compare(runs, date="d")


def test_one_label_or_no_reports_is_refused():
    with pytest.raises(CompareError, match="at least two labels"):
        compare(three("a"), date="d")
    with pytest.raises(CompareError, match="no reports"):
        compare([], date="d")


def test_the_command_writes_the_record_and_prints_the_gates(tmp_path, capsys):
    paths = []
    for label, n in [("a", 1), ("a", 2), ("b", 1)]:
        path = tmp_path / f"{label}{n}.json"
        path.write_text(json.dumps(report(model=label)), encoding="utf-8")
        paths.append(f"{label}={path}")
    out = tmp_path / "record.json"

    assert main([*paths, "--out", str(out), "--date", "2026-11-01"]) == 0

    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["date"] == "2026-11-01"
    assert list(record["candidates"]) == ["b"]
    assert "a: 2 of 2 runs passed" in capsys.readouterr().out


def test_the_command_refuses_with_exit_2_and_writes_nothing(tmp_path, capsys):
    good = tmp_path / "g.json"
    good.write_text(json.dumps(report()), encoding="utf-8")
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps(report(stems=("c09__z",))), encoding="utf-8")
    out = tmp_path / "record.json"

    assert main([f"a={good}", f"b={bad}", "--out", str(out), "--date", "d"]) == 2

    assert not out.exists()
    assert "refused: documents differ" in capsys.readouterr().err


def test_a_malformed_pair_or_missing_file_is_refused(tmp_path):
    out = str(tmp_path / "o.json")
    assert main(["nolabel", "--out", out, "--date", "d"]) == 2
    assert main(["a=missing.json", "--out", out, "--date", "d"]) == 2


def test_two_labels_with_the_same_configuration_are_refused():
    runs = three("sonnet", model="same") + three("gpt", model="same")
    with pytest.raises(CompareError, match="'sonnet' and 'gpt' carry the same config"):
        compare(runs, date="d")


def test_a_missing_precision_is_refused_naming_the_run_and_metric():
    broken = report(model="g")
    broken["totals"]["tunable"] = {**TALLY, "precision": None}
    runs = three("a") + [("b", "none.json", broken)]
    with pytest.raises(CompareError, match="none.json has no value for tunable_prec"):
        compare(runs, date="d")
