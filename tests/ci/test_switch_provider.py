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
    AZURE_MODEL,
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
    assert f"MODEL={AZURE_MODEL}" in code(switch)
    assert DEFAULT_EFFORT in AZURE_EFFORTS
    assert f"{ENV_EFFORT}:-{DEFAULT_EFFORT}" in code(switch)


def test_anthropic_removes_everything_azure_sets(switch: str):
    body = code(switch)
    start = body.index("  anthropic)")
    arm = body[start : body.index(";;", start)]
    assert "--remove-env-vars $ALL_VARS" in arm
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
  *latestRevisionName*) echo some-app--rev ;;
  *properties.active*) echo true ;;
esac
exit 0
"""

ENV_FILE = "AZURE_OPENAI_ACCOUNT=cvr-aoai-1234\nAZURE_OPENAI_DEPLOYMENT=gpt-5.4\n"
needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")


def run(tmp_path: Path, args: list[str], extra_env: dict[str, str], env_file: str):
    fake = tmp_path / "az"
    fake.write_text(FAKE_AZ, newline="\n")
    fake.chmod(0o755)
    (tmp_path / "env").write_text(env_file, newline="\n")
    log = tmp_path / "calls"
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("CVR_LABEL_")},
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "AZ_LOG": str(log),
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
    assert "CVR_LABEL_AZURE_ENDPOINT=https://cvr-aoai-1234.openai.azure.com/" in update
    assert "CVR_LABEL_AZURE_DEPLOYMENT=gpt-5.4" in update
    assert "AZURE_SCOPE" not in update and "API_VERSION" not in update
    # Overrides not given are cleared, so an earlier try cannot linger.
    removal = next(c for c in calls if "--remove-env-vars" in c)
    assert "CVR_LABEL_AZURE_SCOPE" in removal
    assert "CVR_LABEL_AZURE_API_VERSION" in removal
    assert not any("ingress" in c or "revision activate" in c for c in calls)


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
def test_azure_fails_by_name_without_an_account(tmp_path):
    result, calls = run(tmp_path, ["azure"], {}, "AZURE_RESOURCE_GROUP=rg\n")
    assert result.returncode != 0
    assert "AZURE_OPENAI_ACCOUNT" in result.stdout
    assert not any("containerapp update" in c for c in calls)


@needs_sh
def test_anthropic_removes_the_variables_and_reminds_to_stop(tmp_path):
    result, calls = run(tmp_path, ["anthropic", "rg", "app"], {}, ENV_FILE)
    assert result.returncode == 0, result.stderr
    removal = next(c for c in calls if "--remove-env-vars" in c)
    for name in SET_VARS:
        assert name in removal
    assert not any("--set-env-vars" in c for c in calls)
    assert "demo.sh down" in result.stdout


@needs_sh
def test_an_unknown_action_is_a_usage_error(tmp_path):
    result, calls = run(tmp_path, ["bogus"], {}, ENV_FILE)
    assert result.returncode == 2
    assert calls == []
