# 06: Canary leak test covers the MCP server

**What to build:** the content boundary in ADR-0016 is proved as ADR-0013's is. The canary leak test gains an MCP case, and a canary in the CV body or the file name reaches nothing it shouldn't.

**Blocked by:** 04, 05

**Status:** ready-for-agent

- [ ] The canary Candidate goes through all four Layouts via `reformat_cv`, with a canary in the file name too, over `RealLabeller` and the fake chat model, including the retry scenarios and the failure answers
- [ ] No canary appears in any Tool result field other than `output_path`, and the file-name canary appears in `output_path` only
- [ ] No PII canary appears on stderr
- [ ] No canary appears in any structure-mode span
- [ ] The model key's value appears nowhere (stderr, Tool result, spans)
- [ ] Positive controls: stderr holds content text and the spans hold the run id
- [ ] The default run stays under thirty seconds, or the new cases are marked `slow`
