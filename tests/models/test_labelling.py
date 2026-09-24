"""The labelling result the labeller hands the verifier: a reference-shaped
mirror of ``CVContent`` plus removals, or a labelling failure. Its JSON
schema is what the LLM is asked to fill, so it must be strict-compatible."""

import pytest
from pydantic import ValidationError

from cvr.models import (
    ContentReferences,
    EducationReference,
    ExperienceReference,
    Labelling,
    LabellingFailure,
    Reference,
    RemovalReference,
    RemovalRule,
)


def test_reference_is_a_block_and_a_mandatory_quote():
    reference = Reference(block_id="body:3", quote="Python")
    assert (reference.block_id, reference.quote) == ("body:3", "Python")
    with pytest.raises(ValidationError):
        Reference(block_id="body:3")
    with pytest.raises(ValidationError):
        Reference(block_id="body:3", quote=None)


def test_entries_carry_one_dates_reference_for_the_whole_range():
    entry = ExperienceReference(
        title=Reference(block_id="body:4", quote="Engineer"),
        employer=Reference(block_id="body:5", quote="Acme"),
        location=None,
        dates=Reference(block_id="body:6", quote="Jan 2020 - Present"),
        bullets=[],
    )
    assert entry.dates.quote == "Jan 2020 - Present"
    assert not hasattr(entry, "start") and not hasattr(entry, "end")
    education = EducationReference(
        institution=Reference(block_id="body:7", quote="UCD"),
        qualification=Reference(block_id="body:8", quote="BSc"),
        dates=None,
        details=[],
    )
    assert education.dates is None


def test_removal_label_rule_is_the_closed_set_of_text_rules():
    label = RemovalReference(rule="RM_EMAIL", block_id="body:1", quote="a@example.org")
    assert label.rule is RemovalRule.EMAIL
    with pytest.raises(ValidationError):
        RemovalReference(rule="RM_PHOTO", block_id="body:1", quote="x")
    with pytest.raises(ValidationError):
        RemovalReference(rule="RM_NINTH", block_id="body:1", quote="x")


def test_labelling_failure_carries_a_reason():
    failure = LabellingFailure(reason="response did not match the schema")
    assert failure.reason.startswith("response")


def _object_schemas(schema: dict) -> list[dict]:
    """The root and every ``$defs`` entry that describes an object."""
    objects = [schema, *schema.get("$defs", {}).values()]
    return [obj for obj in objects if obj.get("type") == "object"]


def test_labelling_schema_is_strict_compatible():
    # Strict structured output (Azure OpenAI in Phase 2) needs every property
    # required, no additional properties, and nullable in place of optional;
    # the same schema has to serve both providers.
    schema = Labelling.model_json_schema()
    objects = _object_schemas(schema)
    assert objects, "no object schemas found"
    for obj in objects:
        properties = obj["properties"]
        assert sorted(obj["required"]) == sorted(properties), obj["title"]
        assert obj["additionalProperties"] is False, obj["title"]
        for name, prop in properties.items():
            assert "default" not in prop, f"{obj['title']}.{name} has a default"


def test_labelling_schema_closes_the_rule_enumeration():
    schema = Labelling.model_json_schema()
    rule = schema["$defs"]["RemovalReference"]["properties"]["rule"]
    assert sorted(rule["enum"]) == sorted(
        rule.value for rule in RemovalRule if rule is not RemovalRule.PHOTO
    )


def test_content_references_mirror_cv_content():
    from cvr.models import CVContent

    assert set(ContentReferences.model_fields) == set(CVContent.model_fields)
    tree = ContentReferences(
        name=Reference(block_id="body:0", quote="Padraig Lonergan"),
        profile=[],
        skills=[Reference(block_id="body:2", quote="QGIS")],
        education=[],
        experience=[],
        certifications=[],
        additional=[],
    )
    labelling = Labelling(content=tree, removals=[])
    assert labelling.content.skills[0].quote == "QGIS"
