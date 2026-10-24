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
# AZURE_CONTAINER_APP, AZURE_OPENAI_ACCOUNT, AZURE_OPENAI_DEPLOYMENT), then to
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
    ACCOUNT=$(from_env AZURE_OPENAI_ACCOUNT || true)
    DEPLOYMENT=$(from_env AZURE_OPENAI_DEPLOYMENT || true)
    DEPLOYMENT=${DEPLOYMENT:-$MODEL}
    [ -n "$ACCOUNT" ] || { echo "FAIL: AZURE_OPENAI_ACCOUNT is not in .env.azure (run the provisioning wizard)"; exit 1; }
    drop=""
    set -- \
      CVR_LABEL_PROVIDER=azure_openai \
      "CVR_LABEL_MODEL=$MODEL" \
      "CVR_LABEL_EFFORT=${CVR_LABEL_EFFORT:-medium}" \
      "CVR_LABEL_AZURE_ENDPOINT=https://$ACCOUNT.openai.azure.com/" \
      "CVR_LABEL_AZURE_DEPLOYMENT=$DEPLOYMENT"
    if [ -n "${CVR_LABEL_AZURE_SCOPE:-}" ]; then
      set -- "$@" "CVR_LABEL_AZURE_SCOPE=$CVR_LABEL_AZURE_SCOPE"
    else
      drop="$drop CVR_LABEL_AZURE_SCOPE"
    fi
    if [ -n "${CVR_LABEL_AZURE_API_VERSION:-}" ]; then
      set -- "$@" "CVR_LABEL_AZURE_API_VERSION=$CVR_LABEL_AZURE_API_VERSION"
    else
      drop="$drop CVR_LABEL_AZURE_API_VERSION"
    fi
    echo "== setting on $APP ($RG):"
    printf '   %s\n' "$@"
    az containerapp update --name "$APP" --resource-group "$RG" \
      --set-env-vars "$@" --only-show-errors --output none
    if [ -n "$drop" ]; then
      # shellcheck disable=SC2086
      az containerapp update --name "$APP" --resource-group "$RG" \
        --remove-env-vars $drop --only-show-errors --output none
    fi
    report
    ;;
  anthropic)
    echo "== removing the CVR_LABEL_* provider variables from $APP ($RG)"
    # shellcheck disable=SC2086
    az containerapp update --name "$APP" --resource-group "$RG" \
      --remove-env-vars $ALL_VARS --only-show-errors --output none
    report
    ;;
  *) usage ;;
esac
