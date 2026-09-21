# 13: CI eval gate

**What to build:** The gate in front of every merge. `ci.yml` becomes `check` → `eval`: `check` (sync, lint, format check, unit tests) on every push as today; `eval` needs `check`, runs on `pull_request` and on `push` to `main`, takes the LLM key from a repository secret, runs the eval runner against the committed thresholds, uploads `report.json` and `report.md` as artifacts, writes the markdown into the job summary and posts it as a PR comment (updating the same comment on re-runs rather than stacking), and fails on non-zero exit. Workflow-level `concurrency` with cancel-in-progress so two quick pushes never pay for two full eval runs. Branch protection on `main` requires `check` and `eval` to pass. The first PR through this gate has its numbers on the PR page, not behind a download.

**Blocked by:** 10 (Baseline and thresholds)

**Status:** ready-for-agent

- [ ] `eval` job defined as specified; the key is a repository secret with a documented name; no key in the workflow file
- [ ] The eval job runs on pull requests and pushes to main only; `check` still runs on every push
- [ ] Artifacts uploaded; job summary shows the markdown; the PR comment is created on first run and updated on subsequent runs
- [ ] Workflow concurrency group with cancel-in-progress; verified by two rapid pushes with the first run cancelled
- [ ] Branch protection on `main` requires `check` and `eval`; recorded in the PR description with a screenshot or the `gh api` output
- [ ] The ticket's own PR goes green through the new gate, with the report comment visible; tokens and cost for the run are in the comment
- [ ] `CLAUDE.md` CI section updated
