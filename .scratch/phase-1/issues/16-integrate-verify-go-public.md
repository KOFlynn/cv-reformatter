# 16: Integrate, verify, go public

**What to build:** Phase 1 declared done against the brief's §10 exit criteria, and the repo opened. Walk the seven criteria (pipeline on the golden set; unit tests for parse, verify, transform and render; eval gate in Actions with thresholds from the baseline; Dockerfile running locally; deployed through OIDC; README as ADR; demo PR proven to block a deploy) and record where each is evidenced. Revise the README with every number that now exists (baseline, thresholds, cost per run, image size, cold-start time) and its links to the demo PR, the baseline and the ten ADRs. Update `CLAUDE.md`'s project status and package list to describe Phase 1 as it is, and the Phase 2 outline as what comes next. Check the whole repo once more for anything that must not be public: no real names, no keys, no cache, no `.env`, no report with anything odd in it. Then make the repo public, and write the Phase 1 release note in the scratch area the way Phase 0's was written.

Going public also unlocks ticket 13's last box, branch protection on `main` requiring `check` and `eval` (unavailable on a private repo on the free plan; the `gh api` command is in ticket 13's comment). Before it is switched on, close the gap ticket 13's runs on #29 showed: a push to a PR branch starts a `push` run whose `eval` job is skipped by its `if:`, beside the `pull_request` run whose `eval` really runs, and both report a check named `eval` on the PR's head commit. GitHub counts a skipped job as satisfying a required check, so a PR whose real eval failed could still pass protection on the skipped one. The `push` run must not produce an `eval` check outside `main`, for example by splitting the eval into a workflow that triggers only on `pull_request` and on `push` to `main`, so that `check` still runs on every push as ticket 13 requires.

**Blocked by:** 08 (README as ADR), 15 (The demo PR)

**Status:** ready-for-agent

- [ ] §10 Phase 1 checklist with a link per item (test file, workflow run, PR, ADR) in the release note
- [ ] README revised with actual numbers and links; no "to come" language remains except for Phase 2 items, which are named as such
- [ ] `CLAUDE.md` status, package list and commands match the repo
- [ ] Repo-wide check for secrets, real data and stray caches recorded in the release note
- [ ] No skipped `eval` check reaches a PR: a push to a non-`main` branch produces no `eval` check run, shown on a PR's checks list
- [ ] Branch protection on `main` requires `check` and `eval`, set after going public; proven by a PR whose failing `eval` cannot be merged, with the `gh api` output recorded (ticket 13's last box, ticked there too)
- [ ] Repo visibility set to public; the demo PR, the baseline and the ADRs are reachable from the README
- [ ] `.scratch/phase-1/release-NN-NN.md` written, listing the tickets, the post-review fixes and the numbers, as Phase 0's release note did
- [ ] Every Phase 1 ticket marked done via its mark-done PR
