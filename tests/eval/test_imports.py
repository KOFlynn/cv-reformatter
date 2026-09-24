"""Importing a metric never loads the adapter's dependencies: ``cvr.eval``
re-exports the metrics only, and the adapter is imported by its own path.

Run in a fresh interpreter, since this test session has already imported
python-docx and the template elsewhere.
"""

import subprocess
import sys


def test_importing_cvr_eval_loads_neither_python_docx_nor_the_template():
    probe = (
        "import sys, cvr.eval; "
        "print(sorted(m for m in ('docx', 'docxtpl', 'cvr.template') if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
