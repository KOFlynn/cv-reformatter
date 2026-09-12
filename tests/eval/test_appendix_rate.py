import pytest

from cvr.eval import appendix_rate

# Source content tokens are the source minus rule-removed tokens, so the rate
# does not move with how much contact detail a layout happens to carry.
CONTENT = ["Led", "the", "team", "Python", "Available", "for", "work", "now"]


def test_empty_appendix_is_a_rate_of_zero():
    assert appendix_rate([], CONTENT) == 0.0


def test_rate_is_appendix_tokens_over_source_content_tokens():
    assert appendix_rate(["Available", "for", "work", "now"], CONTENT) == 0.5


def test_multiplicity_counts_on_both_sides():
    assert appendix_rate(["now", "now"], [*CONTENT, "now"]) == pytest.approx(2 / 9)


def test_empty_inputs_are_a_rate_of_zero():
    assert appendix_rate([], []) == 0.0


def test_appendix_with_no_source_content_is_a_rate_of_one():
    # Everything in the appendix is unaccounted for; added_tokens says where it
    # came from. The rate stays a number rather than a division error.
    assert appendix_rate(["stray"], []) == 1.0
