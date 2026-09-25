# syntax=docker/dockerfile:1
#
# The service image: `python -m cvr.api` on port 8000, as a non-root user.
#
#   docker build -t cvr .
#   docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY cvr
#
# The LLM key is a runtime environment variable only: no ARG carries it and
# no layer holds it. What the build context may contain is .dockerignore's
# allowlist (never cvr.golden, cvr.eval, fixtures, tests, .git, .env or the
# eval cache); scripts/check-image.sh checks the built image.

# --- builder: the locked, dev-free virtual environment -----------------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /bin/uv

# Compile bytecode at build time (the running user cannot write it), copy
# rather than hard-link out of the uv cache, and use the image's interpreter.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first: this layer is reused until pyproject.toml or uv.lock
# changes.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Then the project itself, installed editable: the template is found relative
# to the source tree (cvr.template.paths), so /app keeps the repo's layout.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev \
    && python -m compileall -q src

# --- runtime: the environment, the source and the template, nothing else -----
FROM python:3.12-slim AS runtime

RUN groupadd --system --gid 10001 cvr \
    && useradd --system --uid 10001 --gid cvr --create-home --shell /usr/sbin/nologin cvr

WORKDIR /app

# Owned by root, read-only to the service user.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY templates/fictitious_recruitment.docx /app/templates/fictitious_recruitment.docx

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CVR_API_HOST=0.0.0.0 \
    CVR_API_PORT=8000

USER cvr

EXPOSE 8000

CMD ["python", "-m", "cvr.api"]
