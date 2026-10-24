"""The retry's answer: path-addressed additions on top of the first answer.
Its JSON schema is what the LLM is asked to fill on a retry, so like
``Labelling``'s it must be strict-compatible."""

import pytest
from pydantic import ValidationError

from cvr.models import Addition, Additions, Reference


def test_an_addition_is_a_path_and_a_reference():
    addition = Addition(
        path="experience[0].bullets", reference=Reference(block_id="body:3", quote="x")
    )
    assert addition.path == "experience[0].bullets"
    assert addition.reference.block_id == "body:3"
    with pytest.raises(ValidationError):
        Addition(path="skills")
    with pytest.raises(ValidationError):
        Addition(reference=Reference(block_id="body:3", quote="x"))


def test_additions_is_a_list_and_may_be_empty():
    assert Additions(additions=[]).additions == []
    with pytest.raises(ValidationError):
        Additions()


def test_additions_schema_is_strict_compatible():
    schema = Additions.model_json_schema()
    objects = [
        obj
        for obj in [schema, *schema.get("$defs", {}).values()]
        if obj.get("type") == "object"
    ]
    assert {obj["title"] for obj in objects} == {"Additions", "Addition", "Reference"}
    for obj in objects:
        properties = obj["properties"]
        assert sorted(obj["required"]) == sorted(properties), obj["title"]
        assert obj["additionalProperties"] is False, obj["title"]
        for name, prop in properties.items():
            assert "default" not in prop, f"{obj['title']}.{name} has a default"
