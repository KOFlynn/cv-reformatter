"""The path grammar: where in the content tree a reference sits. The paths
the pipeline itself builds (``name``, ``skills[2]``, ``experience[0].bullets[1]``,
``removals[3]``) and the ones a retry's model writes (``Addition.path``) share
it. A model-written path is free text, so anything that records one past the
content boundary (ADR-0013) goes through ``safe_path`` first."""

import re

__all__ = ["safe_path"]

_FIELDS = "title|employer|location|dates|bullets|institution|qualification|details"
_PATH = re.compile(
    r"(?:name"
    r"|(?:profile|skills|certifications|additional)(?:\[[0-9]{1,9}\])?"
    r"|removals\[[0-9]{1,9}\]"
    rf"|(?:experience|education)\[[0-9]{{1,9}}\]\.(?:{_FIELDS})(?:\[[0-9]{{1,9}}\])?)"
)

UNKNOWN = "unknown"


def safe_path(path: str) -> str:
    """``path`` if it fully matches the grammar (so it is made only of known
    field names, brackets and digits), else ``unknown``: the same treatment as
    a block id that is not one of the document's."""
    return path if _PATH.fullmatch(path) else UNKNOWN
