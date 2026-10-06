# 16: Integrate, verify, go public

**What to build:** Phase 1 declared done against the brief's §10 exit criteria, and the repo opened. Walk the seven criteria (pipeline on the golden set; unit tests for parse, verify, transform and render; eval gate in Actions with thresholds from the baseline; Dockerfile running locally; deployed through OIDC; README as ADR; demo PR proven to block a deploy) and record where each is evidenced. Revise the README with every number that now exists (baseline, thresholds, cost per run, image size, cold-start time) and its links to the demo PR, the baseline and the ten ADRs. Update `CLAUDE.md`'s project status and package list to describe Phase 1 as it is, and the Phase 2 outline as what comes next. Check the whole repo once more for anything that must not be public: no real names, no keys, no cache, no `.env`, no report with anything odd in it. Then make the repo public, and write the Phase 1 release note in the scratch area the way Phase 0's was written.

Going public also unlocks ticket 13's last box, branch protection on `main` requiring `check` and `eval` (unavailable on a private repo on the free plan; the `gh api` command is in ticket 13's comment). Before it is switched on, close the gap ticket 13's runs on #29 showed: a push to a PR branch starts a `push` run whose `eval` job is skipped by its `if:`, beside the `pull_request` run whose `eval` really runs, and both report a check named `eval` on the PR's head commit. GitHub counts a skipped job as satisfying a required check, so a PR whose real eval failed could still pass protection on the skipped one. The `push` run must not produce an `eval` check outside `main`, for example by splitting the eval into a workflow that triggers only on `pull_request` and on `push` to `main`, so that `check` still runs on every push as ticket 13 requires.

**Blocked by:** 08 (README as ADR), 15 (The demo PR)

**Status:** done

- [x] §10 Phase 1 checklist with a link per item (test file, workflow run, PR, ADR) in the release note
- [x] README revised with actual numbers and links; no "to come" language remains except for Phase 2 items, which are named as such
- [x] `CLAUDE.md` status, package list and commands match the repo
- [x] Repo-wide check for secrets, real data and stray caches recorded in the release note
- [x] No skipped `eval` check reaches a PR: a push to a non-`main` branch produces no `eval` check run, shown on a PR's checks list
- [x] Branch protection on `main` requires `check` and `eval`, set after going public; proven by a PR whose failing `eval` cannot be merged, with the `gh api` output recorded (ticket 13's last box, ticked there too)
- [x] Repo visibility set to public; the demo PR, the baseline and the ADRs are reachable from the README
- [x] `.scratch/phase-1/release-NN-NN.md` written, listing the tickets, the post-review fixes and the numbers, as Phase 0's release note did
- [x] Every Phase 1 ticket marked done via its mark-done PR

## Comments

### 2026-10-06: built on #36, three boxes wait for the maintainer (branch `phase-1/14-cost-check`)

The maintainer chose to land all of Phase 1's remaining work in one merge, so ticket 16 is built on #36 beside ticket 14's close. Six boxes are ticked. Three are not, and are not the agent's to do: visibility, branch protection, and the mark-done of 13, 15 and 16, each **pending maintainer approval**.

**What was built.**
- **The CI split (box 5).** `.github/workflows/ci.yml` (check, eval, deploy) now runs only on `pull_request` and on `push` to `main` (with the docs-only `paths-ignore`), and `eval` has no `if:`, so every `eval` check on a pull request is a real run. A push to any other branch runs the new `.github/workflows/branch.yml`: the same `check` job and nothing else, cancelling its own older run. `deploy` stays in `ci.yml` because it `needs: eval`. `tests/ci/test_workflow.py` (test-first: red, then green) pins both triggers, the absent `if:`, that the two `check` jobs are identical, and branch.yml's read-only permissions, cancellation and lack of secrets.
- **The evidence (box 5), on #36's checks.** Before the split, commit `9f82528` carried two `eval` checks: `skipped` from push run 37520333534 and `success` from pull-request run 37520338239. After it, commit `75df46b` carries one `eval` (`success`, pull-request run 37521015614, all 48 answers from the cache, $0.00) and the push run 37521006232 (`Branch check`) has `check` alone.
- **Docs (boxes 2, 3).** The README gains a Status section with every Phase 1 number and its evidence, a table of the ten ADRs, the commands that now exist and the CI split; the only "to come" language left is named Phase 2. `CLAUDE.md`: status (Phase 1 done, Phase 2's outline next), the CI paragraph, the layout. `docs/development.md`: the two workflows. The brief: status line and §10's Phase 1 boxes ticked with where each is evidenced.
- **The release note (boxes 1, 4, 8).** [`.scratch/phase-1/release-01-19.md`](../release-01-19.md): the §10 checklist with a link per item, the numbers, the per-ticket summary, the post-review fixes (17, 18, 19, #31, the split and the docs-only filter), and the readiness check with its method and results.

**The readiness check found nothing that needs history rewritten**, and four things the maintainer should decide before going public, set out in the release note's Review section: the live endpoint's URL is in history and logs while `/reformat` spends the app's Anthropic key unauthenticated (recommended: a spend limit on that key's workspace first); the Azure subscription, tenant and client ids are printed by `azure/login` in every deploy run's log (in no file or commit); the maintainer's own email in commits and `pyproject.toml`; and one non-`555` Cork number used as a format example in two eval tests.

**Pending (maintainer), in order.** The commands are in the release note's last section.
1. Decide the review items; make the repository public (`gh repo edit ... --visibility public`). Then box 7.
2. Branch protection on `main` requiring `check` and `eval`, with ticket 13's `gh api` command; record the output here, in ticket 13 and on #36. Box 6, first half.
3. Prove it on #32 (already red, no cost): `gh api repos/KOFlynn/cv-reformatter/pulls/32 --jq .mergeable_state` should say `blocked`. #32's head predates the split and still carries a skipped `eval` beside its failed one; if GitHub does not report it blocked, an empty commit to `demo/degraded-prompt` after #36 merges re-runs the gate under the split (a live run, about $3.30). Box 6, second half, and ticket 15's box 5.
4. Merge #36: the one full uncached eval of this release (about $3.30) and a redeploy. Then one mark-done PR for 13, 15 and 16 (docs only, so it runs nothing on `main`). Box 9.

PR: #36.


### 2026-10-06: the readiness decisions, built on #36

The maintainer decided the four review items; the release note's Review section records each. What changed on the branch, from two sub-agents in their own worktrees and a docs pass:

- **`/reformat` is keyed and capped** (`src/cvr/api`, `tests/api`, test-first). It needs `X-API-Key` equal to `CVR_API_KEY`, checked from the headers alone before the body is read or a labeller built: 401 for a missing or wrong key, a closed 503 when the app has no key, 411 without `Content-Length`, 413 over 5 MB. `/health` stays open for the probes. A test shows the key never reaches the logs. `scripts/check-image.sh` gives the container a random key and asserts the 401; its keyless run passed locally on 2026-10-06, after a fix (Git Bash's curl received `/dev/null` literally under `MSYS_NO_PATHCONV`).
- **Ingress is off by default.** I disabled it on `cvr-ca` on 2026-10-06 (it was external, port 8000, transport Auto); the URL now answers 404 from Azure's edge. The deploy job opens it, runs the smoke test (401 without the key, then a `.docx` with `X-Run-Id` with it) and closes it whatever the result. `scripts/demo.sh up` / `down` opens it for a demo and wakes the app. No nightly auto-off: the maintainer will revisit how demos open it when a later phase plans them.
- **The Azure ids are masked.** `azure/login` reads them from repository secrets, so GitHub masks them; the two names stay variables; every `az` call runs with `--output none` or a narrow `--query`. The wizard sets the ids as secrets, generates the API key into the Container Apps secret `cvr-api-key` and the GitHub secret `CVR_API_KEY`, and leaves ingress closed. ADR-0010 is amended (dated 2026-10-06), and `tests/ci/` pins the workflow, the scripts and the wizard.
- **The email and the phone numbers.** `pyproject.toml`'s author email is the GitHub no-reply address, which commits now use; the phone numbers are accepted as they are.
- **Docs.** README, `CLAUDE.md` and `docs/development.md` describe all of it.

Default suite and slow suite green, lint and format clean (counts on #36).

**Pending (maintainer), in order**, with the exact commands in the release note's last section. Steps 1 and 2 must come before the merge, or its deploy fails at `azure/login` and at the smoke test.
1. Move the three ids from repository variables to secrets.
2. Create the API key in the app (secret and env var) and as the GitHub secret `CVR_API_KEY`.
3. Optional: `ANTHROPIC_API_KEY=... sh scripts/check-image.sh` for one real `/reformat` (about $0.07).
4. Make the repository public. Box 7.
5. Branch protection on `main` requiring `check` and `eval`; record the output here, in ticket 13 and on #36. Box 6, first half.
6. #32 reported `blocked`, with a screenshot. Box 6, second half, and ticket 15's box 5. If it is not blocked (its stale skipped `eval`), that box waits for a re-run of #32 after the merge.
7. Record the evidence and mark 13, 15 and 16 done on #36 (box 9, inside #36 rather than a separate PR, as for ticket 14).
8. Merge #36: the one full uncached eval of this release (about $3.30) and a deploy that opens and closes ingress.
9. Check the deploy log shows the ids as `***`, then delete the logs of runs 37052388148 (both attempts), 37056912371, 37065847534 and 37066259507.

### 2026-10-06: public, protected, proven; done

Maintainer steps 1–7 are done:

1. The three Azure ids moved from variables to secrets, and the variables deleted. `gh variable list` now shows only `AZURE_CONTAINER_APP` and `AZURE_RESOURCE_GROUP`.
2. The API key was created and stored as the Container Apps secret `cvr-api-key`, with env `CVR_API_KEY=secretref:cvr-api-key` on revision `cvr-ca--0000005` (ingress still off), and as the GitHub secret `CVR_API_KEY`.
3. The keyed `check-image.sh` passed: 325 MB, uid 10001, no key in the history or filesystem, `/reformat` without the key 401, with it 200 and 39,164 bytes on prompt 1.3.0, $0.0702.
4. **Box 7.** The repository is public: `gh repo edit KOFlynn/cv-reformatter --visibility public --accept-visibility-change-consequences` → `{"visibility":"PUBLIC"}`. The README links the demo PR #32, `eval/baseline-2026-09-29.json` and all ten ADRs, each checked to exist.
5. **Box 6, first half.** Branch protection, with `enforce_admins` on at the maintainer's choice, so a red gate blocks admins too:

```
$ gh api repos/KOFlynn/cv-reformatter/branches/main/protection/required_status_checks
{"strict":false,"contexts":["check","eval"],"checks":[{"context":"check","app_id":15368},{"context":"eval","app_id":15368}], ...}
$ gh api repos/KOFlynn/cv-reformatter/branches/main/protection --jq '{required_checks: .required_status_checks.contexts, strict: .required_status_checks.strict, enforce_admins: .enforce_admins.enabled}'
{"enforce_admins":true,"required_checks":["check","eval"],"strict":false}
```

6. **Box 6, second half.** #32 could not be the proof. Its merge state is `dirty`: it conflicts with `main` since ticket 19 changed `prompt.md`, and it still carries a pre-split skipped `eval`. Re-running it would cost about $3.30 live. The proof is the throwaway PR [#37](https://github.com/KOFlynn/cv-reformatter/pull/37), branched from #36's branch so it ran under the split workflows, with `appendix_rate.max` at 0.5.
   - Its first push (`max: 0`) was stopped by `check`. Two unit tests pin the committed thresholds, the guard against quietly loosening one. In #37 only, as its description states, `test_the_committed_thresholds_are_the_ones_the_baseline_records` and `test_a_structural_miss_fails_whatever_the_thresholds` were edited.
   - Then `check` passed (Branch check [37535322595](https://github.com/KOFlynn/cv-reformatter/actions/runs/37535322595), CI [37535330217](https://github.com/KOFlynn/cv-reformatter/actions/runs/37535330217)). `eval` failed with "appendix_rate: 0.70% above the maximum 0.5% (c09, c11)", in 23 s from the cache at $0, and `deploy` was skipped.
   - The push run produced no `eval` check, which shows box 5 again.
   - #37 was closed, never merged, and its branch deleted.

```
$ gh api repos/KOFlynn/cv-reformatter/pulls/37 --jq .mergeable_state
blocked
$ gh pr view 37 --json mergeStateStatus,statusCheckRollup
{"mergeStateStatus":"BLOCKED","checks":[{"name":"check","conclusion":"SUCCESS","workflow":"Branch check"},{"name":"check","conclusion":"SUCCESS","workflow":"CI"},{"name":"eval","conclusion":"FAILURE","workflow":"CI"},{"name":"deploy","conclusion":"SKIPPED","workflow":"CI"}]}
```

7. **Box 9.** Tickets 13, 15 and 16 are marked done here, inside #36, as ticket 14 was. Every `.scratch/phase-1/issues/*.md` now reads `**Status:** done`.

What remains follows the merge and is recorded here, not as boxes:

- **Step 8.** Merging #36 runs the release's one full uncached eval (about $3.30) and a deploy that opens ingress for the smoke test and closes it.
- **Step 9.** Check that the deploy log shows the three ids as `***`, then delete the logs of runs 37052388148 (both attempts), 37056912371, 37065847534 and 37066259507.
