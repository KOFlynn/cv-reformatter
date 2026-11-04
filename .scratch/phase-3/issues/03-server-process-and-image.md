# 03: The server as a process, and kept out of the image

**What to build:** `python -m cvr.mcp` builds the server from the environment and serves it over stdio, so Claude Desktop can start it. The deployed image is unchanged: neither `cvr.mcp` nor the SDK reaches it.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] `python -m cvr.mcp` reads the Workspace from `CVR_MCP_ROOT` once, at startup, and serves `create_server(...)` over stdio
- [ ] It refuses to start, with a named error on stderr, when `CVR_MCP_ROOT` is unset, empty or not a directory, and when `CVR_RETRY_MAX` is invalid (`retry_max()` is read at startup)
- [ ] Only the SDK writes to stdout; logging and warnings go to stderr
- [ ] A subprocess test, run with a temporary Workspace and no key, covers the initialise handshake, the tool list, every stdout line parsing as JSON-RPC and a clean exit when stdin closes. It makes no `reformat_cv` call
- [ ] `.dockerignore`'s allowlist leaves out `src/cvr/mcp`, and `tests/docker/` checks both that and that the service runs with `cvr.mcp` impossible to import
- [ ] `docs/development.md` gives the command to run the server locally and its environment variables
