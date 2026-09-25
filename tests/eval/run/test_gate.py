"""The gate over per-document totals: every hard gate fails the run whatever
the thresholds; thresholds apply to the run's totals and name the candidates
that fall short; punctuation is soft unless ``hard: true``."""

import pytest

from cvr.eval import Tally
from cvr.eval.run.report import Totals, gate
from cvr.eval.run.thresholds import Thresholds

CLEAN = Totals(
    documents=1,
    structural=Tally(10, 10, 10),
    tunable=Tally(20, 20, 20),
    appendix_tokens=0,
    content_tokens=100,
)
PLACEHOLDERS = Thresholds()


def _run(**damaged) -> dict[str, Totals]:
    """Three clean documents, and c02's damaged by ``damaged``."""
    bad = Totals(**{**vars_of(CLEAN), **damaged})
    return {"c01__single-column": CLEAN, "c02__text-box": bad, "c03__two-column": CLEAN}


def vars_of(totals: Totals) -> dict:
    return {name: getattr(totals, name) for name in totals.__dataclass_fields__}


def test_a_clean_run_passes():
    assert gate(_run(), PLACEHOLDERS) == []


@pytest.mark.parametrize(
    ("damage", "metric"),
    [
        ({"errors": 1}, "errors"),
        ({"added": 1}, "added_tokens"),
        ({"dropped": 2}, "dropped_tokens"),
        ({"provenance": 1}, "provenance_violations"),
        ({"pii": 1}, "pii_leak"),
        ({"images": 1}, "image_leak"),
        ({"ordering_failures": 1}, "ordering"),
        ({"structural": Tally(9, 10, 10)}, "placement_accuracy (structural)"),
        ({"structural": Tally(9, 9, 10)}, "placement_accuracy (structural)"),
    ],
)
def test_every_hard_gate_fails_the_run_irrespective_of_thresholds(damage, metric):
    loosest = Thresholds(placement_min=0, appendix_max=100, punctuation_hard=False)
    (failure,) = gate(_run(**damage), loosest)
    assert failure.metric == metric
    assert failure.candidates == ["c02"]
    assert failure.documents == ("c02__text-box",)
    assert failure.summary().startswith(f"{metric}: ")
    assert failure.summary().endswith("(c02)")


def test_punctuation_fails_only_when_hard():
    run = _run(punctuation=3)
    assert gate(run, PLACEHOLDERS) == []
    (failure,) = gate(run, Thresholds(punctuation_hard=True))
    assert failure.metric == "punctuation_fidelity"
    assert failure.candidates == ["c02"]


def test_the_placement_minimum_holds_precision_and_recall_on_the_totals():
    # c02 recalls 15 of 20 tunable leaves: 55 of 60 over the run, 91.67%.
    run = _run(tunable=Tally(15, 15, 20))
    assert gate(run, Thresholds(placement_min=91)) == []
    (failure,) = gate(run, Thresholds(placement_min=92))
    assert failure.metric == "placement_accuracy (tunable)"
    assert failure.detail == "recall 91.67% below the minimum 92%"
    assert failure.candidates == ["c02"]
    both = gate(_run(tunable=Tally(15, 20, 20)), Thresholds(placement_min=100))
    assert [f.detail.split()[0] for f in both] == ["precision", "recall"]


def test_the_appendix_maximum_holds_the_token_weighted_rate():
    # 30 appendix tokens over 300 content tokens: 10%, though c02 is at 30%.
    run = _run(appendix_tokens=30)
    assert gate(run, Thresholds(appendix_max=10)) == []
    (failure,) = gate(run, Thresholds(appendix_max=9.5))
    assert failure.metric == "appendix_rate"
    assert failure.detail == "10.00% above the maximum 9.5%"
    assert failure.candidates == ["c02"]


def test_failures_come_hard_gates_first_in_a_fixed_order():
    run = _run(pii=1, added=1, tunable=Tally(0, 0, 20))
    metrics = [f.metric for f in gate(run, Thresholds(placement_min=70))]
    assert metrics == ["added_tokens", "pii_leak", "placement_accuracy (tunable)"]
