# 04: Every refusal and failure as a fixed category

**What to build:** every way a `reformat_cv` call can go wrong comes back as a tool error (`isError`) in one of eight fixed categories, each with a fixed message and never an exception's text. A labelling failure is not an error: the job completes with the banner document, as the API's 200 does. See the spec, "Errors".

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] `outside_workspace`: escapes by `..`, by an absolute path and by a symlink are each refused (the symlink test is skipped where the platform cannot create one)
- [ ] `not_found`: a missing path, and a directory, are refused
- [ ] `not_docx`: a file that doesn't end in `.docx` (case-insensitive) is refused
- [ ] `too_large`: a file over `MAX_UPLOAD_BYTES` is refused before it is read
- [ ] `exists`: an existing output name is refused, nothing is overwritten and there is no silent retry
- [ ] `provider_unavailable` for `ProviderUnavailable`, and `misconfigured` for `LabellerMisconfigured`, each with its fixed message
- [ ] `internal` for anything else, logged by type name only
- [ ] A labelling failure writes the banner document and returns `status: labelling_failed` with the other fields filled
- [ ] Each failed call logs its summary line alone to stderr, with the error category and any `LabelRun` already paid for, as the API does
