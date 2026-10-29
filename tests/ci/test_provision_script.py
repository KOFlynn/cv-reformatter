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


# Phase 2 ticket 18: the Azure OpenAI stage. No key is ever created, listed or
# stored; every create reads first; the role is on the account, not the group.
@pytest.fixture(scope="module")
def aoai_stage(script: str) -> str:
    # azq is az with CRs stripped: the reads are written with it.
    return _stage(script, "Azure OpenAI").replace("azq ", "az ")


def test_aoai_stage_sits_between_retention_and_the_record(script: str) -> None:
    assert (
        script.index('stage "Log retention')
        < script.index('stage "Azure OpenAI')
        < script.index('stage "Record for')
    )


def test_the_provider_is_registered_and_awaited(aoai_stage: str) -> None:
    assert "az provider register --namespace Microsoft.CognitiveServices --wait" in (
        aoai_stage
    )
    assert "registrationState" in aoai_stage
    assert aoai_stage.index("registrationState") < aoai_stage.index("usage list")


def test_no_quota_stops_the_wizard_before_anything_is_created(aoai_stage: str) -> None:
    assert "az cognitiveservices usage list" in aoai_stage
    assert "OpenAI.$AOAI_SKU.$AOAI_MODEL" in aoai_stage
    stop = aoai_stage.index("== 0 ]]")
    first_create = min(
        aoai_stage.index(c)
        for c in (
            "az cognitiveservices account create",
            "az resource update",
            "az cognitiveservices account deployment create",
            "az role assignment create",
            "az containerapp identity assign",
        )
    )
    assert stop < first_create
    assert "exit 1" in aoai_stage[stop:first_create]
    assert "quota" in aoai_stage[stop:first_create]


def test_capacity_defaults_to_the_smaller_of_available_and_the_models_cap(
    aoai_stage: str,
) -> None:
    assert "quota_free > capacity_cap" in aoai_stage
    assert "gpt-5.4) printf '500'" in aoai_stage
    assert "gpt-5.4-mini) printf '200'" in aoai_stage
    assert "max_completion_tokens" in aoai_stage
    assert 'ask_default "$capacity_key"' in aoai_stage
    assert "AZURE_OPENAI_CAPACITY_$(" in aoai_stage  # remembered per model


def test_the_account_has_its_own_remembered_region_and_model(aoai_stage: str) -> None:
    assert "ask_default AZURE_OPENAI_LOCATION" in aoai_stage
    assert "swedencentral" in aoai_stage
    assert "ask_default AZURE_OPENAI_MODEL" in aoai_stage
    model_line = aoai_stage.split("ask_default AZURE_OPENAI_MODEL")[1].splitlines()[0]
    assert model_line.endswith(" gpt-5.4-mini")  # the default
    # Quota and the account use the account's region, never the app's.
    assert "$AZURE_LOCATION" not in aoai_stage.split('say "Reading')[1]
    create = aoai_stage[aoai_stage.index("az cognitiveservices account create") :]
    assert (
        '--location "$AZURE_OPENAI_LOCATION"' in create[: create.index("--output none")]
    )
    assert "exists in another region" in aoai_stage


def test_the_deployment_is_named_after_its_model_and_other_models_are_left_alone(
    aoai_stage: str,
) -> None:
    assert "AZURE_OPENAI_DEPLOYMENT=$AOAI_MODEL" in aoai_stage
    assert "ask_default AZURE_OPENAI_DEPLOYMENT" not in aoai_stage
    # Only the chosen deployment is looked up before creating; nothing deletes.
    assert "deployment delete" not in aoai_stage


def test_account_is_ai_services_with_a_custom_subdomain(aoai_stage: str) -> None:
    create = aoai_stage[aoai_stage.index("az cognitiveservices account create") :]
    create = create[: create.index("--output none")]
    assert "--kind AIServices" in create
    assert "--sku S0" in create
    assert '--custom-domain "$AZURE_OPENAI_ACCOUNT"' in create
    assert "openssl rand -hex 2" in aoai_stage  # cvr-aoai-<4 random>


def test_key_auth_is_disabled_through_arm_only_when_it_is_not_already(
    aoai_stage: str,
) -> None:
    update = aoai_stage.index("az resource update")
    assert "--set properties.disableLocalAuth=true" in aoai_stage[update:]
    before = aoai_stage[:update]
    assert "properties.disableLocalAuth -o tsv" in before
    assert "else" in before[before.rindex("disableLocalAuth -o tsv") :]


def test_deployment_is_data_zone_standard_with_a_version_pinned_per_model(
    aoai_stage: str,
) -> None:
    assert "AOAI_SKU=DataZoneStandard" in aoai_stage
    assert "gpt-5.4) printf '2026-03-05'" in aoai_stage
    assert "gpt-5.4-mini) printf '2026-03-17'" in aoai_stage
    assert "gpt-5.6-terra) printf '2026-07-09'" in aoai_stage
    assert "AOAI_MODEL=$AZURE_OPENAI_MODEL" in aoai_stage
    create = aoai_stage[aoai_stage.index("deployment create") :]
    create = create[: create.index("--output none")]
    for flag in (
        "--model-format OpenAI",
        '--model-name "$AOAI_MODEL"',
        '--model-version "$AOAI_MODEL_VERSION"',
        '--sku-name "$AOAI_SKU"',
        '--sku-capacity "$AZURE_OPENAI_CAPACITY"',
    ):
        assert flag in create


def test_every_create_reads_first(aoai_stage: str) -> None:
    for show, create in (
        ("az cognitiveservices account show", "az cognitiveservices account create"),
        (
            "az cognitiveservices account deployment show",
            "az cognitiveservices account deployment create",
        ),
        ("az containerapp identity show", "az containerapp identity assign"),
        ("az role assignment list", "az role assignment create"),
    ):
        assert aoai_stage.index(show) < aoai_stage.index(create), create
    assert "already exists" in aoai_stage


def test_roles_are_the_inference_role_on_the_account_for_the_app_and_the_user(
    aoai_stage: str,
) -> None:
    assert 'AOAI_ROLE="Cognitive Services OpenAI User"' in aoai_stage
    assert "--system-assigned" in aoai_stage
    assert "az ad signed-in-user show" in aoai_stage
    create = aoai_stage[aoai_stage.index("az role assignment create") :]
    create = create[: create.index("--output none")]
    assert '--scope "$aoai_id"' in create
    assert '--role "$AOAI_ROLE"' in create
    assert "$rg_id" not in aoai_stage
    assert "az group show" not in aoai_stage
    assert 'grant_role "$app_principal" ServicePrincipal' in aoai_stage
    assert 'grant_role "$user_principal" User' in aoai_stage


def test_the_identity_change_waits_for_the_app(aoai_stage: str) -> None:
    lines = aoai_stage.splitlines()
    i = next(n for n, l in enumerate(lines) if "az containerapp identity assign" in l)
    assert "wait_app_ready" in lines[i + 2]


def test_the_stage_reads_back_and_fails_loudly(aoai_stage: str) -> None:
    assert "properties.disableLocalAuth" in aoai_stage[aoai_stage.index("Read-back") :]
    assert "model.version" in aoai_stage
    assert "az role assignment list --scope" in aoai_stage
    assert 'local_auth_off" == true' in aoai_stage
    assert "bad=1" in aoai_stage
    assert "exit 1" in aoai_stage[aoai_stage.index("bad == 0") :]


def test_the_stage_prints_what_the_app_will_need_but_does_not_change_the_app(
    aoai_stage: str,
) -> None:
    assert "CVR_LABEL_AZURE_ENDPOINT=https://" not in aoai_stage  # via the variable
    assert 'AZURE_OPENAI_ENDPOINT="https://$subdomain.openai.azure.com/"' in aoai_stage
    assert "CVR_LABEL_AZURE_ENDPOINT=$AZURE_OPENAI_ENDPOINT" in aoai_stage
    assert "CVR_LABEL_AZURE_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT" in aoai_stage
    assert "az containerapp update" not in aoai_stage
    assert "--set-env-vars" not in aoai_stage


def test_aoai_values_are_remembered_in_the_env_file(aoai_stage: str) -> None:
    for key in (
        "AZURE_OPENAI_ACCOUNT",
        "AZURE_OPENAI_LOCATION",
        "AZURE_OPENAI_MODEL",
    ):
        assert f"ask_default {key} " in aoai_stage
    # What switch-provider.sh reads is written only once the read-back passed.
    readback = aoai_stage[aoai_stage.index("(( bad == 0 ))") :]
    for key in ("ENDPOINT", "DEPLOYMENT", "CAPACITY"):
        assert f'write_env AZURE_OPENAI_{key} "$AZURE_OPENAI_{key}"' in readback
        assert (
            f'write_env AZURE_OPENAI_{key} "$'
            not in aoai_stage[: aoai_stage.index("(( bad == 0 ))")]
        )
    assert "set_secret" not in aoai_stage


def test_no_key_is_ever_listed_or_created(script: str) -> None:
    assert "cognitiveservices account keys" not in script
    assert "keys list" not in script
    assert "keys regenerate" not in script


def test_every_aoai_az_write_is_silent(aoai_stage: str) -> None:
    for prefix in (
        "az cognitiveservices account create",
        "az resource update",
        "az cognitiveservices account deployment create",
        "az containerapp identity assign",
        "az role assignment create",
    ):
        for first, last in _az_commands(aoai_stage, prefix):
            block = "\n".join(aoai_stage.splitlines()[first : last + 1])
            assert "--output none" in block, prefix


def test_role_assignment_lists_use_object_ids_not_a_graph_lookup(
    aoai_stage: str,
) -> None:
    lines = aoai_stage.splitlines()
    found = [
        "\n".join(lines[a : b + 1])
        for a, b in _az_commands(aoai_stage, "az role assignment list")
    ]
    found += [line for line in lines if "az role assignment list" in line]
    assert found
    for block in found:
        assert "--assignee " not in block, block
        assert "--fill-principal-name false" in block, block


def test_the_readback_table_cannot_abort_a_good_run(aoai_stage: str) -> None:
    i = aoai_stage.index("--output table")
    assert "|| true" in aoai_stage[i : aoai_stage.index("\n", i)]


def test_an_absent_quota_row_shows_what_the_subscription_reports(
    aoai_stage: str,
) -> None:
    stop = aoai_stage.index("Nothing was created")
    assert "contains(name.value,'gpt-5.4')" in aoai_stage[stop : stop + 600]


def test_a_failed_user_lookup_is_a_clear_error(aoai_stage: str) -> None:
    i = aoai_stage.index("az ad signed-in-user show")
    tail = aoai_stage[i : aoai_stage.index("\n", aoai_stage.index("exit 1", i))]
    assert "||" in tail and "by hand" in tail


def test_the_stage_checks_for_a_running_replica_at_the_end(aoai_stage: str) -> None:
    assert aoai_stage.rindex("az containerapp replica list") > aoai_stage.index(
        "CVR_LABEL_AZURE_DEPLOYMENT"
    )
    assert "runningState=='Running'" in aoai_stage


def test_the_deployment_readback_is_captured_before_it_is_split(
    aoai_stage: str,
) -> None:
    assert "dep_info=$(" in aoai_stage
    assert "< <(" not in aoai_stage


def test_an_existing_account_must_be_ai_services(aoai_stage: str) -> None:
    assert "--query kind" in aoai_stage
    assert "not kind AIServices" in aoai_stage


def test_disabling_local_auth_pins_the_api_version_and_retries(
    aoai_stage: str,
) -> None:
    i = aoai_stage.index("az resource update")
    assert "--api-version 2024-10-01" in aoai_stage[i : i + 200]
    assert "sleep" in aoai_stage[i : i + 500]


def test_no_key_is_listed_or_regenerated_by_any_spelling(script: str) -> None:
    assert "listKeys" not in script
    assert "regenerate" not in script.lower()


def test_path_conversion_is_off_before_the_aoai_stage(script: str) -> None:
    assert script.index("export MSYS_NO_PATHCONV=1") < script.index(
        'stage "Azure OpenAI'
    )


def test_the_readback_covers_every_deployment_on_the_account(aoai_stage: str) -> None:
    readback = aoai_stage[aoai_stage.index("Read-back:") :]
    assert "account deployment list" in readback
    assert "while IFS= read -r dep" in readback
    assert "properties.model.name" in readback
    assert "model_version" in readback
    assert 'dep" != "$AZURE_OPENAI_DEPLOYMENT' in readback
