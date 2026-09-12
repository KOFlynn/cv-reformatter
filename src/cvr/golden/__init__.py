"""Golden set: Candidates, Layouts and the generator. Depends on ``text`` and ``models`` only."""

from cvr.golden.candidate import PII, Candidate, Personal, Referee, Tag
from cvr.golden.loader import (
    CANDIDATES_DIR,
    CandidateLoadError,
    load_candidate,
    load_candidates,
)

__all__ = [
    "CANDIDATES_DIR",
    "PII",
    "Candidate",
    "CandidateLoadError",
    "Personal",
    "Referee",
    "Tag",
    "load_candidate",
    "load_candidates",
]
