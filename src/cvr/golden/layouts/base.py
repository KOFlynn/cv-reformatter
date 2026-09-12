"""The Layout interface, the rules every Layout shares, and the manifest.

A Layout renders any Candidate into one visual style of source document,
deterministically: same Candidate, same bytes. The base class owns what the
style matrix does not vary per column:

- entry order: dated entries in the Layout's fixed scramble, then undated
  entries in Candidate order, never scrambled among themselves;
- date printing: a literal date is printed verbatim whatever the date style,
  ``present`` prints the Layout's present text, everything else goes through
  the Layout's ``format_date``;
- the manifest, which records the layout decisions made and never Candidate
  content, so it cannot become a second ground truth;
- byte-stable packaging, so the document SHA is a real file hash.
"""

import hashlib
import io
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar, Literal

from docx.document import Document as DocumentType
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from pydantic import Field

from cvr.golden.candidate import Candidate
from cvr.models import DateValue, EducationEntry, ExperienceEntry, StrictModel
from cvr.text import CONFUSABLES

__all__ = [
    "GENERATOR_VERSION",
    "MANIFEST_VERSION",
    "Decisions",
    "FragmentPlacement",
    "Generated",
    "Layout",
    "Manifest",
    "Plan",
    "PlannedEntry",
    "PrintedDate",
    "Section",
]

# Bump when a Layout's output changes, so a manifest says which generator wrote it.
GENERATOR_VERSION = "0.1.0"
# Bump when the manifest schema changes.
MANIFEST_VERSION = 1

Section = Literal["experience", "education"]

# Fixed timestamps: python-docx stamps zip entries with the wall clock, which
# would make every regeneration a new file. Core properties are set to match.
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
_ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)

# python-docx's default template carries a Word 2010 duplicate of the styles
# part, a thumbnail, a hundred table styles and a latent-styles list: 800 KB
# of ballast in a stored zip. Everything a Layout may use survives the trim.
_DROPPED_DOCUMENT_RELS = (
    "http://schemas.microsoft.com/office/2007/relationships/stylesWithEffects",
    RT.CUSTOM_XML,
)
_KEPT_TABLE_STYLES = ("Normal Table", "Table Grid")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class PrintedDate(StrictModel):
    """The string a Layout printed for one entry date. ``entry`` indexes the
    section in Candidate order. The only Candidate-derived strings a manifest
    may carry."""

    section: Section
    entry: int
    which: Literal["start", "end"]
    printed: str


class FragmentPlacement(StrictModel):
    """Where an unplaceable fragment (by index into ``Candidate.unplaceable``) went."""

    index: int
    location: str


class Manifest(StrictModel):
    """The generator's own account of one document. Read by generator tests and
    humans, never by a metric."""

    candidate_id: str
    layout: str
    seed: int
    generator_version: str
    manifest_version: int
    dates: list[PrintedDate]
    experience_order: list[int] = Field(
        description="Candidate-order indices of experience entries, as emitted."
    )
    education_order: list[int] = Field(
        description="Candidate-order indices of education entries, as emitted."
    )
    contact_block: str
    confusables: list[str] = Field(
        description="Confusable characters injected, as U+XXXX, sorted."
    )
    photo: bool
    fragments: list[FragmentPlacement]
    document_sha256: str


@dataclass(frozen=True)
class PlannedEntry[E: (ExperienceEntry, EducationEntry)]:
    """One entry with the Layout's decisions already made: its position in
    Candidate order, and the date strings the Layout will print."""

    index: int
    entry: E
    start: str | None
    end: str | None

    @property
    def dated(self) -> bool:
        return self.start is not None or self.end is not None


@dataclass(frozen=True)
class Plan:
    """The base class's decisions for one Candidate: emit order and date strings.
    A Layout renders the Plan; it does not reorder or reformat."""

    experience: list[PlannedEntry[ExperienceEntry]]
    education: list[PlannedEntry[EducationEntry]]


@dataclass
class Decisions:
    """What a Layout reports back from ``render`` for the manifest."""

    contact_block: str
    photo: bool = False
    confusables: set[str] = field(default_factory=set)
    fragments: list[FragmentPlacement] = field(default_factory=list)

    def injected(self, char: str) -> None:
        """Record a confusable from the shared table as injected."""
        if char not in CONFUSABLES:
            raise ValueError(f"{char!r} is not in the confusable table")
        self.confusables.add(char)


@dataclass(frozen=True)
class Generated:
    document: bytes
    manifest: Manifest


class Layout(ABC):
    """Candidate in, document bytes and manifest out. Subclasses set ``name``,
    implement ``format_date`` and ``render``, and may override ``scramble``."""

    name: ClassVar[str]
    contact_block: ClassVar[str]
    present_text: ClassVar[str] = "Present"
    # Every Phase 0 Layout is a fixed permutation and draws nothing from a
    # seed; the manifest carries it so a Layout that ever did would have a slot.
    seed: ClassVar[int] = 0

    @abstractmethod
    def format_date(self, month: int | None, year: int) -> str:
        """The Layout's date style for a structured date; ``month`` may be absent."""

    @abstractmethod
    def render(
        self, candidate: Candidate, plan: Plan, decisions: Decisions
    ) -> DocumentType:
        """Build the document from the Plan, recording layout decisions."""

    def stem(self, candidate: Candidate) -> str:
        """The shared file stem of a Candidate's document and manifest."""
        return f"{candidate.id}__{self.name}"

    def scramble(self, section: Section, indices: list[int]) -> list[int]:
        """Reorder the dated entries of a section. The base emits Candidate order."""
        return indices

    def generate(self, candidate: Candidate) -> Generated:
        plan = self.plan(candidate)
        decisions = Decisions(contact_block=self.contact_block)
        document = self.render(candidate, plan, decisions)
        placed = sorted(placement.index for placement in decisions.fragments)
        if placed != list(range(len(candidate.unplaceable))):
            raise ValueError(
                f"{self.name}: unplaceable fragments placed {placed}, "
                f"expected every index below {len(candidate.unplaceable)}"
            )
        data = _stable_bytes(document, title=self.stem(candidate))
        manifest = Manifest(
            candidate_id=candidate.id,
            layout=self.name,
            seed=self.seed,
            generator_version=GENERATOR_VERSION,
            manifest_version=MANIFEST_VERSION,
            dates=_printed_dates(plan),
            experience_order=[planned.index for planned in plan.experience],
            education_order=[planned.index for planned in plan.education],
            contact_block=decisions.contact_block,
            confusables=sorted(f"U+{ord(char):04X}" for char in decisions.confusables),
            photo=decisions.photo,
            fragments=sorted(
                decisions.fragments, key=lambda placement: placement.index
            ),
            document_sha256=hashlib.sha256(data).hexdigest(),
        )
        return Generated(document=data, manifest=manifest)

    def plan(self, candidate: Candidate) -> Plan:
        return Plan(
            experience=self._plan_section("experience", candidate.content.experience),
            education=self._plan_section("education", candidate.content.education),
        )

    def print_date(self, date: DateValue) -> str:
        """Literal verbatim; present as the Layout's word; otherwise the Layout's style."""
        if date.literal is not None:
            return date.literal
        if date.present:
            return self.present_text
        if date.year is None:
            raise ValueError(f"date has neither year, literal nor present: {date!r}")
        return self.format_date(date.month, date.year)

    def _plan_section[E: (ExperienceEntry, EducationEntry)](
        self, section: Section, entries: list[E]
    ) -> list[PlannedEntry[E]]:
        planned = [
            PlannedEntry(
                index=index,
                entry=entry,
                start=self.print_date(entry.start) if entry.start else None,
                end=self.print_date(entry.end) if entry.end else None,
            )
            for index, entry in enumerate(entries)
        ]
        dated = {p.index: p for p in planned if p.dated}
        order = self.scramble(section, list(dated))
        if sorted(order) != sorted(dated):
            raise ValueError(f"{self.name}: scramble of {section} is not a permutation")
        return [dated[index] for index in order] + [p for p in planned if not p.dated]


def _printed_dates(plan: Plan) -> list[PrintedDate]:
    dates: list[PrintedDate] = []
    for section, planned in (
        ("experience", plan.experience),
        ("education", plan.education),
    ):
        for entry in sorted(planned, key=lambda p: p.index):
            for which, printed in (("start", entry.start), ("end", entry.end)):
                if printed is not None:
                    dates.append(
                        PrintedDate(
                            section=section,
                            entry=entry.index,
                            which=which,
                            printed=printed,
                        )
                    )
    return dates


def _trim(document: DocumentType) -> None:
    """Drop the default template's ballast; see ``_DROPPED_DOCUMENT_RELS``."""
    for rel in list(document.part.rels.values()):
        if rel.reltype in _DROPPED_DOCUMENT_RELS:
            document.part.drop_rel(rel.rId)
    package = document.part.package
    for rel in list(package.rels.values()):
        if rel.reltype == RT.THUMBNAIL:
            del package.rels[rel.rId]
    for style in list(document.styles):
        if style.type == WD_STYLE_TYPE.TABLE and style.name not in _KEPT_TABLE_STYLES:
            style.delete()
    latent = document.styles.element.find(f"{_W}latentStyles")
    if latent is not None:
        document.styles.element.remove(latent)


def _stable_bytes(document: DocumentType, title: str) -> bytes:
    """Serialise with fixed metadata and zip timestamps, stored not deflated, so
    the bytes are a pure function of the content on any platform."""
    _trim(document)
    props = document.core_properties
    props.title = title
    props.author = "cvr golden generator"
    props.last_modified_by = "cvr golden generator"
    props.created = _EPOCH
    props.modified = _EPOCH
    props.revision = 1
    raw = io.BytesIO()
    document.save(raw)
    stable = io.BytesIO()
    with (
        zipfile.ZipFile(raw) as source,
        zipfile.ZipFile(stable, "w", zipfile.ZIP_STORED) as target,
    ):
        for info in source.infolist():
            entry = zipfile.ZipInfo(info.filename, date_time=_ZIP_DATE_TIME)
            entry.compress_type = zipfile.ZIP_STORED
            entry.external_attr = info.external_attr
            target.writestr(entry, source.read(info))
    return stable.getvalue()
