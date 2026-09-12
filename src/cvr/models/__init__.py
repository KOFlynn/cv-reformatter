"""Content model: ``CVContent`` and its entries.

Every string here is a candidate's own text, held verbatim. Typos, odd
capitalisation and punctuation are baked into the strings on purpose and
must never be normalised out: the golden set treats this model as ground
truth, and the pipeline must reproduce it word for word.

Depends on pydantic only; never on ``cvr.golden`` or ``cvr.eval``.
"""

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["CVContent", "DateValue", "EducationEntry", "ExperienceEntry"]


class _Strict(BaseModel):
    # Unknown keys are rejected so a typo in a fixture key fails fast rather
    # than silently dropping a field.
    model_config = ConfigDict(extra="forbid")


class DateValue(_Strict):
    """An entry date: the structured parts plus the hand-written expected output.

    ``expected`` is written by hand by the fixture author and is never derived
    from ``month``/``year``/``present`` by code. If the date formatter had a
    bug, deriving ``expected`` with it would let the bug cancel out on both
    sides of the comparison. There is no raw source string: the printed form
    is a Layout decision recorded in the manifest, not part of the fixture.
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


class ExperienceEntry(_Strict):
    title: str
    employer: str
    location: str | None = None
    start: DateValue | None = None
    end: DateValue | None = None
    bullets: list[str] = []


class EducationEntry(_Strict):
    institution: str
    qualification: str
    start: DateValue | None = None
    end: DateValue | None = None
    details: list[str] = []


class CVContent(_Strict):
    """Expected output content as plain strings, in expected output order.

    Absent sections are empty lists, never ``None``. Skills hold one item per
    comma- or bullet-separated source item, with parenthetical qualifiers
    attached. Minor sub-headings inside additional information ("Languages")
    are content lines and stay verbatim.
    """

    name: str
    profile: list[str] = []
    skills: list[str] = []
    education: list[EducationEntry] = []
    experience: list[ExperienceEntry] = []
    certifications: list[str] = []
    additional: list[str] = []
