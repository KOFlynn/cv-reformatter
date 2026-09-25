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
"""

import json
import sys
from collections.abc import Iterable
from typing import TextIO

from cvr.models import Run, Span

__all__ = ["MAX_LINE_BYTES", "request_lines", "write_lines"]

# The field size Log Analytics truncates at; no line may reach it.
MAX_LINE_BYTES = 32 * 1024


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _dump(model) -> object:
    return model.model_dump(mode="json")


def _block_ids(run: Run) -> list[str]:
    """Every block the Run mentions, in ledger (source) order: verify keeps a
    ledger for every block, so the rest only guards against a hand-built
    Run."""
    ids = dict.fromkeys(run.ledgers)
    for removal in run.removals:
        if isinstance(removal.subject, Span):
            ids.setdefault(removal.subject.block_id)
    for normalisation in run.normalisations:
        ids.setdefault(normalisation.block_id)
    for residue in run.residue:
        ids.setdefault(residue.span.block_id)
    for _, span in run.date_map:
        ids.setdefault(span.block_id)
    for spans in run.split_map.values():
        ids.setdefault(spans[0].block_id)
    return list(ids)


def _block_line(run: Run, block_id: str) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "line": "block",
        "block_id": block_id,
        "ledger": [_dump(entry) for entry in run.ledgers.get(block_id, [])],
        "removals": [
            _dump(removal)
            for removal in run.removals
            if isinstance(removal.subject, Span)
            and removal.subject.block_id == block_id
        ],
        "normalisations": [
            _dump(normalisation)
            for normalisation in run.normalisations
            if normalisation.block_id == block_id
        ],
        "residue": [
            _dump(residue)
            for residue in run.residue
            if residue.span.block_id == block_id
        ],
        "dates": [
            [date, _dump(span)]
            for date, span in run.date_map
            if span.block_id == block_id
        ],
        # A multi-span unit's spans are all of one block.
        "splits": {
            path: [_dump(span) for span in spans]
            for path, spans in run.split_map.items()
            if spans[0].block_id == block_id
        },
    }


def request_lines(
    run_id: str, status: int, *, run: Run | None = None, error: str | None = None
) -> list[str]:
    """The log lines of one request: the summary first, then a line per block
    when there is a ``run``. A request refused before the pipeline ran, or
    one the pipeline failed on, has only the summary, with its ``error``."""
    summary: dict[str, object] = {"run_id": run_id, "line": "summary", "status": status}
    if error is not None:
        summary["error"] = error
    if run is None:
        return [_json(summary)]
    blocks = _block_ids(run)
    summary |= {
        "label": None if run.label is None else _dump(run.label),
        "label_failed": run.label_failed,
        "blocks": len(blocks),
        "images": [
            _dump(removal)
            for removal in run.removals
            if not isinstance(removal.subject, Span)
        ],
        "removals": len(run.removals),
        "normalisations": len(run.normalisations),
        "residue": len(run.residue),
        "unplaced": len(run.unplaced),
        "dates": len(run.date_map),
        "splits": len(run.split_map),
    }
    return [_json(summary), *(_json(_block_line(run, b)) for b in blocks)]


def write_lines(lines: Iterable[str], stream: TextIO | None = None) -> None:
    """Write ``lines`` to ``stream`` (standard output as it is at call time,
    so a test's capture sees them), one per line, and flush."""
    out = sys.stdout if stream is None else stream
    for line in lines:
        out.write(line + "\n")
    out.flush()
