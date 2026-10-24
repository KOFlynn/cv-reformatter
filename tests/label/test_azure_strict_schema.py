"""Both schemas the labeller sends (``Labelling`` for the first attempt,
``Additions`` for a retry) against Azure OpenAI's strict structured-output
limits (ticket 17), offline.

Source: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs
(page dated 2026-08-24, read 2026-10-24), section "JSON Schema support and
limitations":

- supported types: string, number, boolean, integer, object, array, enum,
  anyOf; the root object cannot be ``anyOf``;
- all fields must be required (optional is a union with ``null``);
- ``additionalProperties: false`` on every object;
- "up to 100 object properties total, with up to five levels of nesting";
- unsupported keywords: ``minLength maxLength pattern format`` (strings),
  ``minimum maximum multipleOf`` (numbers), ``patternProperties
  unevaluatedProperties propertyNames minProperties maxProperties``
  (objects), ``unevaluatedItems contains minContains maxContains minItems
  maxItems uniqueItems`` (arrays);
- ``$defs`` and recursion are supported.

Beyond the page, and conservatively: ``default``, ``allOf``, ``oneOf`` and
``not`` are refused here too (OpenAI's own strict-mode list). Nesting is
counted in objects (``Labelling``: 4 of 5); the page does not say whether
arrays count as levels too, and if they do ``Labelling`` is at 6, one over, so
the headroom test records both figures. The page gives no enum limit.
"""

from typing import Any

import pytest

from cvr.label.versions import ADDITIONS_JSON_SCHEMA, LABELLING_JSON_SCHEMA

MAX_PROPERTIES = 100
MAX_NESTING = 5

UNSUPPORTED = {
    "minLength", "maxLength", "pattern", "format",
    "minimum", "maximum", "multipleOf",
    "patternProperties", "unevaluatedProperties", "propertyNames",
    "minProperties", "maxProperties",
    "unevaluatedItems", "contains", "minContains", "maxContains",
    "minItems", "maxItems", "uniqueItems",
    "default", "allOf", "oneOf", "not",
}  # fmt: skip
SUPPORTED_TYPES = {"string", "number", "boolean", "integer", "object", "array", "null"}


def scan(schema: dict[str, Any]) -> tuple[list[str], int, int, int]:
    """(every way ``schema`` breaks Azure's strict-mode rules as sentences,
    its object-property total, its object nesting depth, its nesting depth
    with arrays counted as levels too). The limit is applied to the object
    depth, the reading of the page's "five levels of nesting" that matches
    OpenAI's examples; the array-inclusive figure is recorded because the page
    does not say which is meant (see ticket 17)."""
    problems: list[str] = []
    definitions = schema.get("$defs", {})
    properties_total = 0
    deepest_objects = 0
    deepest_any = 0

    if "anyOf" in schema or schema.get("type") != "object":
        problems.append("the root must be an object, not anyOf")

    def visit(
        node: dict[str, Any], where: str, objects: int, levels: int, seen: frozenset
    ) -> None:
        nonlocal properties_total, deepest_objects, deepest_any
        if "$ref" in node:
            target = node["$ref"].removeprefix("#/$defs/")
            if target not in definitions:
                problems.append(f"{where}: unresolved reference {node['$ref']}")
            elif target not in seen:
                visit(
                    definitions[target],
                    f"{where}->{target}",
                    objects,
                    levels,
                    seen | {target},
                )
            return
        for keyword in sorted(UNSUPPORTED & node.keys()):
            problems.append(f"{where}: unsupported keyword {keyword}")
        kind = node.get("type")
        for one in [kind] if isinstance(kind, str) else kind or []:
            if one not in SUPPORTED_TYPES:
                problems.append(f"{where}: unsupported type {one}")
        for index, option in enumerate(node.get("anyOf", [])):
            visit(option, f"{where}|{index}", objects, levels, seen)
        if kind == "array":
            deepest_any = max(deepest_any, levels + 1)
            visit(node.get("items", {}), f"{where}[]", objects, levels + 1, seen)
        if kind == "object":
            deepest_objects = max(deepest_objects, objects + 1)
            deepest_any = max(deepest_any, levels + 1)
            properties = node.get("properties", {})
            properties_total += len(properties)
            if sorted(node.get("required", [])) != sorted(properties):
                problems.append(f"{where}: not every property is required")
            if node.get("additionalProperties") is not False:
                problems.append(f"{where}: additionalProperties is not false")
            for name, child in properties.items():
                visit(child, f"{where}.{name}", objects + 1, levels + 1, seen)

    visit(schema, schema.get("title", "root"), 0, 0, frozenset())
    if properties_total > MAX_PROPERTIES:
        problems.append(f"{properties_total} properties, over {MAX_PROPERTIES}")
    if deepest_objects > MAX_NESTING:
        problems.append(f"nesting depth {deepest_objects}, over {MAX_NESTING}")
    return problems, properties_total, deepest_objects, deepest_any


def strict_problems(schema: dict[str, Any]) -> list[str]:
    return scan(schema)[0]


@pytest.mark.parametrize(
    "schema",
    [LABELLING_JSON_SCHEMA, ADDITIONS_JSON_SCHEMA],
    ids=["Labelling", "Additions"],
)
def test_the_schema_meets_azures_strict_mode_limits(schema):
    assert strict_problems(schema) == []


def test_the_schemas_headroom_is_recorded():
    # Recorded 2026-10-24 so a growing schema is noticed here, not on Azure
    # (and a schema change needs a version bump and an eval anyway). Figures
    # are (properties, object depth, depth with arrays counted). Labelling is
    # one level over the limit if the page's "levels of nesting" counts arrays
    # as well as objects: only a live call on the deployment settles that.
    assert scan(LABELLING_JSON_SCHEMA)[1:] == (49, 4, 6)
    assert scan(ADDITIONS_JSON_SCHEMA)[1:] == (5, 3, 4)


# Test the test: the checker rejects each way a schema can break the rules.
def _object(properties: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
        **overrides,
    }


@pytest.mark.parametrize(
    ("schema", "fragment"),
    [
        (_object({"a": {"type": "string"}}, required=[]), "not every property"),
        (
            _object({"a": {"type": "string"}}, additionalProperties=True),
            "additionalProperties",
        ),
        (_object({"a": {"type": "string", "maxLength": 3}}), "maxLength"),
        (_object({"a": {"type": "array", "items": {}, "minItems": 1}}), "minItems"),
        (_object({"a": {"type": "string", "default": "x"}}), "default"),
        (_object({"a": {"type": "string", "pattern": "x"}}), "pattern"),
        ({"anyOf": [_object({}), _object({})]}, "root"),
        (_object({"a": {"$ref": "#/$defs/missing"}}), "unresolved"),
        (
            _object({f"p{i}": {"type": "string"} for i in range(101)}),
            "101 properties",
        ),
        (
            _object(
                {
                    "a": _object(
                        {
                            "b": _object(
                                {
                                    "c": _object(
                                        {
                                            "d": _object(
                                                {
                                                    "e": _object(
                                                        {"f": {"type": "string"}}
                                                    )
                                                }
                                            )
                                        }
                                    )
                                }
                            )
                        }
                    )
                }
            ),
            "nesting depth 6",
        ),
    ],
)
def test_the_checker_catches_each_violation(schema, fragment):
    assert any(fragment in problem for problem in strict_problems(schema))
