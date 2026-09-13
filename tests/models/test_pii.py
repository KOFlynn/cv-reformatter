import pytest
from pydantic import ValidationError

from cvr.golden import PII as GoldenPII
from cvr.models import PII, RemovalRule


def test_every_removal_rule_is_named_by_its_id():
    # The nine rules of the brief; the id is the string the transform log and
    # the PII leak metric both carry.
    assert {rule.value for rule in RemovalRule} == {
        "RM_PHONE",
        "RM_EMAIL",
        "RM_ADDRESS",
        "RM_URL",
        "RM_PHOTO",
        "RM_DOB",
        "RM_PERSONAL",
        "RM_REFEREE",
        "RM_HEADING",
    }
    assert RemovalRule.REFEREE == "RM_REFEREE"


def test_pii_defaults_to_nothing_to_remove():
    pii = PII()
    assert pii.phone is None
    assert pii.address == []
    assert pii.personal.nationality is None
    assert pii.referees == []


def test_pii_rejects_an_unknown_key():
    # No `photo` key: the photo is a Layout decision, not a Candidate value.
    with pytest.raises(ValidationError):
        PII.model_validate({"photo": "sample.png"})


def test_the_golden_set_reuses_the_models_pii():
    assert GoldenPII is PII
