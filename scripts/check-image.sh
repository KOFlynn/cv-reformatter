#!/bin/sh
# Builds the service image and checks it the way ticket 12 asks: size, what
# is (not) in it, the user it runs as, no key in its history or filesystem,
# and a running container answering /health and reformatting a golden-set
# document. Needs Docker and curl; POSIX sh, runs under Git Bash.
#
#   sh scripts/check-image.sh              # /reformat skipped without a key
#   ANTHROPIC_API_KEY=... sh scripts/check-image.sh
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

echo "== build"
docker build -t "$IMAGE" .

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
docker run --rm "$IMAGE" python -c "import cvr.golden" 2>/dev/null \
  && fail "cvr.golden imports" || echo "cvr.golden: not importable"

echo "== no key in the history or the filesystem"
# A key-shaped string (prefix plus a long body), and the key itself if set.
PATTERN='sk-ant-[A-Za-z0-9]+-[A-Za-z0-9_-]{20,}'
hist=$(docker history --no-trunc "$IMAGE" | grep -cE "$PATTERN" || true)
echo "docker history --no-trunc $IMAGE | grep -cE '$PATTERN': $hist"
container=$(docker create "$IMAGE")
fs=$(docker export "$container" | grep -acE "$PATTERN" || true)
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  literal=$(docker export "$container" | grep -acF "$ANTHROPIC_API_KEY" || true)
else
  literal="not checked (no key set)"
fi
docker rm "$container" >/dev/null
echo "docker export | grep -acE '$PATTERN': $fs; the key itself: $literal"
[ "$hist" = 0 ] && [ "$fs" = 0 ] || fail "a key-shaped string is in the image"
[ "$literal" = 0 ] || [ -z "${ANTHROPIC_API_KEY:-}" ] || fail "the key is in the image"

echo "== run"
docker run -d --rm --name "$NAME" -p "$PORT:8000" -e ANTHROPIC_API_KEY "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
i=0
until curl -fs "http://127.0.0.1:$PORT/health" >/dev/null; do
  i=$((i + 1)); [ "$i" -lt 30 ] || fail "no /health after 30s"; sleep 1
done
curl -si "http://127.0.0.1:$PORT/health"; echo

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  out=$(mktemp -d)
  status=$(curl -s -o "$out/out.docx" -D "$out/headers" -w '%{http_code}' \
    -F "file=@$DOC" "http://127.0.0.1:$PORT/reformat")
  cat "$out/headers"
  echo "status $status, $(wc -c < "$out/out.docx") bytes"
  [ "$status" = 200 ] || fail "/reformat answered $status"
  grep -qi '^x-run-id:' "$out/headers" || fail "no X-Run-Id"
  docker logs "$NAME" 2>&1 | head -c 600; echo
else
  echo "/reformat skipped: set ANTHROPIC_API_KEY to post $DOC"
fi
echo "== ok"
