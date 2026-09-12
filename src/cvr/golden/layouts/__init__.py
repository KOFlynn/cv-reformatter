"""The Layouts: one deterministic source-document style each, and the registry
the generator iterates."""

from cvr.golden.layouts.base import (
    GENERATOR_VERSION,
    MANIFEST_VERSION,
    Decisions,
    FragmentPlacement,
    Generated,
    Layout,
    Manifest,
    Plan,
    PlannedEntry,
    PrintedDate,
    Section,
)
from cvr.golden.layouts.single_column import SingleColumnLayout

__all__ = [
    "GENERATOR_VERSION",
    "LAYOUTS",
    "MANIFEST_VERSION",
    "Decisions",
    "FragmentPlacement",
    "Generated",
    "Layout",
    "Manifest",
    "Plan",
    "PlannedEntry",
    "PrintedDate",
    "Section",
    "SingleColumnLayout",
]

# Every registered Layout, in the style matrix's column order. The generator
# renders every Candidate through every one of these.
LAYOUTS: tuple[Layout, ...] = (SingleColumnLayout(),)
