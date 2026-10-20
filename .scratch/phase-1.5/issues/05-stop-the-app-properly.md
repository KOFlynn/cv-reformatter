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

**Status:** done

- [x] The deploy job's close step deactivates the revision after closing ingress, under the same always-once-logged-in condition, and `tests/ci/test_workflow.py` pins both the order and the condition
- [x] `demo.sh up` activates before opening ingress, and `demo.sh down` deactivates after closing ingress and checks replicas, all pinned by `tests/ci/test_deploy_scripts.py`. Neither script prints an identifier
- [x] The ADR-0010 amendment and the doc fixes are done. No doc still says that closing ingress scales the app to zero
- [x] `uv run pytest -q`, `ruff check` and `ruff format --check` are green
- [x] After the merge: the deploy run finished, and `az containerapp replica list` for the new revision is empty. The output (with no identifiers) is recorded here

## Comments

**2026-10-19.** Done test-first. The deploy's final step is now "Close ingress and stop the app" (same `always() && steps.login.outcome == 'success'` condition): it closes ingress, looks the revision up with `properties.latestRevisionName`, deactivates it, then polls `az containerapp replica list` (12 tries, 5 s apart) and fails with an error annotation if a replica is still `Running`. `demo.sh up` activates the latest revision before opening ingress; `down` closes ingress only if an FQDN exists, always deactivates the revision, polls up to `STOP_SECONDS` (60) and exits 1 if a replica still runs, so an already-closed app is no longer an early exit but is still stopped. Decisions beyond the ticket: the poll treats an `az` failure as "unknown" (not zero), so it fails rather than passes; the ADR amendment also records that the earlier "scale to zero" paragraph holds only while ingress exists; README's stale claims were fixed along with CLAUDE.md and the development guide. No `az` command was run; the live check is the post-merge box.

**2026-10-20.** Decision: the stop logic lives in one place. The deploy job's final step no longer calls `az` inline; it runs `sh scripts/demo.sh down "$RG" "$APP"` (same condition, same `APP`/`RG` env from the variables). Reasons: `demo.sh down` already does more (closes ingress only if an FQDN exists and verifies it is gone, deactivates only an active revision, polls replicas for `STOP_SECONDS`), and two copies would drift. Because `demo.sh` falls back to `.env.azure` and then `cvr-rg`/`cvr-ca` on an empty argument, the step fails with an `::error::` annotation before the call if `RG` or `APP` is empty, and adds `::error::$APP may still be running; see the step log` if the script exits non-zero. `demo.sh` itself is unchanged and prints only the app and resource group names. `tests/ci/test_workflow.py` now pins the call, the guard before it, the absence of inline `az` commands, the condition and that the step is last after the smoke test; the tests that pinned the inline commands were replaced by these. Status stays `in-review`.

**2026-10-20, review.** Since the deploy now runs `demo.sh down`, a gap in the script started to matter. `fqdn()` and `revision()` piped `az` straight into `tr`, so a failed `az` call came back as an empty value with exit status 0. If the FQDN lookup alone failed, `down` skipped closing ingress and still printed "Stopped: … has no ingress". The inline step had run under `bash -e`, so it would have failed instead. Fix: a `value` helper returns non-zero when `az` fails, and `down` assigns the FQDN before testing it, so `set -e` stops the script. A new test runs `down` against a fake `az` whose FQDN lookup fails. It failed on the old script and passes now. The narrow-query test now also covers the calls made through `value`.

**2026-10-20, after the merge (PR #38, CI run 39481527850).** The deploy succeeded. Its final step, through `demo.sh down`, logged:

```
== closing ingress on cvr-ca (cvr-rg)
== deactivating the latest revision of cvr-ca
Stopped: cvr-ca has no ingress, its revision is inactive and no replica is running.
```

The maintainer then ran `az containerapp replica list` for the latest revision, with `--query "[].properties.runningState"`. It returned `[]`, so no replica is running.

