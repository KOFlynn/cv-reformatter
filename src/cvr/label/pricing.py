"""One price table for the labeller's cost estimate, USD per million tokens.
Checked against https://claude.com/pricing on 2026-09-23; update
``PRICE_TABLE_CHECKED`` whenever the table is re-checked. Quotes copy the
CV, so output tokens dominate; the spec's baseline is roughly $7 per
48-document run on Opus 5, $3 on Sonnet 5.
"""

__all__ = ["PRICE_TABLE", "PRICE_TABLE_CHECKED", "estimate_cost"]

PRICE_TABLE_CHECKED = "2026-09-23"

# model name -> (input $ / million tokens, output $ / million tokens)
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-5.5": (4.0, 20.0),
    "claude-sonnet-5": (2.0, 10.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of one request, from the price table. A model the table does
    not know costs zero rather than raising, so a labelling failure or a
    provider change never crashes cost accounting."""
    prices = PRICE_TABLE.get(model)
    if prices is None:
        return 0.0
    input_price, output_price = prices
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
