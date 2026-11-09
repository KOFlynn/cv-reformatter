"""The fixed ways a Run fails, shared by both surfaces: the labeller's two
errors by type, anything else ``internal``, and never an exception's text."""

import pytest

from cvr.label import LabellerMisconfigured, ProviderUnavailable
from cvr.runlog import MAX_UPLOAD_BYTES, ErrorCategory, category_of


def test_the_upload_limit_is_five_megabytes():
    assert MAX_UPLOAD_BYTES == 5 * 1024 * 1024


def test_the_categories_are_the_specs_eight():
    assert [c.value for c in ErrorCategory] == [
        "outside_workspace",
        "not_found",
        "not_docx",
        "too_large",
        "exists",
        "provider_unavailable",
        "misconfigured",
        "internal",
    ]


@pytest.mark.parametrize(
    ("exc", "category"),
    [
        (ProviderUnavailable("overloaded"), ErrorCategory.PROVIDER_UNAVAILABLE),
        (LabellerMisconfigured("bad key"), ErrorCategory.MISCONFIGURED),
        (ValueError("Jane Doe"), ErrorCategory.INTERNAL),
        (KeyError("x"), ErrorCategory.INTERNAL),
    ],
)
def test_an_exception_is_classified_by_its_type(exc, category):
    assert category_of(exc) is category
