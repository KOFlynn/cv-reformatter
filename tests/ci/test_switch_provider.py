"""The provider switch (ticket 19), read statically and run against a fake
`az` that records its calls: it reaches the live app, so what is pinned is
which variables it sets and removes, that it carries no key, and that it
leaves stopping the app to demo.sh."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from cvr.label.azure_openai import AZURE_EFFORTS
from cvr.label.config import (
    AZURE_MINI_MODEL,
    AZURE_MODEL,
    AZURE_TERRA_MODEL,
    DEFAULT_EFFORT,
    ENV_AZURE_API_VERSION,
    ENV_AZURE_DEPLOYMENT,
    ENV_AZURE_ENDPOINT,
    ENV_AZURE_SCOPE,
    ENV_EFFORT,
    ENV_MODEL,
    ENV_PROVIDER,
)

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

SET_VARS = (
    ENV_PROVIDER,
    ENV_MODEL,
    ENV_EFFORT,
    ENV_AZURE_ENDPOINT,
    ENV_AZURE_DEPLOYMENT,
    ENV_AZURE_SCOPE,
    ENV_AZURE_API_VERSION,
)


@pytest.fixture(scope="module")
def switch() -> str:
    return (SCRIPTS / "switch-provider.sh").read_text(encoding="utf-8")


def code(script: str) -> str:
    return "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )


def test_every_variable_it_touches_is_one_the_labeller_reads(switch: str):
    assert set(re.findall(r"CVR_LABEL_[A-Z_]+", code(switch))) == set(SET_VARS)


def test_the_model_and_default_effort_are_valid_for_azure(switch: str):
    # The model is derived from the deployment, which the wizard writes only
    # after its read-back, not from the earlier-remembered model choice.
    assert "from_env AZURE_OPENAI_DEPLOYMENT" in code(switch)
    assert "AZURE_OPENAI_MODEL" not in code(switch)
    assert "MODEL=$DEPLOYMENT" in code(switch)
    assert f"{AZURE_MODEL}|{AZURE_MINI_MODEL}|{AZURE_TERRA_MODEL}" in code(switch)
    assert DEFAULT_EFFORT in AZURE_EFFORTS
    assert f"{ENV_EFFORT}:-{DEFAULT_EFFORT}" in code(switch)
    assert "|".join(AZURE_EFFORTS) in code(switch)


def test_anthropic_removes_everything_azure_sets(switch: str):
    body = code(switch)
    start = body.index("  anthropic)")
    arm = body[start : body.index(";;", start)]
    assert "present $ALL_VARS" in arm
    assert "--remove-env-vars $gone" in arm
    listed = re.search(r'ALL_VARS="([^"]+)"', body).group(1).split()
    assert set(listed) == set(SET_VARS)


def test_it_carries_no_key_and_prints_no_secret(switch: str):
    body = code(switch)
    assert "set -x" not in body
    assert not re.search(r"api_key|secret|token", body, re.IGNORECASE)


def test_it_never_stops_or_opens_the_app_itself(switch: str):
    body = code(switch)
    for word in ("revision activate", "revision deactivate", "ingress"):
        assert word not in body
    assert "scripts/demo.sh down" in switch


def test_the_documented_sequence_ends_with_demo_down_and_a_replica_check(switch: str):
    head = switch.split("set -eu")[0]
    at = -1
    for step in (
        "switch-provider.sh azure",
        "demo.sh up",
        "smoke-deploy.sh",
        "demo.sh down",
        "switch-provider.sh anthropic",
        "demo.sh down",
        "replica list",
    ):
        at = head.index(step, at + 1)


def test_every_az_call_is_quiet_or_narrow(switch: str):
    body = code(switch).replace("\\\n", " ")
    calls = re.findall(r"\baz [a-z].*", body)
    assert calls
    for call in calls:
        assert "--output none" in call or "--query" in call or "--output tsv" in call


FAKE_AZ = """#!/bin/sh
echo "$*" >> "$AZ_LOG"
case "$*" in
  *"env[].name"*) printf '%s\n' $AZ_ENV_NAMES ;;
  *latestRevisionName*) echo some-app--rev ;;
  *properties.active*) echo true ;;
esac
exit 0
"""

ENDPOINT = "https://cvr-aoai-1234.openai.azure.com/"
ENDPOINT_LINE = f"AZURE_OPENAI_ENDPOINT={ENDPOINT}\n"
# What the wizard writes after deploying gpt-5.4.
ENV_FILE = ENDPOINT_LINE + "AZURE_OPENAI_DEPLOYMENT=gpt-5.4\n"
needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")


def run(
    tmp_path: Path,
    args: list[str],
    extra_env: dict[str, str],
    env_file: str,
    current: str = "PATH_X CVR_API_KEY",
):
    fake = tmp_path / "az"
    fake.write_text(FAKE_AZ, newline="\n")
    fake.chmod(0o755)
    (tmp_path / "env").write_text(env_file, newline="\n")
    log = tmp_path / "calls"
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("CVR_LABEL_")},
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "AZ_LOG": str(log),
        "AZ_ENV_NAMES": current,
        "ENV_FILE": str(tmp_path / "env"),
        **extra_env,
    }
    result = subprocess.run(
        ["sh", str(SCRIPTS / "switch-provider.sh"), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


@needs_sh
def test_azure_sets_the_endpoint_and_deployment_from_the_wizards_file(tmp_path):
    result, calls = run(tmp_path, ["azure", "rg", "app"], {}, ENV_FILE)
    assert result.returncode == 0, result.stderr
    update = next(c for c in calls if "--set-env-vars" in c)
    assert "CVR_LABEL_PROVIDER=azure_openai" in update
    assert "CVR_LABEL_MODEL=gpt-5.4" in update
    assert "CVR_LABEL_EFFORT=medium" in update
    assert f"CVR_LABEL_AZURE_ENDPOINT={ENDPOINT}" in update
    assert "CVR_LABEL_AZURE_DEPLOYMENT=gpt-5.4" in update
    assert "AZURE_SCOPE" not in update and "API_VERSION" not in update
    # Nothing to clear: no override is set on the app, so nothing is removed.
    assert not any("--remove-env-vars" in c for c in calls)
    assert len([c for c in calls if "containerapp update" in c]) == 1
    assert not any("ingress" in c or "revision activate" in c for c in calls)


@needs_sh
@pytest.mark.parametrize("model", ["gpt-5.4-mini", "gpt-5.6-terra", "gpt-5.4"])
def test_azure_derives_the_model_from_the_deployment_the_wizard_wrote(tmp_path, model):
    env_file = ENDPOINT_LINE + f"AZURE_OPENAI_DEPLOYMENT={model}\n"
    result, calls = run(tmp_path, ["azure"], {}, env_file)
    assert result.returncode == 0, result.stderr
    update = next(c for c in calls if "--set-env-vars" in c)
    assert f"CVR_LABEL_MODEL={model}" in update
    assert f"CVR_LABEL_AZURE_DEPLOYMENT={model}" in update


@needs_sh
def test_azure_ignores_a_remembered_model_choice_the_deploy_did_not_confirm(tmp_path):
    # AZURE_OPENAI_MODEL is written before the stage's read-back; the deployment
    # only after it. A choice without its deployment is not deployed.
    env_file = ENDPOINT_LINE + "AZURE_OPENAI_MODEL=gpt-5.6-terra\n"
    result, calls = run(tmp_path, ["azure"], {}, env_file)
    assert result.returncode != 0
    assert "AZURE_OPENAI_DEPLOYMENT" in result.stdout
    assert calls == []


@needs_sh
def test_azure_refuses_a_deployment_that_is_not_a_model_the_wizard_deploys(tmp_path):
    env_file = ENDPOINT_LINE + "AZURE_OPENAI_DEPLOYMENT=gpt-9\n"
    result, calls = run(tmp_path, ["azure"], {}, env_file)
    assert result.returncode != 0
    assert "AZURE_OPENAI_DEPLOYMENT" in result.stdout
    assert calls == []


@needs_sh
def test_azure_passes_the_callers_overrides_through(tmp_path):
    extra = {
        "CVR_LABEL_AZURE_SCOPE": "https://cognitiveservices.azure.com/.default",
        "CVR_LABEL_AZURE_API_VERSION": "2025-06-01",
    }
    result, calls = run(tmp_path, ["azure"], extra, ENV_FILE)
    assert result.returncode == 0, result.stderr
    update = next(c for c in calls if "--set-env-vars" in c)
    assert (
        "CVR_LABEL_AZURE_SCOPE=https://cognitiveservices.azure.com/.default" in update
    )
    assert "CVR_LABEL_AZURE_API_VERSION=2025-06-01" in update
    assert not any("--remove-env-vars" in c for c in calls)


@needs_sh
def test_azure_fails_by_name_without_the_endpoint(tmp_path):
    result, calls = run(tmp_path, ["azure"], {}, "AZURE_RESOURCE_GROUP=rg\n")
    assert result.returncode != 0
    assert "AZURE_OPENAI_ENDPOINT" in result.stdout
    assert not any("containerapp update" in c for c in calls)


@pytest.mark.parametrize("effort", ["max", "none", "", "Medium"])
@needs_sh
def test_azure_refuses_an_effort_it_does_not_accept_before_any_az_call(
    tmp_path, effort
):
    if effort == "":
        pytest.skip("an empty value means the default")
    result, calls = run(tmp_path, ["azure"], {"CVR_LABEL_EFFORT": effort}, ENV_FILE)
    assert result.returncode != 0
    assert "CVR_LABEL_EFFORT" in result.stdout
    assert calls == []


@needs_sh
def test_anthropic_removes_the_variables_and_reminds_to_stop(tmp_path):
    current = " ".join(SET_VARS) + " CVR_API_KEY"
    result, calls = run(tmp_path, ["anthropic", "rg", "app"], {}, ENV_FILE, current)
    assert result.returncode == 0, result.stderr
    updates = [c for c in calls if "containerapp update" in c]
    assert len(updates) == 1
    removal = updates[0]
    assert "CVR_API_KEY" not in removal
    for name in SET_VARS:
        assert name in removal
    assert not any("--set-env-vars" in c for c in calls)
    assert "demo.sh down" in result.stdout


@needs_sh
def test_anthropic_removes_only_names_that_are_present(tmp_path):
    result, calls = run(
        tmp_path, ["anthropic"], {}, ENV_FILE, "CVR_LABEL_PROVIDER CVR_API_KEY"
    )
    assert result.returncode == 0, result.stderr
    removal = next(c for c in calls if "--remove-env-vars" in c)
    assert "CVR_LABEL_PROVIDER" in removal
    assert "CVR_LABEL_MODEL" not in removal


@needs_sh
def test_anthropic_with_nothing_to_remove_makes_no_revision(tmp_path):
    result, calls = run(tmp_path, ["anthropic"], {}, ENV_FILE, "CVR_API_KEY")
    assert result.returncode == 0, result.stderr
    assert not any("containerapp update" in c for c in calls)


@needs_sh
def test_an_unknown_action_is_a_usage_error(tmp_path):
    result, calls = run(tmp_path, ["bogus"], {}, ENV_FILE)
    assert result.returncode == 2
    assert calls == []
