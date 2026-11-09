# 01: Shared Run log writer

**What to build:** the per-Run log writer the API uses today (one summary line and one line per block, PII stripped), `MAX_UPLOAD_BYTES` and the error categories move into one module that both the API and the MCP server will use. The writer takes the stream it writes to: the API keeps stdout, and the MCP server will use stderr. This is a prefactor, so the API behaves exactly as before. See the spec, "The shared module".

**Blocked by:** None (can start immediately)

**Status:** done

- [x] The writer, `MAX_UPLOAD_BYTES` and the error categories live in one shared module (working name `cvr.runlog`; final name chosen here), and `api` imports them from there
- [x] The writer takes the stream it writes to; the API passes stdout, and its output is byte-for-byte unchanged
- [x] The existing log tests move with the writer and keep their assertions, and the rest of the API tests pass with only import paths changed
- [x] A new test shows the writer writing to a given stream and nothing to stdout when given another
- [x] The shared module depends on no server package (neither `api` nor `mcp`), and CLAUDE.md's package entries name it

## Comments

- 2026-11-04: Done. The final name is `cvr.runlog`. `runlog.lines` is `api.log` moved with `git mv`, and `write_lines(lines, stream)` now requires the stream. `runlog.errors` holds `MAX_UPLOAD_BYTES`, `ErrorCategory` (all eight of the spec's categories, five of them unused until tickets 03 and 04) and `category_of`, which the API now uses to pick its 503 or 500. The API's stdout was compared byte for byte against `0dcb5a4` and found identical: two documents, a 415 and a 401, with the run id pinned, 36,356 bytes each. The log tests are split. The ones over `request_lines` are now `tests/runlog/test_lines.py`, and the ones that drive the app stay in `tests/api/test_log.py`, with the canaries shared through `tests/log_canaries.py`. An AST comparison shows all 24 functions kept their bodies. One non-import edit in the API tests: the `broken` stub in `test_app.py` takes `stream`, or it would have failed with a TypeError in place of the OSError it is there to raise. `tests/runlog/test_runlog_imports.py` pins the rule against importing a server package, by a static check and in a subprocess. It was shown to fail when `errors.py` imported `cvr.api`.
