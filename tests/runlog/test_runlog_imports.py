"""The shared module sits below both surfaces: it imports neither the API nor
the MCP server, so either can use it without importing the other."""

import ast
import subprocess
import sys
from pathlib import Path

import cvr.runlog

SERVERS = ("cvr.api", "cvr.mcp")
SOURCE = Path(cvr.runlog.__file__).parent


def _imported(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_module_of_runlog_imports_a_server_package():
    files = sorted(SOURCE.glob("*.py"))
    assert files
    for path in files:
        for name in _imported(path):
            assert not name.startswith(SERVERS), (path.name, name)


def test_importing_runlog_loads_no_server_package():
    probe = (
        "import sys, cvr.runlog; "
        f"print([m for m in sys.modules if m.startswith({SERVERS!r})])"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip() == "[]"
