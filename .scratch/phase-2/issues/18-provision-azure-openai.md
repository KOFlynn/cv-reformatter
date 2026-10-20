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
- [ ] The wizard's static test covers the step; values the wizard remembers stay in the gitignored env file
- [ ] The account and deployment names are recorded in CLAUDE.md's deployment entry
- [ ] No idle cost: the maintainer checks the cost a few days later, noted on the ticket
