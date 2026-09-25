"""The ``--layout``/``--candidate`` filters and the thresholds file."""

import pytest
import yaml

from cvr.eval.run.documents import generated_stems, select
from cvr.eval.run.thresholds import THRESHOLDS_FILE, Thresholds, load_thresholds

STEMS = generated_stems()


def test_every_generated_document_is_selected_by_default():
    assert len(STEMS) == 48
    assert select(STEMS) == STEMS


def test_filters_combine_and_repeat():
    assert select(STEMS, layouts=["text-box"], candidates=["c04"]) == ["c04__text-box"]
    assert len(select(STEMS, layouts=["text-box", "two-column"])) == 24
    assert len(select(STEMS, candidates=["c01", "c12"])) == 8


@pytest.mark.parametrize(
    "filters", [{"layouts": ["three-column"]}, {"candidates": ["c99"]}]
)
def test_a_filter_matching_nothing_is_an_error(filters):
    with pytest.raises(ValueError, match="unknown"):
        select(STEMS, **filters)


def test_the_committed_thresholds_are_the_placeholders():
    assert load_thresholds() == Thresholds(
        placement_min=0, appendix_max=100, punctuation_hard=False
    )
    assert "ticket 10" in THRESHOLDS_FILE.read_text(encoding="utf-8")


def _write(tmp_path, data):
    path = tmp_path / "thresholds.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


GOOD = {
    "placement_accuracy": {"min": 95},
    "appendix_rate": {"max": 3.5},
    "punctuation_fidelity": {"hard": True},
}


def test_thresholds_are_read_as_written(tmp_path):
    assert load_thresholds(_write(tmp_path, GOOD)) == Thresholds(95, 3.5, True)


@pytest.mark.parametrize(
    "data",
    [
        {**GOOD, "placement_accuracy": {"minimum": 95}},
        {k: v for k, v in GOOD.items() if k != "appendix_rate"},
        {**GOOD, "ordering": {"min": 100}},
    ],
)
def test_a_misspelt_or_missing_setting_is_an_error(tmp_path, data):
    with pytest.raises(ValueError, match="expected exactly"):
        load_thresholds(_write(tmp_path, data))


def test_punctuation_hard_must_be_a_boolean(tmp_path):
    data = {**GOOD, "punctuation_fidelity": {"hard": "yes please"}}
    with pytest.raises(TypeError):
        load_thresholds(_write(tmp_path, data))
