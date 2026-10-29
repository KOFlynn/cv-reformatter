"""One price table for the labeller's cost estimate, USD per million tokens.
The Claude rows were checked against https://claude.com/pricing on 2026-10-19;
the gpt-5.4 and gpt-5.4-mini rows on 2026-10-24 and the gpt-5.6-terra row on
2026-10-29 (see below). ``PRICE_TABLE_CHECKED`` is the oldest of them: update it whenever the whole table is re-checked. Quotes copy
the CV, so output tokens dominate: a 48-document run is about $1.6 on the
default, Sonnet 5.5, and was about $3.3 on Opus 5.5 (ADR-0011).
"""

__all__ = [
    "PRICE_TABLE",
    "PRICE_TABLE_CHECKED",
    "UnpricedModel",
    "estimate_cost",
    "require_price",
]

PRICE_TABLE_CHECKED = "2026-10-19"

# model name -> (input $ / million tokens, output $ / million tokens)
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    # The base tier, prompts up to 100K tokens; every golden-set prompt is far below.
    "claude-haiku-5-5": (0.10, 0.50),
    # Azure OpenAI gpt-5.4, Data Zone Standard, context up to 272K tokens (the
    # long-context meters are separate; every golden-set prompt is far below).
    # Source, checked 2026-10-24: Microsoft's Azure Retail Prices API
    # (https://prices.azure.com/api/retail/prices, serviceName "Foundry Models",
    # meters "5.4 inp Dz" and "5.4 opt Dz", northeurope, effective 2026-06-01;
    # the same figures in every EU Data Zone region listed), which is what the
    # pricing page https://azure.microsoft.com/en-us/pricing/details/azure-openai/
    # renders from (its static HTML shows "$-" placeholders). Cached input
    # ("5.4 cd inp Dz") is $0.275, a tenth of input; it is not in the table
    # because nothing here requests caching (Azure's automatic caching, if it
    # applies, only makes the real cost lower than this estimate).
    "gpt-5.4": (2.75, 16.50),
    # gpt-5.4-mini, Data Zone Standard, same source and date: meters "5.4 mini
    # Inp Dz" ($0.825) and "5.4 mini Opt Dz" ($4.95), queried for swedencentral
    # (effective 2026-03-01) and northeurope (effective 2026-06-01), the same
    # figures. Cached input ("5.4 mini cd Inp Dz") is $0.0825; not in the table,
    # as for gpt-5.4.
    "gpt-5.4-mini": (0.825, 4.95),
    # gpt-5.6-terra (version 2026-07-09), Data Zone Standard, short context,
    # same source, checked 2026-10-29: meters "5.6 terra ShortCo Inp Std DZ"
    # ($2.20) and "5.6 terra ShortCo Opt Std DZ" ($13.20), swedencentral,
    # effective 2026-08-01. The API also lists "61 terra" meters (effective
    # 2026-10-01, $1.20 / $6.00): a different model, not used here. Cached input
    # ("5.6 terra ShortCo Cd Inp Std DZ") is $0.22.
    "gpt-5.6-terra": (2.20, 13.20),
}


class UnpricedModel(KeyError):
    """A model the labeller is configured for has no row in ``PRICE_TABLE``."""


def require_price(model: str) -> tuple[float, float]:
    """The model's (input, output) prices, or :class:`UnpricedModel`. For
    tests and for anything that must not silently read zero."""
    try:
        return PRICE_TABLE[model]
    except KeyError:
        raise UnpricedModel(
            f"no price for model {model!r}: add it to cvr.label.pricing.PRICE_TABLE"
        ) from None


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of one request, from the price table. A model the table does
    not know costs zero rather than raising, so a labelling failure or a
    provider change never crashes cost accounting."""
    prices = PRICE_TABLE.get(model)
    if prices is None:
        return 0.0
    input_price, output_price = prices
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
