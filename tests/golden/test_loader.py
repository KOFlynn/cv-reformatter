import json

import pytest

from cvr.golden import CANDIDATES_DIR, CandidateLoadError, load_candidates


def _c01_as_dict() -> dict:
    return json.loads((CANDIDATES_DIR / "c01.json").read_text(encoding="utf-8"))


def _write(directory, name: str, data: dict) -> None:
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


def test_unknown_tag_is_rejected_with_the_file_name(tmp_path):
    data = _c01_as_dict()
    data["tags"] = ["not-a-tag"]
    _write(tmp_path, "c01.json", data)
    with pytest.raises(CandidateLoadError, match=r"(?s)c01\.json.*not-a-tag"):
        load_candidates(tmp_path)


def test_missing_field_is_rejected_with_the_file_name(tmp_path):
    data = _c01_as_dict()
    del data["content"]["name"]
    _write(tmp_path, "c01.json", data)
    with pytest.raises(CandidateLoadError, match=r"(?s)c01\.json.*name"):
        load_candidates(tmp_path)


def test_date_without_expected_is_rejected_with_the_file_name(tmp_path):
    data = _c01_as_dict()
    del data["content"]["experience"][0]["start"]["expected"]
    _write(tmp_path, "c01.json", data)
    with pytest.raises(CandidateLoadError, match=r"(?s)c01\.json.*expected"):
        load_candidates(tmp_path)


def test_id_must_match_the_file_name(tmp_path):
    _write(tmp_path, "c99.json", _c01_as_dict())
    with pytest.raises(CandidateLoadError, match=r"(?s)c99\.json.*c01"):
        load_candidates(tmp_path)


def test_empty_directory_is_an_error_not_an_empty_golden_set(tmp_path):
    with pytest.raises(CandidateLoadError):
        load_candidates(tmp_path)
