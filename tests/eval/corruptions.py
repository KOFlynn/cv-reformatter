"""The corruption table: deliberate damage to a pipeline result, each row with a
declared blast radius over the metrics that exist.

Columns are ``CHECKS`` (one per metric; a check is true when the metric
passes) and rows are ``CORRUPTIONS``. Later tickets add a metric by adding a
check and placing it in every row's ``fails`` or ``passes``, and add a
corruption by adding a row; the test that reads this table does not change.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from fake_pipeline import MetricInputs, PipelineResult, unplaceable_share

from cvr.eval import added_tokens, appendix_rate, dropped_tokens
from cvr.golden import Candidate

__all__ = ["CHECKS", "CORRUPTIONS", "Corruption", "NotApplicable", "failed_metrics"]

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
}


def failed_metrics(candidate: Candidate, inputs: MetricInputs) -> set[str]:
    return {name for name, check in CHECKS.items() if not check(candidate, inputs)}


class NotApplicable(Exception):
    """The Candidate lacks what this corruption damages (a job with bullets)."""


@dataclass(frozen=True)
class Corruption:
    name: str
    damage: Damage
    fails: frozenset[str]
    passes: frozenset[str]


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


def _row(name: str, damage: Damage, fails: str, passes: str) -> Corruption:
    return Corruption(name, damage, frozenset(fails.split()), frozenset(passes.split()))


# Both columns are written out in full, as in the spec's table, so that a new
# metric has to be placed in every row on purpose.
CORRUPTIONS: list[Corruption] = [
    _row("insert a word into a bullet", insert_a_word, "added", "dropped appendix"),
    _row("drop a bullet", drop_a_bullet, "dropped", "added appendix"),
    _row(
        "move one job's bullets into the appendix",
        bullets_to_appendix,
        "appendix",
        "added dropped",
    ),
]
