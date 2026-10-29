"""The price table the labeller's cost estimate reads: one place, one date
it was checked."""

import pytest

from cvr.label.pricing import (
    PRICE_TABLE,
    PRICE_TABLE_CHECKED,
    UnpricedModel,
    estimate_cost,
    require_price,
)


def test_price_table_has_the_default_model_and_a_checked_date():
    assert "claude-opus-5" in PRICE_TABLE
    assert PRICE_TABLE_CHECKED  # a non-empty date string


def test_cost_is_tokens_times_the_table_price():
    input_price, output_price = PRICE_TABLE["claude-opus-5"]
    cost = estimate_cost(
        "claude-opus-5", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == input_price + output_price


def test_haiku_is_priced_so_its_runs_do_not_cost_zero():
    assert "claude-haiku-5-5" in PRICE_TABLE
    input_price, output_price = PRICE_TABLE["claude-haiku-5-5"]
    cost = estimate_cost(
        "claude-haiku-5-5", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == input_price + output_price == 0.10 + 0.50


def test_sonnet_5_5_is_priced_so_its_runs_do_not_cost_zero():
    assert "claude-sonnet-5-5" in PRICE_TABLE
    input_price, output_price = PRICE_TABLE["claude-sonnet-5-5"]
    cost = estimate_cost(
        "claude-sonnet-5-5", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == input_price + output_price == 2.0 + 10.0


def test_unknown_model_costs_zero_rather_than_raising():
    assert (
        estimate_cost("some-future-model", input_tokens=100, output_tokens=100) == 0.0
    )


def test_gpt_5_4_is_priced_at_azure_data_zone_standard():
    # Azure Retail Prices API, "5.4 inp Dz" / "5.4 opt Dz", northeurope,
    # checked 2026-10-24 (see the comment in cvr.label.pricing).
    assert PRICE_TABLE["gpt-5.4"] == (2.75, 16.50)
    cost = estimate_cost("gpt-5.4", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 2.75 + 16.50


def test_gpt_5_4_mini_is_priced_at_azure_data_zone_standard():
    # Azure Retail Prices API, "5.4 mini Inp Dz" / "5.4 mini Opt Dz",
    # swedencentral and northeurope, checked 2026-10-24.
    assert PRICE_TABLE["gpt-5.4-mini"] == (0.825, 4.95)
    cost = estimate_cost(
        "gpt-5.4-mini", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == 0.825 + 4.95


def test_gpt_5_6_terra_is_priced_at_azure_data_zone_standard():
    # Azure Retail Prices API, "5.6 terra ShortCo Inp/Opt Std DZ",
    # swedencentral, checked 2026-10-29.
    assert PRICE_TABLE["gpt-5.6-terra"] == (2.20, 13.20)


def test_every_known_model_has_a_price():
    from cvr.label.config import DEFAULT_MODEL, KNOWN_MODELS

    assert DEFAULT_MODEL in KNOWN_MODELS
    assert "gpt-5.4-mini" in KNOWN_MODELS
    assert "gpt-5.6-terra" in KNOWN_MODELS
    unpriced = [model for model in KNOWN_MODELS if model not in PRICE_TABLE]
    assert not unpriced, f"no price in cvr.label.pricing.PRICE_TABLE for {unpriced}"
    for model in KNOWN_MODELS:
        input_price, output_price = require_price(model)
        assert input_price > 0 and output_price > 0, model


def test_require_price_fails_loudly_for_a_model_without_one():
    with pytest.raises(UnpricedModel, match="some-future-model"):
        require_price("some-future-model")
