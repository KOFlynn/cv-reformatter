# 11: The API

**What to build:** The service a caller, a browser, and Phase 3's MCP server will all use. FastAPI with `POST /reformat` taking a multipart `.docx` and returning the reformatted `.docx` with `Content-Disposition: attachment; filename="<stem>-reformatted.docx"` and `X-Run-Id`; middleware sets `X-Run-Id` on every response including 4xx and 5xx, so a failure is as traceable as a success. `GET /health` returns liveness and never touches the labeller. The real labeller is constructed once at startup from `LabellerConfig`; tests inject the oracle. The transform log is written to standard output as one summary line and per-block detail lines sharing the run id (Log Analytics truncates a single field around 32 KB; a 40-block ledger would not fit one line). A non-`.docx` upload is a 4xx with the run id; a labelling failure is still a 200 with a document under the banner. No endpoint returns a run, a log or a list of anything.

**Blocked by:** 06 (Pipeline function), 07 (The real labeller)

**Status:** ready-for-agent

- [ ] `fastapi`, `uvicorn` runtime dependencies; `httpx` dev dependency; a `python -m cvr.api` entry that serves on the configured port
- [ ] Test client with the oracle labeller: a golden-set document returns 200, a `.docx` body, the derived filename, and an `X-Run-Id` that matches the `Run`
- [ ] A `.pdf` upload returns 4xx with `X-Run-Id`; an unhandled exception path returns 5xx with `X-Run-Id` (asserted with a labeller that raises)
- [ ] `GET /health` returns 200 with no labeller constructed (asserted by constructing the app without a key)
- [ ] Log lines: one summary JSON line and N detail lines per request, all carrying the run id; no single line exceeds 32 KB for the largest golden-set document
- [ ] No route other than `/reformat` and `/health`
- [ ] `docs/development.md` gains the run-locally instructions and the environment variables
