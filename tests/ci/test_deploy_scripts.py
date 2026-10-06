"""The smoke test and the demo switch, read from the scripts without running
them: both reach a live app, so what is pinned here is how they treat the
API key and the ingress, not whether the app answers."""

import re
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
