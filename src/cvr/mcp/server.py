"""The MCP server: one tool, ``reformat_cv(path)``, over the official SDK's
``FastMCP`` (ADR-0016).

The caller names a ``.docx`` inside the Workspace (``CVR_MCP_ROOT``, read
once when the server is created). The path is absolute or relative to the
Workspace, and ``..`` and symlinks are resolved before it is checked, so
neither escapes. The tool calls the same ``reformat`` the API and the eval
call, writes the output next to the source as
``<stem>-reformatted-<first 8 characters of the run id>.docx`` through an
exclusive create (nothing is ever overwritten), and returns a Tool result:
where the output went, the run id, the status, the retries, removal counts by
rule, the unplaced count, tokens and cost. No field carries candidate text,
and ``output_path`` is the only one that names a file.

Every call is logged to standard error (standard output is the protocol's)
through ``cvr.runlog``: the API's summary keys, one line per block, PII
stripped, never the path or the file name, which can itself be PII. A call
that goes wrong is a tool error with a fixed message in one of
``cvr.runlog``'s categories, never an exception's text.

The labeller is injected for tests. Without one, the real labeller is built
from ``LabellerConfig`` on the first call and kept, so the server starts and
lists its tool without a model key; calls run one at a time, because the
labeller records its last run on itself.
"""

import logging
import os
import sys
import threading
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from cvr.label import LabellerConfig, RealLabeller
from cvr.models import LabelRun, Run
from cvr.pipeline import Labeller, reformat, retry_max
from cvr.runlog import ErrorCategory, category_of, request_lines, write_lines
from cvr.tracing import Tracer

__all__ = [
    "APPENDIX",
    "ENV_WORKSPACE",
    "MESSAGES",
    "TOOL_NAME",
    "ToolResult",
    "Unplaced",
    "WorkspaceMissing",
    "create_server",
    "workspace_from_env",
]

ENV_WORKSPACE = "CVR_MCP_ROOT"
TOOL_NAME = "reformat_cv"
logger = logging.getLogger(__name__)

APPENDIX = (
    "Some source text could not be placed in the template; it is in the "
    "review appendix at the end of the document, for the user to review."
)

# What the caller is told for each category: fixed, so no exception's text,
# which may carry CV text, and no path ever reaches the calling model.
MESSAGES: Mapping[ErrorCategory, str] = {
    ErrorCategory.OUTSIDE_WORKSPACE: "the path resolves outside the Workspace",
    ErrorCategory.NOT_FOUND: "no file at that path",
    ErrorCategory.NOT_DOCX: "the file is not a .docx",
    ErrorCategory.TOO_LARGE: "the file is over the size limit",
    ErrorCategory.EXISTS: "the output file already exists; nothing was written",
    ErrorCategory.PROVIDER_UNAVAILABLE: (
        "the labelling provider is unavailable; try again later"
    ),
    ErrorCategory.MISCONFIGURED: "the labeller is misconfigured",
    ErrorCategory.INTERNAL: "internal error",
}

DESCRIPTION = (
    "Reformat a candidate CV (.docx) into the agency's branded template. "
    "`path` names a .docx inside the Workspace, absolute or relative to it; "
    "a path that resolves outside the Workspace is refused. The reformatted "
    "document is written next to the source as "
    "<stem>-reformatted-<first 8 characters of the run id>.docx and never "
    "overwrites a file. The result holds no CV text: only the output path, "
    "the run id, the status, the retries, removal counts by rule, the "
    "unplaced count, tokens and cost. Give the user the output path to open "
    "the document; do not describe or guess what it says."
)


class WorkspaceMissing(RuntimeError):
    """``CVR_MCP_ROOT`` is unset, empty or not a directory: the server will
    not start (it fails closed, as the API does without its key)."""


class Unplaced(BaseModel):
    """The text the labelling left unplaced, counted, never quoted."""

    spans: int
    characters: int


class ToolResult(BaseModel):
    """What ``reformat_cv`` returns (CONTEXT.md, Tool result)."""

    output_path: str
    run_id: str
    status: Literal["ok", "labelling_failed"]
    retries: int
    removals: dict[str, int] = Field(description="removal rule id -> count")
    unplaced: Unplaced
    appendix: str | None = Field(
        description="a fixed sentence when unplaced text went to the appendix"
    )
    input_tokens: int
    output_tokens: int
    cost_usd: float


class _Refused(Exception):
    """A call refused before or after the pipeline, in its category."""

    def __init__(self, category: ErrorCategory) -> None:
        super().__init__(category.value)
        self.category = category


def workspace_from_env(environ: Mapping[str, str] | None = None) -> Path:
    """The Workspace, ``CVR_MCP_ROOT`` resolved, or ``WorkspaceMissing``."""
    value = (os.environ if environ is None else environ).get(ENV_WORKSPACE, "")
    if not value or not Path(value).is_dir():
        raise WorkspaceMissing(
            f"{ENV_WORKSPACE} must name an existing directory, the Workspace "
            "the server reads CVs from and writes their outputs to"
        )
    return Path(value).resolve()


def _resolve(path: str, workspace: Path) -> Path:
    """``path`` as the file it names, ``..`` and symlinks resolved, or
    refused when that is outside the Workspace."""
    resolved = (workspace / path).resolve()
    if not resolved.is_relative_to(workspace):
        raise _Refused(ErrorCategory.OUTSIDE_WORKSPACE)
    return resolved


def _output_path(source: Path, run_id: str) -> Path:
    """``<stem>-reformatted-<run_id[:8]>.docx`` beside ``source``."""
    return source.with_name(f"{source.stem}-reformatted-{run_id[:8]}.docx")


def _write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as file:
            file.write(content)
    except FileExistsError:
        raise _Refused(ErrorCategory.EXISTS) from None


def _tool_result(run: Run, output: Path) -> ToolResult:
    attempts = run.label_runs
    unplaced = run.unplaced
    return ToolResult(
        output_path=str(output),
        run_id=run.run_id,
        status="labelling_failed" if run.label_failed else "ok",
        retries=len(run.retries),
        removals=dict(sorted(Counter(r.rule.value for r in run.removals).items())),
        unplaced=Unplaced(
            spans=len(unplaced),
            characters=sum(span.end - span.start for span in unplaced),
        ),
        appendix=APPENDIX if unplaced else None,
        input_tokens=sum(r.input_tokens for r in attempts),
        output_tokens=sum(r.output_tokens for r in attempts),
        cost_usd=sum(r.cost_usd for r in attempts),
    )


def _result_text(result: ToolResult) -> str:
    """The Tool result as short text, the same fields as the structured
    content."""
    removals = ", ".join(f"{rule}: {n}" for rule, n in result.removals.items())
    unplaced = result.unplaced
    lines = [
        f"Reformatted document written to {result.output_path}",
        f"Run id: {result.run_id}",
        f"Status: {result.status}",
        f"Retries: {result.retries}",
        f"Removals: {removals or 'none'}",
        f"Unplaced: {unplaced.spans} spans, {unplaced.characters} characters",
    ]
    if result.appendix is not None:
        lines.append(result.appendix)
    lines.append(
        f"Tokens: {result.input_tokens} in, {result.output_tokens} out; "
        f"cost ${result.cost_usd:.4f}"
    )
    return "\n".join(lines)


def _log(
    run_id: str,
    status: str,
    *,
    run: Run | None = None,
    labels: Sequence[LabelRun] = (),
    error: str | None = None,
) -> None:
    """The call's transform log to standard error; ``status`` is the Tool
    result's (``ok``, ``labelling_failed``) or the error category, where the
    API writes its HTTP status."""
    try:
        write_lines(
            request_lines(run_id, status, run=run, labels=labels, error=error),
            sys.stderr,
        )
    except Exception as exc:  # noqa: BLE001 - never fail the call
        logger.error(
            "run %s: the transform log was not written (%s)",
            run_id,
            type(exc).__name__,
        )


class _LabellerSource:
    """The injected labeller, or the real one built on first use and kept."""

    def __init__(self, labeller: Labeller | None) -> None:
        self._labeller = labeller
        self._lock = threading.Lock()

    def get(self) -> Labeller:
        with self._lock:
            if self._labeller is None:
                self._labeller = RealLabeller(LabellerConfig.from_env())
            return self._labeller


def create_server(
    labeller: Labeller | None = None,
    tracer: Tracer | None = None,
    workspace: Path | str | None = None,
) -> FastMCP:
    """The server, labelling with ``labeller`` or, when none is given, with
    the real labeller built from ``CVR_LABEL_*`` on the first call; reading
    and writing inside ``workspace`` or, when none is given, ``CVR_MCP_ROOT``
    as it is now (``WorkspaceMissing`` if that is not a directory). Each Run
    is traced with ``tracer``; without one it is untraced. ``CVR_RETRY_MAX``
    is read here once, so a bad value stops the server at start-up."""
    retry_max()
    root = (
        workspace_from_env()
        if workspace is None
        else workspace_from_env({ENV_WORKSPACE: str(workspace)})
    )
    tracer = tracer if tracer is not None else Tracer.disabled()
    traced = {"tracer": tracer} if tracer.enabled else {}
    source = _LabellerSource(labeller)
    # One call at a time: the labeller records its LabelRun on itself.
    one_at_a_time = threading.Lock()

    def run_tool(path: str) -> CallToolResult:
        run_id = uuid4().hex
        run: Run | None = None
        try:
            source_path = _resolve(path, root)
            body = source_path.read_bytes()
            labeller = source.get()
            with one_at_a_time:
                output, run = reformat(body, labeller, run_id=run_id, **traced)
            output_path = _output_path(source_path, run_id)
            _write_new(output_path, output)
        except Exception as exc:  # noqa: BLE001 - every failure is a category
            refused = isinstance(exc, _Refused)
            category = exc.category if refused else category_of(exc)
            if not refused:
                # An exception's message may carry CV text or a path: the
                # log gets its type name, the caller the fixed message.
                logger.error("run %s failed: %s", run_id, type(exc).__name__)
            _log(
                run_id,
                category.value,
                # A failure after the Run (the output name taken) still logs
                # what the labelling cost.
                labels=run.label_runs if run is not None else (),
                error=category.value if refused else type(exc).__name__,
            )
            raise ToolError(f"{category.value}: {MESSAGES[category]}") from None
        finally:
            tracer.flush()
        result = _tool_result(run, output_path)
        _log(run_id, result.status, run=run)
        return CallToolResult(
            content=[TextContent(type="text", text=_result_text(result))],
            structuredContent=result.model_dump(mode="json"),
        )

    server = FastMCP("cv-reformatter")

    @server.tool(
        name=TOOL_NAME,
        description=DESCRIPTION,
        annotations=ToolAnnotations(
            title="Reformat a CV",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    async def reformat_cv(
        path: Annotated[
            str,
            Field(
                description="the .docx to reformat, absolute or relative to "
                "the Workspace"
            ),
        ],
    ) -> Annotated[CallToolResult, ToolResult]:
        # The pipeline blocks for the length of a labelling; off the event
        # loop, so the session keeps answering while it runs.
        return await anyio.to_thread.run_sync(run_tool, path)

    return server
