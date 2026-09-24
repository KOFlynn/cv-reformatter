"""Test the test: the fake pipeline over every Candidate.

Row 0 is the fake pipeline returning the Candidate's own content, which must
score clean on every metric; a malformed Candidate is the first thing to fail
here. Each corruption row declares a blast radius, and the metrics are proven
independent by every corruption failing exactly the metrics it declares.

Two rows are the evidence for ADR-0007 that no single check would have been
enough: "swap two words inside a bullet" fails provenance while both
multiset checks pass, and "straighten a curly apostrophe" fails punctuation
fidelity while provenance passes. See the row comments in ``corruptions``.
"""

import pytest
from corruptions import CHECKS, CORRUPTIONS, Direction, NotApplicable, failed_metrics
from fake_pipeline import fake_pipeline, metric_inputs

from cvr.eval import placement_accuracy
from cvr.golden import CANDIDATES_DIR, load_candidate
from cvr.template import template_text, template_tokens

# Parametrised over files rather than loaded Candidates so that one malformed
# file fails its own cases, not the collection of the whole module.
CANDIDATE_FILES = sorted(CANDIDATES_DIR.glob("*.json"))
# An empty directory would otherwise parametrise to nothing and pass silently.
assert CANDIDATE_FILES, f"no Candidate files in {CANDIDATES_DIR}"
candidates = pytest.mark.parametrize("path", CANDIDATE_FILES, ids=lambda p: p.stem)
corruptions = pytest.mark.parametrize("corruption", CORRUPTIONS, ids=lambda c: c.name)


def damaged_result(corruption, candidate):
    """The corruption applied to the honest result. The matrix is asserted
    over every committed Candidate, so a row that does not apply to one is a
    hole in the evidence, not a case to skip: a new Candidate must carry what
    every row damages (a job with bullets, two jobs, an email, an apostrophe
    or a hyphen)."""
    try:
        return corruption.damage(candidate, fake_pipeline(candidate))
    except NotApplicable as why:
        pytest.fail(f"{corruption.name!r} does not apply to {candidate.id}: {why}")


@candidates
def test_row_0_returning_the_candidate_unchanged_fails_no_metric(path):
    candidate = load_candidate(path)
    inputs = metric_inputs(candidate, fake_pipeline(candidate))
    assert failed_metrics(candidate, inputs) == set()


def test_the_fake_pipeline_maps_a_candidate_to_every_metric_input():
    candidate = load_candidate(CANDIDATES_DIR / "c01.json")
    inputs = metric_inputs(candidate, fake_pipeline(candidate))
    # Output units are the content leaves, plain strings in Candidate order.
    assert inputs.output_units[0] == candidate.content.name
    assert candidate.content.experience[0].bullets[0] in inputs.output_units
    assert candidate.content.experience[0].start.expected in inputs.output_units
    # Output tokens are the tokenised leaves plus the template's own fixed
    # text, extracted from the built template rather than typed in.
    assert inputs.template_tokens == template_tokens()
    assert "Airflow" in inputs.output_tokens
    assert "Recruitment" in inputs.output_tokens
    assert "Recruitment" not in inputs.source_tokens
    # Each expected date maps to itself.
    assert ("03/2022", "03/2022") in inputs.date_map
    # Removed tokens are the PII values; they are in the source, not the output.
    assert "sinead.osampla@example.com" in inputs.removed_tokens
    assert "sinead.osampla@example.com" in inputs.source_tokens
    assert "sinead.osampla@example.com" not in inputs.output_tokens
    assert "sinead.osampla@example.com" not in inputs.source_content_tokens
    # The appendix is the unplaceable list, empty for c01.
    assert inputs.appendix_tokens == []
    # The placed content is what the structural metrics compare to the Candidate's.
    assert inputs.output_content == candidate.content
    # Output text is what pii_leak reads: every placed leaf and the appendix
    # in the body, the template's own header text; no PII value in either.
    assert candidate.content.experience[0].bullets[0] in inputs.output_text["body"]
    assert "sinead.osampla@example.com" not in inputs.output_text["body"]
    assert "sinead.osampla@example.com" not in inputs.output_text["header"]
    # No images on either side until ticket 06's template says otherwise.
    assert inputs.output_image_hashes == []
    assert inputs.template_image_hashes == []
    # Source blocks are the leaves themselves, since there is no document:
    # content, PII and unplaceable fragments, everything a Layout would print.
    assert candidate.content.experience[0].bullets[0] in inputs.source_blocks
    assert candidate.pii.email in inputs.source_blocks
    # Template units are the template's fixed paragraphs, read from the file.
    assert inputs.template_units == template_text()
    # Every output unit is located in a source block, and the raw pair is
    # what punctuation fidelity compares; the honest pipeline's pairs are equal.
    assert len(inputs.pairs) == len(inputs.output_units)
    assert all(span == unit for span, unit in inputs.pairs)
    assert (candidate.content.name, candidate.content.name) in inputs.pairs


# The spec's table ("Test the test", Phase 0 spec), copied here as data so the
# corruption module cannot drift from it: a row is named, the metrics it must
# fail are listed, and the direction is given where the spec gives one. The
# spec writes "recall down" alone for the appendix row; with two figures
# reported separately, that reads as precision unchanged.
SPEC_TABLE: dict[str, tuple[set[str], Direction | None]] = {
    "insert a word into a bullet": (
        {"added", "provenance", "placement"},
        Direction(precision="down", recall="down"),
    ),
    "drop a bullet": (
        {"dropped", "placement"},
        Direction(precision="unchanged", recall="down"),
    ),
    "re-emit the source email in the header": ({"pii"}, None),
    "reverse experience order": ({"ordering"}, None),
    "swap two words inside a bullet": (
        {"provenance", "placement"},
        Direction(precision="down", recall="down"),
    ),
    "move one job's bullets into the appendix": (
        {"appendix", "placement"},
        Direction(precision="unchanged", recall="down"),
    ),
    "leave the photo in": ({"image"}, None),
    "straighten a curly apostrophe": ({"punctuation"}, None),
    "join two slices out of source order": ({"provenance"}, None),
}
SPEC_COLUMNS = {
    "added",
    "dropped",
    "provenance",
    "punctuation",
    "pii",
    "image",
    "placement",
    "ordering",
    "appendix",
}


def test_the_corruption_table_is_the_spec_table():
    assert CHECKS.keys() == SPEC_COLUMNS
    assert {c.name for c in CORRUPTIONS} == SPEC_TABLE.keys()
    assert len(CORRUPTIONS) == len(SPEC_TABLE) == 9
    for corruption in CORRUPTIONS:
        fails, direction = SPEC_TABLE[corruption.name]
        assert corruption.fails == fails, corruption.name
        assert corruption.passes == SPEC_COLUMNS - fails, corruption.name
        assert corruption.direction == direction, corruption.name


@corruptions
def test_every_corruption_declares_a_blast_radius_over_every_metric(corruption):
    # A metric a row forgets to place is a metric nobody has decided about, so
    # adding a column to CHECKS forces every row to be revisited.
    assert corruption.fails.isdisjoint(corruption.passes)
    assert corruption.fails | corruption.passes == CHECKS.keys()


@candidates
@corruptions
def test_a_corruption_fails_every_metric_inside_its_blast_radius_and_no_other(
    path, corruption
):
    candidate = load_candidate(path)
    damaged = damaged_result(corruption, candidate)
    inputs = metric_inputs(candidate, damaged)
    assert failed_metrics(candidate, inputs) == corruption.fails


directed = pytest.mark.parametrize(
    "corruption",
    [c for c in CORRUPTIONS if c.direction is not None],
    ids=lambda c: c.name,
)


@candidates
@directed
def test_a_corruption_moves_precision_and_recall_in_its_declared_direction(
    path, corruption
):
    # Row 0 scores 1.0 on both, so "down" is strictly below one and
    # "unchanged" is still one; a metric failing for the wrong reason (recall
    # falling when only precision should) is caught here, not by the blast radius.
    candidate = load_candidate(path)
    damaged = damaged_result(corruption, candidate)
    inputs = metric_inputs(candidate, damaged)
    overall = placement_accuracy(inputs.output_content, candidate.content).overall
    assert (overall.precision < 1.0) == (corruption.direction.precision == "down")
    assert (overall.recall < 1.0) == (corruption.direction.recall == "down")
