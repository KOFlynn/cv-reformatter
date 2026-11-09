# 02: `reformat_cv` in-process (tracer bullet)

**What to build:** an MCP client, in-process, calls `reformat_cv` with the path of a `.docx` inside the Workspace. The reformatted document appears next to it as `<stem>-reformatted-<first 8 characters of the run id>.docx`, and the client gets back a Tool result with no candidate text. This is the first slice of `cvr.mcp`, built on the official `mcp` SDK's `FastMCP`. See the spec, "Implementation Decisions", and ADR-0016.

**Blocked by:** 01

**Status:** done

- [x] `mcp` is an optional dependency group, installed by the local `uv sync` and not by the image's `--no-dev` sync; `uv.lock` updated
- [x] A factory, `create_server(labeller=None, tracer=None, workspace=None)`, mirrors the API's `create_app`. Tests inject the oracle labeller and a temporary Workspace
- [x] Exactly one tool, `reformat_cv(path)`. Its description states the Workspace rule, the output naming, that the result holds no CV text and that the caller should give the user the output path. Its annotations are `readOnlyHint` false, `destructiveHint` false, `idempotentHint` false and `openWorldHint` true
- [x] The path is resolved (absolute, or relative to the Workspace, with `..` and symlinks resolved first), and a path outside the Workspace is refused. The full set of refusals is ticket 04
- [x] The output is written next to the source document under the specified name through an exclusive create
- [x] The Tool result is structured content plus a short text rendering of `output_path`, `run_id`, `status`, `retries`, `removals` (rule → count), `unplaced` (spans and characters), `appendix` (a fixed sentence or none), `input_tokens`, `output_tokens` and `cost_usd` summed over every attempt. No field carries candidate text
- [x] `RealLabeller` is built on the first call and reused, calls are serialised by a lock, and the server lists its tool without a model key
- [x] Each Run is logged to stderr through the shared writer, with the API summary's keys and never the path or the file name
- [x] The pipeline's allowed importers are `api`, the eval runner and `mcp`; a test also fails if `api` imports `mcp` or `mcp` imports `api`
- [x] In-memory client tests (the SDK's client session) cover a successful call (the file exists, is a `.docx`, is named as specified, and the fields agree with the Run), the tool list with its schema, description and annotations, and one escape outside the Workspace

## Comments

2026-11-04, done on `phase-3/release-01-07`. `cvr.mcp.server` on the `mcp` SDK 1.30 (`FastMCP`); 21 tests in `tests/mcp/` through the SDK's in-memory client session (`mcp.shared.memory`), the oracle labeller and a temporary Workspace. The `mcp` group is pulled in by `dev` (`{ include-group = "mcp" }`), so `uv sync` installs it and `uv export --locked --no-dev` lists no `mcp`.

Decisions made here, for tickets 03 to 05:

- **The log's `status`.** The summary keys are the API's (tested against `request_lines`), but `status` is the Tool result's status (`ok`, `labelling_failed`) or the error category, where the API writes an HTTP code; `request_lines` takes `int | str`.
- **Errors.** A failure is a `ToolError` whose text is `<category>: <fixed message>` (the SDK prefixes `Error executing tool reformat_cv: `). `MESSAGES` already holds all eight categories, but only `outside_workspace` and `exists` are raised; `not_found`, `not_docx` and `too_large` checks, and their tests, are ticket 04's, as is the API's `_Paying` wrapper for a retry that raises. A failure after the Run (the output name taken) already logs the labelling it paid for under `attempts` (tested).
- **The pipeline runs off the event loop** (`anyio.to_thread.run_sync`), one call at a time under a lock (tested by three concurrent calls; shown to fail with the lock removed).
- **Tracer.** `create_server` without a tracer is untraced (`Tracer.disabled()`); building it from the environment with `surface=mcp` is ticket 05's.
- **Left as is from review:** `_LabellerSource` repeats the API's eight-line class; sharing it would need a module both servers import, which `runlog` is not the place for.
