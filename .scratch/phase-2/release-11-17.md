# Phase 2 release 11-17

Phase 2's retry loop and the Azure OpenAI provider: path-addressed additions in verify, the retry prompt, the retry decision and the loop on the graph, the retry in the eval, the canary test over the retry, and `azure_openai` as a second provider through the default Azure credential. All seven tickets are done on `phase-2/release-11-17` (reviewed, with the fixes below on `phase-2/review-fixes`). Tickets 01-10 are on `main` (PR #40, merged 2026-10-24). One pull request for this release is the next step; it triggers one eval and one deploy.

## What each ticket delivered

- **11 Path-addressed additions in verify.** `Additions` (a list of `{path, reference}`) on top of the first answer: a list path appends, an empty leaf is filled, the next entry index opens a new entry; anything else is `bad_path` and claims nothing. Additions join the same ledger after every first-answer reference, so the first answer wins every conflict. Without additions verify is unchanged.
- **12 The retry prompt in `RealLabeller`.** `labeller(blocks, feedback=, first=)` sends `retry_prompt.md` (blocks, first answer, feedback with its text) and asks for `Additions`; a call without feedback is the first attempt. Four artefacts are version-checked at import and `CONTENT_HASH` covers all four.
- **13 Retry decision, feedback and `Run.retries`.** `verify.retry`: `decide_retry`, `build_feedback`, `unplaced_chars`, `retry_max` (`CVR_RETRY_MAX`, default 2). `Run.retries` (omitted when empty) holds one record per retry; `Run.label_runs` is what totals sum over.
- **14 The retry loop.** `verify -> label` is a conditional edge while unplaced text remains and attempts are left. A failed or unavailable retry keeps the previous result; an outage on the first attempt raises. Traced (a span per visit, a generation per attempt, a `retry_decision` event) and in the API summary (`retries`, `attempts`).
- **15 The retry in the eval, and ADR-0012.** The cache key covers each attempt; the report gains retries fired, characters placed by a retry and retry cost, with the expected pattern (c09 and c11, one no-progress retry each layout).
- **16 The canary test covers the retry.** Three retry scenarios (fixed, no progress, malformed) in all four layouts, through the API and `reformat`; nothing in `Run.retries`, logs, structure spans, exceptions or failure reasons. The request to the fake is excluded on purpose and a positive control shows it holds the text.
- **17 The Azure provider.** `CVR_LABEL_PROVIDER=azure_openai`: `AzureChatOpenAI` with a token provider, no key path, `reasoning_effort`, `max_completion_tokens`, strict structured output, Azure error classification, `gpt-5.4` priced. Offline strict-schema check. Not run against the real service.

## Decisions (the orchestrator's, recorded on the tickets and in ADR-0012)

- A failed first attempt is re-asked with the first prompt (an `Additions` answer cannot carry removals) and counts against N.
- Hints come only from the base answer's own rejections.
- The prompt shows the base answer folded with every earlier retry's placed additions (`verify.fold`); verify still runs over the unfolded base plus all additions, so the first answer wins every conflict (review S5).
- A defect on a retry (`LabellerMisconfigured`) stays a 500; the API's failure summary now sums every attempt paid for (review S2).

## Review fixes (`phase-2/review-fixes`)

- **B1 (blocking).** An addition's `path` is model-written; on `bad_path` it was stored verbatim in the `Rejection`, the `RetryRejection`, the structure-mode span and the API log. A path is now recorded only if it fits the path grammar (`cvr.models.safe_path`), else `unknown`, in verify, in the retry record and in `rejection_payload`. The canary test has a retry whose additions carry canaries as path and block id (block ids were already reported only when real). The `Additions` schema is unchanged.
- **S1.** An entry index of more than four digits is `bad_path`, not a `ValueError` (a 500).
- **S2.** See above.
- **S3.** Azure's `LengthFinishReasonError` is a `LabellingFailure` (`invalid JSON`, as Anthropic's truncation) and `ContentFilterFinishReasonError` one (`the model refused to answer`), on the first attempt and a retry.
- **S4.** `DefaultAzureCredential(exclude_environment_credential=True)`; `base_url`, `openai_api_base`, `azure_endpoint` and `default_headers` in `CVR_LABEL_EXTRA` are refused. Docs say the deployed app uses a system-assigned managed identity (ticket 18).
- **S5.** See above.
- **S6 and nits.** Stale docs corrected; the Feedback defaults use `default_factory` and the RUF012 ignore is gone; the non-separator count is one function, `cvr.text.significant_chars`; `tests/label/test_spike.py` read `run.config.model` on a dict (a plain bug fix in a test skipped without a key).

Existing assertions changed by the review: `test_an_unknown_field_or_a_malformed_path_is_bad_path` (free-text paths are recorded as `unknown`) and `test_hints_come_only_from_the_first_answer_not_from_earlier_additions` (the answer shown the second retry is the first plus the placed bullet, not identical).

## Open

- **Ticket 15's live-eval box** and **ticket 17's image-size box**: both are satisfied by the pull request's CI (the eval report, and the image check in the deploy job) and are ticked afterwards.
- **Ticket 19's live proof** must settle the token scope (`https://ai.azure.com/.default` against `https://cognitiveservices.azure.com/.default`), the API version, and whether Azure's five-level nesting limit counts arrays (`Labelling` is 4 levels by objects, 6 if arrays count; if rejected, a schema bump plus an eval).
- Tickets 18-21: provisioning, the managed identity proven live, the provider comparison and the ADR.

## Evidence

Eval: PR #41's CI eval (run 40117636883 at 193271d, 2026-10-24) passed every gate: every hard gate at zero, tunable placement 98.49% precision / 98.58% recall, appendix 0.67%. First attempts were replayed from the cache (48 hits; their keys are unchanged), the 9 retries were live, costing $0.1181. Pattern: c11 in all four Layouts and c09 in single-column, text-box and two-column made one retry each with no progress; the 40 other documents made none. The deviation: c09 header-footer made two, the first placing 25 characters its first attempt had left unplaced, the second making no progress, so the retry earned its keep there and stopped as the rules say. The report is the PR #41 comment and the run's `eval-report` artifact.

After the merge (2026-10-24): the `main` run at `accea1f` passed `check`, `eval` (`--no-cache`: the same totals, $1.7103 over 57 live calls, 137.5 s) and `deploy` (image 277MB on the runner against 231MB before, smoke 200, the app left off with no replica). Recorded on ticket 17.
