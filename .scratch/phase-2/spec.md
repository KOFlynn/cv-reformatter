# Phase 2: agentic workflow, observability, second provider

Status: ready-for-agent

Vocabulary: `CONTEXT.md`. This phase adds **Attempt**, **Retry**, **Feedback**, **Trace** and **Deployed provider**, beside **Run**, **Transform log**, **Labelling failure**, **Unplaced text**, **Rejection**-bearing **Claim** and **Model comparison**. Decisions: `docs/adr/0001` (the LLM labels, code transforms), `0004` (review by exception), `0008` (claim ledger), `0009` (structured labelling), `0010` (deployment), `0011` (Sonnet is the default). This phase writes ADR-0012 to 0015 as their tickets land. Source brief: `docs/project-brief.md` §10, Phase 2, and §8, which this phase amends. The decisions here come from a grilling session held on 2026-10-20.

## Problem Statement

Phase 1 proved the lifecycle: a plain function pipeline, one labelling call, an eval gate, and a deployment through OIDC. Three of the gaps the brief names are still open.

- **Agentic framework, hands-on.** The pipeline is a straight run of five calls. When the labeller misquotes or misses text, that text goes straight to the review appendix. Nothing asks the model to try again, though the brief's architecture has always drawn a bounded retry loop.
- **Observability tooling.** A Run's only record is the transform log in Log Analytics. Nothing shows the steps of a Run, what the labeller answered, what verify rejected, how long each step took or what it cost, and nothing links an API response's `X-Run-Id` to such a record. Demo step 4 ("the trace") has nothing to show.
- **Managed identity to Azure OpenAI, and a provider chosen by eval.** Only Anthropic is wired. The brief promises a second provider reached with no key at all, and a provider verdict backed by numbers.

Building tracing also brought to light a problem that is already live. The deployed app writes every word of every CV to Log Analytics, including the PII values it removed. A labelling failure's reason repeats the model's own text, because it is built from the pydantic error. Sending text to a third-party tracing service would make that worse unless the boundary is designed rather than assumed.

## Solution

The pipeline moves onto LangGraph with the same five nodes and one conditional edge from `verify` back to `label`.

**The retry.** A **Retry** fires only while **Unplaced text** remains, at most twice (N = 2). Each retry sends the model every block, its first answer and **Feedback**: the unplaced runs, plus the unlocatable rejections in those blocks as hints. The model answers with path-addressed additions only, and verify re-runs over the first answer followed by the additions. The loop stops early when an attempt leaves no less unplaced text than the one before. Anything still unplaced goes to the appendix as before.

**Tracing.** Every Run is traced in Langfuse Cloud (EU, Hobby), with the run id itself as the trace id.
- In production a trace is a structure trace: ids, counts, reasons, timings, tokens and cost, never candidate text.
- Full traces, with the text, are produced only by the CI eval and by local runs, both of which use synthetic fixtures.

The boundary is built as an allowlist and backed by a mask hook. It is proved by a canary test in the default test run, which also covers the logs, error bodies and exceptions.

**Logs and errors.** The logs stay full inside our own tenant, except that PII values are stripped wherever they occur. Failure reasons and exception messages are reduced to fixed categories, so the model's text never reaches them.

**Azure OpenAI.** Azure OpenAI is added as a second provider: gpt-5.4 on a Data Zone Standard (EU) deployment, reached from Container Apps through a managed identity, with key authentication disabled on the resource. It is compared with Sonnet 5.5 at `medium` as a **Model comparison**, run by hand: three runs against three, recorded and dated. The verdict goes in an ADR.
- The eval gate always runs the **Deployed provider**.
- If Azure wins, CI reaches it through a narrow OIDC identity that holds only the inference role.
- Whichever provider wins, the managed identity path is proven once against the live app.

## User Stories

Actors:
- the *maintainer*, who runs evals and provisioning and makes the calls;
- the *reviewer*, a hiring manager or interviewer reading the evidence;
- the *caller*, who posts a CV to the API;
- *CI*, the gate and the deploy job;
- *Phase 3*, the MCP server, which inherits the pipeline;
- a *sub-agent*, which implements one ticket.

### The graph

1. As the reviewer, I want the pipeline to run as a LangGraph state machine, so that the agentic-framework gap is closed by real, used code.
2. As the maintainer, I want the graph to keep exactly the five Phase 1 nodes (parse, label, verify, transform, render), so that the Phase 1 promise that the swap is mechanical is shown to hold.
3. As the maintainer, I want the first graph ticket to change no behaviour at all, so that an unchanged eval report proves the node boundaries held.
4. As the API and the eval runner, I want `reformat` to keep its signature and return type, so that neither caller changes when the orchestration does.
5. As the maintainer, I want any new return data added only as new optional fields, so that existing readers of the Run never break.
6. As a sub-agent, I want the labeller to stay injected, so that tests drive the graph without an LLM.
7. As the maintainer, I want the graph to know nothing about prompts, so that prompt versioning stays inside the labeller.
8. As the maintainer, I want the image size checked with the existing image check after the swap, so that I can see LangGraph added nothing. It is already in the lock file through `langchain`.
9. As the maintainer, I want `langgraph` declared as a direct dependency, so that the code doesn't rely on a transitive pin.

### The retry

10. As the caller, I want text the labeller misquoted or missed to get another chance before it goes to the appendix, so that the banner appears only when it means something.
11. As the maintainer, I want at most N retries (default 2), so that cost and latency are bounded.
12. As the maintainer, I want a retry only while unplaced text remains, so that a document the first attempt placed fully costs one call.
13. As the maintainer, I want `conflict` and `removed` rejections never to trigger a retry, so that no call is spent on what an additions-only retry cannot change.
14. As the maintainer, I want the loop to stop as soon as an attempt leaves no less unplaced text than the one before, so that a genuinely unplaceable fragment costs exactly one retry.
15. As the maintainer, I want progress measured in unplaced non-separator characters, so that it counts what the appendix would show.
16. As the caller, I want a retry to be unable to remove or move anything the first attempt placed, so that a retry can only improve the document.
17. As the maintainer, I want a retry's answer to address each addition by a path into the first answer's tree (an existing slot or a new entry), so that the pipeline never has to guess which entry an addition belongs to.
18. As the maintainer, I want an addition whose path addresses nothing to be rejected as `bad_path`, logged and traced, so that a bad path is visible rather than silently dropped.
19. As the maintainer, I want verify to re-run from scratch over the first answer's references followed by the additions, so that provenance and the claim ledger rules stay exactly as they are.
20. As the maintainer, I want the retry prompt and the additions schema to carry their own versions with hash checks, as the first prompt and schema do, so that a change to either without a bump fails at import.
21. As the maintainer, I want the labeller to pick the retry prompt whenever feedback is present, so that the graph only passes state.
22. As the maintainer, I want the feedback sent to the provider to carry text (the unplaced runs and the rejected quotes), so that the model can place what it is shown. The provider already holds the whole document from attempt 1.
23. As the maintainer, I want a retry to resend every block plus the first answer, so that the model can see an unplaced bullet's job and address paths into the first answer.
24. As the caller, I want a retry whose answer is a labelling failure to leave the previous result in place, so that a bad retry never makes the document worse.
25. As the caller, I want a provider outage during a retry to keep the previous result and complete the job, so that a usable document is not turned into a 503.
26. As the caller, I want a first attempt that is a labelling failure to be retried, counting against N, so that one malformed answer does not empty the whole document into the appendix.
27. As the maintainer, I want an outage on the first attempt still to stop the job with a 503, as today, so that a fault outside the CV is still reported as one.

### The Run

28. As the maintainer, I want the Run's `label` section to stay the first attempt, unchanged, so that existing readers keep working.
29. As the maintainer, I want a new `retries` list on the Run, empty by default, so that every retry is recorded.
30. As the maintainer, I want each retry's record to hold its labelling record, the feedback as block ids, offsets and reasons, and the unplaced character count after it, so that the transform log shows what each retry was asked and what it achieved, without storing text twice.
31. As the maintainer, I want the API's summary log line and the eval report to sum cost and tokens over the first attempt and every retry, so that cost figures stay true.
32. As the reviewer, I want the Run to stay JSON-round-trippable, so that the logs can still rebuild it.

### Tracing

33. As the reviewer, I want every Run traced in Langfuse, so that demo step 4 can show each step, the labeller's answer and verify's rejections.
34. As the caller, I want the `X-Run-Id` I receive to be the trace id, so that one id finds both the logs and the trace with no lookup table.
35. As the maintainer, I want every API log line to keep carrying the run id, so that the brief's exit criterion ("the run ID linked from API logs") holds.
36. As the maintainer, I want each eval document's Run traced and tagged `env=eval`, production `env=prod`, and local runs `env=local`, so that traces can be filtered by origin.
37. As the maintainer, I want one trace per Run, with one span per node visit, one generation per attempt, and verify's rejections and the retry decisions recorded, so that the trace tells the story of the Run.
38. As the maintainer, I want each generation's start and end to be the times measured around the model call, so that latency in the trace is real.
39. As the maintainer, I want each generation's cost taken from the project's own price table, so that Langfuse never guesses a price from a deployment name it can't match.
40. As the maintainer, I want eval cache hits traced too, marked as cached with zero cost, so that the eval's traces exist on every run, cached or not.
41. As the maintainer, I want unit tests never to trace, and a client with no keys to be a quiet no-op, so that tests and keyless local runs need no Langfuse.
42. As the maintainer, I want the Langfuse keys held in the same places as the other secrets (GitHub secrets for the eval, Container Apps secrets for the app), so that no key is committed or baked into the image.
43. As the maintainer, I want the image check run after the Langfuse dependency is added, so that I can see the size the OpenTelemetry packages add.
44. As the maintainer, I want the Langfuse project kept private, used within its Hobby limits and shown in demos from my own login, with a committed screenshot of one full eval trace and its run id, so that the demo stays within Langfuse's terms.

### The content boundary

45. As the reviewer, I want production traces to carry structure only, set by one visible switch that defaults to structure, so that the deployed endpoint never sends candidate text to a third party.
46. As the maintainer, I want full text only for the CI eval and local runs, which use synthetic fixtures, so that the demo trace exists without loosening production.
47. As the maintainer, I want every span built by one pure payload function that emits only allowlisted fields in structure mode, so that a new field leaks only if someone adds it on purpose.
48. As the maintainer, I want the full and structure modes to differ only in that function's output, so that there is one place to review.
49. As the maintainer, I want the LangChain callback handler never attached, in either mode, so that nothing captures prompts behind the allowlist and generations are never counted twice.
50. As the maintainer, I want the Langfuse client to have its own tracer provider and an export filter that passes only our own instrumentation scope, so that an instrumented library cannot add spans of its own.
51. As the maintainer, I want the mask hook installed as a second layer, redacting input and output and any metadata key not on the allowlist, so that ids and categories survive while stray text cannot.
52. As the maintainer, I want lint to ban the Langfuse LangChain integration and its decorator project-wide, so that neither can be reintroduced by accident.
53. As the reviewer, I want the ADR to say plainly that the LLM provider receives the CV text on every run, and that beyond it candidate text reaches no third party, Langfuse in production receiving structure only, so that the claim is true as written.

### Logs and errors

54. As the maintainer, I want the logs to keep the transform log's text inside our own tenant, so that a dropped word can still be shown to be a deliberate removal.
55. As the reviewer, I want PII values stripped from the log lines wherever they occur (removals, ledger claims, residue, exception messages), so that the one class of text whose content the log need not show never reaches Log Analytics.
56. As the maintainer, I want each stripped removal to log its rule, offsets, length and class, so that an over-eager PII rule is at least visible in production. The eval's `removal_precision`, which reads the in-memory Run, stays the real check.
57. As the maintainer, I want stripping applied only by the log writer, so that the Run, the eval and `removal_precision` are untouched.
58. As the maintainer, I want the Log Analytics workspace retention set as low as Azure allows (target 7 days), so that the ADR can record a retention policy rather than a default.
59. As the maintainer, I want every exception at the labeller boundary wrapped into a labelling failure or a provider error with a fixed reason, so that no library error that echoes the model's output (pydantic, LangChain's output parser, provider SDKs) carries text onward.
60. As the maintainer, I want a labelling failure's reason built from a category plus allowlisted error locations (known field names and integers), so that the reason says where the answer was wrong, never what it said.
61. As the maintainer, I want any exception recorded anywhere (log, trace, retry record) to be its type name plus our own fixed message, so that error paths cannot leak.
62. As the caller, I want any exception that escapes the app to become a generic 500 through a catch-all handler that logs the type name only, so that uvicorn never prints a traceback containing text.
63. As the maintainer, I want full stack traces only behind an environment flag that is off in production, so that "local only" is enforced rather than assumed. Container Apps ships standard error to Log Analytics too.

### Azure OpenAI and the provider choice

64. As the maintainer, I want a read-only spike first that reads `cvr_sub`'s offer and quota tier and confirms that a gpt-5.4 Data Zone Standard (EU) deployment can be created, so that a zero quota is found before any build work.
65. As the maintainer, I want gpt-5.4 deployed as Data Zone Standard (EU), so that processing on the Azure path stays inside the EU.
66. As the maintainer, I want the exact model identifier and its Data Zone availability checked against the Azure docs in that ticket, so that the spec's model name is not taken on trust.
67. As the maintainer, I want the `Labelling` and additions schemas checked against Azure's strict structured-output limits (every field required, no additional properties, nesting depth, unsupported keywords), so that a schema the Azure path rejects is found before an eval run. Any change bumps the schema version and is followed by an eval on the deployed provider.
68. As the reviewer, I want the Container App to reach Azure OpenAI through a managed identity holding only the inference role, so that no key exists for that path.
69. As the reviewer, I want key authentication disabled on the Azure OpenAI resource, so that "no key" is literally true.
70. As the maintainer, I want the provider selected by configuration (the existing `CVR_LABEL_*` settings), so that switching provider is a config change, never a code change.
71. As the maintainer, I want the Azure wiring unit-tested with fakes (config to chat-model arguments, a token provider in place of a key, never a key), so that the non-deployed provider's code path cannot rot unseen.
72. As the maintainer, I want the price table to cover gpt-5.4 at its Data Zone prices (including cached input if prompt caching is used), and a test that fails if any configured model has no price, so that cost figures cannot silently read zero.
73. As the reviewer, I want the managed identity path proven once against the live app whichever provider wins (a revision set to Azure OpenAI, smoke-tested, then switched back if Anthropic wins), with the run id and outcome recorded, so that the gap is closed by evidence.
74. As the maintainer, I want the provider compared as a Model comparison (three gpt-5.4 runs against three Sonnet 5.5 `medium` runs, on the same prompt versions and golden set), run by hand and recorded as a dated file beside the earlier comparison, so that the verdict rests on numbers.
75. As the reviewer, I want an ADR recording the provider verdict and its numbers, so that §12 item 5 ("provider chosen by eval results") is met.
76. As the reviewer, I want the ADR to say that the Anthropic path has no EU-only processing guarantee, and that for real CVs this would weigh against it, so that residency is a disclosed trade-off rather than a hidden one.
77. As the maintainer, I want the ADR to require the comparison to be re-run whenever the prompt, a schema or either model changes, so that the non-deployed provider's standing doesn't go stale.

### The gate

78. As the reviewer, I want the eval gate always to run the deployed provider, so that the gate tests what production runs.
79. As the maintainer, I want the gate to run on one provider only, so that CI cost and the OIDC scope stay as they are while Anthropic is deployed.
80. As the maintainer, if Azure OpenAI wins, I want the eval job to reach it through a separate Entra app with only the inference role on that one resource, federated for `pull_request` and for `main`, so that CI holds no key and a stolen token can only make inference calls.
81. As the maintainer, I want fork pull requests to get neither the OIDC token nor the eval secrets, so that the eval identity cannot be used from outside the repo. Today they get neither, and this is to stay true.
82. As the maintainer, I want the brief's §8 amended to say which provider gates (the deployed one) and where the comparison is recorded, so that the brief and the build agree.

### The eval

83. As the maintainer, I want the eval report to show retries fired, characters placed by a retry, and retry cost, so that the retry's value and price are visible.
84. As the maintainer, I want the eval cache key to include a hash of the feedback, so that each attempt is cached separately and a cached run replays the retries exactly.
85. As the maintainer, I want the thresholds unchanged, so that the retry is judged against the same bar as Phase 1.
86. As the maintainer, I want to see the expected retry pattern in the report: the eight documents carrying deliberate unplaceable fragments (c09 and c11, every Layout) show one retry each with no progress, and documents whose first attempt places everything show none, so that cost creep shows up.

### Evidence

87. As the reviewer, I want each architectural decision recorded as an ADR when its ticket lands: the graph and its additions-only bounded retry; the content boundary (provider, tenant, third party, PII) with its two layers; Azure OpenAI through a managed identity and the eval's narrow OIDC identity; and the provider verdict, so that the reasoning is part of the evidence.
88. As the reviewer, I want "what would change" recorded: trimming retry feedback to the neighbouring blocks, leaner feedback (measurable on a failure-prone model such as Haiku, then confirmed on the deployed one), self-hosted Langfuse or masking for real CVs, a DPA, Data Zone or an EU-bound route for every provider, and retention set by policy, so that the trade-offs read as chosen.
89. As the maintainer, I want the README and CLAUDE.md updated as each ticket lands, so that the docs never describe a pipeline that no longer exists.
90. As Phase 3, I want `reformat` to stay the one entry point, so that the MCP server wraps the same graph.

## Implementation Decisions

### Order of work

1. The graph swap, with no behaviour change. The eval report must match Phase 1's.
2. Langfuse tracing, with the content boundary, the log and error hardening, and the canary test.
3. The retry.
4. Azure OpenAI: the provider wiring, provisioning, the managed identity, and the live proof.
5. The model comparison, the verdict ADR and, if Azure wins, the gate's OIDC identity.

The read-only quota spike on `cvr_sub` runs alongside step 1 and blocks only step 4. The §8 amendment is made in the first ticket that touches the docs. Each non-docs merge to `main` costs a live eval (about $1.60 on Sonnet), so tickets are batched into pull requests where that is sensible.

### The graph

- `pipeline.reformat` keeps its signature and its `(bytes, Run)` result. Internally it builds and invokes the LangGraph graph. It gains one optional keyword, the tracer (below); nothing else.
- The nodes are parse, label, verify, transform and render. The graph state carries the parsed document, the attempts so far, the current verified result and the feedback. One conditional edge leaves verify: back to label when the retry rules say so, otherwise on to transform.
- No checkpointer, no persistence, no streaming. The graph runs to completion in-process for one Run.
- Pipeline import rules stay: only `api` and the eval runner import `pipeline`.

### The labeller

- The `Labeller` type gains an optional feedback argument. A labeller that ignores it (the oracles) still works, and a call without feedback is the first attempt.
- `RealLabeller` sends the first prompt when there is no feedback and the retry prompt when there is. The retry prompt and the additions schema each get an entry in the versions record, with hashes, checked at import like the existing two.
- The **additions schema** is a list of additions, each a path plus a reference (block id and quote). A path addresses an existing slot in the first answer's tree (a list field such as an entry's bullets, the skills or the additional items, or a leaf the first answer left empty) or a new experience or education entry with its own leaves. It must be strict-compatible on both providers.
- Every exception at the labeller boundary is classified:
  - provider unavailable;
  - misconfigured;
  - a labelling failure, with a fixed category (refusal, invalid JSON, schema mismatch, unexpected) and the error locations, filtered to known field names and integers.

  No exception text and no `input_value` survive. The schema has no dict fields with keys chosen by the model; the location allowlist enforces the same thing regardless.
- Each attempt records its labelling record as today, and records the times measured around the model call.

### Verify and the retry rules

- `verify` gains an optional additions argument. It resolves each addition's path against the first answer, rejects an unresolvable one as `bad_path`, and runs the ledger over the first answer's references followed by the resolved additions. Claim rules are unchanged.
- The retry decision is a pure function of the verified result, the previous unplaced count, the number of attempts so far and N:
  - retry only while unplaced text remains and attempts are left;
  - stop when an attempt did not reduce the unplaced non-separator characters;
  - stop after a retry that was a labelling failure, keeping the previous verified result;
  - stop after a provider outage on a retry, keeping the previous result.

  A first-attempt labelling failure is retried with feedback saying the answer was unusable. N comes from configuration and defaults to 2.
- **Feedback** is built from the verified result: the unplaced runs (block id and offsets, with the text when sent to the provider) and the unlocatable rejections in those blocks as hints. `conflict` and `removed` rejections are never feedback.

### The Run

- New optional `retries`, defaulting to empty. Each retry record holds the attempt's labelling record, the feedback as block ids, offsets and reasons (no text), the rejections it produced, and the unplaced character count after it. `label` stays the first attempt.
- Cost and token totals across attempts are computed by readers (the API summary line, the eval report). The stored records stay as they are.

### Tracing

- A new package owns the Langfuse client and the payload function. It is a runtime dependency of `pipeline` and `api` and never of the other nodes. The Langfuse SDK is pinned at its current major (v5, OpenTelemetry-based). That `span_exporter`, `tracer_provider` and `should_export_span` exist in the pinned version is checked against that version's docs in the ticket.
- The client is built from the environment by the API (once per process) and by the eval runner, and passed to `reformat`. With no keys it is a no-op, and the warning is tolerated in tests.
- The trace id is the run id (`uuid4().hex`, 32 lowercase hex). The ticket confirms that the SDK accepts it.
- The content mode comes from one setting, `structure` or `full`, defaulting to `structure`. CI's eval job and local runs set `full`, and the deployed app never does.
- Trace shape:
  - one trace per Run;
  - one span per node visit;
  - one generation per attempt (model, token counts, cost from the price table, and measured start and end);
  - events for rejections and retry decisions;
  - tags for the environment and for cache hits.

  In full mode the same spans also carry the blocks, the rendered prompt messages, the raw answer and the rejections' quotes.
- The LangChain callback handler is never attached. Lint (ruff's banned-api rule) forbids the Langfuse LangChain integration and its decorator.
- The client's own tracer provider is never set as the global one. Its export filter passes only our instrumentation scope. The mask hook redacts input and output in structure mode, plus any metadata key not on the allowlist, in every mode.

### Logs and errors

- The log writer strips PII values wherever they occur in its lines: text removals, ledger claims whose rule is a PII rule, residue that overlaps a removal, and any error field. A stripped removal keeps its rule, block, offsets, length and character class. Headings removed under the heading rule are not PII and stay. The Run itself is not changed.
- The API gets a catch-all exception handler: a generic 500, `X-Run-Id` set, and one summary log line with the exception's type name only.
- A debug setting (off by default, never set in production) allows full exceptions on standard error locally.
- Log Analytics retention is lowered to the minimum Azure allows, which the ticket checks. The target is 7 days. Provisioning and docs record the value.

### Azure OpenAI

- Resources: an Azure OpenAI (Foundry) account in `cvr-rg` with a custom subdomain, key authentication disabled (set through ARM, Bicep or PowerShell, since `az` has no flag for it), and a Data Zone Standard (EU) gpt-5.4 deployment. Provisioning goes through the existing wizard and is kept idempotent.
- The Container App gets a managed identity holding only the inference role on that account. The token scope is checked in the ticket.
- The provider is `azure_openai` in `LabellerConfig`. Azure-specific arguments (deployment name, endpoint, API version, token provider) are isolated as the Anthropic ones are. New runtime dependencies: `langchain-openai` and `azure-identity`, which pull in `openai` and `tiktoken`. The image check is re-run.
- The price table gains gpt-5.4 at Data Zone prices, with the date checked.
- The live proof: a revision set to Azure OpenAI is smoke-tested through the existing smoke and demo scripts, the run id and outcome are recorded, and the revision is set back if Anthropic is deployed. The app is left off.

### The gate and the comparison

- The gate runs the deployed provider. While Anthropic is deployed, CI is unchanged apart from the Langfuse secrets and `full` mode in the eval job.
- If Azure wins:
  - a separate Entra app with only the inference role on the account, federated for the `pull_request` subject and the `main` subject, in the immutable subject format read from the customisation API;
  - the eval job gains `id-token: write`;
  - no Azure OpenAI key exists anywhere.
- The comparison follows the Phase 1.5 method and is recorded as a new dated comparison file beside `eval/model-comparison-2026-10-19.json`. The verdict ADR follows ADR-0011's shape.

### The eval runner

- It passes the tracer and tags its Runs `env=eval`. The cache key gains the feedback hash, and the additions schema and retry prompt hashes come in through the labeller's content hash.
- The report gains three columns: retries fired, characters placed by retry, and retry cost. Cost totals sum all attempts. Thresholds are unchanged.

### Docs

- ADR-0012: the graph and the bounded, additions-only retry.
- ADR-0013: the content boundary, with the provider, tenant, third-party and PII lines, the allowlist and mask layers, retention, and what changes for real CVs.
- ADR-0014: Azure OpenAI through a managed identity, Data Zone EU, and the eval's OIDC identity if it is needed.
- ADR-0015: the provider verdict.
- The brief's §8 amendment, and CLAUDE.md, README and `docs/development.md` kept current.

## Testing Decisions

A good test exercises behaviour at the highest seam that can see it and asserts on outputs (the document, the Run, log lines, exported spans), never on internals. No unit test reaches an LLM or Langfuse. A red test that worked before a change is evidence against the change, not a test to bend.

Seams, in order of preference:

1. **`reformat`, with an injected labeller and tracer.** Retry behaviour, the Run's `retries`, trace shape and the graph swap.
   - The **scripted fake** is the real `RealLabeller` over a fake chat model returning a scripted sequence (the existing labeller tests build one from a runnable). So the real parsing, exception wrapping and retry-prompt choice run.
   - The tracer is a real Langfuse client over an in-memory OpenTelemetry exporter, with dummy keys.
   - Cases:
     - a perfect first attempt makes no retry;
     - a flawed first attempt fixed by the retry;
     - no progress stops after one retry;
     - N is reached;
     - a retry that fails keeps the previous result;
     - an outage on a retry keeps the previous result;
     - a failed first attempt is retried;
     - a `bad_path` addition is rejected;
     - `conflict` and `removed` rejections never trigger.
   - Prior art: `tests/pipeline/test_reformat.py`, the imperfect oracles.
   - The existing "each node called once, in order" test must pass unchanged after the graph swap. It changes only in the retry ticket, to "in order, with label and verify repeated only on a retry", with the reason stated.
2. **`create_app` through the test client.** The catch-all handler, error bodies, PII stripping in the log lines, and the API half of the canary test. Prior art: `tests/api/`.
3. **`RealLabeller` over a fake chat model.**
   - Exception wrapping across pydantic, the output parser and provider errors.
   - Location allowlisting.
   - Prompt choice by feedback.
   - The versions record for the retry prompt and additions schema.
   - The Azure wiring (config to arguments, a token provider and never a key).
   - Every configured model has a price.
   - Prior art: `tests/label/`.
4. **Pure functions.**
   - verify with additions;
   - the retry decision and progress measure;
   - feedback construction;
   - the payload function in both modes;
   - the export filter (a rogue span from an instrumented call or a decorated function carrying a canary never reaches the exporter).

   Prior art: `tests/verify/`, `tests/api/test_log.py`.

**The canary test** (default run, no LLM):
- **The document.** It is built at test time from a copy of one Candidate, rendered through all four Layouts, with nothing in the fixtures changed. Every content leaf, PII value and fragment becomes a unique canary from a seeded generator, checked for collisions with run ids and hashes. Canaries are shaped like what they replace: unique digit strings for phones, a unique domain for emails such as `@example.invalid`. Dates stay real.
- **The labeller.** The scripted fake gives a flawed first answer, a retry, and a malformed answer that contains a canary, so the failure path carries text.
- **What is checked**, for every canary and its normalised forms (spaces removed, case folded, as the PII metric does):
  - In structure mode, no canary appears in any exported span (names, attributes, events, status, resource attributes, tags, metadata, session ids).
  - No PII canary appears in the captured log output (standard output and error, captured at DEBUG), API error bodies, recorded exceptions, the Run's failure reasons or the retry records.
- **Positive controls**, so a blind test cannot pass:
  - ids and counts appear in the spans;
  - non-PII canaries appear in the logs;
  - in full mode the canaries appear in the trace;
  - the fake received the canaries in its retry feedback.
- A token check (source tokens absent from structure-mode payloads) runs as a second layer.

**The eval** stays the labeller's real test.
- The graph swap ticket shows an eval report matching Phase 1's.
- The retry ticket shows the expected retry pattern and unchanged hard gates.
- Any change to a prompt, a schema or a model is followed by an eval on the deployed provider, with the report diff shown.
- The image check is run and its output pasted into the pull request for the Langfuse and Azure tickets.

Tests parametrised over all 48 generated documents get the slow marker. The canary test runs on a handful of built documents and stays in the default run.

## Out of Scope

- The MCP server (Phase 3).
- A gate that runs both providers on every pull request; the second provider is checked only by the Model comparison.
- Claude on an EU-bound route (through Azure AI Foundry or Bedrock) as a third contender.
- Self-hosted Langfuse, Langfuse public share links, and Langfuse scores or evals.
- Trimming retry feedback to neighbouring blocks, or leaner feedback. Both are recorded as "what would change" only.
- Interactive review, a review queue, or any endpoint exposing the Run or the trace (ADR-0004, ADR-0009).
- LangGraph checkpointing, persistence, streaming or parallel branches.
- Retrying on `conflict` or `removed` rejections, or replacing an earlier answer.
- Entra-protected ingress through Container Apps built-in auth (brief open item 7: not forced).
- Any change to the thresholds, the golden set or the Candidates.

## Further Notes

- **Facts to check inside tickets, not decided here:**
  - the minimum Log Analytics retention;
  - the Langfuse SDK features in the pinned version, and that a `uuid4().hex` is accepted as a trace id;
  - the exact PR OIDC subject (from the customisation API);
  - `cvr_sub`'s offer and quota tier (Free Trial subscriptions reportedly get zero OpenAI quota);
  - the managed identity token scope;
  - the exact gpt-5.4 identifier and its Data Zone EU availability;
  - both schemas against Azure's strict-mode limits.
- **Research on 2026-10-20 (primary sources; re-check when the ticket starts):**
  - `langgraph` 1.2.12 is already locked through `langchain`.
  - Langfuse Hobby allows 50k units a month, 30-day visibility, 2 users and an EU region. This project expects about 6–9k units a month. Its terms bar making the product available to third parties, hence a private project and a screenshot.
  - The mask hook covers input, output and metadata only, not status messages or events; that is why the allowlist is the primary control.
  - In `northeurope`, Azure OpenAI offers Global Standard and Data Zone Standard, not Regional Standard.
  - gpt-5.4 costs about $2.75 input and $16.50 output per million tokens on Data Zone, about 10% above Global. Neither has an idle cost.
  - Fork pull requests receive no OIDC token and no secrets.
- **Cost:**
  - each retry-bearing uncached eval run adds about eight calls to today's ~$1.60;
  - the Model comparison costs three gpt-5.4 runs (the Sonnet side reuses existing runs on the same prompts, if they match, or else three new ones);
  - the live managed identity proof costs one call.
- **Where this landed:** the spec, its tickets and the `CONTEXT.md` additions were committed with PR #39 (docs only), beside Phase 1.5's last ticket updates.
- **Tickets are marked done in the PR that finishes them**, before it merges, never by a separate PR after the merge.
