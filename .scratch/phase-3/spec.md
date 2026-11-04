# Phase 3: the MCP server

Status: ready-for-agent

Vocabulary: `CONTEXT.md`. This phase adds **Tool result** and **Workspace** under Serving, alongside **Run**, **Trace**, **Labelling failure**, **Unplaced text**, **Removal** and **Review appendix**. Decisions: `docs/adr/0001` (the LLM labels, code transforms), `0004` (review by exception), `0010` (deployment), `0013` (the content boundary) and `0016` (the MCP tool returns a summary and writes the document to disk, written during the grilling). Source brief: `docs/project-brief.md` §1, §6 and §10, Phase 3. The decisions here come from a grilling session held on 2026-11-03.

## Problem Statement

One gap the brief names is still open: **an MCP server built from scratch.** Today the pipeline can be reached in two ways: the API (`POST /reformat`, deployed with ingress off by default) and the eval runner. No AI assistant can call it as a tool. The brief's Phase 3 exit criteria are an MCP server exposing `reformat_cv` that works from Claude Desktop, and that server documented in the README.

Exposing the pipeline to a calling model opens a new channel for candidate text. A tool's result goes into the model's context. If it carried the CV's text, a second LLM could restate or reword the candidate's words in the chat, which blurs the project's one invariant. ADR-0013 drew the boundary for the provider, the logs and the trace. It says nothing yet about a tool result, a file on disk, or a file name, which can itself be PII.

## Solution

`cvr.mcp` is a local MCP server over stdio, built on the official `mcp` Python SDK's `FastMCP`. Claude Desktop starts it on the maintainer's machine as `uv run --env-file .env python -m cvr.mcp`. It exposes exactly one tool, `reformat_cv`, which calls the same `reformat` in-process with the real labeller. There's no cloud cost and ingress stays off.

The user names a `.docx` path inside the **Workspace**, one configured folder. The tool writes the reformatted document next to it under a name that never overwrites anything and that contains the run id. It returns a **Tool result** with no candidate text: where the output went, the run id, whether the labelling failed, the number of retries, removal counts by rule, the unplaced count, tokens and cost. Claude can report what happened to a CV and point the user to the file, but it never sees the CV's words through the tool.

Logs go to stderr, written by the same PII-stripping writer as the API, which now lives in a module both servers share. Traces go to Langfuse in structure mode, tagged as coming from the MCP server. Secrets come from the repo's gitignored `.env`, never from the Claude Desktop config. The server and its SDK stay out of the Docker image.

## User Stories

1. As the maintainer, I want to call `reformat_cv` from Claude Desktop with a path to a CV, so that an AI assistant can use the pipeline as a tool.
2. As the maintainer, I want the tool to call the same `reformat` the API and the eval call, so that the MCP server adds no behaviour of its own to the pipeline.
3. As the maintainer, I want the server to run locally over stdio, so that a demo needs no open ingress, no Azure spend and no network path to my app.
4. As the maintainer, I want the server built on the official MCP SDK, so that the work goes into the tool's boundary rather than into message framing.
5. As the maintainer, I want exactly one tool, so that the server's surface matches what the pipeline actually offers (one template).
6. As the maintainer, I want to name the source document by a path, because Claude Desktop does not hand a local server the files attached in the chat.
7. As the maintainer, I want the tool to refuse any path that resolves outside the Workspace, so that a model-driven caller cannot make it read or write files elsewhere.
8. As the maintainer, I want `..` and symlinks resolved before that check, so that the Workspace cannot be escaped through either.
9. As the maintainer, I want a source document that is not a `.docx` refused, as the API refuses it.
10. As the maintainer, I want a source document over 5 MB refused under the same limit as the API, so that both servers accept the same documents.
11. As the maintainer, I want a path that does not exist, or that is a directory, refused with a fixed message.
12. As the maintainer, I want the output written next to the source document, so that I find it where I left the CV.
13. As the maintainer, I want the output named `<stem>-reformatted-<first 8 characters of the run id>.docx`, so that a re-run never overwrites an earlier result.
14. As the maintainer, I want the run id in the output's file name, so that a document leads straight to its trace and its log lines, as `X-Run-Id` does for the API.
15. As the maintainer, I want the tool never to overwrite an existing file, even if a name collides, so that no result is lost.
16. As the maintainer, I want the Tool result to carry no candidate text, so that no second LLM sees the candidate's words through the tool and cannot restate or reword them.
17. As the maintainer, I want the Tool result to state the output path, so that Claude can tell me where the document is.
18. As the maintainer, I want the Tool result to state the run id, so that I can find the trace in Langfuse.
19. As the maintainer, I want the Tool result to state whether the labelling failed, so that Claude can tell me the document is the banner and the appendix only.
20. As the maintainer, I want the Tool result to state how many retries the Run made.
21. As the maintainer, I want the Tool result to give removal counts by rule, so that I can see what was taken out without seeing what it was.
22. As the maintainer, I want the Tool result to give the number of unplaced spans and characters, with a line saying the review appendix holds them, so that I know to read the appendix.
23. As the maintainer, I want the Tool result to give tokens and cost summed over every attempt, so that each call shows what it cost.
24. As the maintainer, I want the tool's description to say that the result holds no CV text and that the caller should point the user to the file, so that Claude does not invent a description of the document.
25. As the maintainer, I want the tool's annotations to say it writes, does not destroy, is not idempotent and calls an outside service, so that the client can treat it correctly.
26. As the maintainer, I want an unavailable provider to come back as a tool error with a fixed message, so that the failure is clear and carries no exception text.
27. As the maintainer, I want a misconfigured labeller, and any unexpected error, to come back as a tool error with a fixed message naming only the category, matching the API's 500.
28. As the maintainer, I want a labelling failure to be a successful call that writes the banner document, as the API's 200 is, so that the job always completes.
29. As the maintainer, I want the server to start and list its tool without the model key, so that a missing key fails on the first call with a clear message rather than stopping the server from loading.
30. As the maintainer, I want the labeller built once, on the first call, and reused, as in the API.
31. As the maintainer, I want calls to run one at a time, because the labeller keeps its last run on itself.
32. As the maintainer, I want the server's secrets to come from the repo's gitignored `.env`, so that Claude Desktop's config holds no secret.
33. As the maintainer, I want the README to show a Claude Desktop config snippet with no secret in it.
34. As the maintainer, I want nothing on stdout but the protocol, so that a stray line never corrupts the session.
35. As the maintainer, I want each Run logged to stderr in the same form as the API's log (one summary line and one line per block, PII stripped), so that both servers record a Run identically.
36. As the maintainer, I want the log writer in one module shared by the API and the MCP server, so that neither server imports the other and the leak test covers a single writer.
37. As the maintainer, I want the source document's path and file name never written to the logs or the trace, because a file name can be PII.
38. As the maintainer, I want the model key never written to stderr, the Tool result or the trace.
39. As the maintainer, I want every Run traced in Langfuse with the run id as the trace id, under the `local` environment with a `surface=mcp` tag, so that MCP runs can be told apart from API and eval runs.
40. As the maintainer, I want the server always to trace in structure mode and to warn if `CVR_TRACE_MODE=full` is set, as the API does.
41. As the maintainer, I want the server untraced and silent when the Langfuse keys are absent.
42. As the maintainer, I want the MCP SDK installed as an optional dependency group that the image's sync skips, so that the deployed image does not grow.
43. As the maintainer, I want `cvr.mcp` left out of the image and a test that fails if the service can import it there.
44. As the maintainer, I want `cvr.mcp` added to the pipeline's allowed importers, and no one else, so that the import rule stays pinned.
45. As the maintainer, I want the API's behaviour unchanged by the shared module, so that the API tests pass without edits other than import paths.
46. As the maintainer, I want the canary leak test to cover the MCP server, with canaries in the body and in the file name, so that the boundary in ADR-0016 is proved as ADR-0013's is.
47. As the maintainer, I want the eval gate unchanged, since this phase changes no prompt, schema or model.
48. As the maintainer, I want to prove the tool live from Claude Desktop on one golden document, with the run id and trace recorded on the ticket.
49. As the maintainer, I want a screenshot or GIF of that call in the README, so that a reader sees the tool working without installing it.
50. As an interviewer, I want to see the tool return a summary and a path, never the CV, so that the invariant visibly holds over a second LLM too.
51. As an interviewer, I want the README to explain why the server is local stdio and not remote, why there is no `list_templates`, and why the result has no text, so that the trade-offs are on record.
52. As a future maintainer, I want CLAUDE.md, `docs/development.md`, brief §10 and the README updated with the server, its command and its environment variables, so that the status stays true.

## Implementation Decisions

- **Transport and SDK.** A local stdio server on the official `mcp` SDK's `FastMCP`. The tool's input schema comes from the function's type hints. Remote Streamable HTTP on `cvr-ca` and hand-written JSON-RPC are rejected (ADR-0016).
- **One tool.** `reformat_cv(path)`. No `list_templates`: the brief names it in brackets only, and one template is "what changes at scale" (§12).
- **A server factory.** `cvr.mcp` exposes a factory, `create_server(labeller=None, tracer=None, workspace=None)`, mirroring the API's `create_app(labeller, tracer)`. Tests inject the oracle labeller, a test tracer and a temporary Workspace. `python -m cvr.mcp` builds the server from the environment and runs it over stdio.
- **Workspace.** It is read from `CVR_MCP_ROOT`, once, when the server is created. If it is unset, empty or not a directory, the server refuses to start with a named error, failing closed like the API's missing `CVR_API_KEY`. The tool resolves the given path (absolute, or relative to the Workspace), resolving `..` and symlinks first, and refuses anything outside the Workspace. It also refuses anything that does not exist, is not a file, does not end in `.docx` (case-insensitive) or is over `MAX_UPLOAD_BYTES`. The size is checked before the file is read.
- **Output.** The output is written next to the source document as `<stem>-reformatted-<run_id[:8]>.docx`, through an exclusive create, so an existing file is never replaced. A collision is a tool error and is never retried silently. The output is inside the Workspace because the source document is.
- **Tool result.** The tool returns structured content plus a short text rendering of the same fields. The fields are:
  - `output_path`
  - `run_id`
  - `status`: `ok` | `labelling_failed`
  - `retries`
  - `removals`: rule id → count
  - `unplaced`: spans and characters
  - `appendix`: a fixed sentence when unplaced text exists, else none
  - `input_tokens`, `output_tokens`, `cost_usd`: summed over every attempt, as the API summary's `attempts`

  No field carries candidate text, and `output_path` is the only field that names a file.
- **Errors.** Fixed categories with fixed messages, returned as tool errors (`isError`):
  - `outside_workspace`, `not_found`, `not_docx`, `too_large`, `exists`
  - `provider_unavailable` (`ProviderUnavailable`)
  - `misconfigured` (`LabellerMisconfigured`)
  - `internal` (anything else, logged by type name only)

  A labelling failure is not an error: the banner document is written and `status` is `labelling_failed`.
- **The shared module.** The API's log writer moves into a module shared by `api` and `mcp`, along with `MAX_UPLOAD_BYTES` and whatever the error mapping needs. The obvious name is `cvr.runlog`, final name at implementation. `api` keeps its behaviour and imports from there. The writer takes its output stream; the API passes stdout, the MCP server stderr. The summary line for an MCP run has the same keys as the API's. It never contains the path or the file name.
- **Labeller lifecycle.** As in the API: `RealLabeller` is built from `LabellerConfig` on the first call and reused, and calls are serialised by a lock. `retry_max()` is read when the server is created, so a bad `CVR_RETRY_MAX` fails at startup.
- **Secrets.** Claude Desktop runs `uv run --env-file .env python -m cvr.mcp` with `--directory` set to the repo. The `.env` holds `ANTHROPIC_API_KEY`, optionally the Langfuse keys and base URL, and `CVR_MCP_ROOT`. The Claude Desktop config holds no secret. `.env` is already gitignored and outside the image's allowlist.
- **Tracing.** `Tracer.from_env(tags=["env=local", "surface=mcp"])` with environment `local`. It is flushed after each call and shut down on exit. The server warns on `CVR_TRACE_MODE=full` and never traces in full mode. Without keys it is disabled and silent.
- **stdout.** Only the SDK writes to stdout. Logging and warnings go to stderr.
- **Tool description and annotations.** The description states the Workspace rule, the output naming, that the result holds no CV text, and that the caller should give the user the output path rather than describe the document. The annotations are `readOnlyHint` false, `destructiveHint` false, `idempotentHint` false and `openWorldHint` true.
- **Dependencies and image.** `mcp` goes in an optional dependency group, installed by the local `uv sync` and skipped by the image's `--no-dev` sync. `.dockerignore`'s allowlist leaves out `src/cvr/mcp`.
- **Import rule.** The allowed importers of `cvr.pipeline` become `api`, the eval runner and `mcp`. `mcp` does not import `api`, and `api` does not import `mcp`.
- **Docs.** The README gains a Phase 3 section: what the tool does, the config snippet, the Workspace and output naming, why stdio, why no text, why no `list_templates`, and the screenshot or GIF. CLAUDE.md, `docs/development.md` and brief §10 are updated.

## Testing Decisions

A good test here calls the tool the way a client does and checks what comes back and what lands on disk, stderr and the trace. It never checks how the server is put together. No test reaches a model. The oracle labeller and the canary test's fake chat model stand in, as they do for the API.

- **The MCP tool, through the SDK's in-memory client session** (the main seam). The server comes from the factory with an injected labeller, tracer and temporary Workspace. Tests cover:
  - a successful call: the output file exists, is a `.docx` and is named as specified, and the Tool result's fields agree with the Run
  - the tool list, schema, description and annotations
  - each error category: escape by `..`, by an absolute path, by a symlink (skipped where the platform cannot create one); not found; a directory; not `.docx`; over the limit, checked before reading; an existing output name
  - a labelling failure producing the banner document and `labelling_failed`
  - a provider outage and a defect producing fixed messages with no exception text
  - the labeller built once and lazily, with the server listing its tool without a key
  - calls serialised by the lock
  - the startup refusals: no Workspace, and a bad `CVR_RETRY_MAX`

  Prior art: `tests/api/test_app.py`, `test_api_retry.py`, `test_api_tracing.py`.
- **The canary leak test** gains an MCP case through the same seam. A canary Candidate goes through all four Layouts with a canary in the file name too, using `RealLabeller` over the fake chat model, including the retry scenarios. The assertions:
  - no canary in any Tool result field other than `output_path`
  - the file-name canary in `output_path` only
  - no PII canary on stderr
  - no canary at all in any structure-mode span
  - the key's value nowhere

  Positive controls: stderr holds content text, the spans hold the run id. Prior art: `tests/tracing/test_canary_leak.py`.
- **A process test.** `python -m cvr.mcp` started as a subprocess over stdio with a temporary Workspace and no key. It covers the initialise handshake, the tool list, every stdout line parsing as JSON-RPC, and a clean exit when stdin closes. It makes no `reformat_cv` call. Prior art: `tests/api/test_main.py`.
- **The shared log writer.** The existing log tests move with it and keep their assertions. One more checks the stream parameter, and that an MCP summary line has the API's keys and no path. Prior art: `tests/api/test_log.py`.
- **Static checks.**
  - `tests/docker/` gains `cvr.mcp` unimportable in the service and `src/cvr/mcp` absent from the allowlist.
  - The import-boundary test in `tests/pipeline/` gains `mcp/` as an allowed importer and a check that `api` and `mcp` do not import each other.
- **Live evidence, not a test.** The maintainer copies `c04__single-column.docx` into the Workspace and calls `reformat_cv` from Claude Desktop. The ticket records the Tool result, the run id and the trace, and the README gets the screenshot or GIF.

## Out of Scope

- A remote MCP server (Streamable HTTP on `cvr-ca`), its authentication (Entra or the API key) and any ingress change.
- A Claude Desktop extension bundle (`.mcpb`), and secrets in the OS credential store.
- `list_templates`, `list_inputs` or any second tool, any MCP resource, prompt or sampling.
- Returning the document's text or bytes to the calling model.
- Any change to the prompt, the schema, the model, the eval gate or its thresholds.
- Any change to the deployed app or the image beyond keeping `cvr.mcp` out of it.
- MCP clients other than Claude Desktop.

## Further Notes

- The phase 2 checkbox in brief §10, "Langfuse tracing on every run, with the run ID linked from API logs", waits on ticket 22's last box (traces under Langfuse's Environment filter after the next eval). The first Phase 3 PR's eval run is that chance. The maintainer can check it then and tick both.
- Ticket 18's idle-cost box was ticked on 2026-11-03 in the working tree and is uncommitted. It goes into the first Phase 3 PR along with `CONTEXT.md`'s Serving terms and ADR-0016.
- Each push to `main` that changes more than docs costs one uncached eval (about $1.60). Phase 3 should merge as few times as its review allows.
- Claude Desktop on this machine is the Microsoft Store package. Its config file lives under the package's AppData folder, not `%APPDATA%\Claude`. The README should name both locations.
