# 03: The server as a process, and kept out of the image

**What to build:** `python -m cvr.mcp` builds the server from the environment and serves it over stdio, so Claude Desktop can start it. The deployed image is unchanged: neither `cvr.mcp` nor the SDK reaches it.

**Blocked by:** 02

**Status:** done

- [x] `python -m cvr.mcp` reads the Workspace from `CVR_MCP_ROOT` once, at startup, and serves `create_server(...)` over stdio
- [x] It refuses to start, with a named error on stderr, when `CVR_MCP_ROOT` is unset, empty or not a directory, and when `CVR_RETRY_MAX` is invalid (`retry_max()` is read at startup)
- [x] Only the SDK writes to stdout; logging and warnings go to stderr
- [x] A subprocess test, run with a temporary Workspace and no key, covers the initialise handshake, the tool list, every stdout line parsing as JSON-RPC and a clean exit when stdin closes. It makes no `reformat_cv` call
- [x] `.dockerignore`'s allowlist leaves out `src/cvr/mcp`, and `tests/docker/` checks both that and that the service runs with `cvr.mcp` impossible to import
- [x] `docs/development.md` gives the command to run the server locally and its environment variables

## Comments

2026-11-05, done on `phase-3/release-01-07`. `cvr.mcp.__main__` is a ten-line `main()` over `create_server()`, serving with `server.run("stdio")`; `tests/mcp/test_mcp_main.py` (7 tests, about ten seconds each, which is the interpreter importing the pipeline) runs it as a subprocess with a temporary Workspace and every `CVR_*`, `ANTHROPIC_*`, `LANGFUSE_*` and `AZURE_*` variable removed.

Decisions made here:

- **Refusal.** `WorkspaceMissing` and `ValueError` (the type `retry_max()` raises) are caught in `main()` only: one line `cvr.mcp: <Type>: <message>` on standard error, exit status 2, nothing on standard output and no traceback. Anything else is a defect and keeps its traceback.
- **Clean stdout.** The test sends initialise, `initialized` and `tools/list`, closes stdin, and asserts exit 0, every stdout line JSON with `jsonrpc` 2.0, and the tool list equal to `["reformat_cv"]`. The SDK logs to standard error by default; nothing in `cvr.mcp` prints.
- **The image.** `.dockerignore` gains `src/cvr/mcp/`; the static test lists three `cvr/mcp` paths as never in the context and drops the package from the "needed" sources. The runtime-imports test now also blocks the top-level `mcp` (the SDK), so it proves the service needs neither; `uv export --locked --no-dev` lists no `mcp`, so `pyproject.toml` is unchanged. The image was not rebuilt (no Docker step changed).
- **Docs.** `docs/development.md` has a section with the command and a variable table; the Claude Desktop setup is left to ticket 07.
- **Review (`/code-review` since aa26d12).** Acted on: `scripts/check-image.sh` now also checks `/app/src/cvr/mcp` absent and `cvr.mcp` and `mcp` unimportable in a built image (not run: Docker not used here); `main()` calls `retry_max()` in its own `try`, so only its `ValueError` is a refusal and any other out of `create_server()` keeps its traceback. Left: the excluded package names are spelled in four test and script places (a shared list would need a module for a three-name tuple); `REFUSED` kept as is; the "only the SDK writes to stdout" box is held by the handshake test and by `cvr.mcp` never printing to stdout, with no active guard (a `reformat_cv` call over stdio is ticket 04's to test).

