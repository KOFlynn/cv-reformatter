"""The generated documents, and every Phase 0 metric fed from a real run.

``score`` takes a Candidate, the source bytes, and what ``reformat`` returned,
and assembles each metric's inputs from real artefacts only: the source side
from the parsed source, the output side from the rendered document through
the adapter (``cvr.eval.adapter``), the removal log, the maps and the
unplaced text from the ``Run``. The Candidate is used only as the expected
side. The eval runner (ticket 09) does the same over the real labeller; this
is the first wiring, and the one it takes over.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from cvr.eval import (
    Finding,
    OrderingReport,
    PiiHit,
    PlacementReport,
    added_tokens,
    dropped_tokens,
    image_leak,
    ordering_report,
    pii_leak,
    placement_accuracy,
    provenance_violations,
    punctuation_fidelity,
)
from cvr.eval.adapter import Adapted, adapt
from cvr.golden import CANDIDATES_DIR, Candidate, Manifest, load_candidate
from cvr.golden.generate import GENERATED_DIR
from cvr.models import (
    CVContent,
    DateValue,
    EducationEntry,
    ExperienceEntry,
    LedgerKind,
    Run,
    Span,
    TransformedContent,
    TransformedEducation,
    TransformedExperience,
)
from cvr.parse import ParsedDocument, parse
from cvr.template import template_text, template_tokens
from cvr.text import canonicalise, canonicalise_with_offsets, tokenise

__all__ = [
    "GENERATED",
    "Document",
    "Scores",
    "document",
    "score",
    "to_cv_content",
    "units",
]


@dataclass(frozen=True)
class Document:
    """One generated source document with its Candidate and manifest."""

    candidate: Candidate
    manifest: Manifest
    source: bytes

    @property
    def stem(self) -> str:
        return f"{self.manifest.candidate_id}__{self.manifest.layout}"


def document(stem: str) -> Document:
    manifest = Manifest.model_validate_json(
        (GENERATED_DIR / f"{stem}.manifest.json").read_text(encoding="utf-8")
    )
    candidate = load_candidate(CANDIDATES_DIR / f"{manifest.candidate_id}.json")
    return Document(candidate, manifest, (GENERATED_DIR / f"{stem}.docx").read_bytes())


GENERATED: list[str] = sorted(
    Path(path).name.removesuffix(".docx") for path in GENERATED_DIR.glob("*.docx")
)
assert len(GENERATED) == 48, f"expected 48 generated documents, found {len(GENERATED)}"


# --- The adapter's output as the CVContent the structural metrics compare.

_MONTH_YEAR = re.compile(r"\A(\d{2})/(\d{4})\Z")
_YEAR = re.compile(r"\A\d{4}\Z")
_FIRST_YEAR = re.compile(r"\d{4}")


def _date(printed: str | None) -> DateValue | None:
    """A printed date read back into the structured form a Candidate uses:
    ``MM/YYYY``, ``YYYY`` and ``Present`` as what they say; anything else a
    literal, carrying its first four-digit year as a Candidate's literal
    does. Only the structured parts alignment keys on are recovered."""
    if printed is None:
        return None
    if match := _MONTH_YEAR.match(printed):
        return DateValue(month=int(match[1]), year=int(match[2]), expected=printed)
    if _YEAR.match(printed):
        return DateValue(year=int(printed), expected=printed)
    if printed == "Present":
        return DateValue(present=True, expected=printed)
    year = _FIRST_YEAR.search(printed)
    return DateValue(
        year=int(year[0]) if year else None, literal=printed, expected=printed
    )


def _experience(entry: TransformedExperience) -> ExperienceEntry:
    return ExperienceEntry(
        title=entry.title or "",
        employer=entry.employer or "",
        location=entry.location,
        start=_date(entry.start),
        end=_date(entry.end),
        bullets=list(entry.bullets),
    )


def _education(entry: TransformedEducation) -> EducationEntry:
    return EducationEntry(
        institution=entry.institution or "",
        qualification=entry.qualification or "",
        start=_date(entry.start),
        end=_date(entry.end),
        details=list(entry.details),
    )


def to_cv_content(content: TransformedContent) -> CVContent:
    return CVContent(
        name=content.name or "",
        profile=list(content.profile),
        skills=list(content.skills),
        education=[_education(entry) for entry in content.education],
        experience=[_experience(entry) for entry in content.experience],
        certifications=list(content.certifications),
        additional=list(content.additional),
    )


def units(content: TransformedContent) -> list[str]:
    """Every rendered leaf of the adapter's content, in document order."""
    out = [content.name, *content.profile, *content.skills]
    for education in content.education:
        out += [education.qualification, education.institution]
        out += [education.start, education.end, *education.details]
    for experience in content.experience:
        out += [experience.title, experience.employer, experience.location]
        out += [experience.start, experience.end, *experience.bullets]
    out += [*content.certifications, *content.additional]
    return [unit for unit in out if unit]


# --- Every metric


@dataclass(frozen=True)
class Scores:
    adapted: Adapted
    added: list[Finding]
    dropped: list[Finding]
    provenance: list[Finding]
    punctuation: list[Finding]
    pii: list[PiiHit]
    images: list[Finding]
    placement: PlacementReport
    ordering: OrderingReport

    @property
    def hard_gates(self) -> dict[str, list]:
        return {
            "added": self.added,
            "dropped": self.dropped,
            "provenance": self.provenance,
            "pii": self.pii,
            "images": self.images,
        }


def _tokens(texts: list[str]) -> list[str]:
    return [token for text in texts for token in tokenise(text)]


def _located(unit: str, sources: list[str]) -> str | None:
    """The raw source slice a rendered unit came from: canonical match,
    raw slice through the offset map; a slice equal to the unit as
    rendered wins over one that is only canonically equal."""
    needle = canonicalise(unit)
    found: list[str] = []
    for source in sources:
        canonical = canonicalise_with_offsets(source)
        at = canonical.text.find(needle)
        if at != -1:
            found.append(canonical.raw_slice(at, at + len(needle)))
    return unit if unit in found else (found[0] if found else None)


def _pairs(
    rendered: list[str], split_map: dict[str, list[Span]], sources: list[str]
) -> list[tuple[str, str]]:
    pieces = [
        piece
        for unit in rendered
        for piece in (
            [span.text for span in split_map[unit]] if unit in split_map else [unit]
        )
    ]
    located = ((_located(piece, sources), piece) for piece in pieces)
    return [(span, piece) for span, piece in located if span is not None]


def _dates_accounted(blocks: dict[str, str], run: Run, printed: set[str]) -> list[str]:
    """The source text transform replaced in entry date fields, accounted
    for only as far as the Run and the output show it went somewhere.

    Each date is accounted for by its ``date_map`` slice, and only if its
    normalised form was printed, so a date lost in transform or render is
    still dropped. What else a claimed range held (the separator, ``to`` or
    a dash, which the template's en dash replaces) is accounted for by the
    claim in the ledger, less those slices.
    """
    mapped = [span for date, span in run.date_map if date in printed]
    accounted = [span.text for span in mapped]
    for block_id, entries in run.ledgers.items():
        for entry in entries:
            if entry.kind is not LedgerKind.CONTENT:
                continue
            if not entry.claimant.endswith(".dates"):
                continue
            at = entry.start
            dates = sorted(
                (
                    span
                    for _, span in run.date_map
                    if span.block_id == block_id
                    and entry.start <= span.start
                    and span.end <= entry.end
                ),
                key=lambda span: span.start,
            )
            for span in dates:
                accounted.append(blocks[block_id][at : span.start])
                at = span.end
            accounted.append(blocks[block_id][at : entry.end])
    return accounted


def _parts(document: ParsedDocument) -> dict[str, str]:
    """The printed text of each part of a document: body, header, footer."""
    parts: dict[str, list[str]] = {"body": [], "header": [], "footer": []}
    for block in document.blocks:
        part = block.kind if block.kind in ("header", "footer") else "body"
        parts[part].append(block.text)
    return {part: "\n".join(texts) for part, texts in parts.items()}


def score(candidate: Candidate, source: bytes, output: bytes, run: Run) -> Scores:
    """Every metric over one real run, the Candidate as the expected side.

    The output is read twice: through the adapter for the leaves, and
    through ``parse`` for everything printed (the template's own text, the
    appendix, any header or footer) and every embedded image.
    """
    blocks = {block.id: block.text for block in parse(source).blocks}
    sources = list(blocks.values())
    printed = parse(output)
    adapted = adapt(output)
    rendered = units(adapted.content)
    date_map = [(span.text, date) for date, span in run.date_map]
    rendered_dates = {date for date, _ in run.date_map}
    split_map = run.split_map
    removed = [
        removal.subject.text
        for removal in run.removals
        if isinstance(removal.subject, Span)
    ]
    output_tokens = _tokens([block.text for block in printed.blocks])
    actual = to_cv_content(adapted.content)
    return Scores(
        adapted=adapted,
        added=added_tokens(
            _tokens(sources), output_tokens, template_tokens(), date_map
        ),
        dropped=dropped_tokens(
            _tokens(sources),
            [*output_tokens, *_tokens(_dates_accounted(blocks, run, set(rendered)))],
            _tokens(removed),
            _tokens(adapted.appendix),
        ),
        provenance=provenance_violations(
            [*rendered, *adapted.appendix],
            sources,
            template_text(),
            date_map,
            [
                (unit, [span.text for span in spans])
                for unit, spans in split_map.items()
            ],
        ),
        punctuation=punctuation_fidelity(
            _pairs(
                [unit for unit in rendered if unit not in rendered_dates],
                split_map,
                sources,
            )
        ),
        pii=pii_leak(_parts(printed), candidate.pii),
        images=image_leak([image.sha256 for image in printed.images], []),
        placement=placement_accuracy(actual, candidate.content),
        ordering=ordering_report(actual, candidate.content),
    )
