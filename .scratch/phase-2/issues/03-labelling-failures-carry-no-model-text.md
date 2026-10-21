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
- The provider errors keep their classification but their messages no longer include the SDK exception's text (only the type name and status code), and they are raised outside the `except` block, so the SDK exception is on neither `__cause__` nor `__context__` (found in review: `from None` alone leaves `__context__` set, which `logger.exception` and tracers can still reach).

Classification policy (also in the module docstring): transient provider errors, `ProviderUnavailable`; rejected requests and unsupported provider, `LabellerMisconfigured`; the model answered unusably, refused, or anything else escaped the model call, a labelling failure with a fixed reason (`unexpected` for the last).

Decisions beyond the ticket text:

- "Anything else" is now a labelling failure with reason `unexpected`, not a propagating defect. Consequence: a code bug inside the model call no longer reaches the API as a 500; it surfaces as a banner document with reason `unexpected`. The test `test_anything_else_is_a_defect_and_propagates_unchanged` was replaced to say this.
- `__cause__` and `__context__` of the two provider errors are now `None` (previously the SDK exception was the cause); the two existing assertions `__cause__ is exc` were changed to assert the opposite, because the cause's message is the leak path.
- The old malformed-answer test used `ValueError("bad json")` and asserted the message in the reason; it now uses a `JSONDecodeError` and asserts `invalid JSON`.
- `build_chat_model`'s misconfiguration error is untouched; it holds no model text.

### 2026-10-21: review (Claude)

Fixed: `from None` left `__context__` set (now the error is raised outside the `except`, asserted `__context__ is None`); two stale docstrings (`anthropic_error`, `errors.py`).

Left for the maintainer: (1) ADR-0009 still says "anything else is a defect and propagates", which this ticket reverses; an amendment is the maintainer's call. (2) `unexpected` as a labelling failure hides code defects as a banner document and, in Phase 2, would be retried as a model failure; a safe log of the exception type was considered and not added (no logger in `label`). (3) The refusal reason keeps its existing text `the model refused to answer` rather than the bare word `refusal` (an existing test pins it). (4) Any `OutputParserException` with no JSON or validation error in its chain is called `invalid JSON`.

### 2026-10-21: maintainer decision (Claude)

The maintainer reversed the `unexpected` category. An unexpected exception from the model call, or a parsing error that is neither JSON nor schema, is not a labelling failure: it raises `LabellerMisconfigured` with a fixed message naming only the exception's type, raised outside the `except` block (no `__cause__`, no `__context__`). The API already maps `LabellerMisconfigured` to its existing 500, so a defect stays loud and nothing retries it as a model failure. Refusal, invalid JSON and schema mismatch stay labelling failures. This supersedes the first decision above ("anything else is a labelling failure with reason `unexpected`") and open point (2) of the review. `failure_reason` now returns `None` for an unrecognised error; the two tests for it assert a `LabellerMisconfigured` with no canary in its message, repr or chain. The labeller and `errors` docstrings, CLAUDE.md's `label` entry and ADR-0009 (amendment) were updated.
