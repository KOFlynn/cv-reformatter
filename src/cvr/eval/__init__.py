"""Eval metrics: pure functions over plain data. Depends on ``text`` and ``models`` only."""

from cvr.eval.alignment import AlignedBy, Alignment, Section
from cvr.eval.appendix import appendix_rate
from cvr.eval.finding import Finding
from cvr.eval.leaves import FieldType
from cvr.eval.multiset import added_tokens, dropped_tokens
from cvr.eval.ordering import OrderingReport, SectionOrdering, ordering_report
from cvr.eval.placement import PlacementReport, Tally, placement_accuracy
from cvr.eval.provenance import provenance_violations
from cvr.eval.punctuation import punctuation_fidelity

__all__ = [
    "AlignedBy",
    "Alignment",
    "FieldType",
    "Finding",
    "OrderingReport",
    "PlacementReport",
    "Section",
    "SectionOrdering",
    "Tally",
    "added_tokens",
    "appendix_rate",
    "dropped_tokens",
    "ordering_report",
    "placement_accuracy",
    "provenance_violations",
    "punctuation_fidelity",
]
