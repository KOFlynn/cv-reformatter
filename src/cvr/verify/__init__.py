"""The verify node: the parsed blocks and the labelling result in; the
content tree in Spans, the flat claim list, the removals, the rejections and
the residue out. Pure: no LLM, no network, no document. Depends on ``text``
and ``models`` only.

One claim ledger per block (``ledger``), filled in this order and no other:
the LLM's removals in schema order, then the regex backstop over every block,
then content in tree-walk order (name, profile, skills, education,
experience, certifications, additional; list order within, an entry's fields
in schema order), then the heading backstop over blocks that hold no placed
content, then coverage over the finished ledgers. Removals therefore always
win: a content claim over a removed range is clipped to what remains, one
piece at an edge or a multi-span unit around the middle. A content claim over
another content claim is a conflict: the later claimant is rejected and gets
no claim, so whatever the earlier one does not hold is residue. A quote with
no occurrence rejects its one leaf. A repeated quote takes the next occurrence
free of content. Coverage reads the ledgers, never the tree. ADR-0008.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from cvr.models import (
    Labelling,
    LabellingFailure,
    LabellingResult,
    Reference,
    Removal,
    RemovalRule,
    SourceBlock,
    Span,
    Unit,
    VerifiedContent,
    VerifiedEducation,
    VerifiedExperience,
)
from cvr.text import is_separator_residue
from cvr.verify.backstops import HEADING_VOCABULARY, heading_key, pii_matches
from cvr.verify.ledger import Kind, Ledger, LedgerEntry

__all__ = ["Claim", "LedgerEntry", "Rejection", "Residue", "Verified", "verify"]

RejectionReason = Literal["unlocatable", "conflict", "removed"]


@dataclass(frozen=True, slots=True)
class Claim:
    """One placed piece: the path of its field and the Span. A multi-span unit
    is several claims under one path."""

    path: str
    span: Span


@dataclass(frozen=True, slots=True)
class Rejection:
    """A reference that placed nothing: ``unlocatable`` (no occurrence in the
    block, or no such block), ``conflict`` (every occurrence is held by
    content already) or ``removed`` (the occurrence lies wholly inside
    removals). The path of an LLM removal is ``removals[i]``."""

    path: str
    block_id: str
    quote: str
    reason: RejectionReason


@dataclass(frozen=True, slots=True)
class Residue:
    """One unclaimed run of a block. ``separator`` means every character is a
    separator: logged, but not unplaced text."""

    span: Span
    separator: bool


@dataclass(frozen=True)
class Verified:
    """What the verify node hands on. ``ledgers`` is per block, entries
    ascending by position; ``residue`` is in block then source order."""

    content: VerifiedContent
    claims: list[Claim] = field(default_factory=list)
    removals: list[Removal] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)
    residue: list[Residue] = field(default_factory=list)
    ledgers: dict[str, list[LedgerEntry]] = field(default_factory=dict)
    label_failed: bool = False

    @property
    def unplaced(self) -> list[Span]:
        """The residue that is not made purely of separators: what goes to
        the review appendix, in block then source order."""
        return [residue.span for residue in self.residue if not residue.separator]


def verify(blocks: list[SourceBlock], labelling: LabellingResult) -> Verified:
    """Verify every reference of ``labelling`` against ``blocks``.

    A ``LabellingFailure`` places nothing and flags the run; the backstops
    still run over every block, so a PII value cannot reach the appendix
    through a bad day for the LLM (ADR-0004: removal takes precedence).
    """
    ledgers = {block.id: Ledger(block) for block in blocks}
    removals: list[Removal] = []
    rejections: list[Rejection] = []
    claims: list[Claim] = []
    failed = isinstance(labelling, LabellingFailure)
    if not failed:
        _verify_removals(ledgers, labelling, removals, rejections)
    _regex_backstop(ledgers, removals)
    content = (
        VerifiedContent()
        if failed
        else _verify_content(ledgers, labelling, claims, rejections)
    )
    _heading_backstop(ledgers, removals)
    residue = _coverage(ledgers)
    return Verified(
        content=content,
        claims=claims,
        removals=removals,
        rejections=rejections,
        residue=residue,
        ledgers={
            block_id: ledger.sorted_entries() for block_id, ledger in ledgers.items()
        },
        label_failed=failed,
    )


# --- The stages, in fill order. Module-level so a test can assert the order.


def _verify_removals(
    ledgers: dict[str, Ledger],
    labelling: Labelling,
    removals: list[Removal],
    rejections: list[Rejection],
) -> None:
    """The LLM's removals, in schema order. An occurrence already wholly
    removed is not reported again: the earlier, more specific rule keeps it."""
    for i, label in enumerate(labelling.removals):
        ledger = ledgers.get(label.block_id)
        occurrences = ledger.occurrences(label.quote) if ledger else []
        if not occurrences:
            rejections.append(
                Rejection(f"removals[{i}]", label.block_id, label.quote, "unlocatable")
            )
            continue
        for start, end in occurrences:
            pieces = ledger.free(start, end, Kind.REMOVAL)
            if pieces:
                _remove(ledger, pieces, RemovalRule(label.rule), removals)
                break


def _regex_backstop(ledgers: dict[str, Ledger], removals: list[Removal]) -> None:
    """Emails, phones and URLs over every block, whatever the LLM did."""
    for ledger in ledgers.values():
        for rule, start, end in pii_matches(ledger.canonical.text):
            raw_start, raw_end = ledger.raw_range(start, end)
            _remove(
                ledger, ledger.free(raw_start, raw_end, Kind.REMOVAL), rule, removals
            )


def _verify_content(
    ledgers: dict[str, Ledger],
    labelling: Labelling,
    claims: list[Claim],
    rejections: list[Rejection],
) -> VerifiedContent:
    """The content tree in tree-walk order; every leaf a Unit or ``None``."""

    def leaf(path: str, reference: Reference | None) -> Unit | None:
        if reference is None:
            return None
        return _place(ledgers, path, reference, claims, rejections)

    def leaves(path: str, references: list[Reference]) -> list[Unit]:
        units = (leaf(f"{path}[{i}]", ref) for i, ref in enumerate(references))
        return [unit for unit in units if unit is not None]

    # Statement order here is the tree-walk order: it decides who is the
    # earlier claimant in a conflict, so it must stay the schema's order.
    tree = labelling.content
    name = leaf("name", tree.name)
    profile = leaves("profile", tree.profile)
    skills = leaves("skills", tree.skills)
    education = []
    for i, entry in enumerate(tree.education):
        path = f"education[{i}]"
        education.append(
            VerifiedEducation(
                institution=leaf(f"{path}.institution", entry.institution),
                qualification=leaf(f"{path}.qualification", entry.qualification),
                dates=leaf(f"{path}.dates", entry.dates),
                details=leaves(f"{path}.details", entry.details),
            )
        )
    experience = []
    for i, entry in enumerate(tree.experience):
        path = f"experience[{i}]"
        experience.append(
            VerifiedExperience(
                title=leaf(f"{path}.title", entry.title),
                employer=leaf(f"{path}.employer", entry.employer),
                location=leaf(f"{path}.location", entry.location),
                dates=leaf(f"{path}.dates", entry.dates),
                bullets=leaves(f"{path}.bullets", entry.bullets),
            )
        )
    return VerifiedContent(
        name=name,
        profile=profile,
        skills=skills,
        education=education,
        experience=experience,
        certifications=leaves("certifications", tree.certifications),
        additional=leaves("additional", tree.additional),
    )


def _heading_backstop(ledgers: dict[str, Ledger], removals: list[Removal]) -> None:
    """A block that holds no placed content and reads, whole, as a known
    heading is removed under RM_HEADING. A block with placed content is never
    touched, so a short bold job title the LLM placed is safe; one it did not
    place is unplaced text, not a heading, unless the vocabulary says so."""
    for ledger in ledgers.values():
        if ledger.has_content():
            continue
        if heading_key(ledger.canonical.text) in HEADING_VOCABULARY:
            pieces = ledger.free(0, len(ledger.block.text), Kind.REMOVAL)
            _remove(ledger, pieces, RemovalRule.HEADING, removals)


def _coverage(ledgers: dict[str, Ledger]) -> list[Residue]:
    """Every unclaimed run of every block, from the ledgers alone."""
    residue: list[Residue] = []
    for ledger in ledgers.values():
        for start, end in ledger.residue():
            text = ledger.block.text[start:end]
            span = Span(block_id=ledger.block.id, start=start, end=end, text=text)
            residue.append(Residue(span=span, separator=is_separator_residue(text)))
    return residue


# --- Placing one reference


def _place(
    ledgers: dict[str, Ledger],
    path: str,
    reference: Reference,
    claims: list[Claim],
    rejections: list[Rejection],
) -> Unit | None:
    """Claim the first occurrence of the quote that no content holds, clipped
    around removals; or reject the leaf and say why."""

    def reject(reason: RejectionReason) -> None:
        rejections.append(Rejection(path, reference.block_id, reference.quote, reason))

    ledger = ledgers.get(reference.block_id)
    occurrences = ledger.occurrences(reference.quote) if ledger else []
    if not occurrences:
        reject("unlocatable")
        return None
    for start, end in occurrences:
        if ledger.overlaps(start, end, Kind.CONTENT):
            continue
        pieces = list(_trimmed(ledger, ledger.free(start, end, Kind.REMOVAL)))
        if not pieces:
            reject("removed")
            return None
        spans = [ledger.claim(s, e, path, Kind.CONTENT) for s, e in pieces]
        claims.extend(Claim(path, span) for span in spans)
        return Unit(spans=spans)
    reject("conflict")
    return None


def _trimmed(
    ledger: Ledger, pieces: list[tuple[int, int]]
) -> Iterator[tuple[int, int]]:
    for start, end in pieces:
        trimmed = ledger.trimmed(start, end)
        if trimmed:
            yield trimmed


def _remove(
    ledger: Ledger,
    pieces: list[tuple[int, int]],
    rule: RemovalRule,
    removals: list[Removal],
) -> None:
    for start, end in pieces:
        span = ledger.claim(start, end, rule.value, Kind.REMOVAL)
        removals.append(Removal(rule=rule, subject=span))
