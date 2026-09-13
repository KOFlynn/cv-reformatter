"""The generate command: every Candidate through every Layout to disk, stably,
and the committed pairs kept in step with the code."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from docx_text import all_text

import cvr.golden
from cvr.golden import CANDIDATES_DIR, LAYOUTS, Manifest, load_candidates
from cvr.golden.generate import GENERATED_DIR, generate_all

CANDIDATES = load_candidates(CANDIDATES_DIR)
STEMS = [layout.stem(candidate) for candidate in CANDIDATES for layout in LAYOUTS]


def read_manifest(directory: Path, name: str) -> Manifest:
    return Manifest.model_validate_json(
        (directory / f"{name}.manifest.json").read_bytes()
    )


# One generation of the whole set per fixture, shared by every case in the
# module: the per-stem cases stay so that a failure names the file that
# drifted, but generating the set once per stem made the module quadratic in
# the size of the golden set.
def _generation(label: str):
    @pytest.fixture(scope="module", name=label)
    def generation(tmp_path_factory) -> Path:
        out_dir = tmp_path_factory.mktemp(label)
        generate_all(out_dir=out_dir)
        return out_dir

    return generation


fresh = _generation("fresh")
fresh_again = _generation("fresh_again")


def test_generate_all_writes_a_document_and_manifest_pair_per_stem(tmp_path):
    written = generate_all(out_dir=tmp_path)
    names = sorted(path.name for path in written)
    assert names == sorted(
        [f"{s}.docx" for s in STEMS] + [f"{s}.manifest.json" for s in STEMS]
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == names
    assert "c01__single-column" in STEMS


def test_manifest_file_is_json_with_the_document_sha(fresh):
    for name in STEMS:
        manifest = read_manifest(fresh, name)
        raw = json.loads((fresh / f"{name}.manifest.json").read_text("utf-8"))
        assert manifest.candidate_id, name
        assert raw["document_sha256"] == manifest.document_sha256


@pytest.mark.parametrize("name", STEMS)
def test_regenerating_gives_identical_text_and_manifest_sha(fresh, fresh_again, name):
    assert all_text(fresh / f"{name}.docx") == all_text(fresh_again / f"{name}.docx"), (
        f"{name}.docx: text differs between two generations"
    )
    assert (
        read_manifest(fresh, name).document_sha256
        == read_manifest(fresh_again, name).document_sha256
    ), f"{name}.manifest.json: document SHA differs between two generations"


@pytest.mark.parametrize("name", STEMS)
def test_committed_pair_matches_a_fresh_generation(fresh, name):
    """The committed golden set must be what the current code produces, or eval
    runs would measure against documents no Layout would write."""
    committed_doc = GENERATED_DIR / f"{name}.docx"
    assert committed_doc.exists(), f"{committed_doc.name} is not committed"
    assert all_text(committed_doc) == all_text(fresh / f"{name}.docx"), (
        f"{name}.docx: committed text differs from a fresh generation; "
        "run `uv run python -m cvr.golden.generate`"
    )
    assert read_manifest(GENERATED_DIR, name) == read_manifest(fresh, name), (
        f"{name}.manifest.json: committed manifest differs from a fresh generation; "
        "run `uv run python -m cvr.golden.generate`"
    )


def test_generated_directory_holds_exactly_the_registered_pairs():
    stems = {path.name.split(".", 1)[0] for path in GENERATED_DIR.glob("*.*")}
    assert stems == set(STEMS)


def test_the_set_is_every_candidate_through_every_style_matrix_layout():
    """Coverage is the product, not a sample: each of the twelve Candidates
    through each of the spec's four Layouts, so the per-layout eval breakdown
    has every cell. That the directory holds exactly these stems is the
    previous test."""
    layouts = ["single-column", "two-column", "text-box", "header-footer"]
    candidate_ids = [f"c{n:02d}" for n in range(1, 13)]
    assert [layout.name for layout in LAYOUTS] == layouts
    assert [candidate.id for candidate in CANDIDATES] == candidate_ids
    assert STEMS == [f"{c}__{layout}" for c in candidate_ids for layout in layouts]
    assert len(STEMS) == 48


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
    package = Path(cvr.golden.__file__).parent
    offenders = [
        path.relative_to(package)
        for path in package.rglob("*.py")
        if re.search(
            r"^\s*(import random|from random )", path.read_text("utf-8"), re.MULTILINE
        )
    ]
    assert offenders == []
