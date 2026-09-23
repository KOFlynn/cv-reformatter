"""The transform node: pure functions from ``VerifiedContent`` to the content
the renderer projects, plus the ``Run`` record.

``transform_content`` walks the verified tree once: every ``Unit`` becomes
the plain string the renderer prints (multi-span units joined by one space
of template text, recorded in ``split_map`` for provenance); every entry's
``dates`` reference is split into a start and an end (``cvr.transform.dates``,
recorded in ``date_map``); experience and education entries are reordered
(``cvr.transform.order``). Removed Spans never reach ``VerifiedContent`` in
the first place, so nothing here has removals to apply.

``Run`` is the transform log's record type, defined here because transform is
the node that assembles it. Its ``ledger`` and ``residue``/``unplaced``
fields are shaped like ``cvr.verify``'s ``LedgerEntry`` and ``Span``, but
transform never imports ``cvr.verify`` (the package dependency rule is
``models`` and ``text`` only): the pipeline function (ticket 06) translates
a ``VerifiedDocument`` into the plain ``LedgerLine``/``Span`` values ``Run``
accepts. ``transform`` (the top-level function) is pure and takes every
labeller-metadata field as an explicit, optional argument, so a ``Run`` can
be hand-built in a test with no pipeline, no labeller and no clock.

Depends on ``cvr.models`` and ``cvr.text`` only.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from cvr.models import (
    Normalisation,
    Removal,
    Span,
    StrictModel,
    Unit,
    VerifiedContent,
    VerifiedEducation,
    VerifiedExperience,
)
from cvr.transform.dates import NormalisedDate, parse_date, split_dates
from cvr.transform.order import Ranked, order

__all__ = [
    "LedgerLine",
    "Run",
    "TransformResult",
    "TransformedContent",
    "TransformedEducation",
    "TransformedExperience",
    "transform",
    "transform_content",
]


class TransformedExperience(StrictModel):
    """One experience entry projected to strings, dates normalised."""

    title: str | None = None
    employer: str | None = None
    location: str | None = None
    start: str | None = None
    end: str | None = None
    bullets: list[str] = Field(default_factory=list)


class TransformedEducation(StrictModel):
    institution: str | None = None
    qualification: str | None = None
    start: str | None = None
    end: str | None = None
    details: list[str] = Field(default_factory=list)


class TransformedContent(StrictModel):
    """``VerifiedContent`` projected to the strings the renderer prints, in
    output order."""

    name: str | None = None
    profile: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[TransformedEducation] = Field(default_factory=list)
    experience: list[TransformedExperience] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    additional: list[str] = Field(default_factory=list)


class LedgerLine(StrictModel):
    """One row of a block's claim ledger, as it appears in the transform
    log: the claimed raw range, its claimant (a removal rule id or a field
    path), and whether the claim was a removal or content."""

    start: int
    end: int
    claimant: str
    kind: Literal["removal", "content"]


class Run(StrictModel):
    """The transform log's record type: one per source document taken once
    through the pipeline. Every labeller-metadata field is optional, so a
    ``Run`` can be built without a labeller at all."""

    run_id: str
    labeller_config: dict[str, object] = Field(default_factory=dict)
    prompt_label: str | None = None
    prompt_hash: str | None = None
    schema_label: str | None = None
    schema_hash: str | None = None
    tokens: dict[str, int] | None = None
    cost: float | None = None
    ledger: dict[str, list[LedgerLine]] = Field(default_factory=dict)
    removals: list[Removal] = Field(default_factory=list)
    normalisations: list[Normalisation] = Field(default_factory=list)
    date_map: dict[str, Span] = Field(default_factory=dict)
    split_map: dict[str, list[Span]] = Field(default_factory=dict)
    residue: list[Span] = Field(default_factory=list)
    unplaced: list[Span] = Field(default_factory=list)
    label_failed: bool = False


@dataclass(frozen=True, slots=True)
class TransformResult:
    """``transform_content``'s output: the projected content plus the two
    provenance maps that go into the ``Run``."""

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


def transform(
    content: VerifiedContent,
    run_id: str,
    *,
    ledger: Mapping[str, Sequence[LedgerLine]] | None = None,
    removals: Sequence[Removal] = (),
    normalisations: Sequence[Normalisation] = (),
    residue: Sequence[Span] = (),
    unplaced: Sequence[Span] = (),
    label_failed: bool = False,
    labeller_config: Mapping[str, object] | None = None,
    prompt_label: str | None = None,
    prompt_hash: str | None = None,
    schema_label: str | None = None,
    schema_hash: str | None = None,
    tokens: Mapping[str, int] | None = None,
    cost: float | None = None,
) -> tuple[TransformedContent, Run]:
    """``transform_content`` plus the ``Run`` it feeds: every argument beyond
    ``content`` and ``run_id`` is optional, so this runs with no labeller,
    no verifier and no clock, over a hand-made ``VerifiedContent``."""
    result = transform_content(content)
    run = Run(
        run_id=run_id,
        labeller_config=dict(labeller_config) if labeller_config else {},
        prompt_label=prompt_label,
        prompt_hash=prompt_hash,
        schema_label=schema_label,
        schema_hash=schema_hash,
        tokens=dict(tokens) if tokens else None,
        cost=cost,
        ledger={block_id: list(lines) for block_id, lines in (ledger or {}).items()},
        removals=list(removals),
        normalisations=list(normalisations),
        date_map=result.date_map,
        split_map=result.split_map,
        residue=list(residue),
        unplaced=list(unplaced),
        label_failed=label_failed,
    )
    return result.content, run
