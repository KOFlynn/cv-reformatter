# 12: Dockerfile and local container run

**What to build:** The service as an image that runs under Docker Desktop and is safe to publish. Multi-stage build on the pinned Python slim base; `uv sync --locked --no-dev`; a non-root user; `.dockerignore` excluding `.git`, the golden and eval packages, fixtures, tests, environment files, the response cache and any other local cache, so the public image carries only the service. The LLM key is a runtime environment variable only, never a build argument and never in a layer; before ticket 14 makes the package public, the built image's layers and filesystem are inspected for secrets and the check is recorded. The container answers `/health` and reformats a golden-set document with the key passed at `docker run`.

**Blocked by:** 11 (The API)

**Status:** ready-for-agent

- [ ] `Dockerfile` and `.dockerignore` at the repo root; image builds locally with `docker build`
- [ ] The image contains neither `cvr.golden` nor `cvr.eval`, nor `fixtures/`, `tests/`, `.git`, `.env` or the cache directory (asserted by listing the final layer)
- [ ] Runs as a non-root user; exposes the service port; `docker run` with the key as `-e` serves `/health` and reformats a document
- [ ] No build argument carries a key; a layer inspection (history plus filesystem grep for the key prefix) finds nothing; the command and its output are in the PR description
- [ ] Image size recorded in the PR description
- [ ] `docs/development.md` gains build and run instructions
