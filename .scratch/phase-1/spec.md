# Phase 1: end-to-end lifecycle

Status: ready-for-agent

Vocabulary: `CONTEXT.md`. Decisions: `docs/adr/0001`–`0007`, plus the three ADRs this phase writes (0008 claim ledger, 0009 structured labelling, 0010 deployment). Source brief: `docs/project-brief.md` §2, §4, §6, §8, §9, §10 Phase 1, §12. Design record: `.scratch/phase-1/grilling.md` (three rounds, every question settled).

## Problem Statement

Phase 0 built the harness: twelve Candidates rendered by four Layouts into 48 source documents, a branded template, nine metrics, and a proof that the metrics fail when and only when they should. Nothing yet reads a source document, asks an LLM anything, or writes an output document. The maintainer cannot show a reviewer a CV going in and a branded CV coming out, cannot show CI turning red on a degraded prompt, and cannot point at a running service. The core claim of the project, that the LLM only labels and never writes, is a design on paper until a pipeline exists that is built that way and an eval gate that would catch it being built any other way.

## Solution

Build the pipeline as a plain function over five nodes with the boundaries LangGraph will take over in Phase 2: parse a source document into blocks; have the LLM label those blocks with references (a block identity plus a verbatim quote) into a reference-shaped content tree plus a list of removals; verify every reference against the source through a per-block claim ledger, so that removals win, conflicts are loud, and everything unclaimed is residue; transform with pure code (removals, invisible normalisation, date normalisation, entry order, multi-span joins); render into the template with the review appendix for unplaced text. Wrap it in a FastAPI service, run it over the golden set from an eval runner that writes a report and fails on any breach, set the thresholds from three baseline runs, put the gate in CI ahead of a build-and-deploy to Azure Container Apps through OIDC, and keep a permanently open draft PR whose degraded prompt turns the gate red. Write the README as the ADR that ties it together.

## User Stories

Actors: the *maintainer* (Kieran, building the demo), the *reviewer* (an interviewer or reader judging the evidence), *Phase 2* (the LangGraph, observability and second-provider work that will consume Phase 1's boundaries), *CI*, and the *caller* (whoever posts a source document to the service).

### Pipeline shape

1. As Phase 2, I want the pipeline to be one function over five nodes (parse, label, verify, transform, render) with the labeller injected, so that the LangGraph swap is a change of orchestration and not of code.
2. As the maintainer, I want every node except label to be a pure function with no LLM, network or clock, so that each is unit-testable with hand-written cases as the Phase 0 metrics are.
3. As the maintainer, I want the pipeline to always complete and always produce a document, so that no input ever hangs, waits for a person, or returns nothing (ADR-0004).
4. As the caller, I want one run id per request, returned on every response including errors, so that a document can be traced to its transform log and its trace.

### Parse

5. As the maintainer, I want a source document read into ordered blocks from body paragraphs, table cells, headers, footers and text boxes, so that no Layout of the golden set has text the pipeline cannot see.
6. As the maintainer, I want block ids to be real addresses in the document (body child, table cell, header type, text-box anchor) with gaps where non-text children sit, so that a block can be found again in the file and two runs over the same file agree.
7. As the maintainer, I want text-box reading order to be anchor order, stated as an approximation in the ADR, so that the limitation is recorded rather than discovered.
8. As the maintainer, I want invisible characters stripped at parse under the named rule `NORM_INVISIBLE`, logged per block, with the pre-strip text discarded, so that the one modification the pipeline makes is the one the transform log records.
9. As the maintainer, I want every embedded image recorded by content hash and removed under `RM_PHOTO` without the LLM's involvement, so that a thing code can do deterministically is never put to a vote.
10. As the maintainer, I want a parser coverage test over all 48 generated documents against the dumb `all_text` helper, so that a text run the parser cannot see fails before any labelling is attempted.

### Label

11. As the maintainer, I want the LLM reached through LangChain's chat-model interface with structured output, provider and model from configuration, so that the Phase 2 provider comparison exercises the same code and the same schema.
12. As the maintainer, I want the schema to be a reference-shaped content tree where every leaf is a block identity plus a mandatory verbatim quote, so that there is no reference the verifier cannot check.
13. As the maintainer, I want the schema's removals to carry a rule id from a closed enumeration of the eight text rules, so that the LLM cannot invent a ninth.
14. As the maintainer, I want the schema written strict-compatible from the start (every property required, no additional properties, nullable rather than optional), so that the Azure OpenAI comparison in Phase 2 runs this schema and not a fork of it.
15. As the maintainer, I want structured output requested through the provider's native structured-output feature rather than a forced tool call, so that adaptive thinking and effort remain available on Opus 5.
16. As the maintainer, I want the prompt kept as a versioned file, and both its hand-bumped version label and a content hash of prompt and schema printed in every report, so that a bumped label with no text change, or the reverse, shows in a diff.
17. As the maintainer, I want the prompt to tell the model: quote verbatim and contiguously; one reference per leaf; dates as printed; referees under `RM_REFEREE`; the source's own headings under `RM_HEADING`; sub-headings inside Additional Information are content; skills split at its judgement with parentheticals kept; and anything that fits nowhere is left unreferenced, so that the appendix stays honest rather than a dumping ground.
18. As the maintainer, I want model, effort, temperature and any other sampling knob to be one configuration object read from the environment and printed into every report, with temperature sent only when set, so that a change to any of them is visibly a model change.
19. As the maintainer, I want a labelling failure (malformed or schema-invalid answer) to complete the job with every block as residue and the run marked `label_failed`, so that a bad day for the LLM is a document under the banner and never an error page.
20. As the maintainer, I want the real labeller exercised by the eval job on pull requests and by one spike test that is skipped without an API key, stated in the spec as "the eval is the labeller's test", so that nobody later mistakes the skip for a gap.

### Verify

21. As the maintainer, I want references matched on canonicalised text and sliced from raw text through an offset map emitted during canonicalisation, so that a curly quote in the source never causes a false rejection and never reaches the output straightened.
22. As the maintainer, I want the offset map tested with known answers directly, independent of the verifier and of the eval, so that a shared bug is not invisible to both.
23. As the maintainer, I want one claim ledger per block, filled in the order LLM removals, regex backstop, content in tree-walk order, so that removal always wins over placement and the order is a fact of the code rather than a hope.
24. As the maintainer, I want that order asserted by a unit test, not left as intention, so that a refactor cannot quietly move coverage ahead of the backstop.
25. As the maintainer, I want a content claim overlapping a removal clipped to what remains, and a content claim overlapping another content claim rejected with the range left unclaimed, so that the loser of a conflict surfaces in the appendix rather than vanishing.
26. As the maintainer, I want repeated identical quotes (c06's duplicated skill) to claim successive unclaimed occurrences, so that a real duplicate places twice and a hallucinated duplicate is rejected.
27. As the maintainer, I want a reference whose quote cannot be located to reject that one leaf and nothing else, so that an entry survives with a hole rather than disappearing.
28. As the maintainer, I want coverage computed last, over the finished ledger, as a flat list of claims that never walks the content tree, so that the ordering worry of the design record is retired by construction.
29. As the maintainer, I want a regex backstop for emails, phones and URLs over every block whatever the LLM did, so that removal is defence in depth as the brief requires.
30. As the maintainer, I want a vocabulary-only backstop for `RM_HEADING` (style-matrix headings and common synonyms, case-folded, trailing colon stripped) applied only to blocks the LLM has not placed, so that a short bold job title is never mistaken for a heading; the ADR records that a false removal is silent while a false appendix entry is loud.
31. As the maintainer, I want residue that consists only of separators (whitespace, list punctuation, dashes, bullet glyphs including Word's Symbol-font ones, quote marks) to be logged but not treated as unplaced text, so that a stray comma between two placed skills does not raise the banner.
32. As the maintainer, I want the separator set to exclude the ampersand, so that `&` standing alone is unplaced text and not silently dropped.

### Transform

33. As the maintainer, I want dates normalised only in entry date fields, to `MM/YYYY`, `YYYY`, or `Present`, accepting the brief's formats, on canonicalised text, so that `Jan ’20` and `Jan '20` parse alike and a date inside a certification is never touched.
34. As the maintainer, I want a range block referenced once by the LLM and split by code, trying the whole string as one date before splitting on range separators, so that `2020-01 - 2021-06` is a range and `2020-01` alone is a date.
35. As the maintainer, I want a date the normaliser cannot parse passed through verbatim as a literal and sorted by the first four-digit year it contains, else last in source order, so that "Summer 2020" is never rewritten and never invents a month.
36. As the maintainer, I want the `date_map` (normalised string to source slice) and the `split_map` (rendered multi-span unit to its ordered slices) emitted by transform and consumed by provenance, so that a normalised date and a clipped bullet are both provable.
37. As the maintainer, I want a multi-span unit to be Spans from one block, ascending, non-overlapping, joined by a single space that is template text, produced only by clipping, so that ADR-0007 stays closed.
38. As the maintainer, I want entry order applied as end date descending with Present first, then start date descending, then source order, so that concurrent roles have a defined order.

### Render

39. As the maintainer, I want the renderer to fill the committed template through docxtpl from the verified content plus the unplaced list, so that rendering is a projection and never a place where text is composed.
40. As the maintainer, I want a renderer round-trip test (known content in, document out, adapter back to leaves, order asserted), so that a composite line assembled in the wrong order is caught by the renderer's own test, which the eval gate cannot see.
41. As the maintainer, I want an adapter that walks a rendered document back to the leaves the metrics compare, as the inverse of the template's composite lines, so that the Phase 0 metrics are fed from real output without changing.

### Transform log

42. As the maintainer, I want one transform log per Run holding the configuration, prompt and schema label and hash, tokens and cost, the per-block ledger, removals, invisible normalisations, date and split maps, residue, unplaced text and any labelling failure, so that a dropped word is proven removed rather than lost.
43. As the maintainer, I want the log written to standard output as one summary line plus per-block detail lines sharing the run id, so that Log Analytics, which truncates a single field around 32 KB, never cuts a 40-block ledger in half.
44. As the reviewer, I want no endpoint that returns a run's log, with the ADR saying that such an endpoint is the first half of a review queue, so that scope decision 4 is visibly upheld.

### API

45. As the caller, I want `POST /reformat` to accept a `.docx` and return the reformatted `.docx` with a derived filename in `Content-Disposition` and the run id in `X-Run-Id`, so that the service is usable from a browser, a script, and Phase 3's MCP server alike.
46. As the caller, I want `X-Run-Id` on every response including 4xx and 5xx, so that a failure is as traceable as a success.
47. As CI, I want `GET /health` to never touch the LLM, so that the Container Apps probe cannot spend money or fail on a provider outage.
48. As the maintainer, I want a post-deploy smoke step that checks the header survives Container Apps ingress, so that the traceability claim is verified rather than assumed.

### Eval runner and thresholds

49. As CI, I want an eval command that runs the pipeline over every generated document (filterable by layout and candidate), feeds the metrics through the adapter, and writes a JSON report and a markdown summary, so that the gate has a number.
50. As CI, I want the runner to exit non-zero on any hard-gate breach or missed threshold, so that a red PR is red for a reason a script can see.
51. As the reviewer, I want the report broken down per metric, per layout, per tag and per candidate, then configuration, versions, tokens, cost and wall time, so that a failure reads as a failure mode and the bill is on the page.
52. As the maintainer, I want the runner to make live LLM calls with a gitignored local response cache keyed on model, prompt and schema versions and source hash, so that local iteration is free after the first run and CI is never theatre.
53. As the maintainer, I want bounded concurrency with retry-and-backoff on rate-limit responses from the start, so that the first red CI run is a real failure and not a 429.
54. As the maintainer, I want thresholds in a committed configuration file (placement minimum, appendix maximum, whether punctuation fidelity is hard), so that the gate is data and its history is in git.
55. As the maintainer, I want the thresholds set from three baseline runs on the default configuration, recording all three and their spread, with one to two points of headroom below the worst placement and above the worst appendix rate, so that a threshold means something and the first unlucky PR is not red.
56. As the maintainer, I want `punctuation_fidelity` promoted to a hard gate in the same ticket iff all three baseline runs are clean, so that the promotion is earned by evidence.
57. As the maintainer, I want the dated baseline committed and the working report gitignored, so that the origin of the numbers is on record without diff churn.
58. As the maintainer, I want the corruption table to gain "join two slices out of source order" failing provenance only, so that the `split_map` is proven to be checked.

### CI, image and deployment

59. As CI, I want one workflow with three jobs (`check` on every push; `eval` on pull requests and pushes to main, needing `check`; `deploy` on pushes to main, needing `eval`), so that lint and unit tests stay cheap and the LLM only runs where the brief says.
60. As the reviewer, I want the eval's markdown summary in the job summary and as a PR comment as well as an uploaded artifact, so that the numbers are on the PR page and not behind a download.
61. As the maintainer, I want workflow-level concurrency with cancel-in-progress, so that two quick pushes never pay for two full eval runs.
62. As the maintainer, I want a multi-stage image on the pinned Python with locked, dev-free dependencies, running as a non-root user, with the golden set, eval package, fixtures, tests, git history, environment files and caches excluded, so that the public image carries only the service.
63. As the maintainer, I want the LLM key passed only as a runtime environment variable, never a build argument, and the built image checked for baked-in secrets before the package goes public, so that a public package is safe to be public.
64. As the maintainer, I want deployment through GitHub Actions with an OIDC federated credential and no Azure secret in GitHub, so that §9 of the brief is evidenced.
65. As the maintainer, I want Container Apps on the consumption plan, scaled to zero, one replica at most, liveness and readiness probes on `/health`, the key as a Container Apps secret, logs to Log Analytics, so that the service stays inside the free grant.
66. As the maintainer, I want provisioning done once, interactively, with the ADR recording that it is manual and that infrastructure as code is what changes at scale, so that the shortcut is a documented decision.
67. As the maintainer, I want the container image published as a public package while the repo stays private, and the repo made public at the end of the phase once the README is in place, so that a visitor's first sight is the reasoning.

### Demo PR

68. As the reviewer, I want a branch that deletes the verbatim-quote rule from the prompt and a permanently open draft PR from it, so that the headline moment is a one-line diff and a red gate.
69. As the maintainer, I want the degradation shown to fail three runs out of three before the demo relies on it, so that the moment is not a coin toss.
70. As the maintainer, I want branch protection on main requiring `check` and `eval`, so that merging the demo PR is mechanically impossible.

### Fixtures and text

71. As the maintainer, I want `C#` and `.NET` added to one Candidate's skills with the tokeniser's treatment of them pinned by a unit test, so that the tokeniser's behaviour on trailing and leading symbols is a documented fact and not a regeneration side-effect.
72. As the maintainer, I want the separator set held beside the confusable table in the text package, so that every consumer reads one definition.

### Documentation

73. As the reviewer, I want the README written as an ADR covering the nine decisions of brief §12 and linking every ADR file, written early while the reasoning is fresh, so that the repo explains itself before it is public.
74. As the reviewer, I want three new ADRs, each landing in the ticket that implements it: the claim ledger and its consequences; structured labelling with a mandatory quote and what it costs; deployment and what changes at scale.
75. As the maintainer, I want the project instructions updated when the pipeline lands, so that "Phase 1 has not started" stops being the first thing an agent reads.

## Implementation Decisions

### Dependency direction

`text` and `models` stay at the bottom. New packages: `parse`, `label`, `verify`, `transform`, `render`, `api`. `parse` depends on `text` and `models`; `label` on `models` and LangChain; `verify` on `text` and `models`; `transform` and `render` on `models` and `text`; `render` also on `template`. `eval` gains a runner and an adapter and now depends on the pipeline packages (never the reverse). `golden` and `eval` remain excluded from the runtime image. The pipeline function lives in its own module and imports every node; nothing imports the pipeline module except `api` and the eval runner.

New runtime dependencies: `langchain`, `langchain-anthropic` (pinned to the major that documents the native structured-output method), `fastapi`, `uvicorn`. Dev additions: `httpx` for the API tests.

### The pipeline function and its seam

`reformat(source_bytes, labeller) -> (output_bytes, Run)`. The labeller is a callable from a list of blocks to a labelling result (the content tree of references, the removals, or a labelling failure). This is the one new test seam. Two implementations: the real LangChain labeller, and an **oracle** used by the tests.

The oracle answers from a Candidate: it locates every content string, PII value and referee line of the Candidate in the parsed blocks (canonicalised both sides, as the Phase 0 source-coverage test does) and emits the references the LLM should emit. **Failure to locate any string is a hard failure of the test**, never a skip or a warning: it means the fixture or the parser is wrong, and it must not silently reduce coverage on exactly the documents where the parser is broken.

The oracle has a small family of deliberately imperfect variants, each a short test over the pipeline seam:

| Variant | Exercises | Expected |
|---|---|---|
| omits one leaf | residue, appendix | that text is unplaced; banner present; nothing else changes |
| emits an unlocatable quote for one leaf | per-leaf rejection | the entry survives with a hole; the source text is residue and unplaced |
| claims one range twice under two fields | ledger conflict | the later claimant is rejected; the range is unplaced |
| returns a schema-invalid answer | labelling failure | every block is residue; run marked `label_failed`; document is banner and appendix |

The perfect oracle over all 48 documents asserts every metric at zero through the adapter. The imperfect oracles assert the machinery of Rounds 2 and 3 end-to-end; the corruption table already covers the same paths at metric level, and nothing else covers them at pipeline level.

**The eval is the labeller's test.** The real labeller is exercised by one spike test (skipped without an API key) that proves native structured output, adaptive thinking and effort work together on the default model, and otherwise only by the eval job. This is deliberate and is not a gap.

### Parse

Blocks are produced in reading order: body children in order (paragraphs and tables share the numbering; a table contributes its cells row by row, paragraphs within a cell in order), then each section's headers and footers, with text boxes emitted at their anchor paragraph's position. Block id grammar: `body:N`; `table:N:rR:cC:P`; `header:S:T:P` and `footer:S:T:P` with `T` in `default | first | even`; `textbox:N:B:P` for the B-th text box anchored in body child N. Gaps in numbering are real: an image-only paragraph or an empty paragraph occupies its index. Stability is for a fixed input file, not content-addressed.

Invisible characters (the confusable table's deletion rows) are stripped at parse and logged per block under `NORM_INVISIBLE`; the pre-strip text is discarded. Visible confusables are untouched.

Images are collected from every part by content hash into `Image(part, sha256, size)` and every one is removed under `RM_PHOTO` at parse; the LLM never sees or labels them. `Removal(rule, subject)` takes a Span or an Image.

### Label

LangChain `init_chat_model` with provider and model from configuration, and `with_structured_output` using the provider's native structured-output method (`json_schema`), not forced tool calling, because forced tool choice is incompatible with thinking and native structured output is not. Anthropic-specific options (adaptive thinking, effort) are isolated in one provider-configuration function.

`LabellerConfig`: provider, model, effort, optional temperature, and any other sampling knob; read from the environment; printed in every report; temperature sent only when set because Opus 5 rejects it. Default `claude-opus-5-5` at effort `medium` (changed from `claude-opus-5` by the maintainer on 2026-09-23), tuned from the baseline; a change to any field counts as a model change under the eval-run rule.

The schema is a reference-shaped mirror of `CVContent`: every leaf is a reference `{block_id, quote}`, `quote` mandatory; entries carry one `dates` reference for the whole range block; a `removals` list of `{rule, block_id, quote}` sits beside the tree with `rule` a closed enumeration of the eight text rules. Depth is at most three. The schema is strict-compatible from day one: every property required, no additional properties, nullable in place of optional, so the same schema serves Azure OpenAI's strict mode in Phase 2.

The prompt is a markdown file inside the label package. `PROMPT_VERSION` and `SCHEMA_VERSION` are hand-bumped strings; the cache key and the report additionally carry a hash of the prompt text and the JSON schema. Prompt rules are as listed in story 17.

A labelling failure is a request-level outcome: the labeller returns a failure value rather than raising; the pipeline continues with an empty tree and every block becomes residue. Retries are Phase 2.

Cost: quotes copy the CV, so output tokens dominate; roughly $7 per 48-document run on Opus 5, $3 on Sonnet 5. The response cache and CI concurrency cancellation are what bound it.

### Verify

Matching is on canonicalised text; slicing is from raw text. `canonicalise` gains a companion that returns the canonical string together with the canonical-to-raw offset map, built during canonicalisation (one-to-one substitutions, one-to-zero deletions, many-to-one whitespace collapse) and never reconstructed afterwards. No case-folding.

One claim ledger per block: a list of `(start, end, claimant)` over raw offsets. Filling order: LLM removals in schema order, then the regex backstop over every block, then content in tree-walk order (name, profile, skills, education, experience, certifications, additional; list order within, entries in schema order). For a quote that occurs more than once in a block, each claimant takes the first unclaimed occurrence in that order. A content claim overlapping a removal is clipped to the remainder (one piece if at an edge, two if in the middle, producing a multi-span unit). A content claim overlapping a content claim is a conflict: the later claimant is rejected and the range stays unclaimed. The node sequence verify-removals → backstop → verify-content → coverage is asserted by a test. Coverage runs last over the finished ledger and emits, per block, the residue runs.

The verifier emits a flat list of `(path, Span)` claims and a `VerifiedContent` tree of Spans (and multi-span units) in `CVContent` shape; coverage sums over the flat list, never the tree.

Backstops: regex for emails, phone numbers and URLs over every block; a heading vocabulary for `RM_HEADING` (the four Layouts' headings, common synonyms, document titles such as "Curriculum Vitae"; case-folded; trailing colon stripped), applied only to blocks holding no placed content. Both only remove; neither places. The vocabulary is deliberately narrow.

Separators: `SEPARATORS` in the text package beside the confusable table: whitespace; `, ; : | / \ ( ) [ ] .`; the dashes `- – —`; bullet glyphs `• · ◦ ▪ ‣ ○ ■` and the Symbol-font Private-Use-Area bullets `U+F0B7 U+F0A7 U+F0D8 U+F0FC U+F076`; quote marks straight and curly. `&` is excluded. A residue run is separator residue iff every character is in the set; otherwise it is unplaced text. All residue is logged.

### Transform

Pure functions over `VerifiedContent`. Date normalisation on canonicalised text: accepted `Jan 2020`, `January 2020`, `01/2020`, `1/2020`, `2020-01`, `Jan '20`, `2020`, and `Present | Current | to date | now` case-folded. The range block is tried as a single date first, then split on ` - `, ` – `, ` — `, ` to `. Output `MM/YYYY`, `YYYY`, or `Present`; never an invented month. Anything else is a literal: passed through verbatim, sorted by its first four-digit year, else undated. Undated entries sort last in source order. Entry order: end date descending, Present first, then start descending, then source order.

`date_map`: normalised string → source slice, one pair per normalised date. `split_map`: rendered multi-span text → ordered slices. Multi-span units: same block, ascending, non-overlapping, joined by one space (template text); produced only by clipping.

Removals are applied (removed Spans never reach content); the transform log is assembled here.

### Render

docxtpl over the committed template, context mirroring `VerifiedContent` projected to strings plus the unplaced list in source order. The renderer composes composite lines exactly as the template does today (employer and location with a comma; the date line with an en dash). The adapter is the inverse: rendered document → leaves by field type, using the template's structure (headings, paragraph styles) and the same composite-line conventions. The renderer round-trip test proves the pair; the ADR states that the eval gate proves the labels and the renderer is proved by its own tests.

### Transform log and Run

`Run`: run id, `LabellerConfig`, prompt and schema label and hash, token counts and cost, per-block ledger, removals, `NORM_INVISIBLE` events, `date_map`, `split_map`, residue (all of it, separator or not), unplaced text, `label_failed`. Written to standard output as one summary line and per-block detail lines sharing the run id. The eval runner uses the in-process object. No endpoint exposes it.

### API

FastAPI. `POST /reformat` takes a multipart `.docx`, returns the output `.docx` with `Content-Disposition: attachment; filename="<stem>-reformatted.docx"` and `X-Run-Id`. `X-Run-Id` is set by middleware on every response including errors. `GET /health` returns liveness without touching the labeller. The labeller is constructed once at startup from `LabellerConfig`.

### Eval runner, report, thresholds

`python -m cvr.eval.run [--layout X] [--candidate cNN] [--no-cache]`. For each generated document: pipeline with the real labeller (through the cache), adapter, every metric. Async with bounded concurrency (about four) and retry-with-backoff on rate-limit responses. Writes `report.json` (gitignored) and `report.md`; exits non-zero on any hard-gate breach or missed threshold. Report order: per-metric totals; per layout; per tag; per candidate; then `LabellerConfig`, prompt and schema label and hash, tokens, cost, wall time. Cache key: `(model, prompt hash, schema hash, source sha256)`, stored gitignored.

`thresholds.yaml`: `placement_accuracy.min`, `appendix_rate.max`, `punctuation_fidelity.hard`. Set from three baseline runs on the default configuration: the baseline file records all three and the spread; placement minimum is the worst run less one to two points, rounded down; appendix maximum is the worst run plus the same headroom, rounded up; punctuation fidelity becomes hard iff all three runs are clean. A wide spread is itself a finding recorded in the baseline. Baseline committed as a dated file.

The fake pipeline gains a `split_map` input and the corruption row "join two slices out of source order" with blast radius provenance only.

### CI, image, deployment

One workflow. `check`: sync, lint, format check, unit tests; every push. `eval`: needs `check`; on `pull_request` and `push` to main; runs the eval runner with the key from a repository secret; uploads report and summary as artifacts; writes the summary to the job summary and posts it as a PR comment; fails on non-zero exit. `deploy`: needs `eval`; `push` to main only; job-level `id-token: write`; builds the image, pushes to GHCR, deploys to Container Apps, then a smoke step that posts a golden-set document and asserts `X-Run-Id` is present on the response. Workflow-level concurrency with cancel-in-progress.

Image: multi-stage on the pinned Python slim base; `uv sync --locked --no-dev`; non-root user; `.dockerignore` excludes `.git`, the golden and eval packages, fixtures, tests, environment files and caches. The key is a runtime environment variable only, never a build argument; the image is inspected for secrets before the package is made public.

Container Apps: consumption plan, external ingress on the service port, min replicas 0, max 1, liveness and readiness probes on `/health`, the key as a Container Apps secret referenced by an environment variable, Log Analytics default workspace. Provisioned once through an interactive wizard; the ADR records that this is manual and that Bicep or Terraform, ACR with managed-identity pull, and a managed identity for the LLM path are what change at scale or in Phase 2. The package is public from first deploy; the repo goes public at the end of the phase.

Demo runbook note: scale-to-zero means a cold start; warm the endpoint before presenting.

### Demo PR

Branch `demo/degraded-prompt` deletes the verbatim-quote rule from the prompt; draft PR, labelled `demo`, never merged. Verified to fail three runs of three before the demo relies on it. Branch protection on main requires `check` and `eval`.

### Fixtures and glossary

`C#` and `.NET` added to c07's skills (a fixture change: maintainer review, regeneration of the 48 documents, commit) and the tokeniser's treatment pinned by a unit test. Glossary terms already written in `CONTEXT.md` during the design: Claim, Multi-span unit, Residue, Separator, Backstop, Labelling failure, Composite line, Run, Transform log, Adapter; Assignment, Template text, Removal and Unplaced text amended.

### ADRs and README

0008: the claim ledger: removals before content, conflicts loud, residue versus unplaced text, the separator set and the ampersand, the vocabulary-only heading backstop and why (a false removal is silent, a false appendix entry is loud), text-box order as an approximation. 0009: structured labelling: LangChain with native structured output, quote mandatory, `RM_PHOTO` never the LLM's, the closed rule enumeration, strict-compatible schema, what it costs and what bounds it, the transform log never exposed because that is half a review queue. 0010: deployment: public package on a private repo, OIDC, manual provisioning, scale to zero, what changes at scale. README as ADR: the nine items of brief §12, each a paragraph linking the ADR file that holds the detail; written early, revised at the end.

## Testing Decisions

A good test exercises one seam from the outside and asserts on what comes out. No LLM in any unit test; the one spike test that reaches the LLM is skipped without a key. The seams, highest first:

1. **Pipeline** (new): source bytes and a labeller in, output bytes and a Run out. The perfect oracle over all 48 generated documents asserts every metric at zero through the adapter. The four imperfect oracles assert residue and appendix, per-leaf rejection, ledger conflict, and labelling failure end-to-end. Oracle location failure is a test failure.
2. **Parser**: `.docx` in, blocks out, observed against the existing `all_text` helper over all 48 documents: every text run is in some block and every block's text is in `all_text`; block ids are stable across two parses; `NORM_INVISIBLE` events match the manifest's injected confusables where the table deletes; the two-column documents yield one image hash, the others none.
3. **Verifier**: blocks and a labelling result in, verified content, claims and residue out. Hand-written cases: exact match; curly-versus-straight match with raw slice preserved; duplicate quote placed twice; unlocatable quote rejected alone; removal clipping at edge and mid-range; content conflict; the fill order asserted; separator residue versus unplaced text; the ampersand case.
4. **Offset map**: known-answer cases on `canonicalise` with offsets, one per row class of the confusable table, independent of the verifier.
5. **Transform**: hand-written cases for every accepted date format, the range-before-split rule, literals and their sort key, undated last, entry order with Present and concurrent roles, `date_map` and `split_map` contents.
6. **Renderer round-trip**: content in, document out, adapter back, leaves equal and in order; composite lines split correctly; banner conditional. Extends the Phase 0 template smoke test.
7. **API**: FastAPI test client with the oracle labeller: `X-Run-Id` on success and on a 4xx; `Content-Disposition` derived from the upload name; `/health` without a labeller.
8. **Eval runner**: with the oracle labeller over a subset: report shape, breakdowns present, exit code zero on clean and non-zero on a breached threshold.
9. **Metrics** (existing harness): the fake pipeline with `split_map` and the new corruption row.
10. **Tokeniser**: `C#` and `.NET` pinned.

Prior art: the Phase 0 metric tests (hand-written inputs, sorted findings), the Layout tests observed through `all_text`, the template smoke test, and the corruption table with blast radii and directions.

Suite speed: 48 documents through parse and render on every push may push the unit suite past feeling instant. If it goes beyond about thirty seconds, the 48-document tests move behind a pytest marker into a slower suite that CI still runs on every push and a developer runs on demand.

## Out of Scope

- Phase 2: LangGraph orchestration, retries (N = 2), Langfuse tracing, Azure OpenAI and the provider comparison, managed identity for the LLM path, ACR with managed-identity pull, infrastructure as code.
- Phase 3: the MCP server.
- Any endpoint returning a run, a log, a queue or a list of documents (ADR-0004; half a review queue).
- Any optional or whole-block reference in the schema (rejected: unverifiable).
- Shape heuristics in the heading backstop (rejected: a false removal is silent).
- Case-folding in the verifier's match.
- PDF input, a second template, scoring, ranking, search, or a review UI (brief §3).
- Real names, real contact details, or real CVs in any fixture, cache or log committed to the repo.
- Committing LLM responses or the eval cache.

## Further Notes

- The `X-Run-Id` header surviving Container Apps ingress is verified by the post-deploy smoke step; it is an assumption until that step is green.
- Text-box reading order as anchor order is an approximation; a floating box anchored far from where it is displayed will read out of order. Stated in ADR-0008, not mitigated.
- The golden set never emits a Symbol-font bullet in paragraph text, so the PUA separators are pinned by a unit test rather than by a fixture.
- The header type slot in block ids (`default | first | even`) is unexercised by the golden set (the header/footer Layout writes only the default header) and is there for real documents.
- Three baseline runs cost roughly $21 on Opus 5; the demo PR verification another $21. Both are one-off.
- Suggested ticket order: text (separators, offset map, tokeniser pin) → models (Span, Image, Removal, Run, VerifiedContent) → parse → verify → transform → render and adapter → pipeline function with oracles → label (spike, prompt, schema, config) → README-as-ADR (early, per Q14) → eval runner and report → baseline and thresholds → API → Dockerfile → CI eval job → provisioning wizard and deploy job → demo PR → c07 fixture change → repo public. `/to-tickets` cuts this into the issue sequence.
