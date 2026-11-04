# 01: Shared Run log writer

**What to build:** the per-Run log writer the API uses today (one summary line and one line per block, PII stripped), `MAX_UPLOAD_BYTES` and the error categories move into one module that both the API and the MCP server will use. The writer takes the stream it writes to: the API keeps stdout, and the MCP server will use stderr. This is a prefactor, so the API behaves exactly as before. See the spec, "The shared module".

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The writer, `MAX_UPLOAD_BYTES` and the error categories live in one shared module (working name `cvr.runlog`; final name chosen here), and `api` imports them from there
- [ ] The writer takes the stream it writes to; the API passes stdout, and its output is byte-for-byte unchanged
- [ ] The existing log tests move with the writer and keep their assertions, and the rest of the API tests pass with only import paths changed
- [ ] A new test shows the writer writing to a given stream and nothing to stdout when given another
- [ ] The shared module depends on no server package (neither `api` nor `mcp`), and CLAUDE.md's package entries name it
