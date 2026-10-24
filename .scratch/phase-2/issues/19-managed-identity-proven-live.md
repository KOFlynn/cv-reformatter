# 19: The managed identity proven live

**What to build:** evidence that Container Apps reaches Azure OpenAI through its managed identity. A revision set to the Azure provider is started, smoke-tested through the existing smoke and demo scripts with one real `/reformat`, and its run id and outcome are recorded. It is then set back to the deployed provider, and the app is left off. ADR-0014 records Azure OpenAI through a managed identity, Data Zone EU, the disabled key auth and, as a decision to apply if Azure wins, the eval's narrow OIDC identity.

**Blocked by:** 17 (merged and deployed), 18

**Status:** ready-for-agent

- [x] The configuration switch is scripted, so it is repeatable rather than portal clicks
- [ ] The smoke run returns 200 with a `.docx` and `X-Run-Id`; the trace in Langfuse shows the Azure model; recorded on this ticket
- [ ] The app's configuration is set back, and `demo.sh down` leaves no replica running (replica list checked)
- [ ] ADR-0014 written; the brief's §10 managed identity box ticked


**2026-10-24, from the 11-17 release.** The live proof must settle three things the code could only guess: (1) the token scope, `https://ai.azure.com/.default` (the default) against `https://cognitiveservices.azure.com/.default`; (2) the API version (`2025-04-01-preview` by default); (3) whether Azure's five-level nesting limit counts arrays as well as objects. `Labelling` is four levels by objects and six if arrays count; if the first live call rejects it, the fix is a schema bump plus an eval on the deployed provider.

## Comments

**2026-10-24, the offline half.** Box 1 is done: `scripts/switch-provider.sh azure|anthropic [RG] [APP]` (tests in `tests/ci/test_switch_provider.py`, including a run against a fake `az`). It reads `AZURE_OPENAI_ACCOUNT` and `AZURE_OPENAI_DEPLOYMENT` from `.env.azure`, sets provider, model `gpt-5.4`, effort `medium` (valid for Azure), endpoint `https://<account>.openai.azure.com/` and deployment, passes `CVR_LABEL_AZURE_SCOPE` and `CVR_LABEL_AZURE_API_VERSION` through from the caller's environment (an override not given again is removed), and `anthropic` removes every one. An update makes a new revision that may start a replica, so the script never stops the app: the sequence ends with `demo.sh down` and a replica list that prints 0 (runbook in `docs/development.md`, Deployment). ADR-0014 is a draft with the scope, API version and nesting-limit results marked "to be settled by the live proof". Boxes 2 to 4 wait for ticket 18 and the maintainer's run; the brief's §10 box stays unticked.