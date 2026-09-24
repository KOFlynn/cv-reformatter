"""The one spike test that reaches a real model: proves native structured
output, adaptive thinking and effort work together on the default model.
Skipped without an API key. The spec is explicit that the eval job, not
this test, is the labeller's real coverage - this only proves the wiring
reaches the provider at all.
"""

import os
from pathlib import Path

import pytest

from cvr.label import LabellerConfig
from cvr.label.labeller import RealLabeller
from cvr.models import Labelling
from cvr.parse import parse

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set: the real labeller is exercised by the eval job instead",
)


def test_real_labeller_returns_a_schema_valid_tree_with_a_name_and_an_experience_entry():
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
    entry = result.content.experience[0]
    assert entry.title is not None or entry.employer is not None or entry.bullets

    run = labeller.last_run
    assert run is not None
    assert run.label_failed is False
    assert run.config.model == config.model
    assert run.prompt_version
    assert run.schema_version
