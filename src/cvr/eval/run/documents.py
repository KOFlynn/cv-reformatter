"""The generated documents the eval runs over, each with its Candidate and
manifest, and the ``--layout``/``--candidate`` filters over them."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cvr.golden import CANDIDATES_DIR, Candidate, Manifest, load_candidate
from cvr.golden.generate import GENERATED_DIR

__all__ = ["Document", "document", "generated_stems", "select"]


@dataclass(frozen=True)
class Document:
    """One generated source document with its Candidate and manifest."""

    candidate: Candidate
    manifest: Manifest
    source: bytes

    @property
    def stem(self) -> str:
        return f"{self.manifest.candidate_id}__{self.manifest.layout}"


def document(stem: str, directory: Path = GENERATED_DIR) -> Document:
    """The generated document ``<candidate>__<layout>`` and its ground truth."""
    manifest = Manifest.model_validate_json(
        (directory / f"{stem}.manifest.json").read_text(encoding="utf-8")
    )
    candidate = load_candidate(CANDIDATES_DIR / f"{manifest.candidate_id}.json")
    return Document(candidate, manifest, (directory / f"{stem}.docx").read_bytes())


def generated_stems(directory: Path = GENERATED_DIR) -> list[str]:
    """Every generated document's stem, sorted: candidate, then layout."""
    return sorted(path.name.removesuffix(".docx") for path in directory.glob("*.docx"))


def select(
    stems: Sequence[str],
    layouts: Sequence[str] = (),
    candidates: Sequence[str] = (),
) -> list[str]:
    """The stems whose layout is one of ``layouts`` and whose candidate is one
    of ``candidates``; an empty filter admits everything. A filter value that
    matches no document at all is an error, not an empty run that passes."""
    split = [stem.split("__", 1) for stem in stems]
    for name, wanted, known in (
        ("layout", layouts, {layout for _, layout in split}),
        ("candidate", candidates, {candidate for candidate, _ in split}),
    ):
        unknown = sorted(set(wanted) - known)
        if unknown:
            raise ValueError(
                f"unknown {name} {', '.join(unknown)}; known: {', '.join(sorted(known))}"
            )
    return [
        stem
        for stem, (candidate, layout) in zip(stems, split, strict=True)
        if (not layouts or layout in layouts)
        and (not candidates or candidate in candidates)
    ]
