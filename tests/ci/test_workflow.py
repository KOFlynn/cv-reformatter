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


def is_step(step: dict, *, uses: str | None = None, runs: str | None = None) -> bool:
    """The step calls the action ``uses`` (any version), or its script
    contains ``runs``."""
    if uses is not None:
        return step.get("uses", "").split("@")[0] == uses
    return runs in step.get("run", "")


def steps(job: dict, **match: str) -> list[dict]:
    return [s for s in job["steps"] if is_step(s, **match)]


def run_text(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job["steps"])


def test_jobs_run_check_then_eval_then_deploy(workflow: dict):
    jobs = workflow["jobs"]
    assert list(jobs) == ["check", "eval", "deploy"]
    assert jobs["eval"]["needs"] == "check"
    assert jobs["deploy"]["needs"] == "eval"


DOCS_ONLY = ["**/*.md", "docs/**", ".scratch/**"]


def test_a_push_of_docs_alone_runs_nothing(workflow: dict):
    # A push to main runs the eval uncached, about $3.30, and redeploys; a
    # docs-only merge changes neither the gate's verdict nor the image.
    # PyYAML reads the bare key `on` as True.
    assert workflow[True]["push"] == {"paths-ignore": DOCS_ONLY}


def test_every_pull_request_runs_every_job(workflow: dict):
    # A required check skipped by a path filter never reports, and branch
    # protection would hold the pull request waiting for it.
    assert workflow[True]["pull_request"] is None


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


def test_deploy_reads_no_repository_secret(deploy: dict):
    # The job token is github.token, not secrets.GITHUB_TOKEN.
    assert "secrets." not in yaml.safe_dump(deploy)


def test_deploys_never_overlap_and_never_cancel_midway(deploy: dict):
    # Two quick merges: the second waits, so the older sha is never deployed
    # last, and a deploy is never cut off between update and smoke.
    assert deploy["concurrency"] == {"group": "deploy", "cancel-in-progress": False}


def test_azure_login_is_oidc_through_repository_variables(deploy: dict):
    (login,) = steps(deploy, uses="azure/login")
    assert login["with"] == {
        "client-id": "${{ vars.AZURE_CLIENT_ID }}",
        "tenant-id": "${{ vars.AZURE_TENANT_ID }}",
        "subscription-id": "${{ vars.AZURE_SUBSCRIPTION_ID }}",
    }


def test_image_is_pushed_to_ghcr_with_the_job_token(deploy: dict):
    (login,) = steps(deploy, uses="docker/login-action")
    assert login["with"]["registry"] == "ghcr.io"
    assert login["with"]["password"] == "${{ github.token }}"
    (build,) = steps(deploy, uses="docker/build-push-action")
    assert build["with"]["push"] is True
    assert "github.sha" in build["with"]["tags"]
    assert not build["with"].get("build-args")


def test_pushed_image_is_pulled_anonymously_and_inspected(deploy: dict):
    runs = run_text(deploy)
    assert "docker logout ghcr.io" in runs
    assert "PULL=1" in runs and "scripts/check-image.sh" in runs
    assert runs.index("docker logout ghcr.io") < runs.index("scripts/check-image.sh")


def test_steps_are_in_deploy_order(deploy: dict):
    def index(**match: str) -> int:
        return next(i for i, s in enumerate(deploy["steps"]) if is_step(s, **match))

    assert (
        index(uses="docker/build-push-action")
        < index(runs="check-image.sh")
        < index(uses="azure/login")
        < index(runs="az containerapp update")
        < index(runs="smoke-deploy.sh")
    )


def test_deploy_updates_the_app_named_by_variables_to_this_commit(deploy: dict):
    (step,) = steps(deploy, runs="az containerapp update")
    joined = yaml.safe_dump(step)
    assert "vars.AZURE_CONTAINER_APP" in joined
    assert "vars.AZURE_RESOURCE_GROUP" in joined
    assert "github.sha" in joined


def test_expressions_reach_scripts_through_env_only(deploy: dict):
    # A ${{ }} inside a script is spliced into the shell source; through env
    # it is a value.
    for step in deploy["steps"]:
        assert "${{" not in step.get("run", ""), step.get("name")
