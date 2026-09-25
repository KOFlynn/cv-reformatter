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
"""

import json
import sys
from collections.abc import Iterable
from typing import TextIO

from pydantic import BaseModel

from cvr.models import Image, LabelRun, Run, Span

__all__ = ["MAX_LINE_BYTES", "request_lines", "write_lines"]

# The field size Log Analytics truncates at; no line may reach it.
MAX_LINE_BYTES = 32 * 1024


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _dump(model: BaseModel) -> object:
    return model.model_dump(mode="json")


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
    for removal in run.removals:
        if isinstance(removal.subject, Span):
            line(removal.subject.block_id)["removals"].append(_dump(removal))
    for normalisation in run.normalisations:
        line(normalisation.block_id)["normalisations"].append(_dump(normalisation))
    for residue in run.residue:
        line(residue.span.block_id)["residue"].append(_dump(residue))
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
        summary["error"] = error
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
