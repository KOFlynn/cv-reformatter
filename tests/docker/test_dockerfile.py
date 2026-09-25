"""The Dockerfile's invariants that can be checked without Docker: read as
text, instruction by instruction. The image itself (it builds, it answers
``/health``, no key in any layer) is checked by ``scripts/check-image.sh``
against a built image."""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"

# Any name that could hold a credential. A build argument or an environment
# variable baked into the image with such a name would put it in a layer.
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)


@dataclass(frozen=True)
class Instruction:
    keyword: str
    args: str


def instructions(text: str) -> list[Instruction]:
    """The Dockerfile's instructions, continuation lines joined, comments and
    parser directives dropped."""
    logical: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not pending and (not line or line.startswith("#")):
            continue
        if pending and line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        logical.append(" ".join((pending + line).split()))
        pending = ""
    assert not pending, "the Dockerfile ends inside a continuation"
    parsed = []
    for line in logical:
        keyword, _, args = line.partition(" ")
        parsed.append(Instruction(keyword.upper(), args.strip()))
    return parsed


def stages(parsed: list[Instruction]) -> list[list[Instruction]]:
    """The instructions grouped by build stage, each starting at its FROM."""
    grouped: list[list[Instruction]] = []
    for instruction in parsed:
        if instruction.keyword == "FROM":
            grouped.append([])
        assert grouped, "an instruction before the first FROM"
        grouped[-1].append(instruction)
    return grouped


@pytest.fixture(scope="module")
def parsed() -> list[Instruction]:
    return instructions(DOCKERFILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def final(parsed) -> list[Instruction]:
    return stages(parsed)[-1]


def env_names(args: str) -> list[str]:
    """The variable names an ENV instruction sets (``K=V K2=V2`` or ``K V``)."""
    if "=" not in args.split()[0]:
        return [args.split()[0]]
    return re.findall(r"(?:^|\s)([A-Za-z_][A-Za-z0-9_]*)=", args)


def test_the_parser_joins_continuations_and_drops_comments():
    text = "# syntax=docker/dockerfile:1\nFROM a AS b\n# note\nRUN x \\\n  # inner\n  && y\n"
    assert instructions(text) == [
        Instruction("FROM", "a AS b"),
        Instruction("RUN", "x && y"),
    ]


def test_env_names_reads_both_forms():
    assert env_names("A=1 B=two") == ["A", "B"]
    assert env_names('PATH="/app/.venv/bin:$PATH"') == ["PATH"]
    assert env_names("A 1") == ["A"]


def test_it_is_a_multi_stage_build(parsed):
    assert len(stages(parsed)) >= 2


def test_every_python_base_matches_the_pinned_version(parsed):
    pinned = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    bases = [
        i.args.split()[0]
        for i in parsed
        if i.keyword == "FROM" and i.args.startswith("python:")
    ]
    assert bases, "no stage is built on the python image"
    assert all(base == f"python:{pinned}-slim" for base in bases), bases


def test_uv_is_copied_from_a_pinned_official_image(parsed):
    copies = [
        i.args
        for i in parsed
        if i.keyword == "COPY" and "--from=ghcr.io/astral-sh/uv" in i.args
    ]
    assert len(copies) == 1
    assert re.search(r"--from=ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+ ", copies[0])


def test_dependencies_are_synced_locked_without_dev(parsed):
    syncs = [i.args for i in parsed if i.keyword == "RUN" and "uv sync" in i.args]
    assert syncs
    for sync in syncs:
        assert "--locked" in sync and "--no-dev" in sync, sync
    # Dependencies first, the project after: a source change keeps the
    # dependency layer cached.
    assert "--no-install-project" in syncs[0]
    assert "--no-install-project" not in syncs[-1]


def test_no_build_argument_or_baked_variable_names_a_secret(parsed):
    names = [i.args.split("=")[0].split()[0] for i in parsed if i.keyword == "ARG"]
    for instruction in parsed:
        if instruction.keyword == "ENV":
            names += env_names(instruction.args)
    assert not [name for name in names if SECRET_NAME.search(name)]
    assert "sk-ant-" not in DOCKERFILE.read_text(encoding="utf-8")


def test_the_final_stage_runs_as_a_non_root_user(final):
    users = [i.args for i in final if i.keyword == "USER"]
    assert users, "the final stage never leaves root"
    assert users[-1].split(":")[0] not in {"root", "0"}
    # Nothing after the last USER switches back to root for the running image.
    last_user = max(n for n, i in enumerate(final) if i.keyword == "USER")
    assert final[-1].keyword == "CMD" and len(final) - 1 > last_user


def test_the_final_stage_serves_the_api_on_all_interfaces(final):
    env = " ".join(i.args for i in final if i.keyword == "ENV")
    assert re.search(r"(?:^|\s)CVR_API_HOST=0\.0\.0\.0(?:\s|$)", env)
    port = re.search(r"(?:^|\s)CVR_API_PORT=(\d+)(?:\s|$)", env)
    assert port
    exposed = [i.args for i in final if i.keyword == "EXPOSE"]
    assert exposed == [port.group(1)]
    cmd = [i.args for i in final if i.keyword == "CMD"]
    assert cmd == ['["python", "-m", "cvr.api"]']


def test_the_final_stage_carries_the_template(final):
    copied = " ".join(i.args for i in final if i.keyword == "COPY")
    assert "templates/fictitious_recruitment.docx" in copied
