"""Lint and layout rules that keep the content boundary honest."""

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]
NODES = ["parse", "label", "verify", "transform", "render", "template"]


def test_ruff_bans_the_langfuse_langchain_integration_and_decorator():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    assert "TID251" in lint["extend-select"]
    banned = lint["flake8-tidy-imports"]["banned-api"]
    assert {"langfuse.langchain", "langfuse.observe", "langfuse.decorators"} <= set(
        banned
    )


def _imports(package: Path) -> set[str]:
    found: set[str] = set()
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def test_no_node_imports_tracing_or_langfuse():
    for node in NODES:
        imported = _imports(ROOT / "src" / "cvr" / node)
        assert not {m for m in imported if m.startswith(("cvr.tracing", "langfuse"))}, (
            node
        )


def test_tracing_imports_models_and_the_sdk_only():
    imported = _imports(ROOT / "src" / "cvr" / "tracing")
    ours = {m for m in imported if m.startswith("cvr.") and m != "cvr.tracing"}
    assert all(m.split(".")[1] in {"models", "tracing"} for m in ours), ours
