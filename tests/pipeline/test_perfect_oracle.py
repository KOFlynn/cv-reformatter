"""The perfect oracle through the whole pipeline over every generated
document: every metric, fed through the adapter from the rendered output,
at its best. What is left for the real labeller to get wrong is only what a
labeller can get wrong."""

import pytest
from oracle import Oracle, OracleMiss
from pipeline_support import GENERATED, document, score

from cvr.eval import FieldType
from cvr.pipeline import reformat


@pytest.mark.slow
@pytest.mark.parametrize("stem", GENERATED)
def test_perfect_oracle_scores_clean_on_every_metric(stem):
    doc = document(stem)
    output, run = reformat(doc.source, Oracle(doc.candidate, doc.manifest))
    scores = score(doc.candidate, doc.source, output, run, doc.manifest.headings)

    assert {
        gate: findings for gate, findings in scores.hard_gates.items() if findings
    } == {}
    assert scores.punctuation == []
    assert scores.ordering.correct
    assert all(n == 0 for n in scores.ordering.unmatched.values())
    for field in FieldType:
        tally = scores.placement.by_field[field]
        assert tally.hits == tally.actual == tally.expected, field
    assert scores.adapted.appendix == list(doc.candidate.unplaceable)
    assert [span.text for span in run.unplaced] == scores.adapted.appendix
    assert run.label_failed is False


def test_a_candidate_string_missing_from_the_document_fails_loudly():
    doc = document("c04__single-column")
    content = doc.candidate.content.model_copy(
        update={"skills": ["Underwater welding"]}
    )
    candidate = doc.candidate.model_copy(update={"content": content})
    with pytest.raises(OracleMiss, match="Underwater welding"):
        reformat(doc.source, Oracle(candidate, doc.manifest))
