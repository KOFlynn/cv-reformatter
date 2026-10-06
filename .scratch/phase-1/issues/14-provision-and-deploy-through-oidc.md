# 14: Provision and deploy through OIDC

**What to build:** A merge to `main` puts the service on Azure with no Azure secret in GitHub. Provisioning is a one-off through an interactive wizard (the `wizard` skill): resource group, Log Analytics workspace, Container Apps environment, the app itself, the Entra app registration with a federated credential for the repo's `main` branch, and the Container Apps secret holding the LLM key. The `deploy` job needs `eval`, runs on `push` to `main` only, has job-level `id-token: write`, logs in with `azure/login` through the federated credential, builds the image, pushes it to GHCR (the package made public at first deploy, so no registry secret), deploys to the app, then runs a smoke step that posts a golden-set document to the live endpoint and asserts a `.docx` comes back with `X-Run-Id` present, verifying the header survives ingress. Container Apps: consumption plan, external ingress on the service port, min replicas 0, max 1, liveness and readiness probes on `/health`, the key as a Container Apps secret referenced by an environment variable, logs to the workspace. ADR-0010 is written here: public package on a private repo, OIDC, manual provisioning with infrastructure as code as what changes at scale, ACR with managed-identity pull and a managed identity for the LLM path as the Phase 2 upgrade, scale to zero and the cold start it implies (warm the endpoint before presenting: a runbook note, not a config change), and the free-grant budget with "kill anything that costs money".

**Blocked by:** 12 (Dockerfile), 13 (CI eval gate)

**Status:** done

- [x] Wizard script committed under the docs or scripts area, with the human-only steps and the values it asks for; the resulting resource names and the federated credential subject recorded in the ADR
- [x] `deploy` job defined as specified; `id-token: write` at job level only; no Azure secret in GitHub
- [x] GHCR package public; the image pulls anonymously; the ticket 12 secret inspection repeated on the pushed image
- [x] Container Apps configured as specified; the app scales to zero when idle and serves `/health` on wake
- [x] Post-deploy smoke step green: `.docx` returned with `X-Run-Id`; the header value appears in a Log Analytics query for the summary line
- [x] Deployment blocked when `eval` fails (proven in ticket 15, referenced here)
- [x] ADR-0010 written under `docs/adr/`; README item 7 (ticket 08) updated from plan to fact
- [x] Cost check after the first day recorded in the PR description

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
  7. the app, by an ARM `PUT` through `az rest` from a JSON spec in a temp file (see the 2026-10-02 comment): `environmentId`, `location`, external ingress 8000, single revision, 0.5 vCPU / 1 GiB, liveness (30 s) and readiness (10 s) on `/health`, min 0 / max 1, the secret `anthropic-api-key` read as `ANTHROPIC_API_KEY`. The key is typed hidden and never put on a command line; the file is removed after `az` reads it, or by a trap on interrupt;
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

### 2026-10-02: the wizard's first run, stage 7 fixed

Stages 1–6 ran on the maintainer's machine against the new subscription `cvr_sub`. Two snags came up before stage 7:
- `az login`'s Windows account-broker popup failed silently. `az config set core.enable_broker_on_windows=false` switched it to the browser sign-in.
- Git Bash needed a restart to pick up the new `az` on its PATH.

Stage 7 then failed with `Bad Request ... The JSON value could not be converted to System.Boolean. Path: $ | BytePositionInLine: 4`. The cause is a known Azure CLI behaviour: `az containerapp create --yaml` deserialises the YAML into the SDK's model and re-serialises every attribute, so fields the file never sets reach ARM as `null` (four bytes) where a boolean is required. The flag-based create avoids that but takes the secret as `--secrets name=value`, on the command line. Stage 7 now `PUT`s the same spec as JSON to the ARM API with `az rest --method PUT --body @<file>` (`api-version=2024-03-01`). It then polls `provisioningState` until it reads `Succeeded`. The key still goes through the private temp file only.

### 2026-10-02: provisioned

The wizard completed on its third run, after the two stage 7 fixes (`ecc4b5e`, then `Content-Type: application/json` on the `az rest` PUT). It created:
- the resource group `cvr-rg`, Log Analytics `cvr-log`, environment `cvr-cae` and app `cvr-ca`, all in `northeurope`, on the subscription `cvr_sub`;
- the Entra app `cvr-github-deploy`, with the OIDC subject `repo:KOFlynn/cv-reformatter:ref:refs/heads/main`;
- the image `ghcr.io/koflynn/cv-reformatter` (public);
- a budget of 5 a month.

All of these match ADR-0010's table. The app is at `https://cvr-ca.orangewave-5499e0c7.northeurope.azurecontainerapps.io`. The full record from stage 12 goes in the release PR, #30.

Checked afterwards from the dev machine:
- `gh variable list` shows the five `AZURE_*` variables;
- `gh secret list` shows `ANTHROPIC_API_KEY` alone, so there is no Azure secret in GitHub;
- `GET /health` on the live URL returned 200 with `X-Run-Id` (warm, 0.07 s), so the header survives ingress on a GET;
- GHCR issues an anonymous pull token for the package.

Boxes 1, 3 and 7 are ticked on this run: the names and subject are now confirmed against the ADR, and stage 6's anonymous pull and inspection passed (the wizard stops on a failed check, and it reached stage 12). Boxes 4 and 5 wait for the first deploy from `main` and the Log Analytics query, box 6 for ticket 15, and box 8 for a day of billing.

### 2026-10-02: first deploy, OIDC subject fixed

The first deploy from `main` (CI run 37052388148, job `deploy`) failed at `azure/login` with `AADSTS700213: No matching federated identity record found for presented assertion subject 'repo:KOFlynn@6141875/cv-reformatter@1367290670:ref:refs/heads/main'`. This repository uses GitHub's immutable OIDC subject format (`gh api repos/KOFlynn/cv-reformatter/actions/oidc/customization/sub` returns `use_immutable_subject: true` and the prefix `repo:KOFlynn@6141875/cv-reformatter@1367290670`), and the wizard had built the legacy name-only subject.

The maintainer fixed Azure by hand: the federated credential `github-main` on `cvr-github-deploy` now has the immutable subject. The decision is to keep the immutable format and make Azure match it: the owner and repo ids pin the trust to this account and repository, so a renamed account or a recreated repository cannot inherit deploy rights.

The `deploy` job was re-run and passed: the image for `666adae` was deployed, the app woke in 22 s on a new revision, `/reformat` returned 200 with a 39,164-byte `.docx`, and `X-Run-Id` was `93a1193cc39f444584be845e4de92f4b`.

Repo change (branch `phase-1/14-oidc-immutable-subject`): `scripts/provision-azure.sh` reads `sub_claim_prefix` from GitHub in stage 2 (legacy fallback with a warning, recomputed every run so a remembered `.env.azure` value never wins) and stage 9 updates an existing `github-main` whose subject differs instead of skipping it. ADR-0010, `docs/development.md` and `CLAUDE.md` record the immutable subject; `tests/ci/test_provision_script.py` pins the wizard's behaviour.

### 2026-10-02: scale to zero and Log Analytics, boxes 4 and 5

**Box 4, scale to zero and wake.** The maintainer left the app idle after the deploy, then timed two `/health` requests from the dev machine:

```
$ time curl -s https://cvr-ca.orangewave-5499e0c7.northeurope.azurecontainerapps.io/health
{"status":"ok"}
real    0m25.883s
$ time curl -s https://cvr-ca.orangewave-5499e0c7.northeurope.azurecontainerapps.io/health
{"status":"ok"}
real    0m0.194s
```

The first answer took 25.9 s, a cold start from zero replicas; the second, 0.19 s, warm. That is the cold start ADR-0010 tells a presenter to warm before a demo.

**Box 5, the run id in Log Analytics.** The query the smoke step printed, run against `cvr-log` through the Log Analytics REST API (`az rest`, since `az monitor log-analytics query` needs an extension), returned one row:

| TimeGenerated | RevisionName_s |
|---|---|
| 2026-10-02T19:25:15.947Z | `cvr-ca--1to8q6e` |

```json
{"run_id":"93a1193cc39f444584be845e4de92f4b","line":"summary","status":200,"label":{"config":{"provider":"anthropic","model":"claude-opus-5-5","effort":"medium","temperature":null,"extra":{}},"prompt_version":"1.1.0","prompt_hash":"9b688aca3f8c5fa0","schema_version":"1.0.0","schema_hash":"3ee02723787bc1ee","content_hash":"0aa170e08b7ff5ca","input_tokens":5386,"output_tokens":2439,"cost_usd":0.070324,"label_failed":false,"failure_reason":null},"label_failed":false,"blocks":54,"images":[],"removals":14,"normalisations":0,"residue":3,"unplaced":0,"dates":10,"splits":0}
```

The `X-Run-Id` the smoke step received through ingress is the run id of the app's summary line. Boxes 4 and 5 are ticked. Box 6 waits for ticket 15, box 8 for a day of billing.

### 2026-10-02: box 6, a red `eval` blocks `deploy`

Proven by ticket 15's demo PR #32. On [run 37061731804](https://github.com/KOFlynn/cv-reformatter/actions/runs/37061731804), `check` passed, `eval` failed (`pii_leak` and tunable precision) and `deploy` was skipped. `deploy` needs `eval` and runs on `push` to `main` only, so a red gate stops it either way. Box 6 is ticked. Box 8 (the cost after the first day) is the one left.

### 2026-10-06: box 8, the cost after the first day

The subscription `cvr_sub` had been billing since provisioning on 2026-10-01. Cost Management's query API (`az rest` to `Microsoft.CostManagement/query`), actual cost and usage from 2026-10-01 to 2026-10-06, grouped by resource group, meter category and meter:

| Date | Resource group | Meter | Usage | Cost |
|---|---|---|---|---|
| 2026-10-01 | `cvr-rg` | Log Analytics, Analytics Logs Data Ingestion | 0.000072 GB | €0.00 |
| 2026-10-02 | `cvr-rg` | Log Analytics, Analytics Logs Data Ingestion | 0.000325 GB | €0.00 |
| **Total** | | | | **€0.00** |

Those are the only rows. The logs are about 0.4 MB against Log Analytics' free 5 GB a month. Container Apps reported no metered usage at all, which fits a consumption-plan app that scales to zero, staying inside the monthly free grant across the deploy, the smoke tests and the scale-to-zero checks; the query shows only that nothing was charged, not the grant's arithmetic. There are no rows after 2026-10-02: the app sat idle at zero replicas. The portal budget `cvr_budget` (€50) shows €0.00 spent.

The free-grant budget ADR-0010 plans for holds: an idle demo costs nothing, and the cost of a presentation is the LLM calls, about $0.07 a document. Box 8 is ticked, and with it every box: the ticket is done.
