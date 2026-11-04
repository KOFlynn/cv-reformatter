"""The Run's log and its failures, shared by both surfaces: the API
(``cvr.api``) and the MCP server (``cvr.mcp``).

``request_lines`` turns one Run, or one refused or failed attempt at one,
into its JSON log lines with PII stripped, and ``write_lines`` writes them to
the stream its caller names: the API's standard output, the MCP server's
standard error. ``MAX_UPLOAD_BYTES`` is the most either accepts, and
``ErrorCategory`` with ``category_of`` the fixed ways a Run fails.

Depends on ``models``, ``verify.backstops`` (the PII patterns) and
``label.errors``; never on a server package, so neither surface imports the
other (a test pins it).
"""

from cvr.runlog.errors import MAX_UPLOAD_BYTES, ErrorCategory, category_of
from cvr.runlog.lines import MAX_LINE_BYTES, request_lines, write_lines

__all__ = [
    "MAX_LINE_BYTES",
    "MAX_UPLOAD_BYTES",
    "ErrorCategory",
    "category_of",
    "request_lines",
    "write_lines",
]
