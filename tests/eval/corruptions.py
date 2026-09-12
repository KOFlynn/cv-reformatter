"""The corruption table: deliberate damage to a pipeline result, each row with a
declared blast radius over the metrics that exist.

Columns are ``CHECKS`` (one per metric; a check is true when the metric
passes) and rows are ``CORRUPTIONS``. Later tickets add a metric by adding a
check and placing it in every row's ``fails`` or ``passes``, and add a
corruption by adding a row; the test that reads this table does not change.

A row may also declare a ``Direction`` for placement: which of precision and
recall it must lower and which it must leave alone, so a metric failing for
the wrong reason is caught.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from fake_pipeline import MetricInputs, PipelineResult, unplaceable_share

from cvr.eval import (
    PlacementReport,
    added_tokens,
    appendix_rate,
    dropped_tokens,
    ordering_report,
    placement_accuracy,
)
from cvr.golden import Candidate

__all__ = [
    "CHECKS",
    "CORRUPTIONS",
    "Corruption",
    "Direction",
    "NotApplicable",
    "failed_metrics",
]

Check = Callable[[Candidate, MetricInputs], bool]
Damage = Callable[[PipelineResult], PipelineResult]

CHECKS: dict[str, Check] = {
    "added": lambda _, i: (
        not added_tokens(
            i.source_tokens, i.output_tokens, i.template_tokens, i.date_map
        )
    ),
    "dropped": lambda _, i: (
        not dropped_tokens(
            i.source_tokens, i.output_tokens, i.removed_tokens, i.appendix_tokens
        )
    ),
    # No threshold exists yet: the rate must be exactly the Candidate's own
    # unplaceable share, which is what an honest pipeline reports.
    "appendix": lambda c, i: (
        appendix_rate(i.appendix_tokens, i.source_content_tokens)
        == unplaceable_share(c)
    ),
    # No threshold exists yet either: every leaf placed, none misplaced, no
    # entry unaligned on either side.
    "placement": lambda c, i: _perfect(placement_accuracy(i.output_content, c.content)),
    "ordering": lambda c, i: ordering_report(i.output_content, c.content).correct,
}


def _perfect(report: PlacementReport) -> bool:
    overall = report.overall
    return (
        overall.precision == 1.0
        and overall.recall == 1.0
        and not any(report.unaligned_entries.values())
    )


def failed_metrics(candidate: Candidate, inputs: MetricInputs) -> set[str]:
    return {name for name, check in CHECKS.items() if not check(candidate, inputs)}


class NotApplicable(Exception):
    """The Candidate lacks what this corruption damages (a job with bullets)."""


Trend = Literal["down", "unchanged"]


@dataclass(frozen=True)
class Direction:
    """How a corruption must move placement precision and recall from row 0."""

    precision: Trend
    recall: Trend


@dataclass(frozen=True)
class Corruption:
    name: str
    damage: Damage
    fails: frozenset[str]
    passes: frozenset[str]
    direction: Direction | None = None


def _first_job_with_bullets(result: PipelineResult) -> int:
    for index, entry in enumerate(result.content.experience):
        if entry.bullets:
            return index
    raise NotApplicable("no experience entry has bullets")


def _with_bullets(
    result: PipelineResult, index: int, bullets: list[str]
) -> PipelineResult:
    experience = list(result.content.experience)
    experience[index] = experience[index].model_copy(update={"bullets": bullets})
    content = result.content.model_copy(update={"experience": experience})
    return replace(result, content=content)


def insert_a_word(result: PipelineResult) -> PipelineResult:
    index = _first_job_with_bullets(result)
    first, *rest = result.content.experience[index].bullets
    words = first.split(" ")
    words.insert(1, "INSERTED")
    return _with_bullets(result, index, [" ".join(words), *rest])


def drop_a_bullet(result: PipelineResult) -> PipelineResult:
    index = _first_job_with_bullets(result)
    return _with_bullets(result, index, result.content.experience[index].bullets[1:])


def bullets_to_appendix(result: PipelineResult) -> PipelineResult:
    index = _first_job_with_bullets(result)
    bullets = result.content.experience[index].bullets
    damaged = _with_bullets(result, index, [])
    return replace(damaged, unplaced=[*result.unplaced, *bullets])


def reverse_experience(result: PipelineResult) -> PipelineResult:
    if len(result.content.experience) < 2:
        raise NotApplicable("fewer than two experience entries")
    content = result.content.model_copy(
        update={"experience": list(reversed(result.content.experience))}
    )
    return replace(result, content=content)


def _row(
    name: str,
    damage: Damage,
    fails: str,
    passes: str,
    direction: Direction | None = None,
) -> Corruption:
    return Corruption(
        name, damage, frozenset(fails.split()), frozenset(passes.split()), direction
    )


# Both columns are written out in full, as in the spec's table, so that a new
# metric has to be placed in every row on purpose.
CORRUPTIONS: list[Corruption] = [
    # A bullet with a word inserted is a different leaf: the placed one is
    # wrong (precision) and the wanted one is not found (recall). The spec's
    # table says precision only, which would need token-level list scoring;
    # whole-leaf scoring is the definition the spec actually gives.
    _row(
        "insert a word into a bullet",
        insert_a_word,
        "added placement",
        "dropped appendix ordering",
        Direction(precision="down", recall="down"),
    ),
    _row(
        "drop a bullet",
        drop_a_bullet,
        "dropped placement",
        "added appendix ordering",
        Direction(precision="unchanged", recall="down"),
    ),
    _row(
        "move one job's bullets into the appendix",
        bullets_to_appendix,
        "appendix placement",
        "added dropped ordering",
        Direction(precision="unchanged", recall="down"),
    ),
    _row(
        "reverse experience order",
        reverse_experience,
        "ordering",
        "added dropped appendix placement",
    ),
]
