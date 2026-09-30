# 13: CI eval gate

**What to build:** The gate in front of every merge. `ci.yml` becomes `check` → `eval`: `check` (sync, lint, format check, unit tests) on every push as today; `eval` needs `check`, runs on `pull_request` and on `push` to `main`, takes the LLM key from a repository secret, runs the eval runner against the committed thresholds, uploads `report.json` and `report.md` as artifacts, writes the markdown into the job summary and posts it as a PR comment (updating the same comment on re-runs rather than stacking), and fails on non-zero exit. Workflow-level `concurrency` with cancel-in-progress so two quick pushes never pay for two full eval runs. Branch protection on `main` requires `check` and `eval` to pass. The first PR through this gate has its numbers on the PR page, not behind a download.

**Blocked by:** 10 (Baseline and thresholds)

**Status:** in-review

- [x] `eval` job defined as specified; the key is a repository secret with a documented name; no key in the workflow file
- [x] The eval job runs on pull requests and pushes to main only; `check` still runs on every push
- [x] Artifacts uploaded; job summary shows the markdown; the PR comment is created on first run and updated on subsequent runs
- [x] Workflow concurrency group with cancel-in-progress; verified by two rapid pushes with the first run cancelled
- [ ] Branch protection on `main` requires `check` and `eval`; recorded in the PR description with a screenshot or the `gh api` output
- [x] The ticket's own PR goes green through the new gate, with the report comment visible; tokens and cost for the run are in the comment
- [x] `CLAUDE.md` CI section updated

## Comments

### 2026-09-30: built, in review (branch `phase-1/13-ci-eval-gate`)

Only what can be checked without GitHub is ticked: the job definition, its triggers and the `CLAUDE.md` section. The artifact/summary/comment box, the concurrency box, branch protection and the green PR all need the workflow to run on GitHub and stay unticked; they are the release PR's job, once the secret is set. `actionlint` is not installed here and was not run; the YAML parses with PyYAML and its structure was read back (two jobs, `needs`, `if`, concurrency, permissions).

**What was built.** `.github/workflows/ci.yml`:
- top-level `permissions: contents: read`; `check` is unchanged in content and still runs on every push and pull request;
- `eval`: `needs: check`, job-level `if:` for `pull_request` or `push` to `main`, `timeout-minutes: 20` (a run is about four minutes, so a hang cannot spend much), `permissions: contents: read, pull-requests: write` (the only job with write), `ANTHROPIC_API_KEY` from `secrets.ANTHROPIC_API_KEY`;
- steps: checkout, uv, Python, `uv sync --locked`, cache, key check, `uv run python -m cvr.eval.run`, then three `if: always()` steps: upload `eval/report.json` and `eval/report.md` as artifact `eval-report`, append `report.md` to `$GITHUB_STEP_SUMMARY`, and the PR comment. The eval step fails the job on the runner's own exit code; nothing captures or masks it;
- the comment is `<!-- cvr-eval-report -->` plus `report.md` (which has the verdict, every table, tokens, cost, wall time, cache use and each gate failure) plus a link to the run, written with `gh api`: the first run POSTs, later runs find the comment by the marker and PATCH it. If no report was written the comment says so. `report.md` is cut at 60,000 bytes to stay under GitHub's comment limit.

**Decisions beyond the ticket text.**
- **Cache: used, with a live run on `main`.** The runner's cache key is the whole labeller config, the prompt and schema hashes and each source sha256, so a hit can only replay the answer to the identical question; any prompt, schema, model, `CVR_LABEL_*` or document change misses and pays. Parse, verify, transform, render, the adapter, the metrics and the thresholds still run in full on every PR, so a code change is gated for free. What a replay does not re-prove is the model's behaviour, which is what a prompt/model change exists to test, and those miss. Always calling would cost about $3.3 per PR push for an answer that cannot differ from the last one in any way the code can see. `actions/cache` keys `eval-responses-<sha>` with restore prefix `eval-responses-`; it is saved only when the job passes, so a failed run's answers are not replayed to make a re-run fail identically. A push to `main` runs `--no-cache`: each merge gets one live, authoritative run, and it refreshes the cache that later PRs restore. The cost is that the first PR through the gate, and any PR after a cache eviction, is fully live. GitHub scopes caches by ref: a PR reads `main`'s cache and its own, not another PR's.
- **Concurrency group** is `workflow-event-ref` (`head_ref` for PRs, else `ref`), not workflow and ref alone. A push to a PR branch starts a `push` run and a `pull_request` run at once; with a shared group they cancel each other and the PR could be left with no `eval`. `cancel-in-progress` is `github.ref != 'refs/heads/main'`: **pushes to `main` are not cancelled.** A cancelled main run leaves a merge with no verdict, merges are rare, and the cost of not cancelling is one extra run. PR and feature-branch pushes cancel as the ticket asks.
- **Missing secret:** a step before the eval fails with an `::error::` annotation naming `ANTHROPIC_API_KEY` and where to set it, rather than a provider stack trace. It fails even on a fully cached run, so a misconfigured repository never looks green.
- **Fork PRs** get no secrets and a read-only token, so `eval` fails at that step and the comment step is skipped (`head.repo.full_name == github.repository`). The repo has no outside contributors; a fork PR cannot pass this gate by design.
- **Permissions:** only `eval` has `pull-requests: write`; the comment uses the job's own `github.token` through `gh`, no PAT.
- Action versions follow the existing file (`checkout@v4`, `setup-uv@v6`) plus `cache@v4` and `upload-artifact@v4`.
- Docs: `CLAUDE.md`'s CI paragraph and `docs/development.md` (intro line and the Eval section) describe the two jobs, the secret and the gate.

**Cost of one full uncached run.** `eval/baseline-2026-09-29.json`: three runs, $9.8047 in all, so about **$3.27 a run** ($3.2736 for the last), 48 documents, 223 to 228 s of wall time on the dev machine.

**Pending (maintainer).**
1. Set the secret (the repo has none): `gh secret set ANTHROPIC_API_KEY` (paste at the prompt; never commit it).
2. Open the release PR `release/phase-1-13` into `main`. It is the first PR through the gate: expect a fully live run (about $3.3), the report comment, the job summary and the `eval-report` artifact; tick the third and sixth boxes from that.
3. Push twice in quick succession to a PR branch and confirm the first run shows `Cancelled`; tick the fourth.
4. Branch protection on `main`, with the `gh api` output in the PR description. The repo is private: on a free personal plan branch protection and rulesets are unavailable for private repositories, so this waits for ticket 16 (going public) or GitHub Pro. Once available:

```
gh api --method PUT repos/KOFlynn/cv-reformatter/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": false, "contexts": ["check", "eval"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

### 2026-09-30: through the gate on #29

The release PR (#29, `release/phase-1-13` → `main`) is the first through the gate, with the secret set. Branch protection is the one box left, and it waits for ticket 16 (the repo is private on a free plan).

- **Concurrency.** The PR's first run (36768319947, `84b5e85`) was cancelled after 3m06s, mid-`eval`, by a push of a one-line comment change two minutes later (`f0b1457`, merged as `bdace06`). The new run sat queued for about 40 seconds before GitHub cancelled the old one, so the handover is not instant. The `push` run of the same commit ran `check` alone beside it and cancelled nothing, as the event in the group intends. The live calls the cancelled run had made were paid for and not cached: part of a run's cost.
- **Green.** The second run (36768558946) passed `check` and `eval`: every gate held, 48 documents, 48 live calls and 0 cache hits (the CI cache was empty), 263,398 tokens in and 111,341 out, **$3.2804**, 234.9 s. Tunable placement recall is 99.91%; the only miss is c06's repeated skill in `single-column` (ticket 19).
- **Report.** Artifact `eval-report` (report.json and report.md), the job summary, and one PR comment carrying tokens and cost. The comment was created by the cancelled run (its comment step runs under `always()`, which includes cancellation, and said no report was written), then edited in place by the green run: one comment, created then updated, as the box asks. The cache was saved as `eval-responses-<merge sha>` under `refs/pull/29/merge`, so the next push to this PR should replay all 48 answers at no cost. The link line names the PR's merge commit (`60392fc`), not the head, because that is what `GITHUB_SHA` is on `pull_request`.
