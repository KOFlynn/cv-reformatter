"""The Azure counterpart of ``test_spike.py``: one real call through the
Azure OpenAI provider, proving strict structured output, the managed-identity
(or developer-sign-in) token and the deployment work together. Skipped unless
the Azure configuration is present (``CVR_LABEL_PROVIDER=azure_openai`` and
``CVR_LABEL_AZURE_ENDPOINT``); the credential comes from the default Azure
chain (``az login`` locally). The eval is the labeller's real test.
"""

import os
from pathlib import Path

import pytest

from cvr.label import LabellerConfig
from cvr.label.labeller import RealLabeller
from cvr.models import Labelling
from cvr.parse import parse

pytestmark = pytest.mark.skipif(
    os.environ.get("CVR_LABEL_PROVIDER") != "azure_openai"
    or not os.environ.get("CVR_LABEL_AZURE_ENDPOINT"),
    reason="Azure OpenAI not configured (CVR_LABEL_PROVIDER=azure_openai and "
    "CVR_LABEL_AZURE_ENDPOINT): the real labeller is exercised by the eval instead",
)


def test_azure_labeller_returns_a_schema_valid_tree_with_a_name_and_an_experience_entry():
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "fixtures" / "generated" / "c01__single-column.docx"
    parsed = parse(source.read_bytes())

    config = LabellerConfig.from_env()
    labeller = RealLabeller(config=config)

    result = labeller(parsed.blocks)

    assert isinstance(result, Labelling), getattr(result, "reason", result)
    assert result.content.name is not None
    assert result.content.name.quote
    assert len(result.content.experience) >= 1

    run = labeller.last_run
    assert run is not None
    assert run.label_failed is False
    assert run.config["provider"] == "azure_openai"
    assert run.input_tokens > 0
    assert run.cost_usd > 0
