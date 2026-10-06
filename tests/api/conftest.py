"""The API tests inject the oracle labeller from ``tests/pipeline/``; put that
directory on ``sys.path`` so ``oracle`` and ``pipeline_support`` import here
as they do there. Every app here expects ``api_support.API_KEY``, set as
``CVR_API_KEY`` before each test builds one."""

import sys
from pathlib import Path

import pytest
from api_support import API_KEY

sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("CVR_API_KEY", API_KEY)
