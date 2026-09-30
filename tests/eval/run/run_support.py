"""The oracle labellers as the runner's labeller, and a thresholds file."""

from pathlib import Path

from pipeline.oracle import Imperfect, Oracle

from cvr.eval.run.cache import LabellerIdentity
from cvr.eval.run.documents import Document

__all__ = ["C04", "ORACLE", "imperfect", "oracle", "thresholds_file"]

ORACLE = LabellerIdentity(
    config={"provider": "oracle", "model": "oracle"},
    prompt_version="oracle",
    prompt_hash="oracle",
    schema_version="oracle",
    schema_hash="oracle",
)

# The four documents the runner tests use: one Candidate in every Layout.
C04 = ["c04__header-footer", "c04__single-column", "c04__text-box", "c04__two-column"]


def oracle(document: Document) -> Oracle:
    return Oracle(document.candidate, document.manifest)


def imperfect(damage):
    def live(document: Document) -> Imperfect:
        return Imperfect(oracle(document), damage)

    return live


def thresholds_file(
    directory: Path,
    placement_min: float = 0,
    appendix_max: float = 100,
    punctuation_hard: bool = False,
) -> Path:
    path = directory / "thresholds.yaml"
    path.write_text(
        f"placement_accuracy:\n  min: {placement_min}\n"
        f"appendix_rate:\n  max: {appendix_max}\n"
        f"punctuation_fidelity:\n  hard: {str(punctuation_hard).lower()}\n",
        encoding="utf-8",
    )
    return path
