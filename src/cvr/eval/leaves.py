"""What a CVContent is made of: leaves, grouped by field type.

Alignment scores entries by leaf overlap and placement tallies leaves by
field, so the one decomposition lives here and both read it. Strings are
held raw; the caller canonicalises at the point of comparison.
"""

from dataclasses import dataclass
from enum import StrEnum

from cvr.models import CVContent, DateValue, EducationEntry, ExperienceEntry

__all__ = ["Entry", "FieldType", "Leaves", "content_leaves", "entry_leaves"]

Entry = ExperienceEntry | EducationEntry


class FieldType(StrEnum):
    """Every kind of leaf, structural ones first.

    Structural leaves identify an entry or the candidate and gate at 100%;
    the rest are free text on the tunable threshold. Start and end dates are
    one type: a date is a date wherever it sits.
    """

    NAME = "name"
    TITLE = "title"
    EMPLOYER = "employer"
    LOCATION = "location"
    DATE = "date"
    INSTITUTION = "institution"
    QUALIFICATION = "qualification"
    PROFILE = "profile"
    SKILL = "skill"
    BULLET = "bullet"
    DETAIL = "detail"
    CERTIFICATION = "certification"
    ADDITIONAL = "additional"

    @property
    def structural(self) -> bool:
        return self in _STRUCTURAL


_STRUCTURAL = frozenset(
    {
        FieldType.NAME,
        FieldType.TITLE,
        FieldType.EMPLOYER,
        FieldType.LOCATION,
        FieldType.DATE,
        FieldType.INSTITUTION,
        FieldType.QUALIFICATION,
    }
)


@dataclass(frozen=True, slots=True)
class Leaves:
    """The leaves of one entry, or of the top level, grouped by field type.

    Scalar fields hold one slot each (``DATE`` holds two: start, end), an
    absent optional scalar being ``None``; list fields hold their items.
    """

    scalars: dict[FieldType, tuple[str | None, ...]]
    lists: dict[FieldType, tuple[str, ...]]

    def present(self) -> list[str]:
        """Every leaf that is actually there, in field order."""
        scalars = [s for slots in self.scalars.values() for s in slots if s is not None]
        return [*scalars, *(i for items in self.lists.values() for i in items)]


def _expected(date: DateValue | None) -> str | None:
    return None if date is None else date.expected


def entry_leaves(entry: Entry) -> Leaves:
    dates = (_expected(entry.start), _expected(entry.end))
    if isinstance(entry, ExperienceEntry):
        return Leaves(
            {
                FieldType.TITLE: (entry.title,),
                FieldType.EMPLOYER: (entry.employer,),
                FieldType.LOCATION: (entry.location,),
                FieldType.DATE: dates,
            },
            {FieldType.BULLET: tuple(entry.bullets)},
        )
    return Leaves(
        {
            FieldType.INSTITUTION: (entry.institution,),
            FieldType.QUALIFICATION: (entry.qualification,),
            FieldType.DATE: dates,
        },
        {FieldType.DETAIL: tuple(entry.details)},
    )


def content_leaves(content: CVContent) -> Leaves:
    """The top-level leaves only; entries are decomposed one at a time."""
    return Leaves(
        {FieldType.NAME: (content.name,)},
        {
            FieldType.PROFILE: tuple(content.profile),
            FieldType.SKILL: tuple(content.skills),
            FieldType.CERTIFICATION: tuple(content.certifications),
            FieldType.ADDITIONAL: tuple(content.additional),
        },
    )
