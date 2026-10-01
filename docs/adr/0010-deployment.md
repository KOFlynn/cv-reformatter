# The service is deployed to Azure Container Apps by a job that signs in through OIDC, from a public image, onto resources provisioned once by hand

The brief (§9) asks for a real deployment behind a real gate: a merge to `main` that passed the eval goes to Azure, and one that failed it never does. This ADR records how the code reaches the cloud, what holds a credential and what does not, and which shortcuts a deployment at scale would undo.

**The `deploy` job.** It is the third job of `ci.yml`, after `check` and `eval`. It `needs: eval` and runs only on a `push` to `main`. A pull request never deploys, and nothing deploys when `eval` failed or was skipped. The job:

1. builds the image and pushes it to GHCR tagged with the commit sha, so every revision names the exact source it runs;
2. logs out of GHCR, pulls the image back anonymously and repeats ticket 12's inspection on it (`PULL=1 sh scripts/check-image.sh`). The inspection checks that no key-shaped string is in the history or filesystem, that neither `cvr.golden` nor `cvr.eval` is in the image, and that `/health` answers;
3. signs in to Azure with `azure/login` through OIDC;
4. moves the container app to the new image (`az containerapp update --image`), which creates a new revision; everything else stays as provisioned;
5. runs the smoke test, `scripts/smoke-deploy.sh`. It wakes the app from zero, timing the cold start, and posts `c04__single-column.docx` to the live `/reformat`. It asserts a 200, a `.docx` body and an `X-Run-Id` header. That proves the run id survives Container Apps ingress, an assumption until this step is green. The run id and the Log Analytics query that finds its summary line go into the job summary.

**OIDC, and no Azure secret in GitHub.** `id-token: write` is granted to `deploy` alone, at job level; the workflow's default stays `contents: read`. The job asks GitHub for a short-lived OIDC token, and Entra exchanges it for an Azure access token. Entra trusts the token because the app registration `cvr-github-deploy` has one federated credential, `github-main`, with:

- issuer `https://token.actions.githubusercontent.com`;
- audience `api://AzureADTokenExchange`;
- subject `repo:KOFlynn/cv-reformatter:ref:refs/heads/main`.

A token from any other branch, from a pull request or from a fork has a different subject and is refused. The registration has no client secret and no certificate.

The three ids `azure/login` reads (client, tenant, subscription) are **repository variables, not secrets**. Microsoft's guide suggests secrets. They are identifiers, not credentials: knowing them opens nothing without a token whose subject is this repository's `main`. Storing them as variables keeps "no Azure secret in GitHub" literally true and checkable: `gh secret list` shows `ANTHROPIC_API_KEY` alone. `tests/ci/test_workflow.py` pins the rest of this paragraph: no `secrets.*AZURE*` reference anywhere, no `client-secret` or `creds`, `id-token` on `deploy` only, and `azure/login` fed from `vars.*`.

The service principal holds **Contributor on the resource group `cvr-rg` only**: it can update the app and read its logs, and it has no rights anywhere else in the subscription.

**A public package on a private repository.** The image is in GHCR (`ghcr.io/koflynn/cv-reformatter`), and the package is public from the first deploy. The repository itself goes public only at the end of Phase 1 (ticket 16). The package is public so that Container Apps pulls with no registry credential: no PAT and no registry password stored as a Container Apps secret. The workflow pushes with its own job token (`packages: write`) and needs nothing else.

The cost of that choice is that anyone can pull the image, so the image must be safe to publish. That safety rests on three things:

- `.dockerignore` is an allowlist (ticket 12), so the build context never holds `.git`, fixtures, tests, the eval cache or any `.env`;
- the key is a runtime environment variable only, never a build argument and never in a layer;
- the deploy job repeats the secret inspection on every pushed image, after an anonymous pull. A pull that needs credentials fails the job, so a package that has gone private stops the deploy instead of breaking the app.

The first image, `:bootstrap`, was pushed from the maintainer's machine by the provisioning wizard, because the app cannot be created before an image exists, and the package was made public by hand: GitHub offers no API for package visibility.

**Container Apps, configured once.** The resources, all in `northeurope` (Dublin):

| Resource | Name | Notes |
|---|---|---|
| Resource group | `cvr-rg` | Holds everything below; deleting it removes the deployment. |
| Log Analytics workspace | `cvr-log` | 30-day retention. |
| Container Apps environment | `cvr-cae` | Consumption only (no workload profiles); logs to `cvr-log`. |
| Container app | `cvr-ca` | See the configuration below. |
| Entra app registration | `cvr-github-deploy` | Federated credential `github-main`; Contributor on `cvr-rg`. |
| Container registry | GHCR, `ghcr.io/koflynn/cv-reformatter` | Public package. |

The container app is configured as follows:

- external ingress on port 8000 (the image's `CVR_API_PORT`), single-revision mode;
- **min replicas 0, max 1**;
- 0.5 vCPU and 1 GiB per replica;
- liveness and readiness probes on `/health` (port 8000; readiness every 10 s, liveness every 30 s, both after 5 s). `/health` never touches the labeller, so a probe can neither spend money nor fail on a provider outage;
- `ANTHROPIC_API_KEY` read from the Container Apps secret `anthropic-api-key`. It is the app's own key, separate from the repository secret the eval uses, so either can be revoked alone;
- console output (the API's summary and per-block JSON lines) goes to `cvr-log`. `ContainerAppConsoleLogs_CL | where Log_s has '<run id>'` finds a request's lines.

One replica at most suits the API, which serialises documents anyway because the labeller keeps `last_run` on itself (ticket 11). A second replica would add cost and nothing else.

**Provisioned by hand, through a wizard.** `scripts/provision-azure.sh` walks the maintainer through all of the above in twelve stages, with a confirmation before anything is created:

1. sign in to Azure;
2. confirm names and region;
3. create the resource group and workspace;
4. create the environment;
5. push the bootstrap image;
6. make the package public and grant the repo's Actions write access, then pull it anonymously and inspect it;
7. create the app (the key is typed hidden, written into a private temp YAML spec and deleted after; it never appears on a command line);
8. smoke test;
9. create the Entra app, its service principal, role assignment and federated credential;
10. set the GitHub variables;
11. set a cost budget;
12. print the record.

Every Azure call is a plain `az` command in that script, so the script is the record of what exists. It is re-runnable: names are remembered in the gitignored `.env.azure`, which holds no secret, and every create step skips what is already there.

Manual provisioning is a shortcut. For one app in one region with one maintainer, a script someone reads before running is cheaper than a Bicep or Terraform module, its state and the CI identity it would need. At scale it is the first thing to change (README item 9): infrastructure as code, applied by the pipeline under its own federated identity. Drift would then be a diff instead of a surprise, a second environment would cost one parameter file, and review of an infrastructure change would be a pull request.

**Phase 2 upgrades, recorded here so they are not mistaken for oversights:**

- **ACR with managed-identity pull** replaces the public GHCR package. The image becomes private again, and the app pulls it with its own identity, still without a registry secret.
- **A managed identity for the LLM path.** When Azure OpenAI is added as the second provider, the app reaches it through the app's managed identity, so that path holds no key at all. The Anthropic key stays a Container Apps secret for as long as Anthropic is a provider.

**Scale to zero, and the cold start it implies.** With min replicas 0 the app costs nothing while idle. The first request after a quiet spell waits for a replica to start: the image is pulled if the node does not have it, Python starts, and the app is ready when `/health` first answers. The smoke step prints this wake time on every deploy. A demo does not change the configuration to hide it. **Runbook: warm the endpoint before presenting** (`curl https://<app url>/health` a minute before) and let the replica's own idle timeout scale it back down afterwards.

**The free-grant budget, and "kill anything that costs money".** The target is to stay inside free allowances:

- **Container Apps consumption:** 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests a month per subscription (Azure pricing page, checked 2026-10-01). At 0.5 vCPU and 1 GiB that is about 100 active replica-hours a month.
- **Log Analytics:** this app writes a few KB per request.
- **GHCR:** free for a public package.

The live cost is the LLM, about $0.07 per document. Each merge to `main` spends one live eval run (about $3.3) plus one smoke document. A cost budget on the subscription alerts by email at 50% and 100% actual and at 100% forecast. If it ever fires, the response is to delete, not to investigate while paying: `az group delete -n cvr-rg` removes every billable resource in one command, and the wizard rebuilds them.

**Considered options:**

- A service-principal client secret stored in GitHub (`AZURE_CREDENTIALS`): rejected. It is a long-lived credential in a second place, which is exactly what the brief's "no Azure secret in GitHub" rules out.
- A federated credential on a GitHub environment instead of the branch: deferred. An environment adds approval gates this one-maintainer repository does not use; the branch subject already limits the trust to `main`.
- A private GHCR package with a registry secret in Container Apps: rejected. That is a PAT stored in Azure, and making the package public costs nothing once the image is checked.
- ACR now: deferred to Phase 2. It is not free, and its value is managed-identity pull, which arrives with the other managed-identity work.
- Min replicas 1: rejected. It removes the cold start but bills idle time around the clock, which is not inside the free grant.
- `azure/container-apps-deploy-action`: not used. One `az containerapp update` line is the whole deployment, and it reads plainly in the workflow.

**Consequence:** the only credentials in this system are the two Anthropic keys, one a GitHub secret for the eval and one a Container Apps secret for the service, plus the job token GitHub issues per run. Azure trusts GitHub only through the federated subject for `main`, and the registry trusts no one because the package is public. A degraded prompt that fails `eval` cannot reach `deploy`, because `deploy` needs `eval`. Ticket 15's demo PR is that claim's proof. Everything Azure-side can be rebuilt from one script and torn down with one command.
