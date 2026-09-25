"""The five imperfect oracles: the perfect answer damaged in one known way,
through the whole pipeline, so the ledger, rejection, residue and
labelling-failure paths are proven end to end rather than only at metric
level. Each runs over one Candidate in all four Layouts, so the damaged
text sits in a table cell, a text box and a bulleted paragraph as well as a
plain one.

An unplaced fragment is the whole unclaimed run of its block, so it keeps
any bullet glyph or comma beside it; the comparisons allow separators
around the expected text and canonicalise, and the Run's own unplaced list
is asserted equal to the appendix exactly.

Only the fifth, a content line removed under a PII rule, trips the removal
precision gate (ticket 17). The other four leave every removal as the
perfect oracle made it (the PII values under their rules, the Layout's
headings by the heading backstop), and even the schema-invalid answer, whose
every removal is a backstop's, removes nothing its rule may not: that is
asserted in each, not assumed.
"""

import pytest
from oracle import (
    Imperfect,
    Oracle,
    location_claims_the_employer_line,
    omit_first_bullet,
    remove_first_bullet_as_personal,
    schema_invalid,
    unlocatable_title,
)
from pipeline_support import Scores, document, score

from cvr.eval import FieldType, Finding, Tally
from cvr.models import (
    ExperienceEntry,
    LedgerKind,
    Reference,
    RemovalRule,
    Run,
    TransformedContent,
    TransformedExperience,
)
from cvr.parse import parse
from cvr.pipeline import reformat
from cvr.template import BANNER
from cvr.text import canonicalise, is_separator_residue

STEMS = [
    "c04__single-column",
    "c04__two-column",
    "c04__text-box",
    "c04__header-footer",
]
layouts = pytest.mark.parametrize("stem", STEMS)


def _is(fragment: str, text: str) -> bool:
    """Whether an unplaced fragment is ``text`` and, around it, only
    separators (a bullet glyph, the comma of an employer line)."""
    canonical, needle = canonicalise(fragment), canonicalise(text)
    at = canonical.find(needle)
    rest = canonical[:at] + canonical[at + len(needle) :]
    return at != -1 and is_separator_residue(rest)


def _only(fragments: list[str], text: str) -> bool:
    return len(fragments) == 1 and _is(fragments[0], text)


def _run(stem, damage) -> tuple[bytes, Run, Scores]:
    doc = document(stem)
    labeller = Imperfect(Oracle(doc.candidate, doc.manifest), damage)
    output, run = reformat(doc.source, labeller)
    return (
        output,
        run,
        score(doc.candidate, doc.source, output, run, doc.manifest.headings),
    )


def _perfect_first_entry(stem) -> tuple[ExperienceEntry, Reference, Reference]:
    """The first experience entry the document prints, from the Candidate,
    and the perfect oracle's title and employer references for it."""
    doc = document(stem)
    labelling = Oracle(doc.candidate, doc.manifest)(parse(doc.source).blocks)
    first = labelling.content.experience[0]
    assert first.title is not None and first.employer is not None
    entry = doc.candidate.content.experience[doc.manifest.experience_order[0]]
    return entry, first.title, first.employer


def _entry(scores: Scores, **match) -> TransformedExperience:
    (entry,) = [
        e
        for e in scores.adapted.content.experience
        if all(getattr(e, key) == value for key, value in match.items())
    ]
    return entry


def _content_claimants(run: Run, block_id: str) -> list[str]:
    return [
        entry.claimant
        for entry in run.ledgers[block_id]
        if entry.kind is LedgerKind.CONTENT
    ]


def _unplaced_in(run: Run, block_id: str) -> list[str]:
    """The block's residue that is not separators, read from the residue
    itself rather than from ``Run.unplaced``, which derives from it."""
    return [
        residue.span.text
        for residue in run.residue
        if residue.span.block_id == block_id and not residue.separator
    ]


def _assert_explained_by_the_run(scores: Scores, run: Run) -> None:
    assert [span.text for span in run.unplaced] == scores.adapted.appendix
    # Every hard gate clean, removal precision included: a leaf lost to the
    # appendix is not a removal.
    assert scores.removals == []
    assert {gate: f for gate, f in scores.hard_gates.items() if f} == {}


# --- Omitted leaf


@layouts
def test_an_omitted_leaf_is_unplaced_and_nothing_else_changes(stem):
    doc = document(stem)
    perfect_output, perfect_run = reformat(
        doc.source, Oracle(doc.candidate, doc.manifest)
    )
    perfect = score(
        doc.candidate, doc.source, perfect_output, perfect_run, doc.manifest.headings
    )
    output, run, scores = _run(stem, omit_first_bullet)
    entry, _, _ = _perfect_first_entry(stem)
    bullet = entry.bullets[0]

    assert _only(scores.adapted.appendix, bullet)
    assert BANNER in [block.text for block in parse(output).blocks]
    _assert_explained_by_the_run(scores, run)
    assert scores.punctuation == perfect.punctuation == []
    assert scores.ordering == perfect.ordering
    for field in FieldType:
        expected = perfect.placement.by_field[field]
        if field is FieldType.BULLET:
            expected = Tally(expected.hits - 1, expected.actual - 1, expected.expected)
        assert scores.placement.by_field[field] == expected, field
    (bullet_block,) = {span.block_id for span in run.unplaced}
    assert _content_claimants(run, bullet_block) == []


# --- Unlocatable quote


@layouts
def test_an_unlocatable_quote_rejects_its_leaf_and_the_entry_survives(stem):
    _, run, scores = _run(stem, unlocatable_title)
    entry, title, _ = _perfect_first_entry(stem)

    placed = _entry(scores, employer=entry.employer)
    assert placed.title is None
    assert placed.location == entry.location
    assert placed.start == (entry.start.expected if entry.start else None)
    assert placed.end == (entry.end.expected if entry.end else None)
    assert placed.bullets == entry.bullets
    assert _only(scores.adapted.appendix, entry.title)
    assert _content_claimants(run, title.block_id) == []
    assert _only(_unplaced_in(run, title.block_id), entry.title)
    _assert_explained_by_the_run(scores, run)


# --- Double claim


@layouts
def test_a_double_claim_rejects_the_later_field_and_leaves_its_range_unplaced(stem):
    _, run, scores = _run(stem, location_claims_the_employer_line)
    entry, _, employer = _perfect_first_entry(stem)
    assert entry.location is not None

    placed = _entry(scores, title=entry.title)
    assert placed.employer == entry.employer
    assert placed.location is None
    assert _only(scores.adapted.appendix, entry.location)
    assert _content_claimants(run, employer.block_id) == ["experience[0].employer"]
    assert _only(_unplaced_in(run, employer.block_id), entry.location)
    _assert_explained_by_the_run(scores, run)


# --- Content removed under a PII rule


@layouts
def test_a_content_line_removed_under_a_pii_rule_fails_removal_precision_alone(stem):
    """The first real run's c07 finding, reproduced: the line is logged as
    removed, so no token is dropped and nothing reaches the appendix; only
    placement recall and removal precision see it, and only the latter is a
    hard gate."""
    _, run, scores = _run(stem, remove_first_bullet_as_personal)
    entry, _, _ = _perfect_first_entry(stem)
    bullet = entry.bullets[0]
    (removed,) = [
        r
        for r in run.removals
        if r.rule is RemovalRule.PERSONAL
        and canonicalise(r.subject.text) == canonicalise(bullet)
    ]

    assert scores.removals == [
        Finding(
            where=removed.subject.block_id,
            what=f"RM_PERSONAL: {canonicalise(bullet)}",
            count=1,
        )
    ]
    assert {gate for gate, f in scores.hard_gates.items() if f} == {"removals"}
    assert scores.adapted.appendix == []
    bullets = scores.placement.by_field[FieldType.BULLET]
    assert bullets.precision == 1.0
    assert bullets.recall < 1.0


# --- Schema-invalid answer


BACKSTOPPED = {RemovalRule.PHONE, RemovalRule.EMAIL, RemovalRule.URL}


@layouts
def test_a_schema_invalid_answer_puts_every_block_under_the_banner(stem):
    output, run, scores = _run(stem, schema_invalid)
    blocks = parse(document(stem).source).blocks
    position = {block.id: index for index, block in enumerate(blocks)}

    assert run.label_failed is True
    assert scores.adapted.content == TransformedContent()
    assert BANNER in [block.text for block in parse(output).blocks]
    assert scores.adapted.appendix
    # Every block is removed, separator residue, or unplaced whole.
    for block in blocks:
        claimed = [e for e in run.ledgers[block.id] if e.kind is LedgerKind.REMOVAL]
        unplaced = _unplaced_in(run, block.id)
        assert claimed or unplaced or is_separator_residue(block.text), block.id
    assert [span.text for span in run.unplaced] == scores.adapted.appendix
    order = [position[span.block_id] for span in run.unplaced]
    assert order == sorted(order)
    assert all(
        entry.kind is LedgerKind.REMOVAL
        for entries in run.ledgers.values()
        for entry in entries
    )
    # Every block's text is printed, removed or separator: nothing dropped,
    # nothing added, every fragment a slice of the source.
    assert scores.dropped == scores.added == scores.provenance == []
    # Every removal is a backstop's, and each is a PII value under its own
    # rule or a heading the Layout wrote: none is wrongful.
    assert scores.removals == []
    # The backstops and RM_PHOTO still ran; what only the LLM removes
    # (addresses, here) is in the appendix, where the banner flags it.
    assert not [hit for hit in scores.pii if hit.rule in BACKSTOPPED]
    assert scores.images == []
    photos = [r for r in run.removals if r.rule is RemovalRule.PHOTO]
    assert len(photos) == (1 if stem.endswith("two-column") else 0)
    assert any(r.rule is RemovalRule.HEADING for r in run.removals)
