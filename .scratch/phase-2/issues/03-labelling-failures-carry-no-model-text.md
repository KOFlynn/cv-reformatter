# 03: Labelling failures carry no model text

**What to build:** no exception or failure reason from the labeller ever carries the model's text. Today a schema-invalid answer's reason is the pydantic error's string, which repeats the model's output, and it flows into the Run, the logs and (later) the trace. Every exception at the labeller boundary is classified as provider unavailable, misconfigured, or a **Labelling failure**. A labelling failure's reason is a fixed category (refusal, invalid JSON, schema mismatch, unexpected) plus the error locations, filtered to known schema field names and integers. The prompt and schema do not change, so there is no version bump.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A malformed answer, a schema-invalid answer, a LangChain output-parser error and a provider SDK error whose message embeds a canary string each produce a result in which the canary appears nowhere (reason, exception, `LabelRun`)
- [ ] Error locations are reduced to an allowlist of the schema's own field names and integer indices; a segment outside the allowlist is dropped (tested)
- [ ] The existing classification is unchanged: transient errors → `ProviderUnavailable`, rejected requests → `LabellerMisconfigured`, a refusal → labelling failure
- [ ] Whatever else escapes the model call is classified rather than propagated with its message; the policy is stated in the labeller's docstring and on this ticket
- [ ] Tested over a fake chat model (the existing labeller test seam); no LLM
