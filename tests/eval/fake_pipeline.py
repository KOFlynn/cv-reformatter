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
from cvr.text import tokenise

__all__ = [
    "MetricInputs",
    "PipelineResult",
    "fake_pipeline",
    "leaves",
    "metric_inputs",
    "pii_values",
    "unplaceable_share",
]


@dataclass(frozen=True)
class PipelineResult:
    """What a real pipeline hands the renderer: placed content plus unplaced text."""

    content: CVContent
    unplaced: list[str] = field(default_factory=list)


def fake_pipeline(candidate: Candidate) -> PipelineResult:
    """The honest pipeline: the Candidate's content and its unplaceable fragments."""
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
    output_units: list[str]
    output_tokens: list[str]
    template_tokens: list[str]
    date_map: list[tuple[str, str]]
    removed_tokens: list[str]
    appendix_tokens: list[str]


# Extracted from the template at run time once ticket 06 builds it.
TEMPLATE_TOKENS: list[str] = []


def metric_inputs(candidate: Candidate, result: PipelineResult) -> MetricInputs:
    source_leaves = leaves(candidate.content)
    removed = pii_values(candidate.pii)
    output_units = leaves(result.content)
    return MetricInputs(
        source_tokens=_tokens([*source_leaves, *removed, *candidate.unplaceable]),
        source_content_tokens=_tokens([*source_leaves, *candidate.unplaceable]),
        output_units=output_units,
        output_tokens=[*_tokens(output_units), *TEMPLATE_TOKENS],
        template_tokens=list(TEMPLATE_TOKENS),
        date_map=[
            (date, date)
            for entry in [*candidate.content.education, *candidate.content.experience]
            for date in _entry_dates(entry)
        ],
        removed_tokens=_tokens(removed),
        appendix_tokens=_tokens(result.unplaced),
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
