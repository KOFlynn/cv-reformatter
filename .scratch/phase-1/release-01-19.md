# Phase 1 release 01–19

Phase 1 is the end-to-end lifecycle: a CV through `parse` → `label` → `verify` → `transform` → `render`, behind an eval gate in CI, deployed to Azure Container Apps through OIDC, with a demo PR the gate stops. Nineteen tickets from 2026-09-21 to 2026-10-06, all on `main` by pull request. The last, ticket 16, lands with ticket 14's close in #36, the one merge to `main` this release still needs.

## Review before merging #36

These need the maintainer. None of them needs history rewritten.

- **The live endpoint is public, and `/reformat` calls the paid model.** The app's URL is in ticket 14's comments (and so in history) and in the logs of every deploy run. Once the repository is public anyone can find it and `POST /reformat`, each call about $0.07 on the app's own Anthropic key. Max replicas 1 bounds concurrency, not spend. Auth is outside the brief's scope, so the decision is the maintainer's: a spend limit on the Anthropic workspace that holds the app's key (the cheapest guard, no code), or accept the exposure for a demo, or remove ingress between demos. **Recommended: set the spend limit before going public.**
- **The Azure subscription, tenant and client ids are in public run logs.** `azure/login` echoes its inputs, so the step log of every deploy run prints all three (runs 37052388148, both attempts; 37056912371; 37065847534; 37066259507), and every future deploy will too. They are identifiers, not credentials: the federated credential trusts only this repository's `main`, and ADR-0010 already calls them identifiers rather than secrets. They are not in any file or commit. Options: accept (the ADR's position), or delete those runs' logs before going public (`gh api -X DELETE repos/KOFlynn/cv-reformatter/actions/runs/<id>/logs` per run) and accept that later runs print them, or mask them in the workflow (a code change, not made here).
- **The maintainer's own name and email** are in commits, `pyproject.toml`'s `authors` and the brief's owner line. Expected; listed so it is a choice, not a surprise.
- **One unit-test phone number is not a reserved one.** `+353 21 4270000` (a Cork number, in `tests/eval/test_pii_leak.py` and `tests/eval/test_removal_precision.py`, history since Phase 0 ticket 08) is a format example with no name attached; every Candidate number is a `555` number. It may be someone's real line. Replacing it in the working tree is a small test-only change; history keeps it either way.
- **Branch protection is stated as fact in the README** (the demo section): true once step 2 below is done, which is before #36 merges.

## Phase 1 exit criteria (brief §10)

| Criterion | Evidence |
|---|---|
| parse, label (single pass, Anthropic), verify, transform, render, working on the golden set | `cvr.pipeline.reformat` ([#25](https://github.com/KOFlynn/cv-reformatter/pull/25)); the perfect oracle over all 48 documents in `tests/pipeline/`; the live, uncached eval on `main` after ticket 19 passed every gate ([run 37065847534](https://github.com/KOFlynn/cv-reformatter/actions/runs/37065847534)) |
| Unit tests for parse, verify, transform and render | [`tests/parse`](../../tests/parse), [`tests/verify`](../../tests/verify), [`tests/transform`](../../tests/transform), [`tests/render`](../../tests/render) ([#20](https://github.com/KOFlynn/cv-reformatter/pull/20), [#21](https://github.com/KOFlynn/cv-reformatter/pull/21), [#23](https://github.com/KOFlynn/cv-reformatter/pull/23)); 1248 default tests and 914 slow on [#36's run 37521015614](https://github.com/KOFlynn/cv-reformatter/actions/runs/37521015614) |
| Eval gate running in GitHub Actions, thresholds set from the baseline | the `eval` job of [`ci.yml`](../../.github/workflows/ci.yml), first through it [#29](https://github.com/KOFlynn/cv-reformatter/pull/29); [`eval/thresholds.yaml`](../../eval/thresholds.yaml) from [`eval/baseline-2026-09-29.json`](../../eval/baseline-2026-09-29.json) ([#27](https://github.com/KOFlynn/cv-reformatter/pull/27)) |
| Dockerfile; image runs locally under Docker Desktop | [`Dockerfile`](../../Dockerfile), `scripts/check-image.sh` passed on 2026-09-29 (325 MB, one real `/reformat`), [#27](https://github.com/KOFlynn/cv-reformatter/pull/27); repeated on every deploy against the anonymous pull |
| Deployed to Azure Container Apps through Actions with OIDC | the `deploy` job, [#30](https://github.com/KOFlynn/cv-reformatter/pull/30), [#31](https://github.com/KOFlynn/cv-reformatter/pull/31); [ADR-0010](../../docs/adr/0010-deployment.md); deploys [37052388148](https://github.com/KOFlynn/cv-reformatter/actions/runs/37052388148) (re-run) and [37066259507](https://github.com/KOFlynn/cv-reformatter/actions/runs/37066259507) |
| README written as an ADR (section 12) | [README](../../README.md) "Decisions" and its table of ADRs 0001–0010 ([#23](https://github.com/KOFlynn/cv-reformatter/pull/23), revised in #36) |
| Demo PR proven to block a deploy | [#32](https://github.com/KOFlynn/cv-reformatter/pull/32): `check` green, `eval` red, `deploy` skipped ([run 37061731804](https://github.com/KOFlynn/cv-reformatter/actions/runs/37061731804)); branch protection's blocked merge is step 3 below |

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
- **13 the CI eval gate** — [#29](https://github.com/KOFlynn/cv-reformatter/pull/29). Branch protection, its last box, is step 2 below.
- **14 provision and deploy through OIDC** — [#30](https://github.com/KOFlynn/cv-reformatter/pull/30), [#31](https://github.com/KOFlynn/cv-reformatter/pull/31), closed by #36 (the cost check).
- **15 the demo PR** — [#32](https://github.com/KOFlynn/cv-reformatter/pull/32) (never merged), evidence [#33](https://github.com/KOFlynn/cv-reformatter/pull/33). Box 5, the blocked merge button, is step 3 below.
- **19 a repeated item quoted once** — [#34](https://github.com/KOFlynn/cv-reformatter/pull/34), mark-done [#35](https://github.com/KOFlynn/cv-reformatter/pull/35). Prompt 1.3.0.
- **16 integrate, verify, go public** — #36: the CI split, the docs, this note, the readiness check.

## Post-review fixes

Each found by evidence after the ticket it fixes had merged.

- **17 `removal_precision` as a hard gate.** Ticket 09's first live run passed every gate yet removed c07's "EU citizen; no visa required for Ireland" under `RM_PERSONAL`: a logged removal counted as accounted for, so `dropped_tokens` could not see it. The metric now judges every removed slice against what its own rule may remove.
- **18 the `RM_PERSONAL` prompt scope (1.1.0).** The same finding, fixed at the cause: work authorisation is CV content; a referees heading goes under `RM_HEADING`.
- **19 a repeated item quoted once (1.3.0).** The one repeated miss in the baseline, a skill listed twice and quoted once. Version 1.3.0, not 1.2.0, because the demo branch already reports 1.2.0.
- **#31 the OIDC subject.** The first deploy failed `AADSTS700213`: this repository's tokens carry GitHub's immutable subject (owner and repo ids), not `repo:owner/name`. The wizard now asks GitHub for the prefix; ADR-0010 records why immutable is kept.
- **#36 no skipped `eval` on a pull request (ticket 16).** A push to a PR branch started a `push` run whose `eval` was skipped by its `if:`, beside the real one, and GitHub counts a skipped job as satisfying a required check. `ci.yml` (check, eval, deploy) now runs only on pull requests and pushes to `main`, with no `if:` on `eval`; `branch.yml` runs the identical `check` alone on every other branch. On #36: before, `9f82528` carried a skipped `eval` from push run 37520333534 beside the real one from 37520338239; after, `75df46b` carries one `eval`, from pull-request run 37521015614, and the push run 37521006232 (`Branch check`) has `check` alone.
- **#36 docs-only pushes run nothing.** A merge to `main` pays for an uncached eval (about $3.30) and a redeploy; a push of only `**/*.md`, `docs/**` or `.scratch/**` now runs no job. Pull requests stay unfiltered, since a required check skipped by a path filter never reports.

## Decisions

- 16 · CI split → `ci.yml` keeps the gate and the deploy (they must share a workflow, `deploy` `needs: eval`), `branch.yml` carries `check` for every other branch; the two `check` jobs are asserted identical by test rather than shared through a reusable workflow, whose check would be named `check / check` and change the required context (sub-agent).
- 16 · visibility, branch protection and the proof → left to the maintainer, with the commands below; nothing outward-facing was changed (orch).
- 16 · readiness findings → recorded, not fixed: each is a choice about exposure (spend limit, logs, ids), and none needs history rewritten (sub-agent).
- 14 · ticket 14 marked done inside #36 rather than by a separate mark-done PR, since merging was all that remained (maintainer).

## Public-readiness check (2026-10-06)

**Method.** `git fetch --all`; every blob reachable from every ref (`git rev-list --all --objects`, 1069 blobs over 353 commits, branches `main`, `demo/degraded-prompt`, `phase-1/14-cost-check`) dumped once: 976 text blobs as text and 93 `.docx` blobs unzipped to their XML. Commit authors, committers and messages over all refs. The CI logs of the last 20 runs on `main`, and the first attempt of 37052388148. The current tree's tracked files and `.gitignore`.

**Searched for:** the Azure subscription, tenant and client ids (read from `az account show` and the repository variables, never printed); `sk-ant-` keys; private-key blocks; GitHub tokens (`ghp_`, `gho_`, `ghs_`, `ghu_`, `github_pat_`); Azure connection strings and client secrets; AWS keys; every GUID; `.env*`, `.cache/`, `eval/report.*`, key and certificate files ever committed; every email domain; phone numbers; `.docx` metadata (`dc:creator`, `cp:lastModifiedBy`); the maintainer's name and Windows username.

**Results.**
- No key, token, private key, connection string or client secret anywhere in history or in any CI log (the Anthropic key is a masked secret).
- The Azure ids appear in **no file or commit**; they are in the `azure/login` input echo of the deploy run logs (see Review, above).
- No `.env`, cache, report, key or certificate file was ever committed. `.gitignore` covers `.env`, `.env.*`, `.cache/` and `eval/report.*`.
- One GUID in history, `EF278816-EC6F-A645-907D-7F25AECB1D4A`: python-docx's default-template `customXml` item id, in two early `.docx` blobs. Not ours.
- `.docx` metadata: `cvr golden generator` (91 blobs) or python-docx's defaults (2). No personal name.
- Emails: `example.*` and `*-fictional.example.com` domains, `domain.tld`, and the maintainer's own address (commits, `pyproject.toml`).
- Phones: every Candidate number is a `555` number, plus `+44 7700 900412` (Ofcom's drama range), and the one Cork test number above.
- Names: the twelve Candidates are invented and were reviewed by the maintainer in Phase 0; institutions are real by design (ADR-0002); employers are invented. The maintainer's name is in the brief and the specs as owner.
- The live app URL is in ticket 14 and the deploy logs (see Review, above).

## Maintainer steps, in order

1. **Decide the Review items**, then make the repository public:
   ```
   gh repo edit KOFlynn/cv-reformatter --visibility public --accept-visibility-change-consequences
   ```
2. **Branch protection on `main`** requiring `check` and `eval` (ticket 13's command), and record the output in ticket 13 and #36:
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
3. **Prove it on #32**, which is already red, at no cost. Read, never merge:
   ```
   gh api repos/KOFlynn/cv-reformatter/pulls/32 --jq '{mergeable_state, draft}'
   gh pr view 32 --json mergeStateStatus,statusCheckRollup
   ```
   Expect `mergeable_state: "blocked"`. Caveat: #32's head commit predates the split, so beside its failed `eval` it still carries the skipped `eval` of its old push run, the very gap #36 closes. If GitHub reports it `blocked`, that is the proof. If not, the failed `eval` alone is not enough while the skipped one stands, and the proof needs a fresh run on #32 under the new workflow: an empty commit pushed to `demo/degraded-prompt` after #36 merges (`git commit --allow-empty -m "Re-run the gate under the split workflow"`), which runs its eval live, about $3.30, since a failing run's answers are never cached. Take a screenshot of the disabled merge button for ticket 15 box 5 either way.
4. **Merge #36.** It changes `ci.yml` and tests, so its push to `main` runs the full uncached eval (about $3.30, four minutes) and redeploys: the one paid run of this release. Then delete the branch, and tick ticket 13's and 15's last boxes and ticket 16's remaining boxes in one mark-done PR (docs only, so it runs nothing on `main`).

## Run log

- 2026-10-06 ticket 16 implemented on `phase-1/14-cost-check` (#36) by a sub-agent: CI split, docs, brief §10, readiness check, this note. PR eval on #36 cached: 48 hits, $0.00.
- 2026-10-06 ticket 14 cost check, €0.00; docs-only `paths-ignore` (#36).
- 2026-10-02 #34 and #35 merged; `main`'s uncached eval and deploy passed (37065847534, 37066259507).
- 2026-10-02 #33's push to `main` failed `eval`: the Anthropic account was out of credit (`LabellerMisconfigured`, "credit balance is too low"), not a gate failure; `deploy` was skipped. Credit restored before #34.
- 2026-10-02 #30, #31 merged; first deploy failed on the OIDC subject, re-run green after the federated credential was fixed.
- 2026-09-30 #27, #28, #29 merged; the first PR through the gate went green at $3.28.
- 2026-09-24 #21–#26 merged.
- 2026-09-21 #19, #20 merged.
