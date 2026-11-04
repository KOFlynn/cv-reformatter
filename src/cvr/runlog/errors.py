"""What both surfaces refuse, and how a failed Run is classified.

``MAX_UPLOAD_BYTES`` is the most either surface accepts: the API's whole
request body, multipart framing included, and the MCP server's source file.

``ErrorCategory`` is the closed set of ways a Run can fail before or instead
of producing a document. The API answers each with a status code; the MCP
server returns it as a tool error with a fixed message (ADR-0016). Neither
ever passes on an exception's text, which may carry CV text. A labelling
failure is not here: the job completes with the banner document (ADR-0004).
"""

from enum import StrEnum

from cvr.label.errors import LabellerMisconfigured, ProviderUnavailable

__all__ = ["MAX_UPLOAD_BYTES", "ErrorCategory", "category_of"]

# A golden-set document is about 40 KB; a CV with photos is a few hundred.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class ErrorCategory(StrEnum):
    # Refused before the pipeline runs. The first two and ``exists`` are the
    # MCP server's alone (a path outside the Workspace, a missing file, an
    # output name already taken); the API has no paths.
    OUTSIDE_WORKSPACE = "outside_workspace"
    NOT_FOUND = "not_found"
    NOT_DOCX = "not_docx"
    TOO_LARGE = "too_large"
    EXISTS = "exists"
    # Raised while the pipeline ran.
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MISCONFIGURED = "misconfigured"
    INTERNAL = "internal"


def category_of(exc: BaseException) -> ErrorCategory:
    """The category of an exception the pipeline raised: the labeller's two
    errors by their type, anything else ``internal``."""
    if isinstance(exc, ProviderUnavailable):
        return ErrorCategory.PROVIDER_UNAVAILABLE
    if isinstance(exc, LabellerMisconfigured):
        return ErrorCategory.MISCONFIGURED
    return ErrorCategory.INTERNAL
