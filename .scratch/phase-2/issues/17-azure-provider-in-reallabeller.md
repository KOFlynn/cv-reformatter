# 17: The Azure provider in RealLabeller

**What to build:** `RealLabeller` can label through Azure OpenAI, selected by configuration (`CVR_LABEL_*`) with no code change. The `azure_openai` provider's arguments (deployment, endpoint, API version, a token provider built from the default Azure credential with the scope found in ticket 01) are isolated, as the Anthropic ones are, and no key path exists. The price table gains gpt-5.4 at Data Zone prices, checked on the day. An offline test checks the `Labelling` and `Additions` schemas against Azure's strict-mode limits.

**Blocked by:** 01, 12

**Status:** ready-for-agent

- [ ] `langchain-openai` and `azure-identity` added; the lock file updated
- [ ] Over fakes: an Azure config yields the expected chat-model arguments, a token provider and never a key; a config with a key is refused as misconfigured (tested)
- [ ] Every configured model has a price, and the test fails loudly for one that does not; cached-input pricing is included if caching is used
- [ ] The schema check covers: every field required, no additional properties, nesting depth, unsupported keywords, root not `anyOf`. If either schema fails it, the fix bumps the schema version and an eval on the deployed provider is shown
- [ ] The image check is run and pasted; the runtime-import test still holds
- [ ] The spike test for the real model gains an Azure counterpart, skipped without Azure configuration
