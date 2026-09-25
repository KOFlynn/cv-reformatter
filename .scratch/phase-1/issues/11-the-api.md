# 11: The API

**What to build:** The service a caller, a browser, and Phase 3's MCP server will all use. FastAPI with `POST /reformat` taking a multipart `.docx` and returning the reformatted `.docx` with `Content-Disposition: attachment; filename="<stem>-reformatted.docx"` and `X-Run-Id`; middleware sets `X-Run-Id` on every response including 4xx and 5xx, so a failure is as traceable as a success. `GET /health` returns liveness and never touches the labeller. The real labeller is constructed once at startup from `LabellerConfig`; tests inject the oracle. The transform log is written to standard output as one summary line and per-block detail lines sharing the run id (Log Analytics truncates a single field around 32 KB; a 40-block ledger would not fit one line). A non-`.docx` upload is a 4xx with the run id; a labelling failure is still a 200 with a document under the banner. No endpoint returns a run, a log or a list of anything.

**Blocked by:** 06 (Pipeline function), 07 (The real labeller)

**Status:** in-review

- [x] `fastapi`, `uvicorn` runtime dependencies; `httpx` dev dependency; a `python -m cvr.api` entry that serves on the configured port
- [x] Test client with the oracle labeller: a golden-set document returns 200, a `.docx` body, the derived filename, and an `X-Run-Id` that matches the `Run`
- [x] A `.pdf` upload returns 4xx with `X-Run-Id`; an unhandled exception path returns 5xx with `X-Run-Id` (asserted with a labeller that raises)
- [x] `GET /health` returns 200 with no labeller constructed (asserted by constructing the app without a key)
- [x] Log lines: one summary JSON line and N detail lines per request, all carrying the run id; no single line exceeds 32 KB for the largest golden-set document
- [x] No route other than `/reformat` and `/health`
- [x] `docs/development.md` gains the run-locally instructions and the environment variables

## Comments

### 2026-09-24: built, in review (branch `phase-1/11-the-api`)

**What was built.** `src/cvr/api/`: `create_app(labeller=None)` in `app.py`, the transform log's line format in `log.py`, and `python -m cvr.api` in `__main__.py`, serving with uvicorn on `CVR_API_HOST` (default `127.0.0.1`) and `CVR_API_PORT` (default `8000`). `POST /reformat` takes the multipart field `file`, a `.docx`, and returns the output `.docx` with `Content-Disposition: attachment; filename="<stem>-reformatted.docx"`. `GET /health` returns `{"status": "ok"}`. Middleware issues the run id and sets `X-Run-Id` on every response. A non-`.docx` upload is a 415, a missing field FastAPI's 422, `ProviderUnavailable` a 503, `LabellerMisconfigured` or any other exception a 500. A labelling failure is a 200 with the banner document. Each `/reformat` request writes one summary JSON line and one line per block to standard output, every line carrying the run id. Dependencies: `fastapi`, `uvicorn` and `python-multipart` (runtime; FastAPI's `File` needs it), `httpx` (dev). Tests in `tests/api/` inject the oracle, a raising labeller or a counting stand-in for `RealLabeller`; none reaches a model. `docs/development.md` gains "Running the API locally" with every environment variable, and `CLAUDE.md` an `api` entry.

**Decisions beyond the ticket text.**

- **The run id is issued by the middleware and handed to the pipeline.** `reformat` gained a keyword `run_id=None` (its own commit, with a test). The Run had an id, but `reformat` minted it, and a refused upload never reaches `reformat` yet still needs one. So the middleware makes a `uuid4` hex before the request is read, and an accepted upload's Run is given the same id. The test asserts `X-Run-Id` equals `Run.run_id` and the summary line's `run_id`.
- **The real labeller is built on the first document, not at startup, and then kept for the process.** The ticket says "constructed once at startup". Once is kept, startup is not. The labeller is built lazily behind a lock, so `/health` never constructs it and never needs a key. The test swaps `RealLabeller` for a counter, removes `ANTHROPIC_API_KEY`, runs the app's startup and shutdown, and asserts no construction; a second test asserts two documents construct it exactly once. The cost: a missing or bad key passes both probes and shows only as a 500 on the first document. The deploy's smoke step (ticket 14) posts a document, which is what catches it. `RealLabeller` constructs without a key today anyway (the key is checked on the call), so eager construction would also have survived the probe; lazy just makes that not depend on LangChain's behaviour.
- **Documents run one at a time.** `RealLabeller` records its `LabelRun` on itself (`last_run`), and the pipeline reads it after the call. Two interleaved requests would swap each other's cost and tokens. A process-wide lock around `reformat` prevents that. With one replica and a demo's traffic this costs nothing. Making `last_run` per call would lift it; that is a label-package change, not taken here.
- **No route but the two, including FastAPI's own.** `docs_url`, `redoc_url` and `openapi_url` are `None`, so `/docs`, `/redoc` and `/openapi.json` are 404s like any other path, with `X-Run-Id`. The test reads the app's routes and asserts exactly `POST /reformat` and `GET /health`, and that nothing else is mounted. A generated schema page is harmless, but "no route other than" is the easier thing to check.
- **What goes on which log line.** The summary carries the status, any error, the label section, `label_failed`, the image removals (they belong to no block) and counts. Each block's line carries that block's ledger, text removals, normalisations, residue, dates and multi-span joins. A test rebuilds the whole Run from the lines. A request with no Run (refused, or failed) logs the summary alone. If the labeller had answered before a later node failed, its `LabelRun` goes on that summary, so money spent is logged either way. `/health` is not logged: the probe calls it every few seconds, and there is no Run to log. Lines are written with `sys.stdout.write`, not `logging`, so each is exactly one JSON object with no prefix.
- **32 KB is tested, not enforced.** The largest golden-set document by block count is `c11__two-column` (60 blocks). A default-suite test checks its lines. A slow test asserts it is the largest and checks all 48. A block line grows with its block's text, so a single paragraph of tens of kilobytes in a real CV would still produce an over-long line. Splitting a block across lines is not built; `log.py` says so.
- **The upload check is a `.docx` name on a zip archive**, anything else a 415 (Unsupported Media Type) before the pipeline runs. A zip that is not a readable `.docx` fails in `parse` and is a 500 with the run id. Content type is not checked, because browsers send it inconsistently.
- **The filename header.** The stem is the upload's name with any client directory stripped and `.docx` matched in any case. The `filename` parameter is made printable ASCII, with quote marks and backslashes replaced by `_`. Whenever that changed the name, the exact name is added as RFC 6266 `filename*`. For an ASCII name the header is exactly the ticket's.
- **`CVR_API_HOST` defaults to `127.0.0.1`.** Locally that serves loopback only; the container (ticket 12) sets `0.0.0.0`.
- **`tests/api/conftest.py` puts `tests/pipeline/` on `sys.path`**, so `oracle` and `pipeline_support` import as they do in `tests/pipeline/`. This is the first such conftest.

**Code review (`code-review` skill, against `origin/release/phase-1-09-11`).** Standards: no hard violations. Fixed:

- `log.py` rescanned every Run field per block; it now groups by block in one pass;
- the middleware function was named `run_id` and shadowed by its own local; it is now `attach_run_id`;
- the error string was built three ways; there is now one `_describe`;
- a one-member path set is gone;
- the tests repeated the media type instead of importing `DOCX_MEDIA_TYPE`;
- the new runtime dependencies were floor-only (uv's default); they are now bounded above, as `langchain` is.

Left as judgement calls:

- `request.state.run`/`label`/`error` is an untyped bag between route and middleware;
- the two test files share small helpers without a support module;
- the `sys.path` conftest has no precedent.

Spec, fixed:

- a failure after the labeller answered dropped the `LabelRun` (tokens and cost) from the log; it is now on the summary, tested;
- if writing the log raised, Starlette's error handler would have answered 500 without `X-Run-Id`; the write is now guarded, tested;
- `log.py`'s docstring overstated the 32 KB guarantee.

Spec, recorded above: the lazy labeller and its cost, the lock, and the 32 KB limit tested rather than enforced. No scope creep found.

**Tests.** Default suite: 1056 passed, 1 skipped (the labeller spike, no key), about 22s. Slow suite: 865 passed, about 35s. `tests/api/`: 31 in the default suite and 49 slow (all 48 documents' log lines, plus the largest-document check). `uv run python -m cvr.api` was started once on port 8765 without a key: `/health` answered 200 with `X-Run-Id` and `/docs` a 404. The server was then stopped.
