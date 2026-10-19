#!/bin/sh
# Opens and closes the live app for a demo (ADR-0010). Ingress is off by
# default: any request through it wakes the app, and the URL is in public
# history. `up` opens it with the provisioned settings and wakes the app
# until /health answers, absorbing the cold start before the audience sees
# it; `down` closes it again. Closing ingress deletes the app's only scale
# rule (the HTTP one), so a running replica would never scale down: "off"
# means the latest revision is deactivated, so `up` activates it first and
# `down` deactivates it and checks that no replica runs. The deploy job
# stops the app the same way after every deploy, so a merge during a demo
# ends the demo.
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
STOP_SECONDS=${STOP_SECONDS:-60}

fqdn() {
  az containerapp show --name "$APP" --resource-group "$RG" \
    --query properties.configuration.ingress.fqdn --output tsv | tr -d '\r'
}

revision() {
  az containerapp show --name "$APP" --resource-group "$RG" \
    --query properties.latestRevisionName --output tsv | tr -d '\r'
}

# Whether the revision is active: "true" or "false".
active() {
  az containerapp revision show --name "$APP" --resource-group "$RG" \
    --revision "$1" --query properties.active --output tsv | tr -d '\r'
}

# How many replicas of the revision are Running, as a number ("?" if az fails).
running() {
  n=$(az containerapp replica list --name "$APP" --resource-group "$RG" \
    --revision "$1" --only-show-errors \
    --query "[?properties.runningState=='Running'] | length(@)" \
    --output tsv 2>/dev/null) || n="?"
  echo "${n:-?}" | tr -d '\r'
}

case "$ACTION" in
  up)
    rev=$(revision)
    echo "== activating the latest revision of $APP ($RG)"
    az containerapp revision activate --name "$APP" --resource-group "$RG" \
      --revision "$rev" --only-show-errors --output none
    echo "== opening ingress on $APP"
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
    if [ -n "$(fqdn)" ]; then
      echo "== closing ingress on $APP ($RG)"
      az containerapp ingress disable --name "$APP" --resource-group "$RG" \
        --only-show-errors --output none
      [ -z "$(fqdn)" ] || { echo "FAIL: $APP still has an ingress FQDN"; exit 1; }
    fi
    rev=$(revision)
    if [ "$(active "$rev")" != false ]; then
      echo "== deactivating the latest revision of $APP"
      az containerapp revision deactivate --name "$APP" --resource-group "$RG" \
        --revision "$rev" --only-show-errors --output none
    fi
    # Termination takes a few seconds.
    n=$(running "$rev")
    waited=0
    while [ "$n" != 0 ] && [ "$waited" -lt "$STOP_SECONDS" ]; do
      sleep 5
      waited=$((waited + 5))
      n=$(running "$rev")
    done
    [ "$n" = 0 ] || { echo "FAIL: $n replica(s) of $APP still running after ${waited}s"; exit 1; }
    echo "Stopped: $APP has no ingress, its revision is inactive and no replica is running."
    ;;
  *) usage ;;
esac
