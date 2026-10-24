# 22: Langfuse Environment field

**What to build:** pass Langfuse's native environment (`eval`, `prod` or `local`) when the client is created, from the same source as the `env=` tag: the eval always `eval`, the API from `CVR_TRACE_ENV` (the existing validation, default `local`). Keep the tag. In the installed langfuse 5.0.4 the parameter is `Langfuse(environment=...)`, also read from the `LANGFUSE_TRACING_ENVIRONMENT` environment variable; the value must be lowercase alphanumeric with hyphens and underscores and must not start with `langfuse` (`eval`, `prod`, `local` all qualify). Prefer the constructor argument over the environment variable, so the value has one source in our code and a stray variable in the shell cannot override the eval's `eval`.

Why: on 2026-10-24 the maintainer reached for the Environment filter in Langfuse first and found only `default`. The spec's "tagged `env=eval`" had been implemented as a tag alone, so the 48 traces of the first traced eval carry the tag but not the environment.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Tests show the API's traces (from `CVR_TRACE_ENV`) and the eval's traces carry the environment as well as the tag, through the injected exporter
- [ ] The canary leak test (`tests/tracing/test_canary_leak.py`) stays green
- [ ] The next eval's traces appear under the Environment filter in Langfuse (noted on this ticket by the maintainer)
- [ ] `docs/development.md` and CLAUDE.md's `tracing` entry say the environment is set natively as well as tagged

## Comments
