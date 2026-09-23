"""Shared builders for transform tests."""

from cvr.models import Span, Unit


def span(text: str, block_id: str = "body:0", start: int = 0) -> Span:
    return Span(block_id=block_id, start=start, end=start + len(text), text=text)


def unit(text: str, block_id: str = "body:0", start: int = 0) -> Unit:
    return Unit(spans=[span(text, block_id=block_id, start=start)])


def multi_unit(*spans: Span) -> Unit:
    return Unit(spans=list(spans))
