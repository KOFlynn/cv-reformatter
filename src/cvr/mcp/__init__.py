"""The MCP server: one tool, ``reformat_cv(path)``, for an AI assistant
(Claude Desktop) over stdio (ADR-0016). It calls the pipeline itself and never
the API; both share ``cvr.runlog``.

``create_server(labeller=None, tracer=None, workspace=None)`` builds the
``FastMCP`` server, mirroring the API's ``create_app``. The tool reads a
``.docx`` inside the Workspace (``CVR_MCP_ROOT``), writes the reformatted
document next to it under a name holding the run id, and returns a Tool
result with no candidate text. The transform log goes to standard error.
"""

from cvr.mcp.server import (
    ENV_WORKSPACE,
    TOOL_NAME,
    ToolResult,
    WorkspaceMissing,
    create_server,
)

__all__ = [
    "ENV_WORKSPACE",
    "TOOL_NAME",
    "ToolResult",
    "WorkspaceMissing",
    "create_server",
]
