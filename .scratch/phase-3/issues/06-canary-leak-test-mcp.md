# 06: Canary leak test covers the MCP server

**What to build:** the content boundary in ADR-0016 is proved as ADR-0013's is. The canary leak test gains an MCP case, and a canary in the CV body or the file name reaches nothing it shouldn't.

**Blocked by:** 04, 05

**Status:** done

- [x] The canary Candidate goes through all four Layouts via `reformat_cv`, with a canary in the file name too, over `RealLabeller` and the fake chat model, including the retry scenarios and the failure answers
- [x] No canary appears in any Tool result field other than `output_path`, and the file-name canary appears in `output_path` only
- [x] No PII canary appears on stderr
- [x] No canary appears in any structure-mode span
- [x] The model key's value appears nowhere (stderr, Tool result, spans)
- [x] Positive controls: stderr holds content text and the spans hold the run id
- [x] The default run stays under thirty seconds, or the new cases are marked `slow`

## Comments

2026-11-05, written against the injected-tracer seam (`create_server(tracer=)`) in parallel with ticket 05, at the maintainer's choice; it must be re-run after 05 merges (05 changes what a call traces from the environment and what a refused call traces, and the tests already harvest refused calls with a canary in the path and assert nothing leaks in any span they produce).

`tests/tracing/test_mcp_canary_leak.py` reuses the harness of `test_canary_leak.py` (imported, not edited): 4 Layouts x 11 scenarios (7 labelling answers, 4 retry scenarios), each a `reformat_cv` call over a temp Workspace, the source named with a canary, plus four refusals. `tests/tracing/conftest.py` puts `tests/mcp` on `sys.path` for `mcp_support`.

Decisions:

- **The text rendering names the output path** (its first line), so the file-name canary may appear there and in `output_path`; the test removes exactly that line and the field, and requires everything else, in every class of canary, to be clean. Not loosened beyond what the Tool result states by design.
- **Standard error is stricter than the ticket**: no PII, model-echo or file-name canary (the log never names the path).
- **The model key** is a canary set as `ANTHROPIC_API_KEY` in the environment; with an injected chat model it is never read, so the check proves it is not echoed by the server, not that the client hides it.
- Tool errors are asserted equal to `<category>: <fixed message>` after the SDK's `Error executing tool reformat_cv: ` lead.
- Cost: about 22 s added to the default run, under the 30 s bar, so the cases are not marked slow.
- Proved able to fail by temporarily mutating `src/` (reverted): exception text in the tool error, the path or exception text in the log, the file name in a non-path structured field, the key on stderr, the path in the text rendering's other lines, block text as a span value. Block text under an unlisted span key is stopped by the allowlist, so that mutant stays green by design.
- **Review** (done inline by the implementing agent, not with sub-agents; fixed point 97dc1a3): standards clean (ruff, no `src/` edit, no existing assertion touched); spec boxes all met. Left as is: the module imports the harness from `test_canary_leak.py` rather than extracting it (keeps that file untouched); the model-key check cannot prove client-side hiding with an injected chat model. The slow suite showed one `test_mcp_main.py` handshake failure under load on this machine, passing alone (7 passed); not related to this ticket.
