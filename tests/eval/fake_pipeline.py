"""A pipeline that returns the Candidate's own content, and the map from a
Candidate and a pipeline result to every metric input.

There is no document anywhere here: the source side is reconstructed from the
Candidate (content leaves, PII values and unplaceable fragments are everything
a Layout would have printed), and the output side from whatever the pipeline
returned. Row 0 runs the honest pipeline; the corruption rows run a damaged
one through the same map, so a metric sees exactly what it would see in
Phase 1 with the document and LLM taken out.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from cvr.golden import PII, Candidate
from cvr.models import CVContent, EducationEntry, ExperienceEntry
from cvr.template import template_text, template_tokens
from cvr.text import canonicalise, tokenise

__all__ = [
    "MetricInputs",
    "PipelineResult",
    "fake_pipeline",
    "leaves",
    "locate",
    "metric_inputs",
    "pii_values",
    "unplaceable_share",
]


@dataclass(frozen=True)
class PipelineResult:
    """What a real pipeline hands the renderer: placed content plus unplaced
    text, and what the rendered document then carries outside the body: the
    header lines and the content hashes of every embedded image."""

    content: CVContent
    unplaced: list[str] = field(default_factory=list)
    header: list[str] = field(default_factory=list)
    image_hashes: list[str] = field(default_factory=list)


def fake_pipeline(candidate: Candidate) -> PipelineResult:
    """The honest pipeline: the Candidate's content and its unplaceable
    fragments, nothing of its own in the header, and no images."""
    return PipelineResult(candidate.content, list(candidate.unplaceable))


def _entry_dates(entry: ExperienceEntry | EducationEntry) -> list[str]:
    return [date.expected for date in (entry.start, entry.end) if date is not None]


def leaves(content: CVContent) -> list[str]:
    """Every comparable string in a CVContent, in content order."""
    out = [content.name, *content.profile, *content.skills]
    for education in content.education:
        out += [education.institution, education.qualification]
        out += [*_entry_dates(education), *education.details]
    for experience in content.experience:
        out += [experience.title, experience.employer]
        if experience.location is not None:
            out.append(experience.location)
        out += [*_entry_dates(experience), *experience.bullets]
    return [*out, *content.certifications, *content.additional]


def pii_values(pii: PII) -> list[str]:
    """Every string a removal rule must delete, in PII field order."""
    values = [pii.phone, pii.email, *pii.address, *pii.urls, pii.dob]
    values += [pii.personal.nationality, pii.personal.marital_status]
    for referee in pii.referees:
        values += [referee.name, referee.role, *referee.contact]
    return [value for value in values if value is not None]


def _tokens(texts: Iterable[str]) -> list[str]:
    return [token for text in texts for token in tokenise(text)]


@dataclass(frozen=True)
class MetricInputs:
    """Everything the metrics take, as the Phase 1 runner will assemble it."""

    source_tokens: list[str]
    source_content_tokens: list[str]  # source minus rule-removed
    source_blocks: list[str]  # the leaves themselves, since there is no document
    output_content: CVContent  # the placed content; the Candidate's is expected
    output_units: list[str]
    output_tokens: list[str]
    template_tokens: list[str]
    template_units: list[str]
    date_map: list[tuple[str, str]]
    removed_tokens: list[str]
    appendix_tokens: list[str]
    output_text: dict[str, str]  # part name (body, header) to its text
    output_image_hashes: list[str]
    template_image_hashes: list[str]
    pairs: list[tuple[str, str]]  # (raw located span, raw rendered unit)


# The template's own fixed words (headings, wordmark, footer, banner), read
# from the built template so the whitelist cannot drift from it. A real
# renderer emits these alongside the content, so the honest pipeline does too.
TEMPLATE_TOKENS: list[str] = template_tokens()
# The template carries no images (tests/template asserts this), so any
# image hash in the output is a leak.
TEMPLATE_IMAGE_HASHES: list[str] = []


TEMPLATE_UNITS: list[str] = template_text()


def locate(unit: str, blocks: Iterable[str]) -> str | None:
    """The raw source span a rendered unit came from, or ``None``.

    Stands in for Phase 1's verifier: a unit is located by canonicalised
    match, as provenance finds it, and the located text is returned raw so
    punctuation fidelity can compare what the renderer was given with what
    it produced. Every unit here is a whole leaf, so the match is whole-block
    equality, narrower than provenance's substring rule; a unit that is only
    part of a block has no span here. A block equal to the unit as rendered
    wins over one that is only canonically equal, so two leaves differing
    only in punctuation are each paired with their own.
    """
    text = canonicalise(unit)
    matches = [block for block in blocks if canonicalise(block) == text]
    for block in matches:
        if block == unit:
            return block
    return matches[0] if matches else None


def metric_inputs(candidate: Candidate, result: PipelineResult) -> MetricInputs:
    source_leaves = leaves(candidate.content)
    removed = pii_values(candidate.pii)
    source_blocks = [*source_leaves, *removed, *candidate.unplaceable]
    output_units = leaves(result.content)
    located = ((locate(unit, source_blocks), unit) for unit in output_units)
    return MetricInputs(
        source_tokens=_tokens(source_blocks),
        source_content_tokens=_tokens([*source_leaves, *candidate.unplaceable]),
        source_blocks=source_blocks,
        output_content=result.content,
        output_units=output_units,
        # Everything printed: the body, whatever reached the header, and the
        # template's own text.
        output_tokens=[
            *_tokens(output_units),
            *_tokens(result.header),
            *TEMPLATE_TOKENS,
        ],
        template_tokens=list(TEMPLATE_TOKENS),
        template_units=list(TEMPLATE_UNITS),
        date_map=[
            (date, date)
            for entry in [*candidate.content.education, *candidate.content.experience]
            for date in _entry_dates(entry)
        ],
        removed_tokens=_tokens(removed),
        appendix_tokens=_tokens(result.unplaced),
        output_text={
            "body": "\n".join([*output_units, *result.unplaced]),
            "header": "\n".join(result.header),
        },
        output_image_hashes=list(result.image_hashes),
        template_image_hashes=list(TEMPLATE_IMAGE_HASHES),
        # A unit provenance cannot locate has no span to compare; it is
        # provenance's finding, not fidelity's.
        pairs=[(span, unit) for span, unit in located if span is not None],
    )


def unplaceable_share(candidate: Candidate) -> float:
    """The appendix rate an honest pipeline must report: the Candidate's
    unplaceable tokens over its content-plus-unplaceable tokens.

    Computed from the Candidate alone, never from ``MetricInputs`` or through
    ``appendix_rate``, so the oracle cannot drift with the thing it checks.
    """
    unplaceable = len(_tokens(candidate.unplaceable))
    content = len(_tokens(leaves(candidate.content))) + unplaceable
    return unplaceable / content if content else 0.0
