"""The service runs without ``cvr.golden`` and ``cvr.eval``, which the image
leaves out. A fresh interpreter makes both unimportable, imports the entry
point, and reformats a golden-set document through the app end to end
(parse, verify, transform, render; the labeller is a stand-in that fails,
so every block goes through to the review appendix). Any import of either
package on that path, eager or lazy, fails the run."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = REPO_ROOT / "fixtures" / "generated" / "c04__single-column.docx"

SCRIPT = r"""
import importlib.abc
import sys

EXCLUDED = ("cvr.golden", "cvr.eval")


def excluded(name):
    return any(name == p or name.startswith(p + ".") for p in EXCLUDED)


class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if excluded(name):
            raise ImportError(f"{name} is not in the image")
        return None


sys.meta_path.insert(0, Blocked())

import cvr.api.__main__  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from cvr.api import create_app  # noqa: E402
from cvr.models import LabellingFailure  # noqa: E402

client = TestClient(create_app(lambda blocks: LabellingFailure(reason="stand-in")))
assert client.get("/health").status_code == 200
with open(sys.argv[1], "rb") as handle:
    response = client.post(
        "/reformat", files={"file": ("cv.docx", handle.read())}
    )
assert response.status_code == 200, response.status_code
assert response.content[:2] == b"PK"

loaded = sorted(name for name in sys.modules if excluded(name))
assert not loaded, loaded
print("ok")
"""


def test_the_service_imports_neither_golden_nor_eval():
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(DOCUMENT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    assert result.stdout.strip().endswith("ok")
