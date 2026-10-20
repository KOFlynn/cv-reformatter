# 08: Traces from the API and the eval

**What to build:** real Runs appear in Langfuse Cloud (EU, Hobby, private project). The API builds the client once per process from the environment and passes it to `reformat`. Every response's `X-Run-Id` is the trace id, and every log line keeps carrying the run id. The eval runner traces each document's Run. Traces are tagged `env=prod`, `env=eval` or `env=local`, and eval cache hits are marked cached with zero cost. The keys live in GitHub secrets (the eval job) and Container Apps secrets (the app), never in the image.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] API tests (injected in-memory client) show the response's `X-Run-Id` equal to the exported trace id, and the log lines carrying the same id
- [ ] Eval runner tests show one trace per document with `env=eval`, and a cache hit tagged cached with zero cost
- [ ] With the keys missing, the API and the eval still run, untraced (tested)
- [ ] The CI eval job and the deploy configuration receive the Langfuse keys as secrets; the workflow's static tests cover it
- [ ] The image check is run and pasted (the size added by the OpenTelemetry packages noted); the runtime-import test still holds
- [ ] The maintainer sees one CI eval run's traces in Langfuse (noted on the ticket); usage checked against the Hobby allowance
- [ ] The development docs and CLAUDE.md list the new environment variables
