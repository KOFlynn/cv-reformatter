"""The price table the labeller's cost estimate reads: one place, one date
it was checked."""

from cvr.label.pricing import PRICE_TABLE, PRICE_TABLE_CHECKED, estimate_cost


def test_price_table_has_the_default_model_and_a_checked_date():
    assert "claude-opus-5" in PRICE_TABLE
    assert PRICE_TABLE_CHECKED  # a non-empty date string


def test_cost_is_tokens_times_the_table_price():
    input_price, output_price = PRICE_TABLE["claude-opus-5"]
    cost = estimate_cost(
        "claude-opus-5", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == input_price + output_price


def test_unknown_model_costs_zero_rather_than_raising():
    assert (
        estimate_cost("some-future-model", input_tokens=100, output_tokens=100) == 0.0
    )
