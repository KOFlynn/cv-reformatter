"""Content model (``CVContent`` and its entries), the PII model (``PII``),
the removal rule ids (``RemovalRule``), and the source-side models the
pipeline passes between its nodes: ``SourceBlock``, ``Span``, ``Image``,
``Removal`` and ``Normalisation``.

Every string here is a candidate's own text, held verbatim. Typos, odd
capitalisation and punctuation are baked into the strings on purpose and
must never be normalised out: the golden set treats this model as ground
truth, and the pipeline must reproduce it word for word.

Depends on pydantic only; never on ``cvr.golden`` or ``cvr.eval``. ``PII``
lives here rather than in the golden set because ``eval`` consumes it too
and the two never import each other.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "PII",
    "BlockKind",
    "CVContent",
    "ContentReferences",
    "DateValue",
    "EducationEntry",
    "EducationReference",
    "ExperienceEntry",
    "ExperienceReference",
    "Image",
    "Labelling",
    "LabellingFailure",
    "LabellingResult",
    "Normalisation",
    "NormalisationRule",
    "Personal",
    "Referee",
    "Reference",
    "Removal",
    "RemovalLabel",
    "RemovalRule",
    "SourceBlock",
    "Span",
    "StrictModel",
    "TextRemovalRule",
]


class RemovalRule(StrEnum):
    """The named rules under which source text is deleted, never rewritten.

    Every removal is logged under its rule; the PII leak metric reports a hit
    under the rule that should have removed it. ``PHOTO`` and ``HEADING``
    remove things that are not fixture strings.
    """

    PHONE = "RM_PHONE"
    EMAIL = "RM_EMAIL"
    ADDRESS = "RM_ADDRESS"
    URL = "RM_URL"
    PHOTO = "RM_PHOTO"
    DOB = "RM_DOB"
    PERSONAL = "RM_PERSONAL"
    REFEREE = "RM_REFEREE"
    HEADING = "RM_HEADING"


class NormalisationRule(StrEnum):
    """The named rules under which the pipeline may modify candidate text.
    There is one: stripping invisible characters, at parse."""

    INVISIBLE = "NORM_INVISIBLE"


class StrictModel(BaseModel):
    """Base for every model loaded from JSON: unknown keys are rejected, so a
    typo in a key fails fast rather than silently dropping a field."""

    model_config = ConfigDict(extra="forbid")


# --- Source side: what the parser emits and every later node reads.

BlockKind = Literal["body", "table", "textbox", "header", "footer"]


class SourceBlock(StrictModel):
    """One unit of source text in reading order, with a stable identity.

    ``id`` is a real address in the file (``body:12``, ``table:12:r1:c0:3``,
    ``header:0:default:2``, ``textbox:12:0:3``), so the same file parsed twice
    gives the same ids and a block can be found again. ``text`` is raw: the
    parser strips invisible characters and touches nothing else.
    """

    id: str
    text: str
    kind: BlockKind


class Span(StrictModel):
    """A verified slice of a block: the only thing that ever reaches the
    rendered output. ``text`` is the raw slice ``block.text[start:end]``, so
    the renderer never has to find the block again."""

    block_id: str
    start: int = Field(ge=0)
    end: int
    text: str

    @model_validator(mode="after")
    def _text_is_the_slice(self) -> Self:
        if self.end <= self.start:
            raise ValueError(f"span {self.start}:{self.end} is empty or backwards")
        if len(self.text) != self.end - self.start:
            raise ValueError(
                f"span text has {len(self.text)} characters but the slice "
                f"{self.start}:{self.end} has {self.end - self.start}"
            )
        return self


class Image(StrictModel):
    """An embedded image, recorded by content hash: ``part`` is the package
    part name (``word/media/image1.png``), ``sha256`` the hex digest of its
    bytes, ``size`` their count. Every one is removed under RM_PHOTO at parse."""

    part: str
    sha256: str
    size: int = Field(ge=0)


class Removal(StrictModel):
    """One logged deletion: a slice of text or an image, under a named rule."""

    rule: RemovalRule
    subject: Span | Image


class Normalisation(StrictModel):
    """One logged modification of a block's text under a named rule: for
    NORM_INVISIBLE, the invisible characters stripped, in source order. The
    pre-strip text is discarded, so there are no positions to record."""

    rule: NormalisationRule
    block_id: str
    characters: list[str]


class DateValue(StrictModel):
    """An entry date: the structured parts plus the hand-written expected output.

    ``expected`` is written by hand by the Candidate's author and is never
    derived from ``month``/``year``/``present`` by code. If the date formatter had a
    bug, deriving ``expected`` with it would let the bug cancel out on both
    sides of the comparison. There is no raw source string: the printed form
    is a Layout decision recorded in the manifest, not part of the ground truth.
    """

    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = None
    present: bool = False
    literal: str | None = Field(
        default=None,
        description=(
            "Set when the date cannot be parsed ('Summer 2020'). The generator prints "
            "exactly this text and the pipeline passes it through untouched."
        ),
    )
    expected: str = Field(
        description=(
            "Hand-written expected output: 'MM/YYYY', 'YYYY', 'Present', or the literal. "
            "Never derived by code."
        ),
    )


class ExperienceEntry(StrictModel):
    title: str
    employer: str
    location: str | None = None
    start: DateValue | None = None
    end: DateValue | None = None
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(StrictModel):
    institution: str
    qualification: str
    start: DateValue | None = None
    end: DateValue | None = None
    details: list[str] = Field(default_factory=list)


class CVContent(StrictModel):
    """Expected output content as plain strings, in expected output order.

    Absent sections are empty lists, never ``None``. Skills hold one item per
    comma- or bullet-separated source item, with parenthetical qualifiers
    attached. Minor sub-headings inside additional information ("Languages")
    are content lines and stay verbatim.
    """

    name: str
    profile: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    additional: list[str] = Field(default_factory=list)


class Referee(StrictModel):
    """Removed under RM_REFEREE: the name, role and every contact line."""

    name: str
    role: str | None = None
    contact: list[str] = Field(default_factory=list)


class Personal(StrictModel):
    """Removed under RM_PERSONAL."""

    nationality: str | None = None
    marital_status: str | None = None


class PII(StrictModel):
    """Values that must be removed, grouped so each key maps to exactly one removal rule.

    ``phone`` RM_PHONE, ``email`` RM_EMAIL, ``address`` RM_ADDRESS (one line per
    item), ``urls`` RM_URL, ``dob`` RM_DOB, ``personal`` RM_PERSONAL, ``referees``
    RM_REFEREE. There is no ``photo`` key: the photo is a Layout decision and
    RM_PHOTO has no Candidate value, as RM_HEADING has none.
    """

    phone: str | None = None
    email: str | None = None
    address: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    dob: str | None = None
    personal: Personal = Field(default_factory=Personal)
    referees: list[Referee] = Field(default_factory=list)


# --- Labelling: what the labeller hands the verifier. The JSON schema of
# ``Labelling`` is what the LLM is asked to fill, so every property is
# required and nullable rather than optional (strict-compatible, ADR-0009).

# The eight rules the LLM may label text under. RM_PHOTO is never the LLM's:
# the parser removes every image deterministically.
TextRemovalRule = Literal[
    RemovalRule.PHONE,
    RemovalRule.EMAIL,
    RemovalRule.ADDRESS,
    RemovalRule.URL,
    RemovalRule.DOB,
    RemovalRule.PERSONAL,
    RemovalRule.REFEREE,
    RemovalRule.HEADING,
]


class Reference(StrictModel):
    """The LLM's claim that a verbatim quote from a block belongs somewhere.
    The quote is never optional: a reference without one cannot be verified."""

    block_id: str
    quote: str


class ExperienceReference(StrictModel):
    """One experience entry as references. ``dates`` is one reference to the
    whole range as printed; code splits it (transform)."""

    title: Reference | None
    employer: Reference | None
    location: Reference | None
    dates: Reference | None
    bullets: list[Reference]


class EducationReference(StrictModel):
    institution: Reference | None
    qualification: Reference | None
    dates: Reference | None
    details: list[Reference]


class ContentReferences(StrictModel):
    """``CVContent`` with a reference in place of every string."""

    name: Reference | None
    profile: list[Reference]
    skills: list[Reference]
    education: list[EducationReference]
    experience: list[ExperienceReference]
    certifications: list[Reference]
    additional: list[Reference]


class RemovalLabel(StrictModel):
    """The LLM's claim that a quote should be removed under one of the eight
    text rules."""

    rule: TextRemovalRule
    block_id: str
    quote: str


class Labelling(StrictModel):
    """A usable answer from the labeller: the content tree and the removals."""

    content: ContentReferences
    removals: list[RemovalLabel]


class LabellingFailure(StrictModel):
    """The labeller's answer for the whole document was unusable (malformed
    or schema-invalid). The job still completes: every block is residue."""

    reason: str


LabellingResult = Labelling | LabellingFailure
