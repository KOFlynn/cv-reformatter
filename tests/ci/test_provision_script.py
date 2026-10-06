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
