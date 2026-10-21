# 01: Azure read-only fact spike

**What to build:** a recorded answer to the facts the Azure tickets depend on. Every one comes from read-only `az` queries (or docs, where no query exists), run by the maintainer in Git Bash. Nothing is created or changed. The answers are written under `## Answer` on this ticket, each with its command or source. If `cvr_sub` has zero quota for OpenAI models, the ticket stops there and reports, so the maintainer can decide between a quota request and recording the path as blocked.

**Blocked by:** None (can start immediately)

**Status:** in-progress (docs researched; waiting on the maintainer's read-only run)

- [ ] `cvr_sub`'s offer type (Free Trial, Pay-As-You-Go, …) and its Azure OpenAI quota tier recorded
- [ ] Available Data Zone Standard (EU) quota for gpt-5.4 recorded, and whether a deployment from a `northeurope` resource is possible
- [ ] The exact gpt-5.4 model identifier and version checked against the current Azure docs (the spec's name is not taken on trust)
- [ ] The managed identity token scope the service currently requires (`https://cognitiveservices.azure.com/.default` or `https://ai.azure.com/.default`) confirmed from Microsoft docs
- [ ] The minimum retention `cvr-log` can be set to recorded, at workspace level and per table, with a source
- [ ] The commands are given as a short read-only snippet the maintainer can paste; no secret or id is committed
- [ ] Each fact in the spec's Further Notes that this ticket settles is marked as settled in the answer

## Answer

Researched 2026-10-21 from Microsoft Learn. Nothing was run against Azure.

### Facts from the docs (settled)

- **Model identifier and version.** `gpt-5.4`, version `2026-03-05` (also `gpt-5.4-pro` 2026-03-05, `gpt-5.4-mini` and `gpt-5.4-nano` 2026-03-17). Supports structured outputs, Chat Completions and Responses APIs, 1,050,000 context, 128,000 max output. The Azure deployment name is free; the model name and version are what the deployment pins. Source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure (page updated 2026-10-08, section GPT-5.4).
- **Data Zone Standard (EU) in northeurope.** The region availability page lists `gpt-5.4` 2026-03-05 as available on Data Zone Standard in every EU region of its Europe table, `northeurope` included (columns francecentral, germanywestcentral, italynorth, northeurope, norwayeast, polandcentral, spaincentral, swedencentral, switzerlandnorth, westeurope). It is also on Global Standard in northeurope. SKU names: `DataZoneStandard`, `GlobalStandard`. Source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability (updated 2026-10-19; sections Data Zone Standard and Global Standard, Europe tabs). Caveat: Q&A threads from April and July 2026 report mini/nano greyed out for Data Zone Standard in EU regions (https://learn.microsoft.com/en-us/answers/questions/5868707/availability-timeline-for-gpt-5-4-mini-gpt-5-4-nan, https://learn.microsoft.com/en-us/answers/questions/5949072/clarification-needed-gpt-data-zone-standard-deploy), so the doc table is necessary but not sufficient: the quota query below is what proves it for `cvr_sub`. Deployment-type background: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types.
- **Managed identity token scope.** Microsoft's current managed identity guide (updated 2026-08-04) uses `https://ai.azure.com/.default` with the `/openai/v1/` endpoint, for both `DefaultAzureCredential` and `ManagedIdentityCredential`, and `--resource https://ai.azure.com` for `az account get-access-token`. It needs a custom subdomain on the resource (401 otherwise) and the role Cognitive Services OpenAI User on the resource (up to five minutes to propagate). Older and third-party samples still use `https://cognitiveservices.azure.com/.default` (e.g. https://learn.microsoft.com/en-us/azure/developer/ai/how-to/switching-endpoints), so both appear in Microsoft's samples. Decision for the implementing ticket: use `https://ai.azure.com/.default` as documented, and let the live managed identity proof confirm it (fall back to the cognitiveservices scope only if it returns 401). Source: https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/managed-identity.
- **Log Analytics minimum retention.** Analytics tables can be set as low as 4 days, by API or CLI; 31 days are included in the ingestion price, so going below 31 saves nothing. Workspace level: set with `az monitor log-analytics workspace update --retention-time`; the page states no workspace minimum other than the 4 day table minimum, so the maintainer's query and the ticket that lowers it confirm what `cvr-log` accepts. Per table: `retentionInDays` 4 to 730 and `totalRetentionInDays` 4 to 4,383 (CLI `--total-retention-time` up to 2,556); -1 inherits the workspace. Basic and Auxiliary plan tables have only total retention (default 30). Shortening a table's total retention is applied after a 30 day wait. A 30 day workspace may keep data for 31 days unless `immediatePurgeDataOn30Days` is true. Source: https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-configure. `scripts/provision-azure.sh` creates `cvr-log` with `--retention-time 30`.

### Read-only snippet for the maintainer (Git Bash)

Only `show`, `list` and `rest GET` calls. `--query` prints just the needed fields; the subscription id stays in a shell variable and is never printed.

```bash
SUB=$(az account show --query id -o tsv)
az rest --method get --url "https://management.azure.com/subscriptions/$SUB?api-version=2022-12-01" --query "subscriptionPolicies.{quotaId:quotaId,spendingLimit:spendingLimit}" -o json
az cognitiveservices usage list -l northeurope --query "[?contains(name.value,'gpt-5.4')].{name:name.value,used:currentValue,limit:limit}" -o table
az cognitiveservices model list -l northeurope --query "[?model.name=='gpt-5.4'].{ver:model.version,skus:model.skus[].name}" -o json
az monitor log-analytics workspace show -g cvr-rg -n cvr-log --query "{sku:sku.name,retentionDays:retentionInDays}" -o json
az monitor log-analytics workspace table list -g cvr-rg --workspace-name cvr-log --query "[?contains(name,'ContainerApp')].{table:name,plan:plan,retentionDays:retentionInDays,totalDays:totalRetentionInDays}" -o table
```

Reading the results: `quotaId` starting `FreeTrial` means Free Trial (reported to have zero OpenAI quota); `PayAsYouGo`, `EnterpriseAgreement` or similar means paid. In the usage list, look for a row like `OpenAI.DataZoneStandard.gpt-5.4`: `limit` above 0 means quota exists. Zero everywhere means stop and report (quota request, or record the path as blocked). The model list shows whether `DataZoneStandard` is offered for `gpt-5.4` from a northeurope resource.

### Results (pending maintainer run)

| Item | Result |
|---|---|
| `cvr_sub` offer type (`quotaId`, `spendingLimit`) | pending maintainer run |
| OpenAI quota tier / `gpt-5.4` Data Zone Standard (EU) limit in northeurope | pending maintainer run |
| `gpt-5.4` offers `DataZoneStandard` from a northeurope resource (model list) | pending maintainer run |
| `cvr-log` workspace retention | pending maintainer run |
| `cvr-log` per-table retention (ContainerApp tables) | pending maintainer run |

### Spec Further Notes: what this settles

- Settled by docs: the exact gpt-5.4 identifier (`gpt-5.4`, `2026-03-05`); its Data Zone EU availability on paper, including northeurope (the quota query still confirms it for `cvr_sub`); the managed identity token scope as documented (`https://ai.azure.com/.default`, live proof in the managed identity ticket); the Log Analytics minimum retention (4 days per table; workspace-level value confirmed when the retention ticket lowers it).
- Still open, settled only by the maintainer's run: `cvr_sub`'s offer and quota tier, and the actual gpt-5.4 Data Zone Standard quota.
- Not touched by this ticket (stay in their own tickets): Langfuse SDK features and `uuid4().hex` as a trace id, the PR OIDC subject, both schemas against Azure's strict-mode limits.
- The Further Notes line on gpt-5.4 prices ($2.75 / $16.50 per million tokens on Data Zone) was not re-checked here.
