# 05: Stop the app properly

**What to build:** After a deploy, and after `demo.sh down`, the app has zero running replicas, and `demo.sh up` still brings it up for a demo.

Today "off" means ingress is closed, and that isn't enough. Closing ingress removes the app's only scale rule, the HTTP one, so a replica that the smoke test already woke never scales down. One replica ran from 2026-10-06 until the maintainer deactivated its revision by hand on 2026-10-19, costing about €1.14 a day once the free grant ran out around 2026-10-11. The app's system logs show it: `ScaledObjectDeleted` a minute after the ingress was closed, then thousands of `FailedGetExternalMetric` events.

From now on, "off" means the revision is deactivated:
- **The deploy job:** its always-run close step (run once the Azure login has succeeded, whatever the smoke test's result) closes ingress and then deactivates the active revision.
- **`demo.sh up`:** activates the latest revision before opening ingress and waking the app.
- **`demo.sh down`:** closes ingress, deactivates the revision, and fails loudly if a replica is still running.

Revisions are looked up at run time, never hard-coded, because every deploy creates a new one. Every `az` call keeps the existing `--output none` or narrow `--query` discipline, so no identifier reaches public logs. The scripts' messages stop claiming that closing ingress scales the app to zero.

Amend ADR-0010 (not a rewrite): why closing ingress wasn't enough, what "off" means now, and that the proof is the replica list, not the cost dashboard, which lags and hides the free grant. Fix the docs that repeat the old claim: CLAUDE.md's deployment entry and the development guide.

This ticket can start now. It ships in the same pull request as tickets 01 to 04, because that's the next merge to `main` that makes a real change, and any deploy before this fix starts the leak again.

Spec: `.scratch/phase-1.5/spec.md`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The deploy job's close step deactivates the revision after closing ingress, under the same always-once-logged-in condition, and `tests/ci/test_workflow.py` pins both the order and the condition
- [ ] `demo.sh up` activates before opening ingress, and `demo.sh down` deactivates after closing ingress and checks replicas, all pinned by `tests/ci/test_deploy_scripts.py`. Neither script prints an identifier
- [ ] The ADR-0010 amendment and the doc fixes are done. No doc still says that closing ingress scales the app to zero
- [ ] `uv run pytest -q`, `ruff check` and `ruff format --check` are green
- [ ] After the merge: the deploy run finished, and `az containerapp replica list` for the new revision is empty. The output (with no identifiers) is recorded here
