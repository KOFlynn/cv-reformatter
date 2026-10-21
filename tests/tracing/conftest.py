"""The tracing tests feed the pipeline the oracle labeller from
``tests/pipeline/``; put that directory on ``sys.path`` (as ``tests/api``
does) so ``oracle`` and ``pipeline_support`` import here."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
