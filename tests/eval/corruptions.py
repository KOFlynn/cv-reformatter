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

from fake_pipeline import MetricInputs, PipelineResult, leaves, unplaceable_share

from cvr.eval import (
    PlacementReport,
    added_tokens,
    appendix_rate,
    dropped_tokens,
    image_leak,
    ordering_report,
    pii_leak,
    placement_accuracy,
    provenance_violations,
    punctuation_fidelity,
)
from cvr.golden import Candidate
from cvr.models import CVContent

__all__ = [
    "CHECKS",
    "CORRUPTIONS",
    "Corruption",
    "Direction",
    "NotApplicable",
    "failed_metrics",
]

Check = Callable[[Candidate, MetricInputs], bool]
# A damage sees the Candidate as well as the result: re-emitting a PII value
# needs the value, which the honest result no longer carries.
Damage = Callable[[Candidate, PipelineResult], PipelineResult]

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
    "pii": lambda c, i: not pii_leak(i.output_text, c.pii),
    "image": lambda _, i: (
        not image_leak(i.output_image_hashes, i.template_image_hashes)
    ),
    "provenance": lambda _, i: (
        not provenance_violations(
            i.output_units, i.source_blocks, i.template_units, i.date_map, i.split_map
        )
    ),
    # Reported, not gated, until the Phase 1 baseline; here it must be clean
    # all the same, or the corruption that targets it proves nothing.
    "punctuation": lambda _, i: not punctuation_fidelity(i.pairs),
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


def insert_a_word(_: Candidate, result: PipelineResult) -> PipelineResult:
    index = _first_job_with_bullets(result)
    first, *rest = result.content.experience[index].bullets
    words = first.split(" ")
    words.insert(1, "INSERTED")
    return _with_bullets(result, index, [" ".join(words), *rest])


def drop_a_bullet(_: Candidate, result: PipelineResult) -> PipelineResult:
    index = _first_job_with_bullets(result)
    return _with_bullets(result, index, result.content.experience[index].bullets[1:])


def bullets_to_appendix(_: Candidate, result: PipelineResult) -> PipelineResult:
    index = _first_job_with_bullets(result)
    bullets = result.content.experience[index].bullets
    damaged = _with_bullets(result, index, [])
    return replace(damaged, unplaced=[*result.unplaced, *bullets])


def swap_two_words(_: Candidate, result: PipelineResult) -> PipelineResult:
    index = _first_job_with_bullets(result)
    first, *rest = result.content.experience[index].bullets
    words = first.split(" ")
    at = next((i for i in range(len(words) - 1) if words[i] != words[i + 1]), None)
    if at is None:
        raise NotApplicable("the first bullet has no two different adjacent words")
    words[at], words[at + 1] = words[at + 1], words[at]
    return _with_bullets(result, index, [" ".join(words), *rest])


def join_slices_out_of_source_order(
    _: Candidate, result: PipelineResult
) -> PipelineResult:
    """Declares the first bulleted job's first bullet a multi-span join of
    its own two halves, logged in the wrong order. What is printed does not
    move: the bullet's text, and every other leaf, are exactly row 0's.
    Nothing but ``split_map``'s claimed order changes, so only provenance's
    ascending-slices check can see it (ADR-0007 amendment)."""
    index = _first_job_with_bullets(result)
    bullet = result.content.experience[index].bullets[0]
    words = bullet.split(" ")
    if len(words) < 2:
        raise NotApplicable("the first bullet has fewer than two words")
    midpoint = len(words) // 2
    first_half = " ".join(words[:midpoint])
    second_half = " ".join(words[midpoint:])
    split_map = {**result.split_map, bullet: [second_half, first_half]}
    return replace(result, split_map=split_map)


def _replace_in_first_leaf(
    node: object, old: str, new: str, leaves: frozenset[str]
) -> object:
    """The dumped content with ``old`` replaced once, in the first leaf that
    carries it, in dump order; unchanged if no leaf does. Strings that are
    not leaves (a date's ``literal``) are left alone: no metric would see
    the change, so it would not be a corruption."""
    if isinstance(node, str):
        return node.replace(old, new, 1) if node in leaves else node
    if isinstance(node, list):
        for i, item in enumerate(node):
            replaced = _replace_in_first_leaf(item, old, new, leaves)
            if replaced != item:
                return [*node[:i], replaced, *node[i + 1 :]]
        return node
    if isinstance(node, dict):
        for key, value in node.items():
            replaced = _replace_in_first_leaf(value, old, new, leaves)
            if replaced != value:
                return {**node, key: replaced}
    return node


CURLY = "\u2019"
EN_DASH = "\u2013"
# One-character swaps drawn from the shared confusable table, so that every
# canonicalised metric is blind to them by construction: the straightening a
# renderer that "fixes" quotes does; then the same change the other way (a
# straight apostrophe curled, as autocorrect does); then a hyphen to an en
# dash, for a Candidate with no apostrophe in any leaf. Every Candidate
# carries a hyphen, so the row applies to all twelve. The straightening
# direction itself is exercised only once a Candidate carries a curly
# apostrophe in a leaf, which none does yet.
CONFUSABLE_SWAPS = ((CURLY, "'"), ("'", CURLY), ("-", EN_DASH))


def swap_a_confusable(_: Candidate, result: PipelineResult) -> PipelineResult:
    dumped = result.content.model_dump()
    leaf_set = frozenset(leaves(result.content))
    for old, new in CONFUSABLE_SWAPS:
        damaged = _replace_in_first_leaf(dumped, old, new, leaf_set)
        if damaged != dumped:
            return replace(result, content=CVContent.model_validate(damaged))
    raise NotApplicable("no apostrophe or hyphen in any leaf")


def reverse_experience(_: Candidate, result: PipelineResult) -> PipelineResult:
    if len(result.content.experience) < 2:
        raise NotApplicable("fewer than two experience entries")
    content = result.content.model_copy(
        update={"experience": list(reversed(result.content.experience))}
    )
    return replace(result, content=content)


def reemit_the_email(candidate: Candidate, result: PipelineResult) -> PipelineResult:
    if candidate.pii.email is None:
        raise NotApplicable("no email to re-emit")
    return replace(result, header=[*result.header, candidate.pii.email])


# Any digest the template does not own; the two-column Layout's placeholder
# photo would hash to something just as foreign.
PHOTO_HASH = "sha256:photo-left-in"


def leave_the_photo_in(_: Candidate, result: PipelineResult) -> PipelineResult:
    return replace(result, image_hashes=[*result.image_hashes, PHOTO_HASH])


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
    # wrong (precision) and the wanted one is not found (recall). One error,
    # a false positive and a false negative at once, as whole-leaf scoring
    # always behaves; "precision only" would need token-level scoring.
    _row(
        "insert a word into a bullet",
        insert_a_word,
        "added placement provenance",
        "dropped appendix ordering punctuation pii image",
        Direction(precision="down", recall="down"),
    ),
    _row(
        "drop a bullet",
        drop_a_bullet,
        "dropped placement",
        "added appendix ordering provenance punctuation pii image",
        Direction(precision="unchanged", recall="down"),
    ),
    _row(
        "move one job's bullets into the appendix",
        bullets_to_appendix,
        "appendix placement",
        "added dropped ordering provenance punctuation pii image",
        Direction(precision="unchanged", recall="down"),
    ),
    _row(
        "reverse experience order",
        reverse_experience,
        "ordering",
        "added dropped appendix placement pii image provenance punctuation",
    ),
    # A leak is correctly copied source text: the multisets and placement
    # see nothing, because the email is in the source and outside the body.
    _row(
        "re-emit the source email in the header",
        reemit_the_email,
        "pii",
        "added dropped appendix placement ordering image provenance punctuation",
    ),
    _row(
        "leave the photo in",
        leave_the_photo_in,
        "image",
        "added dropped appendix placement ordering pii provenance punctuation",
    ),
    # The two rows that prove no single check would have been enough
    # (ADR-0007). Swapped words: the same bag of words, so added and dropped
    # both pass, and only the whole-unit check sees that the bullet is a
    # slice of no block. The unit cannot be located, so it has no raw pair
    # and fidelity has nothing to say. Placement moves as for the inserted
    # word: one leaf wrong and one leaf missing.
    _row(
        "swap two words inside a bullet",
        swap_two_words,
        "provenance placement",
        "added dropped appendix ordering punctuation pii image",
        Direction(precision="down", recall="down"),
    ),
    # A changed apostrophe: every canonicalised metric, provenance included,
    # sees the same string on both sides. Only the raw comparison notices.
    _row(
        "straighten a curly apostrophe",
        swap_a_confusable,
        "punctuation",
        "added dropped appendix ordering placement provenance pii image",
    ),
    # Nothing printed moves: the bullet reads exactly as row 0's. Only the
    # transform log's split_map claims the two halves in the wrong order,
    # which only provenance's ascending-slices check reads at all.
    _row(
        "join two slices out of source order",
        join_slices_out_of_source_order,
        "provenance",
        "added dropped appendix ordering placement pii image punctuation",
    ),
]
