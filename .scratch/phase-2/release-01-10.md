# Phase 2 release 01-10

Phase 2's first ten tickets: the pipeline as a LangGraph graph, labelling failures and logs that carry no model text or PII, Langfuse tracing from the API and the eval in two modes, and the canary test that proves the content boundary. All ten are done on the local branch `phase-2/release-01-10` (merged from per-ticket branches on 2026-10-21; the evidence was added on 2026-10-24 on `phase-2/release-evidence`). Nothing is on `main` yet: one pull request for the release is the next step, and it triggers one eval and one deploy. Tickets 11-21 (the retry loop and Azure OpenAI) and the new ticket 22 are next.

## What each ticket delivered

- **01 Azure read-only fact spike.** The facts the Azure tickets need, from docs and the maintainer's read-only `az` run: `gpt-5.4` 2026-03-05 on Data Zone Standard in northeurope, the managed-identity token scope, the Log Analytics minimums (4 days per table, 30 at the workspace). `Microsoft.CognitiveServices` is not registered on `cvr_sub`, so quota could not be read; that moves to ticket 18.
- **02 Pipeline on LangGraph.** `reformat` runs a `StateGraph` of the five nodes in a line, same signature, same `(bytes, Run)`, behaviour unchanged. `langgraph` is a direct dependency at the version already locked. The graph is built per call, the `Run` is assembled after `invoke`, and there is no `cvr.graph` package (the graph lives in `src/cvr/pipeline/`). No existing test was edited.
- **03 Labelling failures carry no model text.** A labelling failure's reason is a fixed category plus allowlisted schema field names; provider errors keep their classification without the SDK's message, `__cause__` or `__context__`.
- **04 Catch-all 500 and the local traceback flag.** The catch-all logs the exception type only; the traceback goes to standard error only with `CVR_DEBUG_TRACEBACKS=1`, read once at app creation and never set by any workflow, script or the Dockerfile (a static test).
- **05 PII stripped from log lines.** Text removals under PII rules log block, offsets, length and a character class, never text; residue overlapping one likewise; PII-shaped text in the `error` field is replaced.
- **06 Log Analytics retention lowered.** The wizard's stage 12 sets the non-`_CL` ContainerApp tables to 4 days. The populated `_CL` tables are classic tables the API refuses to change, and keep the workspace's 30.
- **07 Structure traces from `reformat`.** The `cvr.tracing` package: `Tracer` over the Langfuse SDK 5.x, one trace per Run with the run id as trace id, a span per node, one generation per labelling attempt, one event per rejection (never the quote). An allowlist decides what a span carries and the SDK's mask hook is the second layer. Tracing can never fail a Run.
- **08 Traces from the API and the eval.** Both build the tracer from the environment, tag `env=prod|eval|local`, flush and shut down; a cache hit's generation is marked `cached` at zero cost; without keys both run untraced. The Langfuse secrets for the eval job and the app are set by GitHub secrets and the wizard.
- **09 Full-text mode.** `CVR_TRACE_MODE=full` adds the blocks, the rendered prompt, the raw answer and rejections' quotes through the same payload functions; the spans are identical. The eval job sets it; the deployment never does (pinned by a static test) and the API warns if it is set.
- **10 Canary leak test and ADR-0013.** One test in the default run (about 11 s, no LLM): seeded canaries through all four Layouts, the API and `reformat` over a fake chat model, none in any structure-mode span, no PII canary in logs, error bodies, exceptions or failure reasons. ADR-0013 records the content boundary. The screenshot of a full-mode trace is in the README.

## Decisions taken along the way

- **`CVR_DEBUG_TRACEBACKS`** is the name of the debug setting (the spec named none).
- **Ticket 03, unexpected errors.** The first build made an unexpected exception from the model call a labelling failure with reason `unexpected`. The maintainer reversed it: it raises `LabellerMisconfigured` naming only the exception's type, so a defect stays a loud 500 and is never retried as a model failure. Refined the same day: every parser or validation error, returned as `parsing_error` or raised by the call, is a labelling failure (`invalid JSON` or `schema mismatch`), which the Phase 2 retry loop should retry. ADR-0009 carries an amendment.
- **Ticket 05.** The maintainer approved the edit to `test_the_lines_hold_the_whole_run` (it now reads stripped spans back with placeholder text) and the dependency of `api` on `verify.backstops` for the PII patterns.
- **Ticket 06, option A.** After the wizard met the classic `_CL` tables, the maintainer accepted 30 days for them (the workspace floor; no documented non-migrating way to change them; synthetic data; nothing saved below 31 days). Option B, `--logs-destination azure-monitor`, is a possible later ticket.
- **Wizard tests.** The test that pinned the old wizard stop logic was replaced, with the maintainer's approval, when the wizard began stopping the app through `demo.sh down`.
- **Ticket 08.** The API warns rather than refuses on `CVR_TRACE_MODE=full` (failing closed would take the demo down; a static test and the warning cover it).

## Independent review of ticket 07

A review separate from the builder found blocking points, all fixed on 2026-10-21. A rejection event's block id is the model's own answer and could carry model text, so it is exported only when it is one of the parsed blocks' ids and is `unknown` otherwise. Tracing could fail a Run (payloads built outside the guard, `propagate_attributes` unguarded), so payloads are now built inside the guard and a raising client, payload function or `propagate_attributes` each leaves the output and Run unchanged (tested). The untraced path builds no payload. A stale `last_run` from an earlier call could be recorded as a generation's, so identity is checked. The mode and mask became a per-mode closure.

## What the canary test found

Ticket 10's test found a real leak. On a failed labelling the whole document is residue, and `cvr.api.log` wrote every residue span's text, so addresses, dates of birth, nationality and referee names (which the regex backstops do not catch) reached the logs. ADR-0013's "logs keep text, minus PII" was false on that path. Fixed test-first in `src/cvr/api/log.py`: a failed labelling logs every residue text-free. Not fixed, and recorded in the ADR: PII the labeller misses in a successful run is unplaced text and is logged, as it is in the appendix; the eval's `pii_leak` measures that. Deliberately breaking the allowlist (scratch, not committed) showed the mask hook catching it alone, and the test failing when both layers were broken.

## The wizard fixes

Found when the maintainer ran `scripts/provision-azure.sh` for tickets 06 and 08: a revision lock conflict (the wizard now waits for the app after every change and skips no-op environment updates); the closing stop now goes through `demo.sh down` instead of its own logic; no script gives curl `/dev/null` to write to, which fails on Windows; and stage 12 warns by table name and goes on when a classic table refuses its update, so stage 13 runs.

## Evidence (2026-10-24, the maintainer's runs on this branch)

| | |
|---|---|
| Eval, `--no-cache`, `CVR_TRACE_MODE=full` | PASS, 48 documents, every hard gate at zero; structural 100.00/100.00; tunable 98.58/98.58 (text-box 95.04); appendix 0.70%; punctuation 0; label fails 0; errors 0 |
| Cost and time | $1.5927, 269,974 tokens in and 105,271 out, 147.8 s, 48 live calls; `claude-sonnet-5-5` at `medium`, prompt 1.3.0, schema 1.0.0 |
| Image check | 350 MB (Phase 1: 325 MB; the 25 MB is Langfuse and OpenTelemetry); uid 10001; `cvr.golden` and `cvr.eval` unimportable; no key in history or filesystem; `/health` 200, `/reformat` without key 401, with key 200; `== ok` |
| Smoke test on Azure | `/health` 1 s then 0 s; no key 401; `c04__single-column.docx` 200, 39,164 bytes, run id `3dc181708738493bb70f73de47997fbb`; `demo.sh down` run afterwards. Main's image is deployed, so it was untraced; the first `env=prod` trace comes from the deploy after the PR merges |
| Langfuse (Cloud EU, Hobby, private) | 48 `env=eval` traces; each `reformat` over parse, label (one generation), verify, transform, render; example trace `67a59f7f658041ed8e6e5815d5f82aeb`, 12.34 s, $0.038; full mode shows the CV text and the JSON answer; Hobby usage 320 of 50,000 units (0.64%) |
| Screenshot | `docs/images/langfuse-trace.png`, linked from the README |

Tunable placement of 98.58% is above the unchanged 98% threshold and under Phase 1's 100% on Opus; text-box is the layout that gives it up. Not yet shown: a CI eval run of this branch (the PR's will be) and any production trace.

## Found along the way

Langfuse's Environment field showed `default` on every trace, because only the `env=` tag was set. Ticket 22 passes the native environment too (`Langfuse(environment=...)`).

## Next

Tickets 11-21: path-addressed additions in `verify`, the retry prompt, the retry decision and loop, the retry in the eval with ADR-0012, and the canary test over the retry (11-16); then Azure OpenAI as a second provider, its provisioning, the managed identity proven live, the provider comparison and verdict, and the gate and deployment on Azure if it wins (17-21). Ticket 22 has no blocker and can go first. Merging the release PR costs one eval (about $1.60) and one deploy.
