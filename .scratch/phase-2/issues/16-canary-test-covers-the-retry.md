# 16: The canary test covers the retry

**What to build:** the leak test from ticket 10, extended to the retry. The provider boundary and the log/trace boundary are kept separate: the scripted fake *receives* canary text in its retry feedback, which is by design, while the `RetryRun`, the logs and the structure traces carry none. A retry whose answer is malformed and contains a canary leaks nowhere.

**Blocked by:** 10, 14

**Status:** done

- [x] Positive control: the fake chat model's retry request contains the unplaced canaries
- [x] No canary appears in `Run.retries`, the log output, structure-mode spans or recorded exceptions, across a retry that succeeds, one with no progress and one that is malformed
- [x] The assertion explicitly excludes the request sent to the fake, and the test says why
- [x] It stays in the default suite

## Comments

**2026-10-24.** Built, in `tests/tracing/test_canary_leak.py` (default suite; no source change, no leak found).

- Three scenarios join the existing seven, each through all four Layouts and both the API and `reformat`, using the real `RealLabeller` over a new `RetryChat` (the old `FakeChat` answers every schema with a `Labelling`, so a retry there just failed): the first answer leaves a job's first bullet unplaced and carries a skill whose quote the model made up (a hint to the retry); then `retry-fixed` (an `Additions` placing the bullet plus one with a made-up quote, then a no-progress one, since c11's unplaceable fragments keep the loop going), `retry-no-progress` (empty `Additions`; the loop stops after one retry) and `retry-malformed` (a malformed answer whose text and parse error carry a model canary and a PII phone).
- Checked by the existing tests, now over the retry scenarios too: spans, logs (stdout, stderr, DEBUG), error bodies, exceptions, the first attempt's failure reason. New: `Run.retries` (JSON) and the retries' failure reasons (`reasons_after_retry`) are checked for every canary.
- Positive controls: the fake's retry requests are recorded (the human message of every `Additions` call) and each holds the unplaced fragments (a content canary) and, in the first retry, the dropped bullet and the made-up quote as an unlocatable hint (a model canary); the retries are exercised in each kind (record counts, `label_failed`, `invalid JSON`), and every retry scenario has `retry_decision` events in its spans.
- The recorded requests are never read by a leak assertion; the module docstring and the retries test say why (provider boundary versus log/trace boundary, ADR-0013). ADR-0013's "what the test does not cover yet" paragraph said the retry did not exist; it now states the exclusion.
- Mutation check: appending `str(parsing_error)` to a labelling failure reason made five tests fail, and the change was reverted.
- Cost: the module goes from about 33 s to about 44 s on this machine (the tests share one module-scoped harvest of 40 runs, 24 of them new).

Decisions beyond the ticket text:

1. Which job comes first depends on the Layout, so the dropped bullet is checked against any job's first bullet (`Harvest.bullets`).
2. `Channels.reasons` stays the first attempt's reason (the existing malformed assertion is unchanged); the retries' reasons are a separate channel, because a failed first answer is now re-asked and fails again (ticket 14, decision 1).
3. The flake: `test_full_mode_changes_no_output_or_run` compared the output `.docx` bytes of two renders. Confirmed: two renders of one source 2.2 s apart have equal parts but different bytes, since each zip entry carries the build time to 2 seconds. It now compares the zip's entry names and decompressed contents (`docx_parts`, moved from `test_review_fixes.py`, which had the same fix already, to `tracing_support.py`); a sabotaged render (one part altered) still fails it. No other test compares rendered `.docx` bytes. Separate commit.
