"""Test the test: the fake pipeline over every Candidate.

Row 0 is the fake pipeline returning the Candidate's own content, which must
score clean on every metric; a malformed Candidate is the first thing to fail
here. The corruption rows each declare a blast radius, and the metrics are
proven independent by every corruption failing exactly its declared metrics.
"""

import pytest
from fake_pipeline import fake_pipeline, metric_inputs, unplaceable_share

from cvr.eval import added_tokens, appendix_rate, dropped_tokens
from cvr.golden import CANDIDATES_DIR, load_candidate

# Parametrised over files rather than loaded Candidates so that one malformed
# file fails its own cases, not the collection of the whole module.
CANDIDATE_FILES = sorted(CANDIDATES_DIR.glob("*.json"))


@pytest.mark.parametrize("path", CANDIDATE_FILES, ids=lambda p: p.stem)
def test_row_0_returning_the_candidate_unchanged_scores_clean(path):
    candidate = load_candidate(path)
    inputs = metric_inputs(candidate, fake_pipeline(candidate))
    assert (
        added_tokens(
            inputs.source_tokens,
            inputs.output_tokens,
            inputs.template_tokens,
            inputs.date_map,
        )
        == []
    )
    assert (
        dropped_tokens(
            inputs.source_tokens,
            inputs.output_tokens,
            inputs.removed_tokens,
            inputs.appendix_tokens,
        )
        == []
    )
    assert appendix_rate(
        inputs.appendix_tokens, inputs.source_content_tokens
    ) == unplaceable_share(candidate)


def test_the_fake_pipeline_maps_a_candidate_to_every_metric_input():
    candidate = load_candidate(CANDIDATES_DIR / "c01.json")
    inputs = metric_inputs(candidate, fake_pipeline(candidate))
    # Output units are the content leaves, plain strings in Candidate order.
    assert inputs.output_units[0] == candidate.content.name
    assert candidate.content.experience[0].bullets[0] in inputs.output_units
    assert candidate.content.experience[0].start.expected in inputs.output_units
    # Output tokens are the tokenised leaves plus template tokens (none yet).
    assert inputs.template_tokens == []
    assert "Airflow" in inputs.output_tokens
    # Each expected date maps to itself.
    assert ("03/2022", "03/2022") in inputs.date_map
    # Removed tokens are the PII values; they are in the source, not the output.
    assert "sinead.osampla@example.com" in inputs.removed_tokens
    assert "sinead.osampla@example.com" in inputs.source_tokens
    assert "sinead.osampla@example.com" not in inputs.output_tokens
    assert "sinead.osampla@example.com" not in inputs.source_content_tokens
    # The appendix is the unplaceable list, empty for c01.
    assert inputs.appendix_tokens == []
