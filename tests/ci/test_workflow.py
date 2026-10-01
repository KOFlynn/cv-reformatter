"""The deploy job's invariants, read from ``ci.yml`` without running it:
what triggers it, what it may do with the token, and that nothing in the
workflow reaches Azure through a stored secret. Whether it actually deploys
is proven by its runs on ``main``, not here."""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PUSH_TO_MAIN = "github.event_name == 'push' && github.ref == 'refs/heads/main'"


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow(text: str) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def deploy(workflow: dict) -> dict:
    return workflow["jobs"]["deploy"]


def steps_using(job: dict, action: str) -> list[dict]:
    return [s for s in job["steps"] if s.get("uses", "").split("@")[0] == action]


def run_text(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job["steps"])


def test_jobs_run_check_then_eval_then_deploy(workflow: dict):
    jobs = workflow["jobs"]
    assert list(jobs) == ["check", "eval", "deploy"]
    assert jobs["eval"]["needs"] == "check"
    assert jobs["deploy"]["needs"] == "eval"


def test_deploy_runs_on_push_to_main_only(deploy: dict):
    assert " ".join(deploy["if"].split()) == PUSH_TO_MAIN


def test_id_token_write_is_granted_to_deploy_alone(workflow: dict):
    assert "id-token" not in workflow["permissions"]
    for name, job in workflow["jobs"].items():
        granted = job.get("permissions", {}).get("id-token")
        assert granted == ("write" if name == "deploy" else None), name


def test_deploy_permissions_are_exactly_what_it_needs(deploy: dict):
    # contents to check out, packages to push to GHCR, id-token for OIDC.
    assert deploy["permissions"] == {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
    }


def test_no_azure_secret_anywhere_in_the_workflow(text: str):
    assert not re.search(r"secrets\.\w*AZURE", text, re.IGNORECASE)
    assert "client-secret" not in text
    assert "creds:" not in text


def test_deploy_reads_no_secret_but_the_job_token(deploy: dict):
    assert "secrets." not in yaml.safe_dump(deploy)


def test_azure_login_is_oidc_through_repository_variables(deploy: dict):
    (login,) = steps_using(deploy, "azure/login")
    assert login["with"] == {
        "client-id": "${{ vars.AZURE_CLIENT_ID }}",
        "tenant-id": "${{ vars.AZURE_TENANT_ID }}",
        "subscription-id": "${{ vars.AZURE_SUBSCRIPTION_ID }}",
    }


def test_image_is_pushed_to_ghcr_with_the_job_token(deploy: dict):
    (login,) = steps_using(deploy, "docker/login-action")
    assert login["with"]["registry"] == "ghcr.io"
    assert login["with"]["password"] == "${{ github.token }}"
    (build,) = steps_using(deploy, "docker/build-push-action")
    assert build["with"]["push"] is True
    assert "github.sha" in build["with"]["tags"]
    assert not build["with"].get("build-args")


def test_pushed_image_is_pulled_anonymously_and_inspected(deploy: dict):
    runs = run_text(deploy)
    assert "docker logout ghcr.io" in runs
    assert "PULL=1" in runs and "scripts/check-image.sh" in runs
    assert runs.index("docker logout ghcr.io") < runs.index("scripts/check-image.sh")


def test_steps_are_in_deploy_order(deploy: dict):
    def index(predicate) -> int:
        return next(i for i, s in enumerate(deploy["steps"]) if predicate(s))

    push = index(lambda s: s.get("uses", "").startswith("docker/build-push-action"))
    inspect = index(lambda s: "check-image.sh" in s.get("run", ""))
    login = index(lambda s: s.get("uses", "").startswith("azure/login"))
    update = index(lambda s: "az containerapp update" in s.get("run", ""))
    smoke = index(lambda s: "smoke-deploy.sh" in s.get("run", ""))
    assert push < inspect < login < update < smoke


def test_deploy_updates_the_app_named_by_variables_to_this_commit(deploy: dict):
    (step,) = [
        s for s in deploy["steps"] if "az containerapp update" in s.get("run", "")
    ]
    joined = yaml.safe_dump(step)
    assert "vars.AZURE_CONTAINER_APP" in joined
    assert "vars.AZURE_RESOURCE_GROUP" in joined
    assert "github.sha" in joined
