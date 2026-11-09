"""Calling the server the way a client does: the SDK's in-memory client
session, connected to a server from ``create_server``."""

import json

import anyio
from mcp.shared.memory import create_connected_server_and_client_session

from cvr.mcp import TOOL_NAME

__all__ = ["call", "list_tools", "log_lines", "summaries"]


def _session(server, work):
    async def main():
        async with create_connected_server_and_client_session(server) as client:
            return await work(client)

    return anyio.run(main)


def call(server, **arguments):
    """The ``CallToolResult`` of one ``reformat_cv`` call."""
    return _session(server, lambda client: client.call_tool(TOOL_NAME, arguments))


def list_tools(server):
    """The server's tools as a client lists them."""

    async def work(client):
        return (await client.list_tools()).tools

    return _session(server, work)


def log_lines(err: str) -> list[dict]:
    """The transform log lines written to standard error."""
    return [json.loads(line) for line in err.splitlines() if line.startswith("{")]


def summaries(err: str) -> list[dict]:
    """The summary lines written to standard error."""
    return [line for line in log_lines(err) if line["line"] == "summary"]
