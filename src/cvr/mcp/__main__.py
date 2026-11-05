"""``python -m cvr.mcp``: serve the MCP server over stdio.

Environment variables:

====================  ==================================================
``CVR_MCP_ROOT``      the Workspace: an existing directory the server
                      reads CVs from and writes outputs to (required)
``CVR_RETRY_MAX``     the most retries a Run may make (default ``2``)
====================  ==================================================

The labeller reads its own ``CVR_LABEL_*`` variables and
``ANTHROPIC_API_KEY`` (``cvr.label.config``), on the first call.

Only the SDK writes to standard output (the JSON-RPC stream); the server
refuses to start, with a named error on standard error and exit status 2,
when the Workspace or ``CVR_RETRY_MAX`` is wrong.
"""

import sys

from cvr.mcp.server import WorkspaceMissing, create_server
from cvr.verify.retry import retry_max

__all__ = ["main"]

REFUSED = 2


def main() -> int:
    try:
        retry_max()
    except ValueError as exc:  # the one ValueError that is a refusal
        return _refuse(exc)
    try:
        server = create_server()
    except WorkspaceMissing as exc:
        return _refuse(exc)
    server.run("stdio")
    return 0


def _refuse(exc: Exception) -> int:
    print(f"cvr.mcp: {type(exc).__name__}: {exc}", file=sys.stderr)
    return REFUSED


if __name__ == "__main__":
    sys.exit(main())
