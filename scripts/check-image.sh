#!/bin/sh
# Builds the service image and checks it the way ticket 12 asks: size, what
# is (not) in it, the user it runs as, no key in its history or filesystem,
# and a running container answering /health, refusing /reformat without
# X-API-Key, and reformatting a golden-set document with it (the key is a
# random one per run). Needs Docker and curl; POSIX sh, runs under Git Bash.
#
#   sh scripts/check-image.sh              # /reformat skipped without a key
#   ANTHROPIC_API_KEY=... sh scripts/check-image.sh
#   IMAGE=ghcr.io/koflynn/cv-reformatter:<tag> PULL=1 sh scripts/check-image.sh
#
# PULL=1 checks a published image instead of building one: it is pulled with
# whatever registry login the shell has (none, after `docker logout ghcr.io`,
# which is how the deploy job proves the package is public).
#
# The /reformat step calls the real model once (one document, a few cents).
# Paste the output into the PR description; it never prints the key.
set -eu
cd "$(dirname "$0")/.."
# Git Bash would otherwise rewrite the container paths below into Windows ones.
export MSYS_NO_PATHCONV=1

IMAGE=${IMAGE:-cvr:local}
PORT=${PORT:-8000}
DOC=fixtures/generated/c04__single-column.docx
NAME=cvr-check-$$
fail() { echo "FAIL: $*"; exit 1; }

if [ "${PULL:-}" = 1 ]; then
  echo "== pull"
  docker pull "$IMAGE" || fail "$IMAGE does not pull (is the package public?)"
else
  echo "== build"
  docker build -t "$IMAGE" .
fi

echo "== size"
docker image ls "$IMAGE" --format '{{.Repository}}:{{.Tag}} {{.Size}}'

echo "== user"
uid=$(docker run --rm --entrypoint id "$IMAGE" -u)
echo "uid $uid"
[ "$uid" != 0 ] || fail "runs as root"

echo "== absent from the image"
docker run --rm --entrypoint sh "$IMAGE" -c '
  status=0
  for p in /app/src/cvr/golden /app/src/cvr/eval /app/fixtures /app/tests \
           /app/.git /app/.env /app/.cache /app/eval /app/.scratch /app/.claude; do
    if [ -e "$p" ]; then echo "present: $p"; status=1; fi
  done
  found=$(find / -xdev \( -name ".env" -o -name ".git" -o -name "eval-responses" \) -print 2>/dev/null)
  [ -z "$found" ] || { echo "present: $found"; status=1; }
  find /app -maxdepth 3 -not -path "/app/.venv/*" | sort
  exit $status' || fail "a path that must not be in the image is"
for module in cvr.golden cvr.eval; do
  docker run --rm "$IMAGE" python -c "import $module" 2>/dev/null \
    && fail "$module imports" || echo "$module: not importable"
done

work=$(mktemp -d)
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -rf "$work"' EXIT

echo "== no key in the history or the filesystem"
# A key-shaped string (prefix plus a long body), and the key itself if set;
# the key goes to grep through a private file, not on its command line.
PATTERN='sk-ant-[A-Za-z0-9]+-[A-Za-z0-9_-]{20,}'
hist=$(docker history --no-trunc "$IMAGE" | grep -cE "$PATTERN" || true)
echo "docker history --no-trunc $IMAGE | grep -cE '$PATTERN': $hist"
container=$(docker create "$IMAGE")
fs=$(docker export "$container" | grep -acE "$PATTERN" || true)
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  (umask 077 && printf '%s\n' "$ANTHROPIC_API_KEY" > "$work/key")
  literal=$(docker export "$container" | grep -acFf "$work/key" || true)
  rm -f "$work/key"
else
  literal="not checked (no key set)"
fi
docker rm "$container" >/dev/null
echo "docker export | grep -acE '$PATTERN': $fs; the key itself: $literal"
[ "$hist" = 0 ] && [ "$fs" = 0 ] || fail "a key-shaped string is in the image"
[ "$literal" = 0 ] || [ -z "${ANTHROPIC_API_KEY:-}" ] || fail "the key is in the image"

echo "== run"
# /reformat needs X-API-Key to equal the container's CVR_API_KEY: a fresh
# random key per run, passed through the environment, never printed.
API_KEY=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')
# No --rm: if /health never answers, the container's logs are still there.
CVR_API_KEY=$API_KEY docker run -d --name "$NAME" -p "$PORT:8000" \
  -e ANTHROPIC_API_KEY -e CVR_API_KEY "$IMAGE" >/dev/null
i=0
until curl -fs "http://127.0.0.1:$PORT/health" >/dev/null; do
  i=$((i + 1))
  [ "$i" -lt 30 ] || { docker logs "$NAME"; fail "no /health after 30s"; }
  sleep 1
done
curl -si "http://127.0.0.1:$PORT/health"; echo

echo "== /reformat without the key"
# Refused from the headers, so no model call: checked with or without a key.
status=$(curl -s -o /dev/null -w '%{http_code}' -F "file=@$DOC" \
  "http://127.0.0.1:$PORT/reformat") || fail "curl exited $? posting $DOC"
echo "status $status"
[ "$status" = 401 ] || fail "/reformat without X-API-Key answered $status, not 401"

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  # Git Bash's curl is a Windows program and MSYS_NO_PATHCONV stops the
  # /tmp path being translated for it, so it gets a Windows form of the path.
  out=$work
  if command -v cygpath >/dev/null 2>&1; then out=$(cygpath -m "$work"); fi
  status=$(curl -s -o "$out/out.docx" -D "$out/headers" -w '%{http_code}' \
    -H "X-API-Key: $API_KEY" -F "file=@$DOC" "http://127.0.0.1:$PORT/reformat") \
    || fail "curl exited $? posting $DOC"
  cat "$work/headers"
  echo "status $status, $(wc -c < "$work/out.docx") bytes"
  [ "$status" = 200 ] || fail "/reformat answered $status"
  grep -qi '^x-run-id:' "$work/headers" || fail "no X-Run-Id"
  # A labelling failure is also a 200 (the banner document); the summary
  # line says whether the model's labelling was used.
  summary=$(docker logs "$NAME" 2>/dev/null | grep -F '"label_failed":' | head -n 1)
  echo "$summary" | cut -c1-400
  case $summary in
    *'"label_failed":false'*) ;;
    *) fail "the labelling failed, or no summary line was logged" ;;
  esac
else
  echo "/reformat skipped: set ANTHROPIC_API_KEY to post $DOC"
fi
echo "== ok"
