"""The smoke test and the demo switch, read from the scripts without running
them: both reach a live app, so what is pinned here is how they treat the
API key and the ingress, not whether the app answers. The one exception
runs `demo.sh down` against a fake `az` that always fails."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture(scope="module")
def smoke() -> str:
    return (SCRIPTS / "smoke-deploy.sh").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def demo() -> str:
    return (SCRIPTS / "demo.sh").read_text(encoding="utf-8")


def code(script: str) -> str:
    """The script without its comment lines."""
    return "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )


def test_smoke_fails_by_name_without_the_key(smoke: str):
    assert re.search(r"\$\{CVR_API_KEY:\?[^}]*CVR_API_KEY", smoke)


def test_smoke_sends_the_key_from_a_private_file_not_the_command_line(smoke: str):
    # A header given as -H "X-API-Key: $CVR_API_KEY" is in the process list;
    # curl reads -H @file instead.
    body = code(smoke)
    assert "umask 077" in body
    assert "X-API-Key:" in body
    assert '-H "@$work/key-header"' in body
    assert not re.search(r'-H "X-API-Key: \$', body)


def test_smoke_asserts_a_request_without_the_key_is_refused(smoke: str):
    body = code(smoke)
    assert '[ "$status" = 401 ]' in body
    # The refusal is checked before the one paid call.
    assert body.index('[ "$status" = 401 ]') < body.index('-H "@$work/key-header"')


@pytest.mark.parametrize("name", ["smoke", "demo"])
def test_scripts_never_trace_or_print_the_key(name: str, request):
    body = code(request.getfixturevalue(name))
    assert "set -x" not in body
    assert not re.search(r"echo[^\n]*\$\{?CVR_API_KEY", body)


def test_demo_opens_ingress_with_the_provisioned_settings(demo: str):
    body = code(demo).replace("\\\n", " ")
    assert "az containerapp ingress enable" in body
    for flag in ("--type external", "--target-port 8000", "--transport auto"):
        assert flag in body


def test_demo_closes_ingress(demo: str):
    assert "az containerapp ingress disable" in code(demo)


def test_demo_wakes_the_app_until_health_answers(demo: str):
    assert "/health" in code(demo)


def test_demo_reads_its_names_from_the_wizards_env_file(demo: str):
    body = code(demo)
    assert ".env.azure" in body
    assert "AZURE_RESOURCE_GROUP" in body and "AZURE_CONTAINER_APP" in body


# Closing ingress deletes the app's only scale rule, so "off" is a
# deactivated revision (ADR-0010 amendment, 2026-10-19).
def branch(script: str, name: str) -> str:
    """The body of one arm of the script's case statement."""
    body = code(script).replace("\\\n", " ")
    start = body.index(f"  {name})")
    return body[start : body.index(";;", start)]


def test_demo_up_activates_the_revision_before_opening_ingress(demo: str):
    arm = branch(demo, "up")
    assert "az containerapp revision activate" in arm
    assert arm.index("revision activate") < arm.index("ingress enable")
    assert arm.index("ingress enable") < arm.index("/health")


def test_demo_down_deactivates_after_closing_ingress_and_checks_replicas(demo: str):
    arm = branch(demo, "down")
    assert "az containerapp revision deactivate" in arm
    assert arm.index("ingress disable") < arm.index("revision deactivate")
    # The replica count is a helper (`running`) over az's replica list.
    helper = code(demo).replace("\\\n", " ")
    assert "az containerapp replica list" in helper
    assert "runningState=='Running'" in helper
    assert arm.index("revision deactivate") < arm.index('running "$rev"')
    assert "exit 1" in arm[arm.index('running "$rev"') :]


def test_demo_down_does_not_exit_early_on_closed_ingress(demo: str):
    # An already-closed app may still have an active revision.
    arm = branch(demo, "down")
    assert "exit 0" not in arm


def test_demo_looks_the_revision_up_and_never_claims_scale_to_zero(demo: str):
    body = code(demo)
    assert "properties.latestRevisionName" in body
    assert "--revision cvr-ca--" not in body
    assert "scales to zero" not in demo and "scale to zero" not in demo


def test_demo_az_calls_print_nothing_but_narrow_queries(demo: str):
    body = code(demo).replace("\\\n", " ")
    # `value` runs az with --output tsv, so its calls need a --query too.
    calls = re.split(r"\b(?:az|value) containerapp", body)[1:]
    assert any("latestRevisionName" in call for call in calls)
    for call in calls:
        call = call.split("\n")[0]
        if "secret show" in call:  # the echoed hint, run by the maintainer
            continue
        assert "--output none" in call or "--query" in call, call


# A fake az where every call works except reading the ingress FQDN: the
# revision is found and active, deactivating succeeds, no replica runs.
FAKE_AZ = """#!/bin/sh
case "$*" in
  *ingress.fqdn*) echo 'az: simulated failure' >&2; exit 1 ;;
  *latestRevisionName*) echo some-app--rev ;;
  *properties.active*) echo true ;;
  *"replica list"*) echo 0 ;;
esac
exit 0
"""


# The deploy stops the app through `down` (2026-10-20), so a failed FQDN
# lookup must fail the script: an empty FQDN read as "ingress already
# closed" would leave ingress open and still report the app stopped.
@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_demo_down_fails_when_the_ingress_lookup_fails(tmp_path: Path):
    fake = tmp_path / "az"
    fake.write_text(FAKE_AZ, newline="\n")
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        ["sh", str(SCRIPTS / "demo.sh"), "down", "some-rg", "some-app"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode != 0
    assert "Stopped" not in result.stdout


# `switch-provider.sh` leaves the new revision active (an env update
# activates it), so `up` straight after it must not activate it again: Azure
# answers RevisionAlreadyInRequestedState (ticket 19, live proof).
FAKE_UP_AZ = """#!/bin/sh
echo "$*" >> "$AZ_LOG"
case "$*" in
  *ingress.fqdn*) echo some-app.example.io ;;
  *latestRevisionName*) echo some-app--rev ;;
  *properties.active*) echo "$AZ_ACTIVE" ;;
esac
exit 0
"""


def run_up(tmp_path: Path, active: str) -> list[str]:
    (tmp_path / "az").write_text(FAKE_UP_AZ, newline="\n")
    (tmp_path / "curl").write_text("#!/bin/sh\nexit 0\n", newline="\n")
    for name in ("az", "curl"):
        (tmp_path / name).chmod(0o755)
    log = tmp_path / "calls"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "AZ_LOG": str(log),
        "AZ_ACTIVE": active,
    }
    result = subprocess.run(
        ["sh", str(SCRIPTS / "demo.sh"), "up", "some-rg", "some-app"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return log.read_text().splitlines()


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_demo_up_skips_activating_a_revision_that_is_already_active(tmp_path: Path):
    calls = run_up(tmp_path, "true")
    assert not any("revision activate" in c for c in calls)
    assert any("ingress enable" in c for c in calls)


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_demo_up_activates_an_inactive_revision_before_opening_ingress(tmp_path: Path):
    calls = run_up(tmp_path, "false")
    activate = next(i for i, c in enumerate(calls) if "revision activate" in c)
    enable = next(i for i, c in enumerate(calls) if "ingress enable" in c)
    assert activate < enable


def test_no_script_gives_curl_dev_null_to_write_to():
    # A native Windows curl first on PATH cannot open /dev/null: every call
    # failed with "(23) client returned ERROR on write". The shell redirect
    # is translated by Git Bash, so it works with either curl.
    for path in sorted(SCRIPTS.glob("*.sh")):
        text = code(path.read_text(encoding="utf-8")).replace("\\n", " ")
        for line in text.splitlines():
            if "curl" in line:
                assert not re.search(r"(-o|--output)[ =]+\S*/dev/null", line), (
                    f"{path.name}: {line.strip()}"
                )
