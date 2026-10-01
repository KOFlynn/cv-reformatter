# 14: Provision and deploy through OIDC

**What to build:** A merge to `main` puts the service on Azure with no Azure secret in GitHub. Provisioning is a one-off through an interactive wizard (the `wizard` skill): resource group, Log Analytics workspace, Container Apps environment, the app itself, the Entra app registration with a federated credential for the repo's `main` branch, and the Container Apps secret holding the LLM key. The `deploy` job needs `eval`, runs on `push` to `main` only, has job-level `id-token: write`, logs in with `azure/login` through the federated credential, builds the image, pushes it to GHCR (the package made public at first deploy, so no registry secret), deploys to the app, then runs a smoke step that posts a golden-set document to the live endpoint and asserts a `.docx` comes back with `X-Run-Id` present, verifying the header survives ingress. Container Apps: consumption plan, external ingress on the service port, min replicas 0, max 1, liveness and readiness probes on `/health`, the key as a Container Apps secret referenced by an environment variable, logs to the workspace. ADR-0010 is written here: public package on a private repo, OIDC, manual provisioning with infrastructure as code as what changes at scale, ACR with managed-identity pull and a managed identity for the LLM path as the Phase 2 upgrade, scale to zero and the cold start it implies (warm the endpoint before presenting: a runbook note, not a config change), and the free-grant budget with "kill anything that costs money".

**Blocked by:** 12 (Dockerfile), 13 (CI eval gate)

**Status:** in-review

- [ ] Wizard script committed under the docs or scripts area, with the human-only steps and the values it asks for; the resulting resource names and the federated credential subject recorded in the ADR
- [x] `deploy` job defined as specified; `id-token: write` at job level only; no Azure secret in GitHub
- [ ] GHCR package public; the image pulls anonymously; the ticket 12 secret inspection repeated on the pushed image
- [ ] Container Apps configured as specified; the app scales to zero when idle and serves `/health` on wake
- [ ] Post-deploy smoke step green: `.docx` returned with `X-Run-Id`; the header value appears in a Log Analytics query for the summary line
- [ ] Deployment blocked when `eval` fails (proven in ticket 15, referenced here)
- [ ] ADR-0010 written under `docs/adr/`; README item 7 (ticket 08) updated from plan to fact
- [ ] Cost check after the first day recorded in the PR description

## Comments

### 2026-10-01: built, in review, nothing provisioned yet (branch `phase-1/14-provision-and-deploy-through-oidc`)

**Nothing has been provisioned, pushed or deployed.** The Azure CLI is not installed on the machine this was written on, and the agent holds no Azure or Anthropic credentials. One box is ticked, the job definition, because it can be checked in the repository. ADR-0010 and the README change are written, but their box also needs the resource names confirmed by a real run, so it stays open. The other boxes need the wizard run, a merge to `main` and a day of billing.

**What was built.**
- `.github/workflows/ci.yml` gains `deploy`:
  - `needs: eval`, `push` to `main` only, `timeout-minutes: 20`;
  - `concurrency: {group: deploy, cancel-in-progress: false}`, so deploys queue rather than overlap or cut off midway;
  - job-level `permissions: contents: read, packages: write, id-token: write`. It is the only job with `id-token`.
  - Steps, in order:
    1. checkout;
    2. the lower-cased image name `ghcr.io/koflynn/cv-reformatter`;
    3. `docker/login-action` to GHCR with `github.token`;
    4. buildx, then `build-push-action` tagged `:<sha>` with the `org.opencontainers.image.source` label;
    5. `docker logout ghcr.io`, then `PULL=1 sh scripts/check-image.sh`. That is an anonymous pull plus ticket 12's inspection on the published image;
    6. `azure/login@v2` with `vars.AZURE_CLIENT_ID`, `vars.AZURE_TENANT_ID` and `vars.AZURE_SUBSCRIPTION_ID`;
    7. `az containerapp update --image` on `vars.AZURE_CONTAINER_APP` in `vars.AZURE_RESOURCE_GROUP`, then read the FQDN, failing if it is empty;
    8. `sh scripts/smoke-deploy.sh "$URL"`.
  - Every expression reaches a script through `env:`.
- `scripts/check-image.sh`: with `PULL=1` it pulls `$IMAGE` instead of building, and fails asking whether the package is public when the pull needs credentials.
- `scripts/smoke-deploy.sh` (POSIX sh, curl):
  - wakes the app through `/health`, retrying for up to `WAKE_SECONDS` (180) and printing the wake time, which is the cold-start figure;
  - posts `c04__single-column.docx` and asserts a 200, the `.docx` content type, a `PK` body and `X-Run-Id`;
  - prints the run id and the Log Analytics query for its summary line, and appends both to `$GITHUB_STEP_SUMMARY` when set.
  - Checked locally against `create_app` with a stand-in labeller: green against the live server, and `FAIL: no /health` against a dead port.
- `scripts/provision-azure.sh`, the wizard (the `wizard` skill's library above the marker, unchanged), twelve stages:
  1. tools and `az login`, subscription, provider registration;
  2. names and region, defaulting to the maintainer's choices (`cvr-rg`, `cvr-log`, `cvr-cae`, `cvr-ca`, `cvr-github-deploy`, `northeurope`);
  3. resource group and workspace (30-day retention);
  4. the environment: consumption only (`--enable-workload-profiles false`), logs to the workspace;
  5. build and push `:bootstrap` from the dev machine (`gh auth refresh -s write:packages`, `gh auth token | docker login`, then logout);
  6. in the browser: the package public, the repository's Actions given Write. Then an anonymous pull plus the inspection;
  7. the app, from a YAML spec in a temp file: `environmentId`, `location`, external ingress 8000, single revision, 0.5 vCPU / 1 GiB, liveness (30 s) and readiness (10 s) on `/health`, min 0 / max 1, the secret `anthropic-api-key` read as `ANTHROPIC_API_KEY`. The key is typed hidden and never put on a command line; the file is removed after `az` reads it, or by a trap on interrupt;
  8. smoke test;
  9. Entra app `cvr-github-deploy`, its service principal, Contributor on `cvr-rg` only, and federated credential `github-main` with subject `repo:KOFlynn/cv-reformatter:ref:refs/heads/main`. No client secret;
  10. `gh variable set` for the five variables, then `gh secret list` to show nothing Azure;
  11. a cost budget in the portal;
  12. the record for ADR-0010.
  - Values are remembered in `.env.azure`; `.env` and `.env.*` are now gitignored. Existing resources are skipped, and the other stages are safe to repeat.
- `tests/ci/test_workflow.py`, written first, 13 tests. It pins:
  - the job order;
  - `deploy`'s trigger, permissions and concurrency;
  - `id-token` on `deploy` alone;
  - no `secrets.*AZURE*`, `client-secret` or `creds` anywhere, and no `secrets.` in `deploy`;
  - `azure/login` fed from `vars.*`;
  - the GHCR push with `github.token` and no build args;
  - logout before the inspection;
  - the step order push, inspect, login, update, smoke;
  - the update naming the variables and the sha;
  - no expression inside a `run:`.
- `tests/docker/test_dockerignore.py`: the two new scripts and `.env.azure` are asserted out of the build context.
- `docs/adr/0010-deployment.md`; README items 7 and 9 now link it, and item 7 is fact rather than plan; `docs/development.md` gains a Deployment section; `CLAUDE.md` covers status, the deployment entry, CI, commands and layout.

**Decisions beyond the ticket text.**
- **The Azure ids are repository variables, not secrets.** Microsoft's guide stores them as secrets. They are identifiers that open nothing without a `main`-branch token, and as variables "no Azure secret in GitHub" stays literally true and checkable with `gh secret list`.
- **The first image is pushed from the dev machine by the wizard.** Container Apps pulls with no registry secret, so the package must exist and be public before the app is created. Otherwise the first CI deploy would push a private package that the app cannot pull. GitHub has no API for package visibility, so that step is in the browser.
- **The app's Anthropic key is its own,** separate from the repository secret the eval uses, so either can be revoked alone.
- **Contributor on the resource group,** not the subscription.
- **Deploys queue** under their own concurrency group. Without it, two quick merges could overlap and the older sha could be deployed last.
- **No `--revision-suffix`.** The image tag already names the sha, and a suffix would collide when a failed deploy job is re-run.
- **Log Analytics is checked by hand.** The smoke step prints the query rather than polling ingestion from CI for minutes.
- **The smoke test passes on a labelling failure** (the banner document is also a 200). It proves ingress, the header and a `.docx`; the eval proves the labelling. A bad key fails it, because that is a 500.

**Code review (`code-review` skill, against `release/phase-1-14`).** Fixed:
- the wizard ran the smoke script with `MSYS_NO_PATHCONV` set, which would break curl's temp paths under Git Bash; it now runs it under `env -u MSYS_NO_PATHCONV`;
- the documented key rotation put the key in shell history; it now reads the key with `read -rs`, then restarts the revision;
- the temp spec had no trap on interrupt; it has one, and the comment no longer claims `chmod 600` protects anything on NTFS;
- `deploy` had no concurrency group;
- the smoke URL was spliced into the script; it now goes through `env:`;
- an empty FQDN was not caught;
- the new scripts are now `100755`;
- the "skips what exists" claim was softened to what the wizard actually does;
- the ADR and README no longer say in the past tense that things were provisioned;
- the YAML spec now carries `environmentId` and `location`, rather than relying on `--environment` beside `--yaml`;
- the test helpers were unified, and one test was renamed.

Left as judgement calls:
- ADR-0010 uses lists and a table where 0001–0009 are prose. The resource table is the record the ticket asks for.
- README item 7's heading keeps the brief's wording ("managed identity at runtime"); the body says that arrives in Phase 2.

**Tests.** Default suite: 1237 passed, 1 skipped (the labeller spike, no key). Slow suite: 914 passed (before the review fixes, which touched no slow test). Ruff check and format check clean. `bash -n` passes on both new scripts. `shellcheck` and `actionlint` are not installed and were not run.

**Pending (maintainer), in this order.**
1. Install the Azure CLI: `winget install -e --id Microsoft.AzureCLI`, then reopen Git Bash.
2. Run the wizard from the repo root: `bash scripts/provision-azure.sh`. Paste its stage 6 output (the inspection of the pulled image) and stage 12 record into the PR. Tick boxes 1, 3 and 7.
3. Merge the release PR. The push to `main` runs `check`, then `eval` (live, about $3.3), then `deploy`. Paste the deploy job's summary (run id, wake time) into the PR.
4. In the portal (Log Analytics, `cvr-log`, Logs), run the query from the job summary and paste the row. Tick box 5.
5. Leave the app idle for about ten minutes, then time a `/health` request. A multi-second first answer shows it scaled to zero and woke. Tick box 4.
6. After a day, check Cost Management for the subscription and record it in the PR. Tick box 8.
7. Box 6 (a red `eval` blocks `deploy`) is proven by ticket 15's demo PR.
