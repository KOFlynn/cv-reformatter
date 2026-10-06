#!/bin/sh
# Opens and closes the live app for a demo (ADR-0010). Ingress is off by
# default: any request through it wakes the app, and the URL is in public
# history. `up` opens it with the provisioned settings and wakes the app
# until /health answers, absorbing the cold start before the audience sees
# it; `down` closes it again. The deploy job closes it after every deploy,
# so a merge during a demo ends the demo.
#
#   sh scripts/demo.sh up   [resource-group] [app]
#   sh scripts/demo.sh down [resource-group] [app]
#
# The names default to the wizard's .env.azure, then to cvr-rg and cvr-ca.
# Needs az (signed in) and curl; POSIX sh, runs under Git Bash.
set -eu
cd "$(dirname "$0")/.."

usage() { echo "usage: sh scripts/demo.sh up|down [resource-group] [app]"; exit 2; }
from_env() { [ -f .env.azure ] && sed -n "s/^$1=//p" .env.azure | tr -d '\r' | tail -n 1; }

ACTION=${1:-}
RG=${2:-$(from_env AZURE_RESOURCE_GROUP || true)}
APP=${3:-$(from_env AZURE_CONTAINER_APP || true)}
RG=${RG:-cvr-rg}
APP=${APP:-cvr-ca}
WAKE_SECONDS=${WAKE_SECONDS:-180}

fqdn() {
  az containerapp show --name "$APP" --resource-group "$RG" \
    --query properties.configuration.ingress.fqdn --output tsv | tr -d '\r'
}

case "$ACTION" in
  up)
    echo "== opening ingress on $APP ($RG)"
    az containerapp ingress enable --name "$APP" --resource-group "$RG" \
      --type external --target-port 8000 --transport auto \
      --only-show-errors --output none
    url="https://$(fqdn)"
    echo "== waking $url"
    start=$(date +%s)
    until curl -fsS --max-time 60 -o /dev/null "$url/health"; do
      elapsed=$(($(date +%s) - start))
      [ "$elapsed" -lt "$WAKE_SECONDS" ] || { echo "FAIL: no /health after ${elapsed}s"; exit 1; }
      sleep 5
    done
    echo "/health answered after $(($(date +%s) - start))s"
    echo
    echo "Live: $url"
    echo "The X-API-Key for /reformat (printed only when you run this):"
    echo "  az containerapp secret show --name $APP --resource-group $RG --secret-name cvr-api-key --query value --output tsv"
    echo "When the demo is over: sh scripts/demo.sh down"
    ;;
  down)
    if [ -z "$(fqdn)" ]; then
      echo "Already closed: $APP has no ingress."
      exit 0
    fi
    echo "== closing ingress on $APP ($RG)"
    az containerapp ingress disable --name "$APP" --resource-group "$RG" \
      --only-show-errors --output none
    [ -z "$(fqdn)" ] || { echo "FAIL: $APP still has an ingress FQDN"; exit 1; }
    echo "Closed: $APP has no ingress; it scales to zero."
    ;;
  *) usage ;;
esac
