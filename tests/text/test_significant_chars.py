"""``significant_chars``: the one count of non-whitespace, non-separator
characters that the retry's progress measure and the eval's retry account
share."""

import pytest

from cvr.text import significant_chars


@pytest.mark.parametrize(
    ("text", "count"),
    [("", 0), ("  \t", 0), ("- • |", 0), ("a b", 2), ("• Led a team", 8)],
)
def test_only_characters_that_are_neither_space_nor_separator_count(text, count):
    assert significant_chars(text) == count
