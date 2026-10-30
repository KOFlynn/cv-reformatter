# Phase 2 release 18-22

Phase 2's last tickets: Azure OpenAI provisioned with no key, the managed identity proven live, the provider comparison and its ADR, and Langfuse's native Environment field. Tickets 18, 19, 20 and 22 are done and ticket 21 is closed as not needed, on `phase-2/release-18-22`. Tickets 01-17 are on `main` (PR #40 and PR #41). One pull request for this release is the next step. The verdict was confirmed by the maintainer on 2026-10-30: Anthropic Sonnet 5.5 at `medium` stays the deployed provider, and Azure OpenAI stays a proven, unused second provider.

## What each ticket delivered

- **18 Provision Azure OpenAI.** Stage 13 of `scripts/provision-azure.sh`: registers `Microsoft.CognitiveServices`, stops if the chosen model has no `DataZoneStandard` quota, creates or confirms an AIServices account with a custom subdomain and `disableLocalAuth` true, a `DataZoneStandard` deployment named after the remembered model, and `Cognitive Services OpenAI User` on the account alone for `cvr-ca`'s system-assigned identity and the maintainer. It reads every deployment back before reporting. No key exists anywhere.
- **19 Managed identity proven live.** `scripts/switch-provider.sh azure|anthropic` points `cvr-ca` at Azure OpenAI and back without ever stopping the app. A real `/reformat` from Container Apps authenticated through the managed identity with scope `https://ai.azure.com/.default` and API version `2025-04-01-preview`. ADR-0014 is accepted; the brief's managed-identity box is ticked.
- **20 Provider comparison and verdict.** `cvr.eval.compare` and `eval/provider-comparison-2026-10-29.json`: three live, uncached runs of each configuration, same prompt, schemas and thresholds. ADR-0015 records the verdict.
- **21 Gate and deployment on Azure.** Closed as not needed; see below.
- **22 Langfuse Environment field.** `Tracer.create` and `Tracer.from_env` take `environment=`, passed to `Langfuse(environment=...)` so it lands on every span as `langfuse.environment`. The API passes `CVR_TRACE_ENV` (default `local`), the eval `eval`; the `env=` tag stays. A test shows a stray `LANGFUSE_TRACING_ENVIRONMENT` cannot override it.

## Evidence

- **Provisioning (2026-10-29).** Account `cvr-aoai-961a` in swedencentral, kind AIServices, `disableLocalAuth` true; deployment `gpt-5.4-mini` 2026-03-17, `DataZoneStandard`, capacity 200 (quota before: limit 200, used 0); exactly two role assignments, both `Cognitive Services OpenAI User` (`cvr-ca`'s identity and the maintainer); `cvr-ca` had 0 replicas afterwards.
- **Live managed-identity run.** Run id `db24fcfa61dd454c93d9b45b72fe8cee`: `c04__single-column.docx` returned 200 with a `.docx` and `X-Run-Id`; the app's summary line shows provider `azure_openai`, model `gpt-5.4-mini`, 3110 input and 2848 output tokens, 0 retries, 0 unplaced; the maintainer saw the generation in Langfuse. Afterwards `demo.sh down` and `switch-provider.sh anthropic` restored the app, and the replica count printed 0.
- **Comparison (ADR-0015).** Sonnet 5.5 `medium`: gate PASS x3, tunable placement 99.65 / 99.73, appendix 0.67%, 9 retries (25 characters placed), $1.711-1.712 and 137.5-139.6 s a run. gpt-5.4-mini `medium`: gate FAIL x3, tunable placement 43.89-44.42 / 43.97-44.50, wrongful removals 7, 6 and 9 (c04 `RM_REFEREE` and c07 `RM_PERSONAL` every run), structural gate failed once (c08 text-box, 99.63%), 14, 16 and 13 retries, $1.029-1.050 and 418.7-435.7 s a run (Azure at `--concurrency 2`). The added, dropped, provenance, PII, image and ordering counts were zero on both. Three runs cost $5.13 and $3.13.
- **Ticket 22.** Tests assert the attribute through the injected exporter for the API and the eval; the canary leak test stays green.

## Closed

- **Ticket 21** was conditional on Azure winning. gpt-5.4-mini failed the gate in all three runs and the stronger models had no quota, so it is closed as not needed. ADR-0015 ("What reopens the decision") says what would reopen it: quota for gpt-5.4 or gpt-5.6-terra on an EU Data Zone deployment, a change to the prompt, schemas or models, or an EU-only processing requirement. The narrow eval identity in ADR-0014 stands for that case.

## Decisions

- **gpt-5.4-mini.** `cvr_sub` had zero `DataZoneStandard` quota for gpt-5.4 in every EU region (2026-10-24) and 200K TPM for gpt-5.4-mini in swedencentral, so the account and the comparison use gpt-5.4-mini. The result is a statement about that model, not about Azure OpenAI.
- **gpt-5.6-terra.** The quota request in swedencentral was refused on 2026-10-29 (no capacity to expand; resubmit with other regions or wait 30 days or more). It stays in `KNOWN_MODELS` and `PRICE_TABLE`.
- **Azure limits.** `max_completion_tokens` is 32000 (`AZURE_MAX_COMPLETION_TOKENS`), since Azure's TPM limiter counts it up front, and the eval runs at `--concurrency 2` against the 200K TPM deployment.
- **Stage 13 read-back.** `az` 2.90 prints a tsv list one element per line; the read-back flattens it. The record stage's variables all have defaults, so it no longer crashes under `set -u` when the smoke test is skipped.
- **`demo.sh up`** skips activating a revision that is already active (`switch-provider.sh`'s env update activates it, and `up` failed with `RevisionAlreadyInRequestedState`).
- **Thresholds unchanged**, as in ADR-0011. No code, deployment or gate changed for the verdict.
- **Verdict confirmed** by the maintainer 2026-10-30: `verdict.maintainer_decision` in the record reads `confirmed`, and ADR-0015's status says so.

## Open (the maintainer's)

- **Ticket 18's idle-cost check:** a few days after 2026-10-29, confirm the Azure OpenAI account costs nothing idle; note it on the ticket.
- **Ticket 22's last box:** after the next eval, confirm the traces appear under Langfuse's Environment filter; note it on the ticket.

## What the pull request will do

The PR's eval replays the first attempts from the cache (no prompt, schema or model changed) and runs any retries live, so it should cost little. The merge to `main` runs an uncached eval (about $1.7) and redeploys; the deployed image gains the `gpt-5.4-mini` price, and the app is left off afterwards with no replica. That main eval is also the run whose traces show whether the Environment field works.
