"""Root conftest: present so that pytest puts ``tests/`` on ``sys.path`` and
the shared ``docx_text`` helper imports from any test directory.

Unit tests never trace to a real Langfuse: the settings are removed from every
test's environment, so a developer with the keys exported cannot send traces
from a test that builds an app or runs the eval without a tracer of its own.
A test that wants a tracer sets the variables itself (``monkeypatch.setenv``)
or injects one."""

import pytest


@pytest.fixture(autouse=True)
def no_langfuse_in_the_environment(monkeypatch):
    for name in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
        "CVR_TRACE_ENV",
    ):
        monkeypatch.delenv(name, raising=False)
