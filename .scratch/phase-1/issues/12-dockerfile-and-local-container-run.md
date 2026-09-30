# 12: Dockerfile and local container run

**What to build:** The service as an image that runs under Docker Desktop and is safe to publish. Multi-stage build on the pinned Python slim base; `uv sync --locked --no-dev`; a non-root user; `.dockerignore` excluding `.git`, the golden and eval packages, fixtures, tests, environment files, the response cache and any other local cache, so the public image carries only the service. The LLM key is a runtime environment variable only, never a build argument and never in a layer; before ticket 14 makes the package public, the built image's layers and filesystem are inspected for secrets and the check is recorded. The container answers `/health` and reformats a golden-set document with the key passed at `docker run`.

**Blocked by:** 11 (The API)

**Status:** done

- [x] `Dockerfile` and `.dockerignore` at the repo root; image builds locally with `docker build`
- [x] The image contains neither `cvr.golden` nor `cvr.eval`, nor `fixtures/`, `tests/`, `.git`, `.env` or the cache directory (asserted by listing the final layer)
- [x] Runs as a non-root user; exposes the service port; `docker run` with the key as `-e` serves `/health` and reformats a document
- [x] No build argument carries a key; a layer inspection (history plus filesystem grep for the key prefix) finds nothing; the command and its output are in the PR description
- [x] Image size recorded in the PR description
- [x] `docs/development.md` gains build and run instructions

## Comments

### 2026-09-25: written, in review, not yet built (branch `phase-1/12-dockerfile-and-local-container-run`)

**Docker is not installed on the machine this was written on.** No image has been built, run or inspected. The first five boxes stay unticked until the maintainer runs the commands under "Pending on Docker" and pastes the output into the PR. Nothing below claims a build result.

**What was built.**
- `Dockerfile`, two stages, both on `python:3.12-slim` (the version in `.python-version`):
  - the builder copies uv from `ghcr.io/astral-sh/uv:0.10.11` (the local uv, inside `uv_build`'s `<0.11` bound);
  - it runs `uv sync --locked --no-dev --no-install-project` on `pyproject.toml`, `uv.lock` and `.python-version` first, then copies `src/` and runs `uv sync --locked --no-dev`, then `compileall`;
  - the runtime stage copies `.venv`, `src/` and the template into `/app`, sets `CVR_API_HOST=0.0.0.0` and `CVR_API_PORT=8000`, runs as the non-root user `cvr` (uid 10001), `EXPOSE 8000`, and has `CMD ["python", "-m", "cvr.api"]`;
  - there is no `ARG`.
- `.dockerignore`.
- `scripts/check-image.sh`.
- `.gitattributes` (`*.sh text eol=lf`).
- `tests/docker/` (51 tests, default suite):
  - `test_dockerfile.py` reads the Dockerfile instruction by instruction. It checks multi-stage, the base matches `.python-version`, uv comes from a pinned image, every sync is `--locked --no-dev` with dependencies first, no `ARG` or `ENV` name looks like a secret and no `sk-ant-` appears, the last `USER` is non-root and precedes `CMD`, host `0.0.0.0` and `EXPOSE` equal the port, and the template is copied.
  - `test_dockerignore.py` applies Docker's matching rules (last match wins, a matched directory excludes its contents, `*` stops at `/`, `**` crosses it) in both directions. Every path the ticket lists is left out: `.git`, `src/cvr/golden`, `src/cvr/eval`, `fixtures/`, `tests/`, `.env*`, 09's `.cache/eval-responses/`, `eval/`, `.scratch/`, `.claude/`, `.venv`, the tool caches, bytecode and docs. Every git-tracked runtime file under `src/`, plus the template and the project files, is sent.
  - `test_runtime_imports.py` starts a fresh interpreter in which `cvr.golden` and `cvr.eval` raise on import. It imports `cvr.api.__main__` and posts a golden-set document through the app with a stand-in labeller that fails, so parse, verify, transform and render all run, with every block in the appendix. It then asserts neither package was loaded.
- `docs/development.md` gains "Running the API in a container".
- `CLAUDE.md` gains the image entry, the commands and the layout.

**Decisions beyond the ticket text.**
- **`.dockerignore` is an allowlist.** It starts with `*` and re-includes only `pyproject.toml`, `uv.lock`, `.python-version`, `src/` and `templates/fictitious_recruitment.docx`. It then excludes `src/cvr/golden/`, `src/cvr/eval/`, `**/.env*`, bytecode and `*.egg-info` again, even under `src/`. A denylist would have to anticipate every new cache or report. An allowlist keeps them out by default, and 09's `.cache/` is out without being named. The test still names each path the ticket lists.
- **The project is installed editable.** That is uv's default, and the image keeps it on purpose. `cvr.template.paths` finds the template as `parents[3] / "templates"`, relative to the source tree. `/app` therefore keeps the repo's layout (`/app/src`, `/app/templates`), and the venv's `.pth` points at `/app/src`. A non-editable wheel would put `cvr` in site-packages and the template path would break. Making the template package data would be a `template` change, and it isn't needed. Checked without Docker by rehearsing the build context in a temp directory: only the allowlisted files, with golden and eval removed. There, `uv sync --locked --no-dev` installed no pytest, ruff or cvr copy. `cvr.api` imported with neither package, `TEMPLATE_PATH` resolved and existed, and `python -m cvr.api` with no key answered `/health` 200 with `X-Run-Id`. That was on Windows with Python 3.12, not in the image.
- **Files are owned by root and read-only to `cvr`.** Nothing on the service path writes to disk. Bytecode is compiled at build time (`UV_COMPILE_BYTECODE` for site-packages, `compileall` for the editable `src/`), and `PYTHONDONTWRITEBYTECODE=1` is set.
- **`scripts/check-image.sh` is committed.** The ticket wants the inspection command and its output in the PR. A script makes the check repeatable, before ticket 14 makes the package public and after any Dockerfile change, and it is about ninety lines of POSIX sh. It does the following:
  - builds `cvr:local` and prints its size;
  - asserts the uid is not 0;
  - asserts `/app/src/cvr/golden`, `/app/src/cvr/eval`, `/app/fixtures`, `/app/tests`, `/app/.git`, `/app/.env`, `/app/.cache`, `/app/eval`, `/app/.scratch` and `/app/.claude` are absent, that no `.env`, `.git` or `eval-responses` exists anywhere on the filesystem, and lists `/app`;
  - asserts `import cvr.golden` and `import cvr.eval` fail;
  - greps `docker history --no-trunc` and `docker export` (the flattened final filesystem) for a key-shaped string. When `ANTHROPIC_API_KEY` is set it also greps for the key itself, read from a private temp file rather than argv;
  - runs the container with `-e ANTHROPIC_API_KEY`, waits for `/health` and prints it;
  - with a key, posts `fixtures/generated/c04__single-column.docx` to `/reformat`, asserts 200 and `X-Run-Id`, and asserts that the logged summary line has `"label_failed":false`, since a labelling failure is also a 200.

  The key pattern is `sk-ant-<kind>-<20+ chars>`, not the bare prefix. A bare `sk-ant-` could match placeholder strings in a dependency's docs; a real key cannot hide from the shaped pattern or the literal grep.
- **`docker export` is the flattened final filesystem, not each layer.** A file added in one layer and deleted in a later one would not show. No step here copies a secret at all: there is no `ARG`, and `.env*` never reaches the build context. `docker history --no-trunc` covers the recorded build commands and `ENV`.
- **Build cache mounts.** `RUN --mount=type=cache,target=/root/.cache/uv` needs BuildKit, which is the default in Docker Desktop and in `docker/build-push-action`.

**Pending on Docker (maintainer).** From the repo root in Git Bash, with Docker Desktop running:

```
sh scripts/check-image.sh                              # everything but /reformat, no key needed
ANTHROPIC_API_KEY=sk-ant-... sh scripts/check-image.sh  # plus one /reformat (one document, a few cents)
```

The script is equivalent to:

```
docker build -t cvr:local .
docker image ls cvr:local                              # size -> PR description
docker run --rm --entrypoint id cvr:local -u           # not 0
docker run --rm --entrypoint sh cvr:local -c 'ls -la /app /app/src/cvr; ls /app/src/cvr/golden /app/src/cvr/eval /app/fixtures /app/tests /app/.git /app/.env /app/.cache 2>&1'
docker history --no-trunc cvr:local | grep -cE 'sk-ant-[A-Za-z0-9]+-[A-Za-z0-9_-]{20,}'      # 0
docker export $(docker create cvr:local) | grep -acE 'sk-ant-[A-Za-z0-9]+-[A-Za-z0-9_-]{20,}'  # 0
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY cvr:local
curl -i http://127.0.0.1:8000/health
curl -F "file=@fixtures/generated/c04__single-column.docx" -D - -o out.docx http://127.0.0.1:8000/reformat
```

Once it passes, tick the first five boxes and put the script's output, which includes the history and filesystem grep commands and their counts plus the image size, in the PR description.

**Code review (`code-review` skill, against `origin/release/phase-1-09-11`).**

Standards: no hard violations. Fixed:
- the non-root test's "nothing after the last `USER`" check was true by definition; it now asserts `CMD` comes after the last `USER`;
- the Dockerfile parser ended a continuation at a blank line, which Docker skips;
- the needed-files check walked the working tree, so a stray local `.pyc` or `.env` under `src/` would fail it; it now reads `git ls-files`;
- the exclusion predicate was duplicated in the runtime-import script;
- `check-image.sh` had `--rm` on the run, so a failed `/health` lost the logs; it put the key in grep's argv; and its temp directory leaked.

Left as judgement calls:
- the golden/eval pair is named in four places (`.dockerignore`, two tests, the script); the tests fail if the first three disagree;
- `REPO_ROOT` is repeated across the three test files, as it is elsewhere in `tests/`;
- the image is described in both `CLAUDE.md` and `docs/development.md`, as every package is;
- `tests/docker/` mirrors no package; it is listed in CLAUDE.md's layout.

Spec: no missing requirement beyond the Docker-dependent boxes. Fixed:
- the script probed only `cvr.golden`; it now probes `cvr.eval` too;
- a 200 from `/reformat` did not prove the model labelled anything; it now requires `"label_failed":false` on the summary line.

Recorded above: the key-shaped pattern rather than the bare prefix, the filesystem listing rather than a per-layer listing, and the test's own matcher standing in for Docker's until a real build runs. Scope: `.gitattributes` and `tests/docker/` were judged justified.

**Tests.** Default suite: 1107 passed, 1 skipped (the labeller spike, no key), about 25s; `tests/docker/` is 51 of them. Slow suite: 865 passed, about 36s. Ruff check and format check clean. All figures are from the feature branch before merging.

### 2026-09-29: built and checked on the dev machine

Docker Desktop (WSL2 engine) on Windows 11. `sh scripts/check-image.sh` run twice from Git Bash, without and with `ANTHROPIC_API_KEY`. The first five boxes are ticked on that evidence; the full output goes in the release PR description.

- **Build:** `cvr:local` builds; **image size 325 MB**.
- **User:** uid 10001 (`cvr`), not root.
- **Absent paths:** none present. `/app` lists only `.venv`, `src/cvr/{api,label,models,parse,pipeline,render,template,text,transform,verify}` and `templates/fictitious_recruitment.docx`. `cvr.golden` and `cvr.eval` are not importable.
- **Key inspection:** `docker history --no-trunc cvr:local | grep -cE 'sk-ant-[A-Za-z0-9]+-[A-Za-z0-9_-]{20,}'`: **0**. `docker export | grep -acE` (same pattern): **0**. The key itself, grepped from a private file: **0**.
- **Run:** `/health` 200 with `X-Run-Id`. `/reformat` with `c04__single-column.docx`: 200, `Content-Disposition: attachment; filename="c04__single-column-reformatted.docx"`, `X-Run-Id`, 39,164 bytes. The summary line has `"label_failed":false` (`claude-opus-5-5`, effort medium, prompt 1.0.0, 5,221 in / 2,302 out tokens, $0.0669). `== ok`.

**A bug found and fixed in the script (`ff6cd32`).** The first keyed run stopped silently after `/health`. `MSYS_NO_PATHCONV=1`, set so Git Bash leaves container paths alone, also stops the `mktemp` path being translated for Git Bash's curl, which is a Windows program. curl exited 23 (write error) on `-o "$work/out.docx"`, and `set -e` ended the script without a `FAIL:` line. Reproduced outside Docker, and confirmed by the same request succeeding by hand with relative paths. curl now gets the directory in its Windows form (`cygpath -m` when present), and a curl failure fails with its exit code. `tests/docker/` still passes (51).
