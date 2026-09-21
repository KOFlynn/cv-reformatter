# 14: Provision and deploy through OIDC

**What to build:** A merge to `main` puts the service on Azure with no Azure secret in GitHub. Provisioning is a one-off through an interactive wizard (the `wizard` skill): resource group, Log Analytics workspace, Container Apps environment, the app itself, the Entra app registration with a federated credential for the repo's `main` branch, and the Container Apps secret holding the LLM key. The `deploy` job needs `eval`, runs on `push` to `main` only, has job-level `id-token: write`, logs in with `azure/login` through the federated credential, builds the image, pushes it to GHCR (the package made public at first deploy, so no registry secret), deploys to the app, then runs a smoke step that posts a golden-set document to the live endpoint and asserts a `.docx` comes back with `X-Run-Id` present, verifying the header survives ingress. Container Apps: consumption plan, external ingress on the service port, min replicas 0, max 1, liveness and readiness probes on `/health`, the key as a Container Apps secret referenced by an environment variable, logs to the workspace. ADR-0010 is written here: public package on a private repo, OIDC, manual provisioning with infrastructure as code as what changes at scale, ACR with managed-identity pull and a managed identity for the LLM path as the Phase 2 upgrade, scale to zero and the cold start it implies (warm the endpoint before presenting: a runbook note, not a config change), and the free-grant budget with "kill anything that costs money".

**Blocked by:** 12 (Dockerfile), 13 (CI eval gate)

**Status:** ready-for-agent

- [ ] Wizard script committed under the docs or scripts area, with the human-only steps and the values it asks for; the resulting resource names and the federated credential subject recorded in the ADR
- [ ] `deploy` job defined as specified; `id-token: write` at job level only; no Azure secret in GitHub
- [ ] GHCR package public; the image pulls anonymously; the ticket 12 secret inspection repeated on the pushed image
- [ ] Container Apps configured as specified; the app scales to zero when idle and serves `/health` on wake
- [ ] Post-deploy smoke step green: `.docx` returned with `X-Run-Id`; the header value appears in a Log Analytics query for the summary line
- [ ] Deployment blocked when `eval` fails (proven in ticket 15, referenced here)
- [ ] ADR-0010 written under `docs/adr/`; README item 7 (ticket 08) updated from plan to fact
- [ ] Cost check after the first day recorded in the PR description
