# 18: Provision Azure OpenAI

**What to build:** the Azure OpenAI path exists, with no key anywhere. The provisioning wizard gains a step, run by the maintainer:
- an Azure OpenAI (Foundry) account in `cvr-rg` with a custom subdomain;
- key authentication disabled, through ARM, Bicep or PowerShell, since `az` has no flag for it;
- a Data Zone Standard (EU) gpt-5.4 deployment;
- a managed identity on `cvr-ca` with only the inference role on the account;
- the same role for the maintainer's user, for local comparison runs.

It is idempotent and verified read-only afterwards.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The wizard step creates or confirms each resource and reports what already existed
- [ ] Read-back confirms that local auth is disabled, that the deployment type is Data Zone Standard, and that the role assignments are as stated
- [x] The wizard's static test covers the step; values the wizard remembers stay in the gitignored env file
- [ ] The account and deployment names are recorded in CLAUDE.md's deployment entry
- [ ] No idle cost: the maintainer checks the cost a few days later, noted on the ticket

## Comments


- 2026-10-24: Stage 13 stopped on zero quota. `cvr_sub` has 0 interactive quota for gpt-5.4 everywhere (northeurope Global and Data Zone rows all 0.0). A read-only usage check across EU regions found the only EU Data Zone Standard chat model with quota is `OpenAI.DataZoneStandard.gpt-5.4-mini`, limit 200 (thousand TPM), in swedencentral, westeurope, germanywestcentral and francecentral (not northeurope). Decision: the account is provisioned in **swedencentral** (its own remembered `AZURE_OPENAI_LOCATION`; the Container App stays in northeurope) with a **gpt-5.4-mini** (2026-03-17) `DataZoneStandard` deployment named `gpt-5.4-mini`, default capacity min(available, 200). The stage now remembers `AZURE_OPENAI_MODEL` (default gpt-5.4-mini; gpt-5.4 pins 2026-03-05, default capacity 500), reads back every deployment on the account, and re-running with the other model adds that deployment without touching the first. ADR-0014 records the region split. The first box ("a Data Zone Standard (EU) gpt-5.4 deployment") is met with gpt-5.4-mini; CLAUDE.md names what was actually deployed once the maintainer has run the stage.
- 2026-10-29: A Data Zone Standard quota request for **gpt-5.6-terra** (swedencentral; model list shows version 2026-07-09 with GlobalStandard and DataZoneStandard) was filed by the maintainer and is pending (`OpenAI.DataZoneStandard.gpt-5.6-terra` is 0.0 today). If granted, re-run stage 13 with `AZURE_OPENAI_MODEL=gpt-5.6-terra` to add that deployment to the same account; the stage accepts gpt-5.4-mini (default), gpt-5.6-terra and gpt-5.4. gpt-5.6-terra is in `KNOWN_MODELS` and `PRICE_TABLE` ($2.20 / $13.20, Retail Prices API, checked 2026-10-29).
