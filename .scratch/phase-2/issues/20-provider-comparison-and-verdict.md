# 20: Provider comparison and verdict

**What to build:** the provider is chosen by numbers, following the **Model comparison** method from Phase 1.5. Three eval runs of gpt-5.4 (Data Zone EU) are set against three of Sonnet 5.5 at `medium`, on the same prompt and schema versions and the same golden set, retry included. The maintainer runs them locally with `az login`. The comparison is committed as a dated record beside the earlier one, and ADR-0015 records the verdict, its numbers, the Anthropic path's lack of an EU-only processing guarantee, and the rule that the comparison is re-run whenever the prompt, a schema or either model changes. The brief's §8 is amended: the gate runs the deployed provider, and the comparison record is where the other provider is judged.

**Blocked by:** 15, 17, 18

**Status:** done

- [x] The Sonnet side reuses existing runs only if they are on the same prompt and schema versions; otherwise three new runs, and the record says which
- [x] The record holds per-run gate results, metrics, retries, cost and wall time for both sides
- [x] ADR-0015 written; the brief's §8 amended and its §10 comparison box ticked
- [x] If Azure wins, ticket 21 is marked ready; if not, it is closed as not needed, with the reason

## Decisions made in preparation

- **The Sonnet side needs three new runs.** The Phase 1.5 comparison (`eval/model-comparison-2026-10-19.json`) is on prompt 1.3.0 and schema 1.0.0 with zero retries; its reports carry no retry versions at all, because the retry (tickets 11-15) did not exist. The retry prompt 1.0.0 (`1dc17179dfa3e638`) and additions schema 1.0.0 (`6f2720458f33bf3e`) are now part of every answer's identity and the retry edge changes what a run does (c09 and c11 fire retries in every Layout), so those runs are not the same configuration in any sense the aggregator can verify. The 2026-10-24 CI evals on `main` and PR #41 replayed first attempts from the cache, so their cost and wall time are not live either. The record must say "three new Sonnet runs, retry included".
- **gpt-5.4 is compared at `medium`.** The Azure provider accepts `low | medium | high | xhigh` (`AZURE_EFFORTS`; `max` is refused as `LabellerMisconfigured`). Sonnet is at `medium` (the deployed default, ADR-0011), so `medium` makes the sides differ in provider and model only, which is what the Model comparison method asks (Phase 1.5 noted Haiku at `high` as a confound). Raising gpt-5.4's effort is a follow-up only if it fails the gate at `medium`, and would be a second, labelled comparison.
- **The reference is the deployed provider** (Sonnet 5.5, `medium`), listed first; gpt-5.4 is the candidate.
- **The report now names the retry hashes.** `report.json` `versions` gained `retry_prompt` and `additions_schema` (hash only; absent for a labeller with no retry, so older reports and the oracle tests are unchanged). Without them the aggregator could not tell runs on different retry prompts apart.
- **`cvr.eval.compare`** folds the six `report.json` files into `eval/provider-comparison-<date>.json` in the shape of the Phase 1.5 record (per-run gate, totals, per-layout, tokens, cost, wall time, retry columns, cache; spread; gates passed; side cost). It refuses runs whose `versions` block, document set, thresholds or (within a side) configuration differ, and any run that replayed cached answers. It writes facts only: the notes, the verdict and the maintainer's decision are added by hand, as in the Phase 1.5 file.

## Maintainer runbook

Git Bash, repo root. About 30 minutes and about $15 in all (below). Do not skip `--no-cache`: a cached run costs nothing and is refused by the aggregator.

```bash
# 0. Sign in and check the subscription.
az login
az account show --query "{name:name, id:id}" -o table      # must be cvr_sub
# The endpoint provision-azure.sh stage 13 wrote to .env.azure once its read-back passed.
# Read it with sed; do not `source` the file. No resource group is needed.
ENDPOINT=$(sed -n 's/^AZURE_OPENAI_ENDPOINT=//p' .env.azure | tr -d '\r"')
# The deployed model and its deployment (stage 13 remembers the choice; gpt-5.4-mini unless it ran with gpt-5.4).
AZ_MODEL=$(sed -n 's/^AZURE_OPENAI_MODEL=//p' .env.azure | tr -d '\r"' | tail -n 1)
AZ_MODEL=${AZ_MODEL:-gpt-5.4-mini}
AZ_DEPLOYMENT=$(sed -n 's/^AZURE_OPENAI_DEPLOYMENT=//p' .env.azure | tr -d '\r"' | tail -n 1)
AZ_DEPLOYMENT=${AZ_DEPLOYMENT:-$AZ_MODEL}
[ -n "$ENDPOINT" ] || { echo "AZURE_OPENAI_ENDPOINT is empty: run stage 13 of provision-azure.sh first"; false; }
echo "$ENDPOINT"                                            # https://<name>.openai.azure.com/
# Your own user needs the role "Cognitive Services OpenAI User" on the account (the default
# Azure credential uses your az login here, the managed identity in Container Apps).

mkdir -p .cache/phase-2-comparison

# 1. The Azure model, three runs. --concurrency 2: the deployment is 200K TPM and Azure counts each
#    request's max_completion_tokens (32000) against it, so four in flight would hit 429s.
unset CVR_LABEL_EXTRA CVR_LABEL_TEMPERATURE ANTHROPIC_API_KEY
export CVR_LABEL_PROVIDER=azure_openai CVR_LABEL_MODEL="$AZ_MODEL" CVR_LABEL_EFFORT=medium
export CVR_LABEL_AZURE_ENDPOINT="$ENDPOINT" CVR_LABEL_AZURE_DEPLOYMENT="$AZ_DEPLOYMENT"
uv run python -m cvr.eval.run --candidate c04 --layout single-column --no-cache --concurrency 2   # smoke: one document, cents; check the config line in eval/report.md
for n in 1 2 3; do
  uv run python -m cvr.eval.run --no-cache --concurrency 2   # exit 1 on a gate breach is a result, not a fault
  cp eval/report.json .cache/phase-2-comparison/azure-$n.json
done

# 2. Sonnet 5.5 at medium, three runs. Unset every CVR_LABEL_* first (export only works in this shell).
unset CVR_LABEL_PROVIDER CVR_LABEL_MODEL CVR_LABEL_EFFORT CVR_LABEL_AZURE_ENDPOINT CVR_LABEL_AZURE_DEPLOYMENT
export ANTHROPIC_API_KEY=...                            # your key, this shell only
for n in 1 2 3; do
  uv run python -m cvr.eval.run --no-cache
  cp eval/report.json .cache/phase-2-comparison/sonnet-$n.json
done

# 3. The record. The first label is the reference (the deployed provider).
uv run python -m cvr.eval.compare \
  sonnet=.cache/phase-2-comparison/sonnet-1.json sonnet=.cache/phase-2-comparison/sonnet-2.json sonnet=.cache/phase-2-comparison/sonnet-3.json \
  "$AZ_MODEL"=.cache/phase-2-comparison/azure-1.json "$AZ_MODEL"=.cache/phase-2-comparison/azure-2.json "$AZ_MODEL"=.cache/phase-2-comparison/azure-3.json \
  --date "$(date +%F)" --out "eval/provider-comparison-$(date +%F).json"
```

Checks before trusting the numbers: the command prints `N of 3 runs passed` per side and refuses (exit 2, `refused: ...`) on any mismatch; each Azure report's config line must read `provider=azure_openai, model=<AZ_MODEL>, effort=medium` (gpt-5.4-mini unless stage 13 deployed gpt-5.4); `eval/report.md` for a failing Azure run names the metric and candidates, which belong in the notes. If a run dies on `ProviderUnavailable` or an Azure 429 after the runner's backoff, note it and repeat that run (a run that errored is a result for the gate, but a quota fault is not a model result). If every Azure call fails with 401 or 403, the role assignment or token scope is wrong (`CVR_LABEL_AZURE_SCOPE=https://cognitiveservices.azure.com/.default` is the documented fallback), which is ticket 19's territory, not a comparison result.

**Cost.** Sonnet: about $1.6 a run (the 2026-10-24 main eval was $1.59, the retry adds about $0.12 when its first attempts are live), so about $5 for three. gpt-5.4 at $2.75 in and $16.50 out per million tokens: input is the same 270,000 tokens a run ($0.74); output is unknown until the first run (reasoning tokens count as output; Sonnet's is about 105,000, which would be $1.74), so on the order of $2.5 to $3.5 a run, about $8 to $10 for three, plus a few cents for the smoke run. Total about $13 to $15. **Wall time:** Sonnet about 2.5 minutes a run (138 to 163 s in Phase 1.5); gpt-5.4 unknown, Azure rate limits may stretch it, so allow up to 10 minutes a run. Replace this estimate with the first Azure report's `tokens` once it exists.

After the runs: hand-write `notes` and `verdict` into the record as in the Phase 1.5 file, then ADR-0015 and the brief's §8 and §10 (not prepared here, they need the numbers).

## Comments

- 2026-10-24: Zero quota found, comparison model changed. The maintainer's live stage 13 stopped: `cvr_sub` has 0 interactive quota for gpt-5.4 everywhere (northeurope Global and Data Zone rows all 0.0). A read-only usage check across EU regions found the only EU Data Zone Standard chat model with quota is `OpenAI.DataZoneStandard.gpt-5.4-mini`, limit 200 (thousand TPM), in swedencentral, westeurope, germanywestcentral and francecentral (not northeurope). Decision: provision the account in swedencentral with a gpt-5.4-mini deployment (version 2026-03-17), so the comparison is **gpt-5.4-mini against Sonnet 5.5**, not gpt-5.4. Consequences for this runbook: the model and deployment are read from `.env.azure` (`AZURE_OPENAI_MODEL`, `AZURE_OPENAI_DEPLOYMENT`); the runs use `--concurrency 2` (200K TPM; the Azure `max_completion_tokens` is now 32000 because Azure's limiter counts it up front); gpt-5.4-mini is $0.825 in / $4.95 out per million tokens (Data Zone Standard, checked 2026-10-24), so about $0.7 a run on the same 270,000 input tokens and Sonnet-like output, about $2 for three, not the $8 to $10 in the cost paragraph below, which is for gpt-5.4. The record and ADR-0015 must say which Azure model was compared. Whether a smaller model passes the same gate at `medium` is itself the question.
- 2026-10-29: A Data Zone Standard quota request for gpt-5.6-terra (swedencentral, version 2026-07-09) was filed by the maintainer and refused 2026-10-29 (Sweden Central has no capacity to expand; Microsoft: resubmit with other regions or wait 30+ days). The comparison is **gpt-5.4-mini against Sonnet 5.5**. The model stays accepted by stage 13 and priced ($2.20 / $13.20 per million tokens) in case quota appears later; the record must say which model was compared.

- 2026-10-24: Prepared, not run (Azure is not provisioned until ticket 18 and ticket 19 proves the identity). Added `cvr.eval.compare` (`src/cvr/eval/compare.py`, `tests/eval/test_compare.py`) and the retry hashes in the report's `versions` (`tests/eval/run/test_report_versions.py`). Decided: the Sonnet side is three new runs (the Phase 1.5 reports predate the retry and carry no retry versions); gpt-5.4 at `medium` to match Sonnet. The runbook above is the maintainer's copy-paste. ADR-0015, the brief's §8 and §10 and the ticket's boxes are deliberately untouched.

- 2026-10-29: Done. Three new Sonnet runs and three gpt-5.4-mini runs, all live and uncached, aggregated by `cvr.eval.compare` into `eval/provider-comparison-2026-10-29.json` (notes and verdict by hand). Sonnet passed 3 of 3 (tunable 99.65/99.73, $1.71, about 138 s); gpt-5.4-mini failed 3 of 3 (6 to 9 wrongful removals a run, c04 RM_REFEREE and c07 RM_PERSONAL; tunable placement 43.89 to 44.42 against 98, only single-column passing; $1.03 to $1.05, about 425 s). Anthropic stays the deployed provider; ADR-0015 written, the brief section 8 amended and the section 10 comparison box ticked. Limitation: gpt-5.4 and gpt-5.6-terra could not be compared (no quota; the terra request was refused 2026-10-29). Ticket 21 closed as not needed.
