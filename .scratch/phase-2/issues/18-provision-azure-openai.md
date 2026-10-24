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

- 2026-10-24: Wizard stage 13 built in `scripts/provision-azure.sh` (the record stage is now 14) and covered by `tests/ci/test_provision_script.py`; not yet run live, so boxes 1, 2, 4 and 5 stay open. It registers `Microsoft.CognitiveServices`, stops with a quota message if the `OpenAI.DataZoneStandard.gpt-5.4` row is absent or 0, asks for capacity (default min(available, 500) thousand TPM, noting `max_completion_tokens` counts against TPM), creates or confirms the AIServices account (`cvr-aoai-<4 hex>`), disables key auth through `az resource update`, creates the deployment, enables the app's system-assigned identity and grants `Cognitive Services OpenAI User` on the account to it and to the signed-in maintainer, then reads back and fails loudly. Remembered in `.env.azure`: `AZURE_OPENAI_ACCOUNT`, `_DEPLOYMENT`, `_CAPACITY`, `_ENDPOINT`. The app's env is untouched (ticket 19). Role assignment needs Owner or User Access Administrator.
