# 16: The canary test covers the retry

**What to build:** the leak test from ticket 10, extended to the retry. The provider boundary and the log/trace boundary are kept separate: the scripted fake *receives* canary text in its retry feedback, which is by design, while the `RetryRun`, the logs and the structure traces carry none. A retry whose answer is malformed and contains a canary leaks nowhere.

**Blocked by:** 10, 14

**Status:** ready-for-agent

- [ ] Positive control: the fake chat model's retry request contains the unplaced canaries
- [ ] No canary appears in `Run.retries`, the log output, structure-mode spans or recorded exceptions, across a retry that succeeds, one with no progress and one that is malformed
- [ ] The assertion explicitly excludes the request sent to the fake, and the test says why
- [ ] It stays in the default suite
