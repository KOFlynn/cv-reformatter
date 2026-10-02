# 15: The demo PR

**What to build:** The headline moment: a one-line diff and a red gate. Branch `demo/degraded-prompt` deletes the verbatim-quote rule from the prompt file and nothing else. Before the demo relies on it, the degradation is shown to fail three eval runs out of three with the cache bypassed, using the same procedure as the thresholds; the three reports and which metrics went red (provenance violations expected, placement drop likely) are recorded in the PR description. The PR is opened as a draft, labelled `demo`, and left open permanently; branch protection makes merging it impossible; `deploy` is shown never to run on it. The README's demo section links it.

**Blocked by:** 14 (Provision and deploy through OIDC)

**Status:** in-progress

- [ ] Branch with exactly one change: the verbatim-quote rule removed from the prompt; `PROMPT_VERSION` bumped so the cache key and the report both show it
- [ ] Three `--no-cache` runs locally all exit non-zero; the failing metrics and their counts recorded per run
- [ ] Draft PR open, labelled `demo`, description explaining what was removed and why the gate catches it, with the three-run evidence
- [ ] CI on the PR: `check` green, `eval` red with the report comment showing the provenance findings, `deploy` not run
- [ ] Merge button disabled by branch protection (screenshot or `gh pr view` output in the description)
- [ ] README demo section links the PR and states what a reviewer should look at first

## Comments

### 2026-10-02: branch and README prepared; nothing run, nothing pushed

Built (no API key, no push):
- Branch `demo/degraded-prompt` from `main`, one commit: the "Quote verbatim and contiguously" bullet deleted from `src/cvr/label/prompt.md` (four lines), and `versions.json` prompt 1.1.0 -> 1.2.0 with hash `01027713bb6e31df`. Minor, as ticket 18's narrowing was 1.0.0 -> 1.1.0. Lint, format and the unit tests pass on it, so `check` stays green.
- This branch (`phase-1/15-demo-pr`): the README demo section now says what a reviewer looks at first, with a marked TODO for the PR number; the draft PR description is `.scratch/phase-1/15-demo-pr-description.md`, with tables to fill.

Decisions beyond the ticket text:
- No helper script. The runs must happen on `demo/degraded-prompt`, and a script committed on this branch would not exist there. The loop below is short enough to paste.
- The ticket and README expected `provenance_violations` to go red. It should not: `verify` rejects any quote that is not a source substring, so the output never holds non-source text. The expected red metrics are `placement_accuracy` (tunable recall; structural if a name, title or date leaf is hit) and `appendix_rate` (the 2% maximum). The README and the PR description say so; provenance is named only as a "would be a hole in verify" signal.
- Risk to settle by the runs: only the rule bullet is deleted. The prompt's opening paragraph and its closing paragraph still say quotes must be verbatim and exact, and the `Reference` schema docstring says "verbatim quote", so the model may keep quoting verbatim and the gate may pass. If a run exits 0, the alternative that is still one change is to remove every verbatim/exact-substring instruction from the prompt (the bullet, the intro's verbatim sentences and the closing paragraph's last sentence) in the same commit, then re-bump the version. Do not weaken the thresholds.

Maintainer's pending steps, in order, in Git Bash with `ANTHROPIC_API_KEY` set:
1. Run the three `--no-cache` evals on `demo/degraded-prompt` (about $3.3 each):
   ```
   git switch demo/degraded-prompt
   mkdir -p .cache/demo-runs
   for n in 1 2 3; do
     uv run python -m cvr.eval.run --no-cache > .cache/demo-runs/run$n.log 2>&1
     echo "run $n exit $?"
     cp eval/report.json .cache/demo-runs/run$n.json
     cp eval/report.md .cache/demo-runs/run$n.md
   done
   ```
   All three must exit 1. Fill the tables in the PR description from `run<n>.md`.
2. Push `demo/degraded-prompt`, create the label (`gh label create demo`), and open the draft PR (`gh pr create --draft --label demo`) with the description.
3. Confirm CI: `check` green, `eval` red with the report comment, `deploy` not run (it runs on `push` to `main` only). Paste the links into the description. Tick boxes 1 to 4.
4. Branch protection is unavailable while the repo is private on the free plan; it waits for ticket 16, as ticket 13's protection box did. Leave the merge-button box for then.
5. Put the PR number in the README (replace the TODO) and push `phase-1/15-demo-pr` as its own PR. Ticket 14's box 6 (a red `eval` blocks `deploy`) is proven by this PR's CI.
