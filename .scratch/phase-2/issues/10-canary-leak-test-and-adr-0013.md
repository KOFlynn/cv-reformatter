# 10: The canary leak test, and ADR-0013

**What to build:** the control that turns the content boundary from a claim into evidence. It is one test in the default pytest run, with no LLM.
- A copy of one Candidate is built at test time, with nothing in `fixtures/` changed. Every content leaf, PII value and fragment becomes a unique canary from a seeded generator, checked for collisions with run ids and hashes. Canaries are shaped like what they replace (digit strings for phones, a unique domain for emails), and dates stay real.
- It is rendered through all four Layouts and taken through the API and `reformat` in structure mode, with the real `RealLabeller` over a fake chat model whose answers include a malformed one containing a canary.
- No canary, nor its normalised forms (spaces removed, case folded), appears in any exported span (names, attributes, events, status, resource attributes, tags, metadata, session ids). No PII canary appears in the logs (stdout and stderr captured at DEBUG), API error bodies, recorded exceptions or the Run's failure reasons.
- Positive controls stop the test passing blind, and a source-token check runs as a second layer.

ADR-0013 records the content boundary:
- the LLM provider receives the CV text on every run;
- beyond it, candidate text reaches no third party, and Langfuse in production receives structure only;
- the logs keep text inside our tenant, minus PII;
- the allowlist and the mask hook are the two layers;
- retention is the figure from ticket 06;
- for real CVs: masking or self-hosted Langfuse, a DPA, retention by policy, and EU-bound processing for every provider.

**Blocked by:** 03, 04, 05, 06, 08, 09

**Status:** ready-for-agent

- [ ] The canary test runs in the default suite and stays fast (no slow marker needed)
- [ ] Positive controls: ids and counts in the spans; non-PII canaries in the logs; canaries in the trace in full mode
- [ ] Deliberately breaking the payload allowlist (in a scratch run, not committed) makes the test fail; noted in the PR
- [ ] ADR-0013 written; the README's ADR section points to it
- [ ] A screenshot of one full-mode eval trace, with its run id, committed for the README (the Langfuse project stays private)
