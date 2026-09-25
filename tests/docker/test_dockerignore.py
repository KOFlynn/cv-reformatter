"""What the build context carries, read from ``.dockerignore`` with Docker's
matching rules: patterns are relative to the context root, ``*`` and ``?``
stop at ``/``, ``**`` crosses it, a pattern that matches a directory excludes
everything under it, ``!`` re-includes, and the last matching line wins.

The file is an allowlist (``*`` first), so what is not named is not sent;
the tests below name every path the ticket says must never reach the image,
and every path the image needs."""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def _regex(pattern: str) -> re.Pattern[str]:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        elif pattern[i] == "[":
            end = pattern.index("]", i)
            out.append(pattern[i : end + 1])
            i = end + 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def rules(text: str) -> list[tuple[bool, re.Pattern[str]]]:
    """``(excludes, regex)`` per pattern line, in file order."""
    parsed = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        excludes = not line.startswith("!")
        pattern = line.lstrip("!").strip().strip("/")
        parsed.append((excludes, _regex(pattern)))
    return parsed


def ignored(path: str, parsed: list[tuple[bool, re.Pattern[str]]]) -> bool:
    """Whether the context leaves out ``path`` (relative, ``/``-separated)."""
    parts = path.strip("/").split("/")
    prefixes = ["/".join(parts[: n + 1]) for n in range(len(parts))]
    verdict = False
    for excludes, regex in parsed:
        if any(regex.fullmatch(prefix) for prefix in prefixes):
            verdict = excludes
    return verdict


@pytest.fixture(scope="module")
def parsed():
    return rules(DOCKERIGNORE.read_text(encoding="utf-8"))


def test_the_matcher_follows_last_match_and_parent_directories():
    parsed = rules("*\n!src/\nsrc/cvr/golden\n**/__pycache__\n")
    assert ignored("README.md", parsed)
    assert ignored(".git/HEAD", parsed)
    assert not ignored("src/cvr/api/app.py", parsed)
    assert ignored("src/cvr/golden/loader.py", parsed)
    assert ignored("src/cvr/api/__pycache__/app.cpython-312.pyc", parsed)


# Every path the ticket and the spec say must never reach the image, plus the
# other local caches and working files that have no business in it.
NEVER = [
    ".git/HEAD",
    ".git/config",
    ".gitignore",
    ".github/workflows/ci.yml",
    "src/cvr/golden/__init__.py",
    "src/cvr/golden/layouts/base.py",
    "src/cvr/eval/__init__.py",
    "src/cvr/eval/adapter.py",
    "src/cvr/eval/run/cache.py",
    "fixtures/candidates/c01.json",
    "fixtures/generated/c01__single-column.docx",
    "tests/conftest.py",
    "tests/docker/test_dockerignore.py",
    ".env",
    ".env.local",
    "src/.env",
    ".cache/eval-responses/0123abcd.json",
    "eval/thresholds.yaml",
    "eval/report.json",
    "eval/report.md",
    ".scratch/phase-1/spec.md",
    ".claude/settings.json",
    ".claude/worktrees/agent/pyproject.toml",
    ".teach/notes.md",
    ".venv/pyvenv.cfg",
    ".pytest_cache/README.md",
    ".ruff_cache/CACHEDIR.TAG",
    "src/cvr/api/__pycache__/app.cpython-312.pyc",
    "src/cvr/api/app.pyc",
    "src/cvr.egg-info/PKG-INFO",
    "dist/cvr-0.1.0-py3-none-any.whl",
    "docs/development.md",
    "scripts/check-image.sh",
    "CLAUDE.md",
    "CONTEXT.md",
    "README.md",
    "Dockerfile",
    ".dockerignore",
]


@pytest.mark.parametrize("path", NEVER)
def test_never_in_the_build_context(path, parsed):
    assert ignored(path, parsed)


def _runtime_sources() -> list[str]:
    """Every tracked file under ``src/`` except the golden and eval packages
    (tracked, so a stray local ``.pyc`` or ``.env`` is not "needed")."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "src"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    ).stdout.split("\0")
    excluded = ("src/cvr/golden/", "src/cvr/eval/")
    return sorted(p for p in tracked if p and not p.startswith(excluded))


def test_the_build_context_carries_what_the_image_needs(parsed):
    needed = [
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        "templates/fictitious_recruitment.docx",
        *_runtime_sources(),
    ]
    assert "src/cvr/label/prompt.md" in needed
    assert "src/cvr/label/versions.json" in needed
    assert [path for path in needed if ignored(path, parsed)] == []
