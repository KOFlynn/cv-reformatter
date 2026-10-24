# 13: Retry decision, feedback and Run.retries

**What to build:** the pure pieces of the retry.
- **The decision:** retry only while **Unplaced text** remains and attempts are left (N from config, default 2). Stop when an attempt did not reduce the unplaced non-separator characters. Stop after a retry that was a labelling failure or a provider outage, keeping the previous verified result. A first attempt that was a labelling failure is retried.
- **Feedback construction from a verified result:** the unplaced runs (block id and offsets) and the unlocatable rejections in those blocks as hints. `conflict` and `removed` rejections are never feedback.
- **The Run's new optional `retries`**, empty by default. Each record holds the attempt's `LabelRun`, the feedback as ids, offsets and reasons (no text), its rejections, and the unplaced count after it. `label` stays the first attempt.

**Blocked by:** 11

**Status:** done

- [x] The decision function is tested for: nothing unplaced, progress, no progress, N reached, retry failure, retry outage, first-attempt failure
- [x] Progress counts unplaced non-separator characters only; separator-only residue never triggers (tested)
- [x] Feedback excludes `conflict` and `removed` rejections and carries no text in its stored form; the text the provider needs is recovered from the blocks by offset (tested)
- [x] A Run with retries round-trips through JSON; a Run without them serialises exactly as today's does (tested)
- [x] N is read from configuration with default 2, and documented

## Comments

**2026-10-24.** Built.

- `cvr.models.feedback` (`Feedback`, `UnplacedRun`, `UnlocatableHint`, the interface shared with ticket 12, not re-exported from `cvr.models`) and, in `cvr.models`, `RetryRun(label, feedback, rejections, unplaced_chars)` and `RetryRejection(path, block_id, reason)`. `Run.retries` defaults to empty. `models/__init__` imports `Feedback` just after `StrictModel` (feedback builds on it), the one non-top import there. `pyproject.toml` ignores RUF012 for `feedback.py` alone (its bare `[]` defaults are safe in pydantic and the file is fixed).
- The rules live in `cvr.verify.retry` (inputs are `VerifiedDocument`s; models/text only; pipeline wires them in ticket 14): `decide_retry(verified, previous_unplaced, attempts, max_retries, outcome="ok"|"failed"|"outage") -> RetryDecision(retry, reason)`, `unplaced_chars`, `build_feedback`, `retry_max`. N is `CVR_RETRY_MAX`, default 2, read only by `retry_max()`; non-numeric or negative raises `ValueError` naming the variable; 0 turns the retry off.
- Decision: `attempts` counts the attempts made including the one just finished, and a retry is allowed while `attempts <= N` (so N = 2 allows attempts 2 and 3). Reasons: `unplaced_text`, `first_attempt_failed` (retry); `nothing_unplaced`, `no_progress`, `attempts_exhausted`, `retry_failed`, `outage` (stop). An outage has no verified result (`verified` may be None); an `ok` outcome needs one. After a failed first attempt the caller passes `unplaced_chars` of that failed result (everything) as the previous count.
- Decision: progress counts non-separator characters, so spaces inside an unplaced run do not count; `no_progress` is `unplaced >= previous`, checked before `attempts_exhausted`.
- Decision: hints are the `unlocatable` rejections in blocks with unplaced text, except an unlocatable removal (`removals[i]`), which an addition cannot address. A labelling failure gives `Feedback(unusable=True)` with every unplaced run, no hints.
- Decision: `Run` omits `retries` from its JSON when empty (a wrap serializer), so a Run without retries serialises exactly as before.
- The API log writer does not serialise `retries` (it writes chosen fields), so nothing leaks; a test pins that a Run with retries logs the same lines as without. Summing cost over retries in the summary line is for the ticket that makes the log read them.

