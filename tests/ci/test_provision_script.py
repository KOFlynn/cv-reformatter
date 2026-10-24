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


def test_the_app_is_left_stopped_after_the_smoke_test(script: str) -> None:
    # Off by default (ADR-0010, 2026-10-19): "off" is a deactivated revision,
    # which only demo.sh down does, with ingress closed. The wizard no longer
    # runs its own ingress commands: demo.sh up opens, demo.sh down stops.
    assert "az containerapp ingress" not in script
    stage = _stage(script, "Smoke test the live app")
    up = stage.index(
        'sh scripts/demo.sh up "$AZURE_RESOURCE_GROUP" "$AZURE_CONTAINER_APP"'
    )
    smoke = stage.index("scripts/smoke-deploy.sh", up)
    down = stage.index(
        'sh scripts/demo.sh down "$AZURE_RESOURCE_GROUP" "$AZURE_CONTAINER_APP"'
    )
    assert down > smoke


# Phase 2 ticket 06: the ContainerApp tables of cvr-log that accept it keep 4
# days, the per-table minimum; the classic _CL ones refuse and keep the
# workspace's 30, the PerGB2018 minimum (option A).
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


def test_a_table_that_cannot_be_updated_warns_and_the_wizard_goes_on(
    retention_stage: str,
) -> None:
    # Classic _CL tables refuse the table API unless migrated; set -e must
    # not end the wizard there.
    write = retention_stage.index("workspace table update")
    line_start = retention_stage.rindex("\n", 0, write)
    assert "if ! " in retention_stage[line_start:write]
    after = retention_stage[write:]
    loop_end = after.index("\ndone")
    assert "warn " in after[:loop_end]
    assert "continue" in after[:loop_end]


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


def _stage(script: str, title: str) -> str:
    start = script.index(f'stage "{title}')
    end = script.find("\nstage ", start + 1)
    return script[start : end if end != -1 else len(script)]


# 2026-10-21: stage 8 raced stage 7's update (ContainerAppLockConflict), and
# the wizard left a woken app running. Every change waits for the app to be
# Succeeded; the app is stopped on every path out of stage 8.
def test_a_helper_waits_for_the_provisioning_state_with_a_bound(script: str) -> None:
    helper = script[script.index("wait_app_ready()") :]
    helper = helper[: helper.index("\n}\n")]
    assert "properties.provisioningState" in helper
    assert "Succeeded" in helper
    assert "seq" in helper or "SECONDS" in helper  # bounded
    assert "warn" in helper  # a clear message when it gives up


def _az_commands(script: str, prefix: str) -> list[tuple[int, int]]:
    """(first, last) line index of each az command that starts with prefix,
    its backslash continuations joined."""
    lines = script.splitlines()
    found = []
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            j = i
            while lines[j].rstrip().endswith("\\"):
                j += 1
            found.append((i, j))
    return found


@pytest.mark.parametrize(
    "prefix", ["az containerapp update", "az containerapp secret set"]
)
def test_every_change_to_the_app_is_followed_by_the_wait(
    script: str, prefix: str
) -> None:
    lines = script.splitlines()
    found = _az_commands(script, prefix)
    assert found
    for _, last in found:
        assert lines[last + 1].strip().startswith("wait_app_ready"), lines[last]


def test_the_env_update_is_skipped_when_the_app_already_has_the_env(
    script: str,
) -> None:
    # A re-run must not create a new revision for nothing: a read-only check
    # guards each update.
    assert "env_var_is()" in script
    assert "env_var_is CVR_API_KEY secretref:cvr-api-key" in script
    assert "env_var_is CVR_TRACE_ENV prod" in script


def test_the_smoke_stage_stops_the_app_whether_or_not_it_ran_the_test(
    script: str,
) -> None:
    stage = _stage(script, "Smoke test the live app")
    down = stage.index('sh scripts/demo.sh down "$AZURE_RESOURCE_GROUP"')
    # Outside the confirm: a declined or failed smoke test still stops the app.
    assert stage.index("\nfi\n") < down
    assert "|| " in stage[down : stage.index("\n", down)] or "if !" in stage[:down]
