# 13: Retry decision, feedback and Run.retries

**What to build:** the pure pieces of the retry.
- **The decision:** retry only while **Unplaced text** remains and attempts are left (N from config, default 2). Stop when an attempt did not reduce the unplaced non-separator characters. Stop after a retry that was a labelling failure or a provider outage, keeping the previous verified result. A first attempt that was a labelling failure is retried.
- **Feedback construction from a verified result:** the unplaced runs (block id and offsets) and the unlocatable rejections in those blocks as hints. `conflict` and `removed` rejections are never feedback.
- **The Run's new optional `retries`**, empty by default. Each record holds the attempt's `LabelRun`, the feedback as ids, offsets and reasons (no text), its rejections, and the unplaced count after it. `label` stays the first attempt.

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] The decision function is tested for: nothing unplaced, progress, no progress, N reached, retry failure, retry outage, first-attempt failure
- [ ] Progress counts unplaced non-separator characters only; separator-only residue never triggers (tested)
- [ ] Feedback excludes `conflict` and `removed` rejections and carries no text in its stored form; the text the provider needs is recovered from the blocks by offset (tested)
- [ ] A Run with retries round-trips through JSON; a Run without them serialises exactly as today's does (tested)
- [ ] N is read from configuration with default 2, and documented
