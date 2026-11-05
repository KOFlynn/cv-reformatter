# 04: Every refusal and failure as a fixed category

**What to build:** every way a `reformat_cv` call can go wrong comes back as a tool error (`isError`) in one of eight fixed categories, each with a fixed message and never an exception's text. A labelling failure is not an error: the job completes with the banner document, as the API's 200 does. See the spec, "Errors".

**Blocked by:** 02

**Status:** done

- [x] `outside_workspace`: escapes by `..`, by an absolute path and by a symlink are each refused (the symlink test is skipped where the platform cannot create one)
- [x] `not_found`: a missing path, and a directory, are refused
- [x] `not_docx`: a file that doesn't end in `.docx` (case-insensitive) is refused
- [x] `too_large`: a file over `MAX_UPLOAD_BYTES` is refused before it is read
- [x] `exists`: an existing output name is refused, nothing is overwritten and there is no silent retry
- [x] `provider_unavailable` for `ProviderUnavailable`, and `misconfigured` for `LabellerMisconfigured`, each with its fixed message
- [x] `internal` for anything else, logged by type name only
- [x] A labelling failure writes the banner document and returns `status: labelling_failed` with the other fields filled
- [x] Each failed call logs its summary line alone to stderr, with the error category and any `LabelRun` already paid for, as the API does

## Comments

2026-11-05, done on a branch off `phase-3/release-01-07`. `tests/mcp/test_mcp_refusals.py` (27 tests, through the in-memory client session) covers each box; ticket 02's tests are unchanged.

Decisions made here:

- **Check order** in `_source_file`: resolve (`outside_workspace`), then not a file (`not_found`, a directory included), then suffix (`not_docx`, on the resolved name, so a symlink inside the Workspace to a non-docx is refused), then `stat` size over `MAX_UPLOAD_BYTES` (`too_large`; exactly the limit passes). Only then is the file read and the labeller built. `exists` stays last, after the pipeline, because the name carries the run id (ticket 02).
- **`_Paying` is repeated in `mcp.server`**, not shared: it needs `can_retry` from `pipeline` and the labeller's `last_run`, and a module both servers import would be a new package for twenty lines; `api` and `mcp` must not import each other. Same call as `_LabellerSource` in ticket 02. The failure log uses `run.label_runs` when the Run exists (the output name taken) and `paying.paid` when an attempt raised.
- **The log's `error`** is the category for a refusal and the exception's type name for anything the pipeline raised; no message text reaches the result or standard error (tested with a canary in the exception text, on an `internal` error and on a defect on the third attempt).
- **The symlink test** skips where `os.symlink` raises (Windows without privilege).
- **Review, left as is:** the size is checked by `stat` and the file read separately, so a file growing between the two is read whole (a local race on a user's own Workspace, and the pipeline bounds the cost); `_Paying` duplicates the API's class (above); its name and the nested conditional in the failure log were judged clear enough. `exists` after the pipeline costs a model call when the name is taken (ticket 02's decision, the name carries the run id).
