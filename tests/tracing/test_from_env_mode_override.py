"""``Tracer.from_env(mode=)`` replaces ``CVR_TRACE_MODE`` for a surface that
never traces in full (the MCP server); the variable is still checked."""

import pytest

from cvr.tracing import ENV_TRACE_MODE, Tracer, UnknownTraceMode

KEYS = {"LANGFUSE_PUBLIC_KEY": "pk-lf-override-test", "LANGFUSE_SECRET_KEY": "sk-x"}


def test_the_override_wins_over_the_variable():
    tracer = Tracer.from_env({ENV_TRACE_MODE: "full"}, mode="structure")
    assert tracer.mode == "structure"
    assert Tracer.from_env({}, mode="full").mode == "full"


def test_the_override_with_keys_builds_a_structure_client():
    tracer = Tracer.from_env({**KEYS, ENV_TRACE_MODE: "full"}, mode="structure")
    assert tracer.enabled
    assert tracer.mode == "structure"
    tracer.shutdown()


def test_without_an_override_the_variable_decides():
    assert Tracer.from_env({ENV_TRACE_MODE: "full"}).mode == "full"


def test_a_typo_in_the_variable_still_fails_with_an_override():
    with pytest.raises(UnknownTraceMode, match=ENV_TRACE_MODE):
        Tracer.from_env({ENV_TRACE_MODE: "nope"}, mode="structure")


def test_an_unknown_override_fails():
    with pytest.raises(UnknownTraceMode):
        Tracer.from_env({}, mode="nope")
