"""The oracle labeller: answers from a Candidate what the LLM should answer.

Given the parsed blocks, it locates every content string, PII value and
referee line of the Candidate (canonicalised both sides, as the Phase 0
source-coverage test does) and emits the references a perfect labeller
would: each a block id plus the raw slice of that block, entries in the order
the document prints them, each entry's dates as one reference to the whole
range as printed. **A string it cannot locate raises ``OracleMiss``**: that
means the fixture or the parser is wrong, and a test must fail on it rather
than quietly lose coverage on exactly the document that is broken.

Locating mirrors the verifier's fill order (removals, then content in
tree-walk order), and every located range is taken, so a repeated string
takes its next free occurrence. Among free occurrences the oracle prefers,
in turn: the block a hint names (an entry's location is looked for on its
employer's line first); an occurrence that fills its block but for
separators (the address line ``Manchester`` over the ``Manchester`` in an
employer line); then the first in block order.

The source headings are not the Candidate's and are left to the verifier's
heading backstop, which is what the golden set's heading vocabulary is for.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from cvr.golden import Candidate, Manifest
from cvr.models import (
    PII,
    ContentReferences,
    EducationEntry,
    EducationReference,
    ExperienceEntry,
    ExperienceReference,
    Labelling,
    LabellingFailure,
    LabellingResult,
    Reference,
    RemovalReference,
    RemovalRule,
    SourceBlock,
)
from cvr.text import (
    Canonical,
    canonicalise,
    canonicalise_with_offsets,
    is_separator_residue,
)

__all__ = [
    "UNLOCATABLE",
    "Imperfect",
    "Oracle",
    "OracleMiss",
    "location_claims_the_employer_line",
    "omit_first_bullet",
    "perfect_labelling",
    "schema_invalid",
    "unlocatable_title",
]


class OracleMiss(AssertionError):
    """A Candidate string the oracle could not find in the parsed blocks."""


@dataclass(frozen=True, slots=True)
class _Occurrence:
    block: int
    start: int  # canonical offsets
    end: int


@dataclass
class _Locator:
    """The parsed blocks, canonicalised once, and the ranges already taken."""

    blocks: Sequence[SourceBlock]
    where: str
    canonical: list[Canonical] = field(init=False)
    taken: list[list[tuple[int, int]]] = field(init=False)

    def __post_init__(self) -> None:
        self.canonical = [canonicalise_with_offsets(b.text) for b in self.blocks]
        self.taken = [[] for _ in self.blocks]

    def reference(self, value: str, *, hint: int | None = None) -> Reference:
        return self._take(self._find([value], hint), value)

    def range_reference(self, first: str, last: str) -> Reference:
        """One reference from ``first`` through ``last`` in one block: an
        entry's date range as printed, separator and all."""
        return self._take(self._find([first, last], None), f"{first} .. {last}")

    def block_of(self, reference: Reference) -> int:
        return next(i for i, b in enumerate(self.blocks) if b.id == reference.block_id)

    def _find(self, values: list[str], hint: int | None) -> _Occurrence | None:
        needles = [canonicalise(value) for value in values]
        found: list[tuple[tuple[bool, bool, int, int], _Occurrence]] = []
        for index, canonical in enumerate(self.canonical):
            for occurrence in self._occurrences(index, canonical.text, needles):
                rank = (
                    index != hint,
                    not self._fills(canonical, occurrence),
                    index,
                    occurrence.start,
                )
                found.append((rank, occurrence))
        return min(found, key=lambda item: item[0])[1] if found else None

    def _occurrences(self, index: int, text: str, needles: list[str]):
        """Every free occurrence of the needles in order in one block, the
        first starting at each place it occurs."""
        at = text.find(needles[0])
        while at != -1:
            end, position = at, at
            for needle in needles:
                found = text.find(needle, position)
                if found == -1:
                    return
                end = position = found + len(needle)
            if not any(s < end and at < e for s, e in self.taken[index]):
                yield _Occurrence(index, at, end)
            at = text.find(needles[0], at + 1)

    @staticmethod
    def _fills(canonical: Canonical, occurrence: _Occurrence) -> bool:
        rest = canonical.text[: occurrence.start] + canonical.text[occurrence.end :]
        return is_separator_residue(rest)

    def _take(self, occurrence: _Occurrence | None, what: str) -> Reference:
        if occurrence is None:
            raise OracleMiss(f"{self.where}: cannot locate {what!r} in any block")
        self.taken[occurrence.block].append((occurrence.start, occurrence.end))
        canonical = self.canonical[occurrence.block]
        return Reference(
            block_id=self.blocks[occurrence.block].id,
            quote=canonical.raw_slice(occurrence.start, occurrence.end),
        )


def _pii_values(pii: PII) -> list[tuple[RemovalRule, str]]:
    """Every PII value and referee line with the rule that removes it, in
    PII field order."""
    values = [
        (RemovalRule.PHONE, pii.phone),
        (RemovalRule.EMAIL, pii.email),
        *((RemovalRule.ADDRESS, line) for line in pii.address),
        *((RemovalRule.URL, url) for url in pii.urls),
        (RemovalRule.DOB, pii.dob),
        (RemovalRule.PERSONAL, pii.personal.nationality),
        (RemovalRule.PERSONAL, pii.personal.marital_status),
    ]
    for referee in pii.referees:
        values += [(RemovalRule.REFEREE, referee.name)]
        values += [(RemovalRule.REFEREE, referee.role)]
        values += [(RemovalRule.REFEREE, line) for line in referee.contact]
    return [(rule, value) for rule, value in values if value is not None]


def _printed_dates(manifest: Manifest, section: str, index: int) -> list[str]:
    """The dates the Layout printed for one entry, start before end."""
    printed = {
        date.which: date.printed
        for date in manifest.dates
        if date.section == section and date.entry == index
    }
    return [printed[which] for which in ("start", "end") if which in printed]


def _dates(locator: _Locator, printed: list[str]) -> Reference | None:
    if not printed:
        return None
    if len(printed) == 1:
        return locator.reference(printed[0])
    return locator.range_reference(printed[0], printed[1])


def _education(
    locator: _Locator, entry: EducationEntry, printed: list[str]
) -> EducationReference:
    return EducationReference(
        institution=locator.reference(entry.institution),
        qualification=locator.reference(entry.qualification),
        dates=_dates(locator, printed),
        details=[locator.reference(detail) for detail in entry.details],
    )


def _experience(
    locator: _Locator, entry: ExperienceEntry, printed: list[str]
) -> ExperienceReference:
    title = locator.reference(entry.title)
    employer = locator.reference(entry.employer)
    location = (
        None
        if entry.location is None
        else locator.reference(entry.location, hint=locator.block_of(employer))
    )
    return ExperienceReference(
        title=title,
        employer=employer,
        location=location,
        dates=_dates(locator, printed),
        bullets=[locator.reference(bullet) for bullet in entry.bullets],
    )


def perfect_labelling(
    candidate: Candidate, manifest: Manifest, blocks: Sequence[SourceBlock]
) -> Labelling:
    """What a perfect labeller answers for ``candidate`` printed as
    ``manifest`` says, over ``blocks``. Raises ``OracleMiss``."""
    locator = _Locator(blocks, f"{candidate.id}__{manifest.layout}")
    removals = []
    for rule, value in _pii_values(candidate.pii):
        reference = locator.reference(value)
        removals.append(
            RemovalReference(
                rule=rule, block_id=reference.block_id, quote=reference.quote
            )
        )
    content = candidate.content
    name = locator.reference(content.name)
    profile = [locator.reference(text) for text in content.profile]
    skills = [locator.reference(text) for text in content.skills]
    education = [
        _education(
            locator,
            content.education[i],
            _printed_dates(manifest, "education", i),
        )
        for i in manifest.education_order
    ]
    experience = [
        _experience(
            locator,
            content.experience[i],
            _printed_dates(manifest, "experience", i),
        )
        for i in manifest.experience_order
    ]
    certifications = [locator.reference(text) for text in content.certifications]
    additional = [locator.reference(text) for text in content.additional]
    return Labelling(
        content=ContentReferences(
            name=name,
            profile=profile,
            skills=skills,
            education=education,
            experience=experience,
            certifications=certifications,
            additional=additional,
        ),
        removals=removals,
    )


@dataclass(frozen=True)
class Oracle:
    """The perfect oracle as a labeller: blocks in, ``perfect_labelling``
    out."""

    candidate: Candidate
    manifest: Manifest

    def __call__(self, blocks: Sequence[SourceBlock]) -> Labelling:
        return perfect_labelling(self.candidate, self.manifest, blocks)


# --- The imperfect oracles: the perfect answer, damaged in one known way.
# Each damages the first experience entry the document prints, which every
# Candidate has, with bullets and an employer line.


def omit_first_bullet(labelling: Labelling) -> Labelling:
    """Leave the first bullet unreferenced, as a labeller that missed it."""
    entry = labelling.content.experience[0]
    damaged = entry.model_copy(update={"bullets": entry.bullets[1:]})
    return _with_first_experience(labelling, damaged)


UNLOCATABLE = "Chief Imagination Officer"


def unlocatable_title(labelling: Labelling) -> Labelling:
    """Quote a title that is not in its block, as a labeller that rewrote it."""
    entry = labelling.content.experience[0]
    assert entry.title is not None
    title = entry.title.model_copy(update={"quote": UNLOCATABLE})
    return _with_first_experience(labelling, entry.model_copy(update={"title": title}))


def location_claims_the_employer_line(labelling: Labelling) -> Labelling:
    """Quote the whole employer line as the location: the employer, claimed
    first in tree-walk order, already holds part of that range."""
    entry = labelling.content.experience[0]
    assert entry.employer is not None and entry.location is not None
    location = entry.location.model_copy(
        update={"quote": f"{entry.employer.quote}, {entry.location.quote}"}
    )
    return _with_first_experience(
        labelling, entry.model_copy(update={"location": location})
    )


def schema_invalid(labelling: Labelling) -> LabellingFailure:
    """What the real labeller returns for an answer that fails the schema."""
    return LabellingFailure(reason="answer failed schema validation")


def _with_first_experience(
    labelling: Labelling, entry: ExperienceReference
) -> Labelling:
    experience = [entry, *labelling.content.experience[1:]]
    content = labelling.content.model_copy(update={"experience": experience})
    return labelling.model_copy(update={"content": content})


@dataclass(frozen=True)
class Imperfect:
    """The perfect oracle's answer, passed through ``damage``."""

    oracle: Oracle
    damage: Callable[[Labelling], LabellingResult]

    def __call__(self, blocks: Sequence[SourceBlock]) -> LabellingResult:
        return self.damage(self.oracle(blocks))
