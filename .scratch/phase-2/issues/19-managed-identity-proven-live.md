# 19: The managed identity proven live

**What to build:** evidence that Container Apps reaches Azure OpenAI through its managed identity. A revision set to the Azure provider is started, smoke-tested through the existing smoke and demo scripts with one real `/reformat`, and its run id and outcome are recorded. It is then set back to the deployed provider, and the app is left off. ADR-0014 records Azure OpenAI through a managed identity, Data Zone EU, the disabled key auth and, as a decision to apply if Azure wins, the eval's narrow OIDC identity.

**Blocked by:** 17 (merged and deployed), 18

**Status:** done except the Langfuse look (box 2)

- [x] The configuration switch is scripted, so it is repeatable rather than portal clicks
- [ ] (Langfuse trace pending the maintainer's check; the run itself is proven, see Comments) The smoke run returns 200 with a `.docx` and `X-Run-Id`; the trace in Langfuse shows the Azure model; recorded on this ticket
- [x] The app's configuration is set back, and `demo.sh down` leaves no replica running (replica list checked)
- [x] ADR-0014 written; the brief's §10 managed identity box ticked


**2026-10-24, from the 11-17 release.** The live proof must settle three things the code could only guess: (1) the token scope, `https://ai.azure.com/.default` (the default) against `https://cognitiveservices.azure.com/.default`; (2) the API version (`2025-04-01-preview` by default); (3) whether Azure's five-level nesting limit counts arrays as well as objects. `Labelling` is four levels by objects and six if arrays count; if the first live call rejects it, the fix is a schema bump plus an eval on the deployed provider.

## Comments

**2026-10-24, the offline half.** Box 1 is done: `scripts/switch-provider.sh azure|anthropic [RG] [APP]` (tests in `tests/ci/test_switch_provider.py`, including a run against a fake `az`). It reads `AZURE_OPENAI_ENDPOINT` (the provisioning-complete marker) and `AZURE_OPENAI_DEPLOYMENT` from `.env.azure`, sets provider, model `gpt-5.4`, effort `medium` (valid for Azure), that endpoint and deployment, in a single update (only override names actually present are removed), passes `CVR_LABEL_AZURE_SCOPE` and `CVR_LABEL_AZURE_API_VERSION` through from the caller's environment (an override not given again is removed), and `anthropic` removes every one. An update makes a new revision that may start a replica, so the script never stops the app: the sequence ends with `demo.sh down` and a replica list that prints 0 (runbook in `docs/development.md`, Deployment). ADR-0014 is a draft with the scope, API version and nesting-limit results marked "to be settled by the live proof". Boxes 2 to 4 wait for ticket 18 and the maintainer's run; the brief's §10 box stays unticked.


**2026-10-29, the live proof.** Account `cvr-aoai-961a` (swedencentral), deployment `gpt-5.4-mini` 2026-03-17 `DataZoneStandard`, 200K TPM (cvr_sub has no gpt-5.4 quota; see tickets 18 and 20 and ADR-0014).

- *Local check first* (the maintainer's `az login`, so the default chain's Azure CLI credential): `uv run python -m cvr.eval.run --candidate c04 --layout single-column --no-cache --concurrency 1` with provider `azure_openai`, model `gpt-5.4-mini`, effort `medium`, the default scope `https://ai.azure.com/.default` and API version `2025-04-01-preview`. The call succeeded and the strict `Labelling` schema was accepted, so Azure's nesting limit did not reject it and there is no schema bump. 3110 input and 4806 output tokens, $0.0264. The gate failed on that one document on quality: `RM_REFEREE` removed a content line ("Role made redundant during the firm's merger; ..."), tunable placement precision 95.65% and recall 91.67%. That is a model-quality result for ticket 20, not a setup fault.
- *Live:* `switch-provider.sh azure` gave revision `cvr-ca--0000011`, active, with `CVR_LABEL_PROVIDER=azure_openai`, model and deployment `gpt-5.4-mini`, effort `medium`, endpoint `https://cvr-aoai-961a.openai.azure.com/`. `demo.sh up` failed with `RevisionAlreadyInRequestedState` (the env update had already activated the revision); the workaround was `demo.sh down` then `demo.sh up`, and `demo.sh up` now skips activating an active revision (tested). Smoke: `/health` after 1 s, no key gave 401, `c04__single-column.docx` gave HTTP 200 with a 39164-byte `.docx` and `X-Run-Id` `db24fcfa61dd454c93d9b45b72fe8cee`. The app's summary line in Log Analytics (revision `cvr-ca--0000011`, 2026-10-29T16:08:09Z): status 200, provider `azure_openai`, model and deployment `gpt-5.4-mini`, effort `medium`, prompt 1.3.0, schema 1.0.0, input 3110 and output 2848 tokens, `cost_usd` 0.0 (the deployed image, main at `accea1f`, has no `gpt-5.4-mini` price; this branch adds it), `label_failed` false, 0 retries, 54 blocks, 14 removals, 0 unplaced.
- *Back:* `demo.sh down`, then `switch-provider.sh anthropic` gave revision `cvr-ca--0000012` with no `CVR_LABEL_*` variables, `demo.sh down` again, and `az containerapp replica list ... length(@)` printed 0.
- *Result:* the managed identity works with scope `https://ai.azure.com/.default` and API version `2025-04-01-preview`; there is no key anywhere. The nesting limit and role propagation were not issues. ADR-0014 is accepted and the brief's section 10 managed-identity box is ticked.
- *Langfuse: pending maintainer check.* Open the trace for run id `db24fcfa61dd454c93d9b45b72fe8cee` and confirm the generation's model is `gpt-5.4-mini` (the cost will show 0, as in the log). Box 2 stays unticked until then.
