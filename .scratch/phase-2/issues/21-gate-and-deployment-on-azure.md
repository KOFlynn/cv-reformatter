# 21: (Only if Azure wins) Gate and deployment on Azure

> Conditional: this ticket is built only if ticket 20's verdict makes Azure OpenAI the **Deployed provider**. Otherwise it is closed as not needed.

**What to build:** the gate keeps testing what production runs. A separate Entra app, `cvr-github-eval`, holds only the inference role on the Azure OpenAI account, with federated subjects for pull requests and for `main` in the immutable format read from the customisation API. The `eval` job gains `id-token: write` and reaches Azure OpenAI with no key. The deployed app's configuration switches to the Azure provider. Fork pull requests still get no token and no secrets.

**Blocked by:** 20

**Status:** closed (not needed)

- [ ] The wizard creates the identity and its two federated credentials idempotently, with no Contributor role
- [ ] The workflow's static tests cover `id-token: write` on `eval` and the Azure login step
- [ ] A PR's eval runs on Azure OpenAI and passes; a push to `main` deploys with the Azure provider, and the smoke test passes
- [ ] ADR-0014 amended with the identity as built; CLAUDE.md's CI and deployment entries updated

## Comments

- 2026-10-29: Closed as not needed. Ticket 20 (ADR-0015, `eval/provider-comparison-2026-10-29.json`) kept Anthropic Sonnet 5.5 as the deployed provider: gpt-5.4-mini failed the gate in all three runs and the stronger Azure models had no quota. Reopen only if an Azure model passes a repeated comparison (ADR-0015, "What reopens the decision"); the design in ADR-0014 (a narrow eval identity, no key) stands for that case.
