"""The generate command: every Candidate through every Layout to disk, stably,
and the committed pairs kept in step with the code."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from docx_text import all_text

from cvr.golden import CANDIDATES_DIR, LAYOUTS, Manifest, load_candidates
from cvr.golden.generate import GENERATED_DIR, generate_all, stem

CANDIDATES = load_candidates(CANDIDATES_DIR)
STEMS = [stem(candidate, layout) for candidate in CANDIDATES for layout in LAYOUTS]


def read_manifest(directory: Path, name: str) -> Manifest:
    return Manifest.model_validate_json(
        (directory / f"{name}.manifest.json").read_bytes()
    )


def test_generate_all_writes_a_document_and_manifest_pair_per_stem(tmp_path):
    written = generate_all(out_dir=tmp_path)
    names = sorted(path.name for path in written)
    assert names == sorted(
        [f"{s}.docx" for s in STEMS] + [f"{s}.manifest.json" for s in STEMS]
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == names
    assert "c01__single-column" in STEMS


def test_manifest_file_is_json_with_the_document_sha(tmp_path):
    generate_all(out_dir=tmp_path)
    for name in STEMS:
        manifest = read_manifest(tmp_path, name)
        raw = json.loads((tmp_path / f"{name}.manifest.json").read_text("utf-8"))
        assert manifest.candidate_id, name
        assert raw["document_sha256"] == manifest.document_sha256


@pytest.mark.parametrize("name", STEMS)
def test_regenerating_gives_identical_text_and_manifest_sha(tmp_path, name):
    first, second = tmp_path / "first", tmp_path / "second"
    generate_all(out_dir=first)
    generate_all(out_dir=second)
    assert all_text(first / f"{name}.docx") == all_text(second / f"{name}.docx"), (
        f"{name}.docx: text differs between two generations"
    )
    assert (
        read_manifest(first, name).document_sha256
        == read_manifest(second, name).document_sha256
    ), f"{name}.manifest.json: document SHA differs between two generations"


@pytest.mark.parametrize("name", STEMS)
def test_committed_pair_matches_a_fresh_generation(tmp_path, name):
    """The committed golden set must be what the current code produces, or eval
    runs would measure against documents no Layout would write."""
    generate_all(out_dir=tmp_path)
    committed_doc = GENERATED_DIR / f"{name}.docx"
    assert committed_doc.exists(), f"{committed_doc.name} is not committed"
    assert all_text(committed_doc) == all_text(tmp_path / f"{name}.docx"), (
        f"{name}.docx: committed text differs from a fresh generation; "
        "run `uv run python -m cvr.golden.generate`"
    )
    assert read_manifest(GENERATED_DIR, name) == read_manifest(tmp_path, name), (
        f"{name}.manifest.json: committed manifest differs from a fresh generation; "
        "run `uv run python -m cvr.golden.generate`"
    )


def test_generated_directory_holds_exactly_the_registered_pairs():
    stems = {path.name.split(".", 1)[0] for path in GENERATED_DIR.glob("*.*")}
    assert stems == set(STEMS)


def test_module_runs_as_a_command(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "cvr.golden.generate", "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "c01__single-column.docx").exists()
    assert "c01__single-column" in result.stdout


def test_no_randomness_anywhere_in_the_golden_package():
    package = Path(__import__("cvr.golden", fromlist=["golden"]).__file__).parent
    offenders = [
        path.relative_to(package)
        for path in package.rglob("*.py")
        if "random" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
