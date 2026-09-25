"""The API tests inject the oracle labeller from ``tests/pipeline/``; put that
directory on ``sys.path`` so ``oracle`` and ``pipeline_support`` import here
as they do there."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
