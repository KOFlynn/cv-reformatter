# 01: Azure read-only fact spike

**What to build:** a recorded answer to the facts the Azure tickets depend on. Every one comes from read-only `az` queries (or docs, where no query exists), run by the maintainer in Git Bash. Nothing is created or changed. The answers are written under `## Answer` on this ticket, each with its command or source. If `cvr_sub` has zero quota for OpenAI models, the ticket stops there and reports, so the maintainer can decide between a quota request and recording the path as blocked.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `cvr_sub`'s offer type (Free Trial, Pay-As-You-Go, …) and its Azure OpenAI quota tier recorded
- [ ] Available Data Zone Standard (EU) quota for gpt-5.4 recorded, and whether a deployment from a `northeurope` resource is possible
- [ ] The exact gpt-5.4 model identifier and version checked against the current Azure docs (the spec's name is not taken on trust)
- [ ] The managed identity token scope the service currently requires (`https://cognitiveservices.azure.com/.default` or `https://ai.azure.com/.default`) confirmed from Microsoft docs
- [ ] The minimum retention `cvr-log` can be set to recorded, at workspace level and per table, with a source
- [ ] The commands are given as a short read-only snippet the maintainer can paste; no secret or id is committed
- [ ] Each fact in the spec's Further Notes that this ticket settles is marked as settled in the answer
