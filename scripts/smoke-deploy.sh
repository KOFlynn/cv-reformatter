#!/bin/sh
# The post-deploy smoke test (ticket 14): one golden-set document through the
# live endpoint. Wakes the app from zero (timing the cold start), checks that
# /reformat refuses a request without the API key, then posts the document
# with it and asserts a 200, a .docx body and an X-Run-Id header, which
# proves the header survives Container Apps ingress. Prints the run id and the
# Log Analytics query that finds its summary line; under GitHub Actions both
# also go to the job summary. Needs curl; POSIX sh, runs under Git Bash.
# Ingress must be open (the deploy job opens it; by hand, scripts/demo.sh up).
#
#   CVR_API_KEY=... sh scripts/smoke-deploy.sh https://<app>.<env>.northeurope.azurecontainerapps.io
#
# Calls the real model once (one document, a few cents).
set -eu
cd "$(dirname "$0")/.."

URL=${1:?usage: sh scripts/smoke-deploy.sh https://<fqdn>}
URL=${URL%/}
: "${CVR_API_KEY:?set CVR_API_KEY, the key /reformat requires as X-API-Key}"
DOC=fixtures/generated/c04__single-column.docx
WAKE_SECONDS=${WAKE_SECONDS:-180}
DOCX_MEDIA_TYPE=application/vnd.openxmlformats-officedocument.wordprocessingml.document
fail() { echo "FAIL: $*"; exit 1; }

# Under the gitignored .cache/, a relative path: curl under Git Bash then
# needs no path translation for -o, -D or -H @file.
mkdir -p .cache
work=$(mktemp -d .cache/smoke.XXXXXX)
trap 'rm -rf "$work"' EXIT
# The key reaches curl through a private file (-H @file), never the command
# line, where it would show in the process list.
(umask 077 && printf 'X-API-Key: %s\n' "$CVR_API_KEY" > "$work/key-header")

echo "== wake $URL"
# Scaled to zero, the first request waits on a replica starting; ingress
# holds it, so each attempt gets a generous timeout before the next.
start=$(date +%s)
until curl -fsS --max-time 60 -o /dev/null "$URL/health"; do
  elapsed=$(($(date +%s) - start))
  [ "$elapsed" -lt "$WAKE_SECONDS" ] || fail "no /health after ${elapsed}s"
  sleep 5
done
echo "/health answered after $(($(date +%s) - start))s"

echo "== reformat without the key"
status=$(curl -sS --max-time 60 -o /dev/null -w '%{http_code}' \
  -F "file=@$DOC" "$URL/reformat") \
  || fail "curl exited $? posting $DOC without the key"
[ "$status" = 401 ] || fail "/reformat without X-API-Key answered $status, not 401"
echo "refused: $status"

echo "== reformat $DOC"
status=$(curl -sS --max-time 240 -o "$work/out.docx" -D "$work/headers" \
  -w '%{http_code}' -H "@$work/key-header" -F "file=@$DOC" "$URL/reformat") \
  || fail "curl exited $? posting $DOC"
cat "$work/headers"
echo "status $status, $(wc -c < "$work/out.docx") bytes"
[ "$status" = 200 ] || fail "/reformat answered $status"
grep -qi "^content-type: $DOCX_MEDIA_TYPE" "$work/headers" || fail "not a .docx content type"
[ "$(head -c 2 "$work/out.docx")" = PK ] || fail "the body is not a .docx (zip) file"
run_id=$(grep -i '^x-run-id:' "$work/headers" | head -n 1 | cut -d: -f2 | tr -d ' \r')
[ -n "$run_id" ] || fail "no X-Run-Id: the header did not survive ingress"

query="ContainerAppConsoleLogs_CL | where Log_s has '$run_id' and Log_s has '\"line\":\"summary\"' | project TimeGenerated, RevisionName_s, Log_s"
echo "run id $run_id"
echo "Log Analytics (a few minutes after the request): $query"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Smoke test: $URL"
    echo
    echo "\`/reformat\` answered 200 with a .docx and \`X-Run-Id: $run_id\`."
    echo
    echo "The summary line in Log Analytics (allow a few minutes for ingestion):"
    echo
    echo '```'
    echo "$query"
    echo '```'
  } >> "$GITHUB_STEP_SUMMARY"
fi
echo "== ok"
