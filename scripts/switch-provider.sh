#!/bin/sh
# Points the live app at Azure OpenAI, or back at its deployed default
# (ticket 19, ADR-0014). `azure` sets the CVR_LABEL_* variables the labeller
# reads (provider, model, effort, endpoint, deployment); there is no key
# variable, the app reaches the account through its managed identity.
# `anthropic` removes them all, so the app is back to the image's defaults
# (Anthropic, Sonnet 5.5 at medium). It prints what it set, never a secret.
#
# An update creates a new revision (single-revision mode), and that revision
# may start a replica. This script does not stop the app: the one copy of the
# stop logic is demo.sh, which must run last. The whole proof is
#
#   sh scripts/switch-provider.sh azure
#   sh scripts/demo.sh up
#   CVR_API_KEY=... sh scripts/smoke-deploy.sh https://<fqdn>
#   sh scripts/demo.sh down
#   sh scripts/switch-provider.sh anthropic
#   sh scripts/demo.sh down        # again: the new revision may be running
#   az containerapp replica list -n cvr-ca -g cvr-rg --query "length(@)" -o tsv   # 0
#
# Overrides, read from the caller's environment and set only when given, so
# the proof can try the other token scope or API version without a code
# change: CVR_LABEL_AZURE_SCOPE, CVR_LABEL_AZURE_API_VERSION, CVR_LABEL_EFFORT
# (default medium; Azure refuses max). An override from an earlier run that
# is not given again is removed, so none outlives its attempt.
#
#   sh scripts/switch-provider.sh azure|anthropic [resource-group] [app]
#
# The names default to the wizard's .env.azure (AZURE_RESOURCE_GROUP,
# AZURE_CONTAINER_APP, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT), then to
# cvr-rg and cvr-ca (ENV_FILE names another file). Needs az (signed in); POSIX sh, runs under Git Bash.
set -eu
cd "$(dirname "$0")/.."

usage() { echo "usage: sh scripts/switch-provider.sh azure|anthropic [resource-group] [app]"; exit 2; }
ENV_FILE=${ENV_FILE:-.env.azure}
from_env() { [ -f "$ENV_FILE" ] && sed -n "s/^$1=//p" "$ENV_FILE" | tr -d '\r' | tail -n 1; }

ACTION=${1:-}
RG=${2:-$(from_env AZURE_RESOURCE_GROUP || true)}
APP=${3:-$(from_env AZURE_CONTAINER_APP || true)}
RG=${RG:-cvr-rg}
APP=${APP:-cvr-ca}
MODEL=gpt-5.4

# Every variable `azure` can set, which `anthropic` removes.
ALL_VARS="CVR_LABEL_PROVIDER CVR_LABEL_MODEL CVR_LABEL_EFFORT CVR_LABEL_AZURE_ENDPOINT CVR_LABEL_AZURE_DEPLOYMENT CVR_LABEL_AZURE_SCOPE CVR_LABEL_AZURE_API_VERSION"

# One value from az, with Windows' \r stripped (as in demo.sh).
value() {
  v=$(az "$@" --output tsv) || return 1
  printf '%s\n' "$v" | tr -d '\r'
}

# The CVR_LABEL_* names the app has now, one per line.
current_names() {
  value containerapp show --name "$APP" --resource-group "$RG"     --query "properties.template.containers[0].env[].name"
}

# Of the names given, those the app has now (removing an absent one is noise).
present() {
  have=$(current_names)
  for name in "$@"; do
    printf '%s
' "$have" | grep -qx "$name" && printf '%s
' "$name"
  done
  return 0
}

report() {
  rev=$(value containerapp show --name "$APP" --resource-group "$RG" \
    --query properties.latestRevisionName)
  echo "== latest revision of $APP: $rev"
  echo "   active: $(value containerapp revision show --name "$APP" --resource-group "$RG" \
    --revision "$rev" --query properties.active)"
  echo "   CVR_LABEL_* now set (names and values only):"
  value containerapp show --name "$APP" --resource-group "$RG" \
    --query "properties.template.containers[0].env[?starts_with(name, 'CVR_LABEL_')].[name, value]" \
    | sed 's/^/     /'
  echo "The revision may be running: finish with  sh scripts/demo.sh down $RG $APP"
}

case "$ACTION" in
  azure)
    # The wizard writes the endpoint only after its read-back passes, so it
    # doubles as the "provisioning completed" marker.
    ENDPOINT=$(from_env AZURE_OPENAI_ENDPOINT || true)
    DEPLOYMENT=$(from_env AZURE_OPENAI_DEPLOYMENT || true)
    DEPLOYMENT=${DEPLOYMENT:-$MODEL}
    [ -n "$ENDPOINT" ] || { echo "FAIL: AZURE_OPENAI_ENDPOINT is not in $ENV_FILE (run the provisioning wizard to the end)"; exit 1; }
    EFFORT=${CVR_LABEL_EFFORT:-medium}
    case "$EFFORT" in
      low|medium|high|xhigh) ;;
      *) echo "FAIL: CVR_LABEL_EFFORT=$EFFORT is not accepted by Azure (low, medium, high or xhigh)"; exit 1 ;;
    esac
    set --       CVR_LABEL_PROVIDER=azure_openai       "CVR_LABEL_MODEL=$MODEL"       "CVR_LABEL_EFFORT=$EFFORT"       "CVR_LABEL_AZURE_ENDPOINT=$ENDPOINT"       "CVR_LABEL_AZURE_DEPLOYMENT=$DEPLOYMENT"
    drop=""
    if [ -n "${CVR_LABEL_AZURE_SCOPE:-}" ]; then
      set -- "$@" "CVR_LABEL_AZURE_SCOPE=$CVR_LABEL_AZURE_SCOPE"
    else
      drop="CVR_LABEL_AZURE_SCOPE"
    fi
    if [ -n "${CVR_LABEL_AZURE_API_VERSION:-}" ]; then
      set -- "$@" "CVR_LABEL_AZURE_API_VERSION=$CVR_LABEL_AZURE_API_VERSION"
    else
      drop="$drop CVR_LABEL_AZURE_API_VERSION"
    fi
    echo "== setting on $APP ($RG):"
    printf '   %s
' "$@"
    # Overrides left by an earlier try and not given now go in the same
    # update, so there is one revision.
    # shellcheck disable=SC2086
    gone=$(present $drop | tr '
' ' ')
    if [ -n "${gone% }" ]; then
      # shellcheck disable=SC2086
      az containerapp update --name "$APP" --resource-group "$RG"         --set-env-vars "$@" --remove-env-vars $gone --only-show-errors --output none
    else
      az containerapp update --name "$APP" --resource-group "$RG"         --set-env-vars "$@" --only-show-errors --output none
    fi
    report
    ;;
  anthropic)
    # shellcheck disable=SC2086
    gone=$(present $ALL_VARS | tr '
' ' ')
    if [ -n "${gone% }" ]; then
      echo "== removing ${gone% } from $APP ($RG)"
      # shellcheck disable=SC2086
      az containerapp update --name "$APP" --resource-group "$RG"         --remove-env-vars $gone --only-show-errors --output none
    else
      echo "== $APP has no CVR_LABEL_* provider variables; nothing to remove"
    fi
    report
    ;;
  *) usage ;;
esac
