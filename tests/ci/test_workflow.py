"""The workflows' invariants, read from ``ci.yml`` and ``branch.yml`` without
running them: what triggers each job, what it may do with the token, and that
nothing reaches Azure through a stored secret. Whether the gate and the deploy
actually work is proven by their runs on pull requests and ``main``, not
here."""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "ci.yml"
BRANCH_WORKFLOW = WORKFLOWS / "branch.yml"
PUSH_TO_MAIN = "github.event_name == 'push' && github.ref == 'refs/heads/main'"


@pytest.fixture(scope="module")
def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow(text: str) -> dict:
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def branch_text() -> str:
    return BRANCH_WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def branch(branch_text: str) -> dict:
    return yaml.safe_load(branch_text)


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


def test_the_gate_runs_on_pull_requests_and_pushes_to_main_only(workflow: dict):
    # A push to main runs the eval uncached, about $3.30, and redeploys; a
    # docs-only merge changes neither the gate's verdict nor the image.
    # Every pull request runs every job: a required check skipped by a path
    # filter never reports, and branch protection would hold the pull request
    # waiting for it. PyYAML reads the bare key `on` as True.
    assert workflow[True] == {
        "push": {"branches": ["main"], "paths-ignore": DOCS_ONLY},
        "pull_request": None,
    }


def test_eval_runs_on_every_trigger_of_its_workflow(workflow: dict):
    # A skipped job still reports a check run, and GitHub counts a skipped
    # `eval` as satisfying a required one. With no `if:` and only the two
    # triggers above, every `eval` check on a pull request is a real run.
    assert "if" not in workflow["jobs"]["eval"]


def test_every_other_branch_runs_check_alone(branch: dict):
    assert branch[True] == {
        "push": {"branches-ignore": ["main"], "paths-ignore": DOCS_ONLY}
    }
    assert list(branch["jobs"]) == ["check"]


def test_a_branch_push_runs_the_same_check_as_the_gate(branch: dict, workflow: dict):
    assert branch["jobs"]["check"] == workflow["jobs"]["check"]


def test_branch_check_is_read_only_and_cancels_its_older_run(branch: dict):
    assert branch["permissions"] == {"contents": "read"}
    assert "permissions" not in branch["jobs"]["check"]
    assert branch["concurrency"]["cancel-in-progress"] is True


def test_branch_check_reads_no_secret(branch_text: str):
    assert "secrets." not in branch_text


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
