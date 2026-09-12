"""Eval metrics: pure functions over plain data. Depends on ``text`` and ``models`` only."""

from cvr.eval.alignment import AlignedBy, Alignment, Section
from cvr.eval.appendix import appendix_rate
from cvr.eval.finding import Finding
from cvr.eval.multiset import added_tokens, dropped_tokens
from cvr.eval.placement import FieldType, PlacementReport, Tally, placement_accuracy

__all__ = [
    "AlignedBy",
    "Alignment",
    "FieldType",
    "Finding",
    "PlacementReport",
    "Section",
    "Tally",
    "added_tokens",
    "appendix_rate",
    "dropped_tokens",
    "placement_accuracy",
]
