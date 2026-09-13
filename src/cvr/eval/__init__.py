"""Eval metrics: pure functions over plain data. Depends on ``text`` and ``models`` only."""

from cvr.eval.alignment import AlignedBy, Alignment, Section
from cvr.eval.appendix import appendix_rate
from cvr.eval.finding import Finding
from cvr.eval.image import image_leak
from cvr.eval.leaves import FieldType
from cvr.eval.multiset import added_tokens, dropped_tokens
from cvr.eval.ordering import OrderingReport, SectionOrdering, ordering_report
from cvr.eval.pii import PiiHit, pii_leak
from cvr.eval.placement import PlacementReport, Tally, placement_accuracy

__all__ = [
    "AlignedBy",
    "Alignment",
    "FieldType",
    "Finding",
    "OrderingReport",
    "PiiHit",
    "PlacementReport",
    "Section",
    "SectionOrdering",
    "Tally",
    "added_tokens",
    "appendix_rate",
    "dropped_tokens",
    "image_leak",
    "ordering_report",
    "pii_leak",
    "placement_accuracy",
]
