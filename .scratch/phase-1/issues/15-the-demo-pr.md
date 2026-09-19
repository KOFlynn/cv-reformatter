# 15: The demo PR

**What to build:** The headline moment: a one-line diff and a red gate. Branch `demo/degraded-prompt` deletes the verbatim-quote rule from the prompt file and nothing else. Before the demo relies on it, the degradation is shown to fail three eval runs out of three with the cache bypassed, using the same procedure as the thresholds; the three reports and which metrics went red (provenance violations expected, placement drop likely) are recorded in the PR description. The PR is opened as a draft, labelled `demo`, and left open permanently; branch protection makes merging it impossible; `deploy` is shown never to run on it. The README's demo section links it.

**Blocked by:** 14 (Provision and deploy through OIDC)

**Status:** ready-for-agent

- [ ] Branch with exactly one change: the verbatim-quote rule removed from the prompt; `PROMPT_VERSION` bumped so the cache key and the report both show it
- [ ] Three `--no-cache` runs locally all exit non-zero; the failing metrics and their counts recorded per run
- [ ] Draft PR open, labelled `demo`, description explaining what was removed and why the gate catches it, with the three-run evidence
- [ ] CI on the PR: `check` green, `eval` red with the report comment showing the provenance findings, `deploy` not run
- [ ] Merge button disabled by branch protection (screenshot or `gh pr view` output in the description)
- [ ] README demo section links the PR and states what a reviewer should look at first
