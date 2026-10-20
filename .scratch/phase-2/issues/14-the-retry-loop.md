# 14: The retry loop

**What to build:** the graph's edge from verify becomes conditional, so a Run with unplaced text loops back to label with **Feedback**, at most N times, before going on to transform. Each retry is recorded in `Run.retries` and traced (a span per node visit, a generation per attempt, an event per retry decision). A labelling failure or a provider outage on a retry keeps the previous result and completes the job. A failed first attempt is retried. An outage on the first attempt still raises, as today. The API's summary log line sums cost and tokens over all attempts.

**Blocked by:** 02, 07, 12, 13

**Status:** ready-for-agent

- [ ] With the scripted fake (the real `RealLabeller` over a fake chat model) through `reformat`: a perfect first attempt makes no retry; a flawed first attempt fixed by a retry places the text and empties the appendix; a true fragment costs exactly one retry; N is respected
- [ ] A malformed retry answer and an outage on a retry each return the previous result's document, and record the failed attempt
- [ ] A first-attempt labelling failure followed by a good retry yields a placed document
- [ ] An outage on the first attempt still raises `ProviderUnavailable` (API: 503)
- [ ] The node-order test is rewritten to "in order, with label and verify repeated only on a retry", with the reason stated in the PR
- [ ] Traces of a retried Run show the extra node visits and generations (in-memory exporter)
- [ ] The API summary line's cost and tokens equal the sum over attempts; no line exceeds the size limit for the golden set
- [ ] The perfect oracle over all 48 documents still scores clean (slow suite)
