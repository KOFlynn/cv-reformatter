# 02: `reformat_cv` in-process (tracer bullet)

**What to build:** an MCP client, in-process, calls `reformat_cv` with the path of a `.docx` inside the Workspace. The reformatted document appears next to it as `<stem>-reformatted-<first 8 characters of the run id>.docx`, and the client gets back a Tool result with no candidate text. This is the first slice of `cvr.mcp`, built on the official `mcp` SDK's `FastMCP`. See the spec, "Implementation Decisions", and ADR-0016.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `mcp` is an optional dependency group, installed by the local `uv sync` and not by the image's `--no-dev` sync; `uv.lock` updated
- [ ] A factory, `create_server(labeller=None, tracer=None, workspace=None)`, mirrors the API's `create_app`. Tests inject the oracle labeller and a temporary Workspace
- [ ] Exactly one tool, `reformat_cv(path)`. Its description states the Workspace rule, the output naming, that the result holds no CV text and that the caller should give the user the output path. Its annotations are `readOnlyHint` false, `destructiveHint` false, `idempotentHint` false and `openWorldHint` true
- [ ] The path is resolved (absolute, or relative to the Workspace, with `..` and symlinks resolved first), and a path outside the Workspace is refused. The full set of refusals is ticket 04
- [ ] The output is written next to the source document under the specified name through an exclusive create
- [ ] The Tool result is structured content plus a short text rendering of `output_path`, `run_id`, `status`, `retries`, `removals` (rule → count), `unplaced` (spans and characters), `appendix` (a fixed sentence or none), `input_tokens`, `output_tokens` and `cost_usd` summed over every attempt. No field carries candidate text
- [ ] `RealLabeller` is built on the first call and reused, calls are serialised by a lock, and the server lists its tool without a model key
- [ ] Each Run is logged to stderr through the shared writer, with the API summary's keys and never the path or the file name
- [ ] The pipeline's allowed importers are `api`, the eval runner and `mcp`; a test also fails if `api` imports `mcp` or `mcp` imports `api`
- [ ] In-memory client tests (the SDK's client session) cover a successful call (the file exists, is a `.docx`, is named as specified, and the fields agree with the Run), the tool list with its schema, description and annotations, and one escape outside the Workspace
