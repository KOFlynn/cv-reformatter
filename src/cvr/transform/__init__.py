"""The transform node: pure functions from ``VerifiedContent`` to the content
the renderer projects, plus transform's section of the ``Run``.

``transform_content`` walks the verified tree once: every ``Unit`` becomes
the plain string the renderer prints (multi-span units joined by one space
of template text, recorded in ``split_map`` for provenance); every entry's
``dates`` reference is split into a start and an end (``cvr.transform.dates``,
recorded in ``date_map``); experience and education entries are reordered
(``cvr.transform.order``). Removed Spans never reach ``VerifiedContent`` in
the first place, so nothing here has removals to apply.

``TransformedContent`` and the ``Run`` live in ``cvr.models``; the pipeline
function puts ``date_map`` and ``split_map`` into the ``Run`` beside the other
nodes' sections.

Depends on ``cvr.models`` and ``cvr.text`` only.
"""

from dataclasses import dataclass

from cvr.models import (
    Span,
    TransformedContent,
    TransformedEducation,
    TransformedExperience,
    Unit,
    VerifiedContent,
    VerifiedEducation,
    VerifiedExperience,
)
from cvr.transform.dates import NormalisedDate, parse_date, split_dates
from cvr.transform.order import Ranked, order

__all__ = ["TransformResult", "transform_content"]


@dataclass(frozen=True, slots=True)
class TransformResult:
    """``transform_content``'s output: the projected content plus the two
    provenance maps that are transform's section of the ``Run``."""

    content: TransformedContent
    date_map: dict[str, Span]
    split_map: dict[str, list[Span]]


def _render(unit: Unit | None, split_map: dict[str, list[Span]]) -> str | None:
    """One ``Unit`` as the renderer prints it: its spans' text joined by a
    single space of template text. A join of more than one span is a
    multi-span unit, recorded in ``split_map`` for provenance."""
    if unit is None:
        return None
    text = " ".join(span.text for span in unit.spans)
    if len(unit.spans) > 1:
        split_map[text] = list(unit.spans)
    return text


def _render_list(units: list[Unit], split_map: dict[str, list[Span]]) -> list[str]:
    return [text for unit in units if (text := _render(unit, split_map)) is not None]


def _split_entry_dates(
    unit: Unit | None, split_map: dict[str, list[Span]]
) -> tuple[NormalisedDate | None, NormalisedDate | None, dict[str, Span]]:
    """The start/end dates of one entry's whole-range reference.

    A single-span range block is split for real, with a ``date_map`` entry
    for each side traced back to its own raw slice. A multi-span range block
    (only ever produced by a removal clipping the range text, which none of
    the golden set's Candidates do) has no single contiguous raw slice
    either side could be traced to, so it is recorded whole in ``split_map``
    and left unsplit: a lone date assigned to ``end``, exactly as a
    single-span block holding one date is.
    """
    if unit is None:
        return None, None, {}
    if len(unit.spans) == 1:
        split = split_dates(unit.spans[0])
        return split.start, split.end, split.date_map
    text = _render(unit, split_map)
    assert text is not None  # a multi-span unit always renders text
    return None, parse_date(text), {}


def _experience(
    entry: VerifiedExperience,
    index: int,
    split_map: dict[str, list[Span]],
    date_map: dict[str, Span],
) -> Ranked[TransformedExperience]:
    start, end, entry_dates = _split_entry_dates(entry.dates, split_map)
    date_map.update(entry_dates)
    item = TransformedExperience(
        title=_render(entry.title, split_map),
        employer=_render(entry.employer, split_map),
        location=_render(entry.location, split_map),
        start=start.value if start is not None else None,
        end=end.value if end is not None else None,
        bullets=_render_list(entry.bullets, split_map),
    )
    return Ranked(item=item, start=start, end=end, index=index)


def _education(
    entry: VerifiedEducation,
    index: int,
    split_map: dict[str, list[Span]],
    date_map: dict[str, Span],
) -> Ranked[TransformedEducation]:
    start, end, entry_dates = _split_entry_dates(entry.dates, split_map)
    date_map.update(entry_dates)
    item = TransformedEducation(
        institution=_render(entry.institution, split_map),
        qualification=_render(entry.qualification, split_map),
        start=start.value if start is not None else None,
        end=end.value if end is not None else None,
        details=_render_list(entry.details, split_map),
    )
    return Ranked(item=item, start=start, end=end, index=index)


def transform_content(content: VerifiedContent) -> TransformResult:
    """``VerifiedContent`` to the strings the renderer prints, in output
    order, plus ``date_map`` and ``split_map`` for the transform log."""
    date_map: dict[str, Span] = {}
    split_map: dict[str, list[Span]] = {}

    name = _render(content.name, split_map)
    profile = _render_list(content.profile, split_map)
    skills = _render_list(content.skills, split_map)
    certifications = _render_list(content.certifications, split_map)
    additional = _render_list(content.additional, split_map)

    experience = order(
        _experience(entry, index, split_map, date_map)
        for index, entry in enumerate(content.experience)
    )
    education = order(
        _education(entry, index, split_map, date_map)
        for index, entry in enumerate(content.education)
    )

    return TransformResult(
        content=TransformedContent(
            name=name,
            profile=profile,
            skills=skills,
            education=education,
            experience=experience,
            certifications=certifications,
            additional=additional,
        ),
        date_map=date_map,
        split_map=split_map,
    )
