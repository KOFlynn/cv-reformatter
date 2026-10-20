# 19: The managed identity proven live

**What to build:** evidence that Container Apps reaches Azure OpenAI through its managed identity. A revision set to the Azure provider is started, smoke-tested through the existing smoke and demo scripts with one real `/reformat`, and its run id and outcome are recorded. It is then set back to the deployed provider, and the app is left off. ADR-0014 records Azure OpenAI through a managed identity, Data Zone EU, the disabled key auth and, as a decision to apply if Azure wins, the eval's narrow OIDC identity.

**Blocked by:** 17 (merged and deployed), 18

**Status:** ready-for-agent

- [ ] The configuration switch is scripted, so it is repeatable rather than portal clicks
- [ ] The smoke run returns 200 with a `.docx` and `X-Run-Id`; the trace in Langfuse shows the Azure model; recorded on this ticket
- [ ] The app's configuration is set back, and `demo.sh down` leaves no replica running (replica list checked)
- [ ] ADR-0014 written; the brief's §10 managed identity box ticked
