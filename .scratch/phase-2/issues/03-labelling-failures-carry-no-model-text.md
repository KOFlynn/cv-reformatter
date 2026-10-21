# 03: Labelling failures carry no model text

**What to build:** no exception or failure reason from the labeller ever carries the model's text. Today a schema-invalid answer's reason is the pydantic error's string, which repeats the model's output, and it flows into the Run, the logs and (later) the trace. Every exception at the labeller boundary is classified as provider unavailable, misconfigured, or a **Labelling failure**. A labelling failure's reason is a fixed category (refusal, invalid JSON, schema mismatch, unexpected) plus the error locations, filtered to known schema field names and integers. The prompt and schema do not change, so there is no version bump.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] A malformed answer, a schema-invalid answer, a LangChain output-parser error and a provider SDK error whose message embeds a canary string each produce a result in which the canary appears nowhere (reason, exception, `LabelRun`)
- [x] Error locations are reduced to an allowlist of the schema's own field names and integer indices; a segment outside the allowlist is dropped (tested)
- [x] The existing classification is unchanged: transient errors → `ProviderUnavailable`, rejected requests → `LabellerMisconfigured`, a refusal → labelling failure
- [x] Whatever else escapes the model call is classified rather than propagated with its message; the policy is stated in the labeller's docstring and on this ticket
- [x] Tested over a fake chat model (the existing labeller test seam); no LLM

## Comments

### 2026-10-21: built (Claude)

What was built, all in `src/cvr/label/labeller.py` (prompt, schema and `versions.json` untouched, no version bump):

- `failure_reason(exc)` gives a fixed category and never any message. It walks the cause/context chain (LangChain's `OutputParserException` wraps pydantic's and json's errors): a pydantic `ValidationError` is `schema mismatch at <locations>`, a `JSONDecodeError` or a bare parser error is `invalid JSON`, anything else is `unexpected`. A refusal keeps its existing text, `the model refused to answer`. A parsed value that is not a `Labelling` is `schema mismatch`.
- Locations: pydantic `loc` tuples are reduced by `_safe_location` to the segments that are integers or in `FAILURE_LOCATIONS` (every property name anywhere in `Labelling`'s JSON schema, computed at import); other segments (keys the model invented, union class names) are dropped, and a location with nothing left is omitted. Locations are de-duplicated, sorted and capped at 10.
- The provider errors keep their classification but their messages no longer include the SDK exception's text (only the type name and status code), and they are raised `from None`, so the SDK exception is not on the chain that `logger.exception` prints.

Classification policy (also in the module docstring): transient provider errors, `ProviderUnavailable`; rejected requests and unsupported provider, `LabellerMisconfigured`; the model answered unusably, refused, or anything else escaped the model call, a labelling failure with a fixed reason (`unexpected` for the last).

Decisions beyond the ticket text:

- "Anything else" is now a labelling failure with reason `unexpected`, not a propagating defect. Consequence: a code bug inside the model call no longer reaches the API as a 500; it surfaces as a banner document with reason `unexpected`. The test `test_anything_else_is_a_defect_and_propagates_unchanged` was replaced to say this.
- `__cause__` of the two provider errors is now `None` (previously the SDK exception); the two existing assertions `__cause__ is exc` were changed to assert the opposite, because the cause's message is the leak path.
- The old malformed-answer test used `ValueError("bad json")` and asserted the message in the reason; it now uses a `JSONDecodeError` and asserts `invalid JSON`.
- `build_chat_model`'s misconfiguration error is untouched; it holds no model text.
