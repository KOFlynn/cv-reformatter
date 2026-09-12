"""Load Candidate JSON from ``fixtures/candidates/``, failing fast on a malformed file."""

from pathlib import Path

from pydantic import ValidationError

from cvr.golden.candidate import Candidate

__all__ = ["CANDIDATES_DIR", "CandidateLoadError", "load_candidate", "load_candidates"]

CANDIDATES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "candidates"


class CandidateLoadError(ValueError):
    """A Candidate file failed validation; the message starts with the file name."""


def load_candidate(path: Path) -> Candidate:
    try:
        candidate = Candidate.model_validate_json(path.read_bytes())
    except ValidationError as err:
        raise CandidateLoadError(f"{path.name}: {err}") from err
    if candidate.id != path.stem:
        raise CandidateLoadError(
            f"{path.name}: id {candidate.id!r} does not match the file name"
        )
    return candidate


def load_candidates(directory: Path = CANDIDATES_DIR) -> list[Candidate]:
    """Every ``*.json`` in ``directory``, in file-name order, validated."""
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise CandidateLoadError(f"no Candidate files in {directory}")
    return [load_candidate(path) for path in paths]
