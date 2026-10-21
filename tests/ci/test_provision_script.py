"""The provisioning wizard's OIDC subject, read from the script without running
it. The first deploy failed because the wizard built the legacy ``repo:owner/name``
subject while this repository's tokens carry the immutable one (owner and repo
ids); the wizard must ask GitHub for the prefix, never rebuild it from the name."""

import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "provision-azure.sh"


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_subject_is_read_from_githubs_customization(script: str) -> None:
    assert "actions/oidc/customization/sub" in script
    assert "sub_claim_prefix" in script


def test_subject_is_not_built_from_the_repo_name_alone(script: str) -> None:
    assert not re.search(r'FED_SUBJECT="repo:\$GITHUB_REPO:', script)
    assert 'FED_SUBJECT="$sub_prefix:ref:refs/heads/main"' in script


def test_existing_credential_with_another_subject_is_updated(script: str) -> None:
    assert "az ad app federated-credential update" in script


# 2026-10-06 (ADR-0010): the three Azure ids become secrets so that GitHub
# masks them in the deploy logs; the two resource names stay variables.
@pytest.mark.parametrize(
    "name", ["AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"]
)
def test_azure_ids_are_set_as_secrets(script: str, name: str) -> None:
    assert f'set_secret {name} "${name}"' in script
    assert f"set_var {name} " not in script


@pytest.mark.parametrize("name", ["AZURE_RESOURCE_GROUP", "AZURE_CONTAINER_APP"])
def test_resource_names_stay_variables(script: str, name: str) -> None:
    assert f'set_var {name} "${name}"' in script


def test_api_key_is_generated_and_stored_in_both_places(script: str) -> None:
    assert "openssl rand" in script
    # The app reads it from a Container Apps secret...
    assert "cvr-api-key" in script
    assert "CVR_API_KEY=secretref:cvr-api-key" in script
    # ...and the deploy job's smoke test from a GitHub secret.
    assert 'set_secret CVR_API_KEY "$CVR_API_KEY"' in script


def test_api_key_is_never_printed(script: str) -> None:
    for line in script.splitlines():
        if re.search(r"\b(say|note|warn|step|echo|printf)\b", line):
            assert "$CVR_API_KEY" not in line, line


def test_ingress_is_left_closed(script: str) -> None:
    # Off by default: opened for the smoke test, closed straight after.
    enable = script.index("az containerapp ingress enable")
    smoke = script.index("scripts/smoke-deploy.sh", enable)
    assert script.index("az containerapp ingress disable", smoke) > smoke


# Phase 2 ticket 06: the ContainerApp tables of cvr-log keep 4 days, the
# per-table minimum (the workspace itself stays at the PerGB2018 minimum, 30).
@pytest.fixture(scope="module")
def retention_stage(script: str) -> str:
    start = script.index('stage "Log retention')
    return script[start : script.index("\nstage ", start)]


def test_retention_stage_precedes_the_record(script: str) -> None:
    assert script.index('stage "Log retention') < script.index('stage "Record for')


def test_total_stages_counts_every_stage(script: str) -> None:
    declared = int(re.findall(r"^TOTAL_STAGES=(\d+)$", script, re.MULTILINE)[-1])
    assert declared == len(re.findall(r'^stage "', script, re.MULTILINE))


def test_retention_is_four_days_in_one_place(retention_stage: str) -> None:
    assert "LOG_TABLE_RETENTION_DAYS=4" in retention_stage
    assert "--retention-time 4" not in retention_stage
    for flag in ("--retention-time", "--total-retention-time"):
        assert f'{flag} "$LOG_TABLE_RETENTION_DAYS"' in retention_stage


def test_retention_covers_only_the_tables_that_exist(retention_stage: str) -> None:
    assert "monitor log-analytics workspace table list" in retention_stage
    assert "ContainerApp" in retention_stage
    assert "monitor log-analytics workspace table update" in retention_stage


def test_retention_reads_before_it_writes(retention_stage: str) -> None:
    read = retention_stage.index("workspace table show")
    write = retention_stage.index("workspace table update")
    assert read < write
    # Only updated when different: the update sits inside a conditional.
    assert re.search(r"if \[\[ .*!=.*\]\]", retention_stage[read:write])


def test_retention_leaves_the_workspace_alone(retention_stage: str) -> None:
    assert "workspace update" not in retention_stage


def test_retention_prints_no_ids(retention_stage: str) -> None:
    assert "customerId" not in retention_stage
    assert "--query id" not in retention_stage
    assert "--output none" in retention_stage


# Phase 2 ticket 08: the app's Langfuse keys are Container Apps secrets read
# through secretref, the tag says prod, and the keys are never printed.
def test_langfuse_keys_are_container_app_secrets_read_by_secretref(
    script: str,
) -> None:
    assert "langfuse-public-key=$LANGFUSE_PUBLIC_KEY" in script
    assert "langfuse-secret-key=$LANGFUSE_SECRET_KEY" in script
    assert "LANGFUSE_PUBLIC_KEY=secretref:langfuse-public-key" in script
    assert "LANGFUSE_SECRET_KEY=secretref:langfuse-secret-key" in script
    assert "CVR_TRACE_ENV=prod" in script
    assert "LANGFUSE_BASE_URL=$LANGFUSE_BASE_URL" in script


def test_langfuse_secrets_are_set_once_and_kept_on_a_rerun(script: str) -> None:
    # Idempotent: the secrets are listed first and only created when absent.
    listed = script.index("langfuse-public-key' || name=='langfuse-secret-key'")
    assert script.index("az containerapp secret set", listed) > listed
    assert 'if [[ "$has_langfuse" == 2 ]]' in script
    assert "--secret-name langfuse-secret-key" in script


def test_langfuse_keys_go_to_github_and_are_never_printed(script: str) -> None:
    assert 'set_secret LANGFUSE_PUBLIC_KEY "$LANGFUSE_PUBLIC_KEY"' in script
    assert 'set_secret LANGFUSE_SECRET_KEY "$LANGFUSE_SECRET_KEY"' in script
    for line in script.splitlines():
        if re.search(r"\b(say|note|warn|step|echo|printf)\b", line):
            assert "$LANGFUSE_SECRET_KEY" not in line, line
            assert "$LANGFUSE_PUBLIC_KEY" not in line, line
