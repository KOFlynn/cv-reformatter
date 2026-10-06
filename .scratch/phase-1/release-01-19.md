# Phase 1 release 01–19

Phase 1 is the end-to-end lifecycle: a CV through `parse` → `label` → `verify` → `transform` → `render`, behind an eval gate in CI, deployed to Azure Container Apps through OIDC, with a demo PR the gate stops. Nineteen tickets from 2026-09-21 to 2026-10-06, all on `main` by pull request. The last, ticket 16, lands with ticket 14's close in #36, the one merge to `main` this release still needs.

## Review before merging #36: the decisions

The readiness check (below) raised four exposures. The maintainer decided each on 2026-10-06; none needed history rewritten.

- **The live endpoint: closed by default and keyed.** The app's URL is in ticket 14's comments, so in public history, and `/reformat` calls the paid model. A spend limit alone would only cap the damage, and any request through ingress wakes the app whatever its answer. So `/reformat` now needs the `X-API-Key` header (401 without it, before the body is read or the model called; a closed 503 if the app has no `CVR_API_KEY`; uploads capped at 5 MB, 413), and the app's ingress is **off by default**: disabled on 2026-10-06 (the settings were external, port 8000, transport Auto, and `demo.sh up` restores them). The deploy job opens it for its smoke test and always closes it after; `sh scripts/demo.sh up` / `down` opens and closes it for a demo. While it is open, wake-ups are bounded by max replicas 1. How demos open it is to be revisited when a later phase plans them. A spend limit on the Anthropic workspace stays an optional backstop.
- **The Azure ids in run logs: masked.** They are identifiers, not credentials, but publishing them served no purpose. `azure/login` echoed them because they were repository variables; they are now repository secrets, so GitHub masks them, and every `az` call runs with `--output none` or a narrow `--query`. Once #36's deploy shows them masked, the logs (not the runs, which this note cites as evidence) of runs 37052388148 (both attempts), 37056912371, 37065847534 and 37066259507 are deleted.
- **The maintainer's email: no-reply from now on.** Commits from 2026-10-06 use `6141875+KOFlynn@users.noreply.github.com`, "Keep my email addresses private" is on, and `pyproject.toml`'s author email is the no-reply address. History keeps the old address: GitHub keeps every pull request's commits under its PR refs, so rewriting `main` would not remove it.
- **The phone numbers: accepted as they are.** `+353 21 4270000` in two eval tests and the Candidates' `555` numbers may be real lines: `555` is reserved for fiction only in North America, not in Ireland. Every value is attached only to fictional people, and the maintainer judged the risk negligible.
- **Branch protection is stated as fact in the README** (the demo section): true since step 5 below, done on 2026-10-06 before #36 merges.

## Phase 1 exit criteria (brief §10)

| Criterion | Evidence |
|---|---|
| parse, label (single pass, Anthropic), verify, transform, render, working on the golden set | `cvr.pipeline.reformat` ([#25](https://github.com/KOFlynn/cv-reformatter/pull/25)); the perfect oracle over all 48 documents in `tests/pipeline/`; the live, uncached eval on `main` after ticket 19 passed every gate ([run 37065847534](https://github.com/KOFlynn/cv-reformatter/actions/runs/37065847534)) |
| Unit tests for parse, verify, transform and render | [`tests/parse`](../../tests/parse), [`tests/verify`](../../tests/verify), [`tests/transform`](../../tests/transform), [`tests/render`](../../tests/render) ([#20](https://github.com/KOFlynn/cv-reformatter/pull/20), [#21](https://github.com/KOFlynn/cv-reformatter/pull/21), [#23](https://github.com/KOFlynn/cv-reformatter/pull/23)); 1248 default tests and 914 slow on [#36's run 37521015614](https://github.com/KOFlynn/cv-reformatter/actions/runs/37521015614) |
| Eval gate running in GitHub Actions, thresholds set from the baseline | the `eval` job of [`ci.yml`](../../.github/workflows/ci.yml), first through it [#29](https://github.com/KOFlynn/cv-reformatter/pull/29); [`eval/thresholds.yaml`](../../eval/thresholds.yaml) from [`eval/baseline-2026-09-29.json`](../../eval/baseline-2026-09-29.json) ([#27](https://github.com/KOFlynn/cv-reformatter/pull/27)) |
| Dockerfile; image runs locally under Docker Desktop | [`Dockerfile`](../../Dockerfile), `scripts/check-image.sh` passed on 2026-09-29 (325 MB, one real `/reformat`), [#27](https://github.com/KOFlynn/cv-reformatter/pull/27); repeated on every deploy against the anonymous pull |
| Deployed to Azure Container Apps through Actions with OIDC | the `deploy` job, [#30](https://github.com/KOFlynn/cv-reformatter/pull/30), [#31](https://github.com/KOFlynn/cv-reformatter/pull/31); [ADR-0010](../../docs/adr/0010-deployment.md); deploys [37052388148](https://github.com/KOFlynn/cv-reformatter/actions/runs/37052388148) (re-run) and [37066259507](https://github.com/KOFlynn/cv-reformatter/actions/runs/37066259507) |
| README written as an ADR (section 12) | [README](../../README.md) "Decisions" and its table of ADRs 0001–0010 ([#23](https://github.com/KOFlynn/cv-reformatter/pull/23), revised in #36) |
| Demo PR proven to block a deploy | [#32](https://github.com/KOFlynn/cv-reformatter/pull/32): `check` green, `eval` red, `deploy` skipped ([run 37061731804](https://github.com/KOFlynn/cv-reformatter/actions/runs/37061731804)); protection's blocked merge on the throwaway [#37](https://github.com/KOFlynn/cv-reformatter/pull/37) (`eval` red, [run 37535330217](https://github.com/KOFlynn/cv-reformatter/actions/runs/37535330217), `BLOCKED`), since #32 now conflicts with `main` (step 6 below) |

## The numbers

| | |
|---|---|
| Golden set | 12 Candidates × 4 Layouts = 48 documents |
| Baseline (prompt 1.1.0, 3 runs, $9.80) | every hard gate held; tunable precision 99.91–100%, recall 99.65–99.82%; appendix 0.73–0.76% |
| Thresholds | tunable placement ≥ 98%, appendix ≤ 2%, punctuation fidelity hard |
| Prompt 1.3.0 (ticket 19) | every hard gate held; tunable 100/100 (1128 of 1128); appendix 0.70%; $3.31 |
| One full uncached eval | about $3.30 and four minutes |
| One document | about $0.07 (5,386 tokens in, 2,439 out on the first smoke test) |
| Image | 325 MB |
| Cold start / warm | 25.9 s / 0.19 s |
| Azure cost, 2026-10-01 to 2026-10-06 | €0.00 (0.4 MB of log ingestion, no Container Apps usage billed) |
| Demo PR | `pii_leak` 56 values on 12 of 12 Candidates; tunable precision 85.67%; three local `--no-cache` runs all red ($10.06) |
| Tests | 1248 default + 914 slow, 1 skipped (the spike test without a key) |

## Per-ticket summary

- **Spec** — [#19](https://github.com/KOFlynn/cv-reformatter/pull/19): the Phase 1 spec, ticket sequence and glossary.
- **01 text foundations and the c07 fixture, 02 parse, 03 verify** — [#20](https://github.com/KOFlynn/cv-reformatter/pull/20). `parse` into addressed `SourceBlock`s (text boxes through lxml); `verify` through a per-block claim ledger (ADR-0008).
- **04 transform, 07 the real labeller** — [#21](https://github.com/KOFlynn/cv-reformatter/pull/21), mark-done [#22](https://github.com/KOFlynn/cv-reformatter/pull/22). Dates, ordering and the multi-span log; `RealLabeller` through LangChain's structured output (ADR-0009), prompt and schema versions pinned by hash.
- **05 render and the adapter, 08 README as ADR** — [#23](https://github.com/KOFlynn/cv-reformatter/pull/23), mark-done [#24](https://github.com/KOFlynn/cv-reformatter/pull/24).
- **06 the pipeline function with oracle labellers** — [#25](https://github.com/KOFlynn/cv-reformatter/pull/25), mark-done [#26](https://github.com/KOFlynn/cv-reformatter/pull/26).
- **09 eval runner, 10 baseline and thresholds, 11 the API, 12 the image, 17 removal precision, 18 the `RM_PERSONAL` prompt scope** — [#27](https://github.com/KOFlynn/cv-reformatter/pull/27), mark-done [#28](https://github.com/KOFlynn/cv-reformatter/pull/28).
- **13 the CI eval gate** — [#29](https://github.com/KOFlynn/cv-reformatter/pull/29). Branch protection, its last box, was set on 2026-10-06 (step 5 below).
- **14 provision and deploy through OIDC** — [#30](https://github.com/KOFlynn/cv-reformatter/pull/30), [#31](https://github.com/KOFlynn/cv-reformatter/pull/31), closed by #36 (the cost check).
- **15 the demo PR** — [#32](https://github.com/KOFlynn/cv-reformatter/pull/32) (never merged), evidence [#33](https://github.com/KOFlynn/cv-reformatter/pull/33). Box 5, the blocked merge button, was shown on #37 (step 6 below).
- **19 a repeated item quoted once** — [#34](https://github.com/KOFlynn/cv-reformatter/pull/34), mark-done [#35](https://github.com/KOFlynn/cv-reformatter/pull/35). Prompt 1.3.0.
- **16 integrate, verify, go public** — #36: the CI split, the docs, this note, the readiness check; public and protected on 2026-10-06, proven on the throwaway [#37](https://github.com/KOFlynn/cv-reformatter/pull/37). Tickets 13, 14, 15 and 16 are marked done inside #36.

## Post-review fixes

Each found by evidence after the ticket it fixes had merged.

- **17 `removal_precision` as a hard gate.** Ticket 09's first live run passed every gate yet removed c07's "EU citizen; no visa required for Ireland" under `RM_PERSONAL`: a logged removal counted as accounted for, so `dropped_tokens` could not see it. The metric now judges every removed slice against what its own rule may remove.
- **18 the `RM_PERSONAL` prompt scope (1.1.0).** The same finding, fixed at the cause: work authorisation is CV content; a referees heading goes under `RM_HEADING`.
- **19 a repeated item quoted once (1.3.0).** The one repeated miss in the baseline, a skill listed twice and quoted once. Version 1.3.0, not 1.2.0, because the demo branch already reports 1.2.0.
- **#31 the OIDC subject.** The first deploy failed `AADSTS700213`: this repository's tokens carry GitHub's immutable subject (owner and repo ids), not `repo:owner/name`. The wizard now asks GitHub for the prefix; ADR-0010 records why immutable is kept.
- **#36 no skipped `eval` on a pull request (ticket 16).** A push to a PR branch started a `push` run whose `eval` was skipped by its `if:`, beside the real one, and GitHub counts a skipped job as satisfying a required check. `ci.yml` (check, eval, deploy) now runs only on pull requests and pushes to `main`, with no `if:` on `eval`; `branch.yml` runs the identical `check` alone on every other branch. On #36: before, `9f82528` carried a skipped `eval` from push run 37520333534 beside the real one from 37520338239; after, `75df46b` carries one `eval`, from pull-request run 37521015614, and the push run 37521006232 (`Branch check`) has `check` alone.
- **#36 docs-only pushes run nothing.** A merge to `main` pays for an uncached eval (about $3.30) and a redeploy; a push of only `**/*.md`, `docs/**` or `.scratch/**` now runs no job. Pull requests stay unfiltered, since a required check skipped by a path filter never reports.
- **#36 the endpoint and the logs (ticket 16).** The readiness check found the live URL in history with an unauthenticated, paid `/reformat`, and the Azure ids echoed in deploy logs. `/reformat` now needs `X-API-Key` and caps uploads at 5 MB; ingress is off by default, opened by the deploy only for its smoke test and by `scripts/demo.sh` for demos; the ids are masked secrets; the wizard sets the API key and leaves ingress closed. ADR-0010 is amended.

## Decisions

- 16 · CI split → `ci.yml` keeps the gate and the deploy (they must share a workflow, `deploy` `needs: eval`), `branch.yml` carries `check` for every other branch; the two `check` jobs are asserted identical by test rather than shared through a reusable workflow, whose check would be named `check / check` and change the required context (sub-agent).
- 16 · visibility, branch protection and the proof → run on the maintainer's approval, step by step (orch); `enforce_admins` on, so the block holds for admins too (maintainer).
- 16 · the proof → a throwaway PR (#37) rather than #32, which conflicts with `main`; its two threshold-pinning tests edited in #37 only, stated in its description, since it is never merged (maintainer).
- 16 · readiness findings → recorded, not fixed: each is a choice about exposure (spend limit, logs, ids), and none needs history rewritten (sub-agent).
- 14 · ticket 14 marked done inside #36 rather than by a separate mark-done PR, since merging was all that remained (maintainer).
- 16 · the live endpoint → an API key on `/reformat` plus ingress off by default, not a spend limit alone, which only caps the damage; no nightly auto-off job, revisit when demos are planned (maintainer).
- 16 · the Azure ids → repository secrets for masking, reversing ADR-0010's "variables, never secrets"; the logs of the five old deploy runs deleted, the runs kept as evidence (maintainer).
- 16 · the phone numbers → accepted; the maintainer's email → no-reply from now on, history left as it is (maintainer).
- 16 · the work split across two sub-agents in their own worktrees (API; CI and Azure) and a docs pass, merged into #36 (orch).

## Public-readiness check (2026-10-06)

**Method.** `git fetch --all`; every blob reachable from every ref (`git rev-list --all --objects`, 1069 blobs over 353 commits, branches `main`, `demo/degraded-prompt`, `phase-1/14-cost-check`) dumped once: 976 text blobs as text and 93 `.docx` blobs unzipped to their XML. Commit authors, committers and messages over all refs. The CI logs of the last 20 runs on `main`, and the first attempt of 37052388148. The current tree's tracked files and `.gitignore`.

**Searched for:** the Azure subscription, tenant and client ids (read from `az account show` and the repository variables, never printed); `sk-ant-` keys; private-key blocks; GitHub tokens (`ghp_`, `gho_`, `ghs_`, `ghu_`, `github_pat_`); Azure connection strings and client secrets; AWS keys; every GUID; `.env*`, `.cache/`, `eval/report.*`, key and certificate files ever committed; every email domain; phone numbers; `.docx` metadata (`dc:creator`, `cp:lastModifiedBy`); the maintainer's name and Windows username.

**Results.**
- No key, token, private key, connection string or client secret anywhere in history or in any CI log (the Anthropic key is a masked secret).
- The Azure ids appear in **no file or commit**; they were in the `azure/login` input echo of the deploy run logs, now masked (see Review, above).
- No `.env`, cache, report, key or certificate file was ever committed. `.gitignore` covers `.env`, `.env.*`, `.cache/` and `eval/report.*`.
- One GUID in history, `EF278816-EC6F-A645-907D-7F25AECB1D4A`: python-docx's default-template `customXml` item id, in two early `.docx` blobs. Not ours.
- `.docx` metadata: `cvr golden generator` (91 blobs) or python-docx's defaults (2). No personal name.
- Emails: `example.*` and `*-fictional.example.com` domains, `domain.tld`, and the maintainer's own address (commits, `pyproject.toml`).
- Phones: every Candidate number is a `555` number, plus `+44 7700 900412` (Ofcom's drama range), and the one Cork test number above, all accepted (see Review, above).
- Names: the twelve Candidates are invented and were reviewed by the maintainer in Phase 0; institutions are real by design (ADR-0002); employers are invented. The maintainer's name is in the brief and the specs as owner.
- The live app URL is in ticket 14 and the deploy logs; ingress is now off by default and `/reformat` keyed (see Review, above).

## Maintainer steps, in order

Steps 1–7 are done (2026-10-06); steps 8 and 9 follow the merge. Steps 1 and 2 had to be done before #36 merges, or its deploy fails at `azure/login` and at the smoke test.

1. **Done. Move the three ids from variables to secrets.** `gh variable list` now shows only `AZURE_CONTAINER_APP` and `AZURE_RESOURCE_GROUP`.
   ```
   for n in AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID; do gh variable get "$n" | tr -d '\r\n' | gh secret set "$n"; done
   gh secret list
   for n in AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID; do gh variable delete "$n"; done
   ```
2. **Done. Create the API key** (secret `cvr-api-key`, env `CVR_API_KEY=secretref:cvr-api-key` on revision `cvr-ca--0000005`, ingress still off; GitHub secret `CVR_API_KEY`) and set it in the app and in GitHub, never printed. The env var makes a new revision of the current image, which ignores it until #36 deploys:
   ```
   key=$(openssl rand -hex 32)
   az containerapp secret set -n cvr-ca -g cvr-rg --secrets "cvr-api-key=$key" -o none
   az containerapp update -n cvr-ca -g cvr-rg --set-env-vars CVR_API_KEY=secretref:cvr-api-key -o none
   printf '%s' "$key" | gh secret set CVR_API_KEY
   unset key
   ```
   For a demo, read it with `az containerapp secret show -n cvr-ca -g cvr-rg --secret-name cvr-api-key --query value -o tsv`.
3. **Done. The image check with a real `/reformat`:** 325 MB, uid 10001, no key in history or filesystem, 401 without the key, 200 and 39,164 bytes with it on prompt 1.3.0, $0.0702.
   ```
   ANTHROPIC_API_KEY=... sh scripts/check-image.sh
   ```
4. **Done. Make the repository public** (`{"visibility":"PUBLIC"}`):
   ```
   gh repo edit KOFlynn/cv-reformatter --visibility public --accept-visibility-change-consequences
   ```
5. **Done. Branch protection on `main`** requiring `check` and `eval` (ticket 13's command), then `enforce_admins` on (`gh api --method POST repos/KOFlynn/cv-reformatter/branches/main/protection/enforce_admins`); result `{"enforce_admins":true,"required_checks":["check","eval"],"strict":false}`, recorded in tickets 13 and 16 and on #36:
   ```
   gh api --method PUT repos/KOFlynn/cv-reformatter/branches/main/protection --input - <<'JSON'
   {
     "required_status_checks": {"strict": false, "contexts": ["check", "eval"]},
     "enforce_admins": false,
     "required_pull_request_reviews": null,
     "restrictions": null
   }
   JSON
   gh api repos/KOFlynn/cv-reformatter/branches/main/protection/required_status_checks
   ```
6. **Done, on #37 instead of #32.** #32 returned `dirty`: it conflicts with `main` since ticket 19 changed `prompt.md`, and still carries a pre-split skipped `eval`; rebasing would re-run it live (about $3.30), so it is left as it is. The throwaway [#37](https://github.com/KOFlynn/cv-reformatter/pull/37), branched from #36 with `appendix_rate.max` 0.5 (and its two threshold-pinning tests edited, in #37 only), went `check` green, `eval` red ("appendix_rate: 0.70% above the maximum 0.5% (c09, c11)", [run 37535330217](https://github.com/KOFlynn/cv-reformatter/actions/runs/37535330217), cached, $0), `deploy` skipped, merge state `BLOCKED`; closed, never merged, branch deleted. The commands as first planned:
   ```
   gh api repos/KOFlynn/cv-reformatter/pulls/32 --jq '{mergeable_state, draft}'
   gh pr view 32 --json mergeStateStatus,statusCheckRollup
   ```
   It returned `dirty`, not `blocked`, for the reasons above, so the proof moved to #37 and the empty-commit fallback (a live re-run of #32, about $3.30) was not needed.
7. **Done. Record the evidence and mark tickets 13, 15 and 16 done on #36** (docs only; the PR's eval replays from the cache, $0.00).
8. **Remaining: merge #36.** It changes code, `ci.yml` and tests, so its push to `main` runs the full uncached eval (about $3.30, four minutes) and redeploys, opening ingress for the smoke test and closing it after: the one paid run of this release. Then delete the branch.
9. **Remaining: check the masking, then delete the old logs.** In the deploy job's `Log in to Azure (OIDC)` step the three ids must show as `***`. Then:
   ```
   for id in 37052388148 37056912371 37065847534 37066259507; do gh api -X DELETE repos/KOFlynn/cv-reformatter/actions/runs/$id/logs; done
   gh run view 37052388148 --attempt 1 --log | head -3   # expect no log
   ```

## Run log

- 2026-10-06 maintainer steps 1–7: ids to secrets, API key set, keyed image check passed ($0.07), repository public, branch protection with `enforce_admins`, the blocked merge proven on the throwaway #37 at $0, tickets 13, 15 and 16 done on #36.
- 2026-10-06 the readiness decisions (#36): `/reformat` keyed and capped, ingress disabled on `cvr-ca` and off by default, the Azure ids masked secrets, `demo.sh`; two sub-agents and a docs pass. The keyless `check-image.sh` passed locally, 401 included, after a fix for Git Bash's curl and `/dev/null`.
- 2026-10-06 ticket 16 implemented on `phase-1/14-cost-check` (#36) by a sub-agent: CI split, docs, brief §10, readiness check, this note. PR eval on #36 cached: 48 hits, $0.00.
- 2026-10-06 ticket 14 cost check, €0.00; docs-only `paths-ignore` (#36).
- 2026-10-02 #34 and #35 merged; `main`'s uncached eval and deploy passed (37065847534, 37066259507).
- 2026-10-02 #33's push to `main` failed `eval`: the Anthropic account was out of credit (`LabellerMisconfigured`, "credit balance is too low"), not a gate failure; `deploy` was skipped. Credit restored before #34.
- 2026-10-02 #30, #31 merged; first deploy failed on the OIDC subject, re-run green after the federated credential was fixed.
- 2026-09-30 #27, #28, #29 merged; the first PR through the gate went green at $3.28.
- 2026-09-24 #21–#26 merged.
- 2026-09-21 #19, #20 merged.
