# Phase 3 release 01-07

Phase 3 is the MCP server: `python -m cvr.mcp`, one tool, `reformat_cv(path)`, over stdio, so Claude Desktop can reformat a CV with the same pipeline the API and the eval run. All seven tickets are done on `phase-3/release-01-07` (spec `.scratch/phase-3/spec.md`, ADR-0016). It was proven live from Claude Desktop on 2026-11-09. One pull request for the whole phase is the next step. The brief's §10 Phase 3 boxes are ticked.

## What each ticket delivered

- **01 The shared Run log writer.** `cvr.runlog`: the API's log lines moved out of `api` (`request_lines`, `write_lines` to the stream the caller names), plus `MAX_UPLOAD_BYTES`, the eight fixed `ErrorCategory`s and `category_of`. The API's standard output is byte-for-byte unchanged; a test pins that `runlog` imports no server package.
- **02 `reformat_cv` in-process.** `cvr.mcp.create_server(labeller, tracer, workspace)` on the official `mcp` SDK (`FastMCP`, 1.30), mirroring `create_app`. The path is resolved (`..` and symlinks) and refused outside the Workspace (`CVR_MCP_ROOT`); the pipeline runs off the event loop, one call at a time; the output is written beside the source as `<stem>-reformatted-<run_id[:8]>.docx` through an exclusive create; the Tool result is structured content with an output schema plus a short text rendering, and holds no CV text. Each call logs the API's summary keys to standard error. The SDK is in the `mcp` dependency group, pulled in by `dev`, so the image's `--no-dev` sync skips it.
- **03 The server as a process, kept out of the image.** `python -m cvr.mcp` serves `create_server()` over stdio and refuses to start (exit 2, one `cvr.mcp: <Type>: <message>` line on standard error) without a Workspace or with a bad `CVR_RETRY_MAX`. `.dockerignore` leaves out `src/cvr/mcp`; `tests/docker/` and `scripts/check-image.sh` prove neither `cvr.mcp` nor the SDK can be imported in the image.
- **04 Every refusal and failure as a fixed category.** `outside_workspace`, `not_found`, `not_docx`, `too_large` (by `stat`, before the read), all before the labeller is built; then `provider_unavailable`, `misconfigured` and `internal` from the pipeline; then `exists`. Each is a tool error `<category>: <fixed message>`, never an exception's text; a labelling failure is not an error but `status: labelling_failed` with the banner document. A failed call logs every attempt already paid for, through `cvr.pipeline.PayingLabeller`, now shared by both servers (it was a private copy in each).
- **05 Tracing for MCP Runs.** Without an injected tracer the server builds `Tracer.from_env(tags=["env=local", "surface=mcp"], environment="local", mode="structure")`: one trace per call under the run id, structure only (`CVR_TRACE_MODE=full` is ignored with a warning; `Tracer.from_env` gained the `mode` override), untraced and silent without Langfuse keys, shut down when the server stops. A call refused before the pipeline starts no trace.
- **06 The canary leak test covers the MCP server.** `tests/tracing/test_mcp_canary_leak.py`: the canary Candidate through all four Layouts and eleven scenarios (labelling answers, failures and retries), with a canary in the file name, plus refused calls with a canary in the path. No canary reaches a Tool result field but `output_path`, standard error, an error text or a structure-mode span, and the model key appears nowhere. Written against the injected tracer in parallel with 05 and re-run green after 05 merged.
- **07 Live from Claude Desktop, and the docs.** The README's Phase 3 section (the tool, the Workspace and naming, the refusals, the Claude Desktop config with no secret, why stdio, why no text, why no `list_templates`), the screenshot, and the status docs.

## Evidence

- **The live call (2026-11-09).** Claude Desktop (Microsoft Store install, Windows 11) called `reformat_cv` on `c04__single-column.docx`: run id `8722af5e156748da81a81758e4c703e2`, status `ok`, no retries, 14 removals (4 address, 1 email, 1 phone, 2 URL, 6 heading), nothing unplaced, 5,523 tokens in and 2,118 out, $0.032. The output `c04__single-column-reformatted-8722af5e.docx` was written beside the source and opened in Word. Claude reported counts and the path, not the CV. Screenshot `docs/images/mcp-reformat-cv.png`.
- **Tests.** `tests/mcp/` and the MCP leak test run through the SDK's in-memory client session and as a stdio process. On 2026-11-09 the default suite is 1879 passed, 2 skipped (about 1 min 50 s) and the slow suite 936 passed (about 2 min). Ruff check and format clean.
- **The image** (`scripts/check-image.sh`, run by the maintainer 2026-11-05): 424 MB, the same as `main`'s (no runtime dependency changed), `src/cvr/mcp` absent, `cvr.mcp` and `mcp` unimportable, a real `/reformat` 200.

## Decisions

- **The log's `status`** is the Tool result's status or the error category, where the API writes an HTTP code; the summary's keys are the API's.
- **Structure-only tracing.** The API traces in the deployment's mode; the MCP server handles the user's own documents, so it never traces `full`.
- **Refusal at start-up** is exit status 2 with one named line on standard error, which Claude Desktop shows in its MCP log.
- **The slow suite** now also holds the tests that start `python -m cvr.mcp` (about ten seconds each) and the MCP leak test (14 s); CI runs it on every push. The documented suite timings were corrected to measured figures.
- **The flaky handshake test** sent its requests and closed stdin at once; closing stdin is the client's shutdown, on which the SDK cancels a request in flight, so `tools/list` was sometimes lost. The test now waits for each response, as a client does (3 failures in 20 before, 0 in 70 under load after). Not a server bug.

## What the live call found

- **`.env` quoting.** uv reads `\` in an unquoted `.env` value as an escape and then loads none of the file, so an unquoted Windows Workspace path stopped the server with `WorkspaceMissing`. The docs now single-quote it.
- **Claude Desktop from the Microsoft Store** keeps its config and logs under `%LOCALAPPDATA%\Claude-Data\claude_<id>\`, not where the docs first said; corrected.

## What the pull request will do

The PR's eval replays the labellings from the cache (no prompt, schema or model changed), so it should cost little. The merge to `main` runs an uncached eval (about $1.60) and redeploys the API's image, which is unchanged in content (the MCP server never reaches it); the app is left off afterwards with no replica.

## Open (the maintainer's)

- Ticket 22's last box (Phase 2): confirm the traces appear under Langfuse's Environment filter after the next eval.
