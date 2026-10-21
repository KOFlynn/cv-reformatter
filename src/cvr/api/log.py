"""The transform log on standard output: one summary line per request and,
when the request produced a Run, one detail line per block, every line a
JSON object carrying the run id.

The Run is split this way because Log Analytics truncates a single field
at around 32 KB, and a 40-block ledger in one line would be cut in half.
Everything block-scoped (the ledger, the text removals, the invisible
normalisations, the residue, the dates and the multi-span joins of that
block) goes on the block's line; everything else (the label section,
``label_failed``, the image removals, which belong to no block) on the
summary. Together the lines hold the whole Run; no endpoint returns it
(ADR-0009: that would be the first half of a review queue).

A block line grows with its block's text, so a single paragraph of tens of
kilobytes would still make a line past the limit. No golden-set document
comes near it (tested); the limit is checked there, not enforced here.

The lines keep the transform log's text, which stays inside our own tenant,
but never a PII value (Phase 2, ticket 05). The rule, applied here and only
here, so the Run, the eval and ``removal_precision`` still see everything:

- a text removal under any rule but ``RM_HEADING`` (headings are not PII)
  logs its block, offsets, length and character class (``a`` a letter, ``9``
  a digit, ``_`` whitespace, ``#`` anything else) and no text, so an
  over-eager rule is still visible;
- a ledger claim carries only offsets and the claimant, never text, and
  stays as it is;
- residue that overlaps such a removal is logged as the same text-free
  subject;
- an ``error`` has every email, phone number and URL in it, and every text a
  PII removal of the Run holds, replaced by ``[pii]``.
"""

import json
import sys
from collections.abc import Iterable
from typing import TextIO

from pydantic import BaseModel

from cvr.models import Image, LabelRun, Removal, RemovalRule, Residue, Run, Span
from cvr.verify.backstops import pii_matches

__all__ = ["MAX_LINE_BYTES", "request_lines", "write_lines"]

# The field size Log Analytics truncates at; no line may reach it.
MAX_LINE_BYTES = 32 * 1024


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _dump(model: BaseModel) -> object:
    return model.model_dump(mode="json")


# The rules whose removed text is not PII: a heading is the source's own word
# (a photo removal's subject is an Image, never a Span, so never here).
_NOT_PII = {RemovalRule.HEADING}
_REDACTED = "[pii]"


def _is_pii(removal: Removal) -> bool:
    return isinstance(removal.subject, Span) and removal.rule not in _NOT_PII


def _shape(text: str) -> str:
    return "".join(
        "a" if c.isalpha() else "9" if c.isdigit() else "_" if c.isspace() else "#"
        for c in text
    )


def _stripped(span: Span) -> dict[str, object]:
    """A span without its text: where it was, how long, and what it looked like."""
    return {
        "block_id": span.block_id,
        "start": span.start,
        "end": span.end,
        "length": span.end - span.start,
        "class": _shape(span.text),
    }


def _dump_removal(removal: Removal) -> object:
    if _is_pii(removal):
        return {"rule": removal.rule.value, "subject": _stripped(removal.subject)}
    return _dump(removal)


def _dump_residue(residue: Residue, pii_spans: list[Span]) -> object:
    span = residue.span
    if any(
        p.block_id == span.block_id and span.start < p.end and p.start < span.end
        for p in pii_spans
    ):
        return {"span": _stripped(span), "separator": residue.separator}
    return _dump(residue)


def _redact(error: str, run: Run | None) -> str:
    """``error`` with PII-shaped text, and the text of the Run's PII
    removals, replaced."""
    for _, start, end in reversed(pii_matches(error)):
        error = error[:start] + _REDACTED + error[end:]
    if run is not None:
        # A very short text (a lone ``+``) would mangle the whole message.
        texts = {
            r.subject.text
            for r in run.removals
            if _is_pii(r) and len(r.subject.text) >= 4
        }
        for text in sorted(texts, key=len, reverse=True):
            error = error.replace(text, _REDACTED)
    return error


def _block_lines(run: Run) -> list[dict[str, object]]:
    """One detail line per block, in ledger (source) order, each holding
    that block's share of the Run. Verify keeps a ledger for every block;
    a block only the rest mention (a hand-built Run) follows the ledgers."""
    lines: dict[str, dict[str, object]] = {}

    def line(block_id: str) -> dict[str, object]:
        if block_id not in lines:
            lines[block_id] = {
                "run_id": run.run_id,
                "line": "block",
                "block_id": block_id,
                "ledger": [],
                "removals": [],
                "normalisations": [],
                "residue": [],
                "dates": [],
                "splits": {},
            }
        return lines[block_id]

    for block_id, ledger in run.ledgers.items():
        line(block_id)["ledger"] = [_dump(entry) for entry in ledger]
    pii_spans = [r.subject for r in run.removals if _is_pii(r)]
    for removal in run.removals:
        if isinstance(removal.subject, Span):
            line(removal.subject.block_id)["removals"].append(_dump_removal(removal))
    for normalisation in run.normalisations:
        line(normalisation.block_id)["normalisations"].append(_dump(normalisation))
    for residue in run.residue:
        line(residue.span.block_id)["residue"].append(_dump_residue(residue, pii_spans))
    for date, span in run.date_map:
        line(span.block_id)["dates"].append([date, _dump(span)])
    for path, spans in run.split_map.items():
        # A multi-span unit's spans are all of one block.
        line(spans[0].block_id)["splits"][path] = [_dump(span) for span in spans]
    return list(lines.values())


def request_lines(
    run_id: str,
    status: int,
    *,
    run: Run | None = None,
    label: LabelRun | None = None,
    error: str | None = None,
) -> list[str]:
    """The log lines of one request: the summary first, then a line per block
    when there is a ``run``. A request refused before the pipeline ran, or
    one the pipeline failed on, has only the summary, with its ``error``
    and, when the labeller had answered before the failure, its ``label``
    section, so the tokens and cost spent are logged either way."""
    summary: dict[str, object] = {"run_id": run_id, "line": "summary", "status": status}
    if error is not None:
        summary["error"] = _redact(error, run)
    if run is None:
        if label is not None:
            summary["label"] = _dump(label)
        return [_json(summary)]
    blocks = _block_lines(run)
    summary |= {
        "label": None if run.label is None else _dump(run.label),
        "label_failed": run.label_failed,
        "blocks": len(blocks),
        "images": [
            _dump(removal)
            for removal in run.removals
            if isinstance(removal.subject, Image)
        ],
        "removals": len(run.removals),
        "normalisations": len(run.normalisations),
        "residue": len(run.residue),
        "unplaced": len(run.unplaced),
        "dates": len(run.date_map),
        "splits": len(run.split_map),
    }
    return [_json(summary), *map(_json, blocks)]


def write_lines(lines: Iterable[str], stream: TextIO | None = None) -> None:
    """Write ``lines`` to ``stream`` (standard output as it is at call time,
    so a test's capture sees them), one per line, and flush."""
    out = sys.stdout if stream is None else stream
    for line in lines:
        out.write(line + "\n")
    out.flush()
