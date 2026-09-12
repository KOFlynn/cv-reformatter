"""Eval metrics: pure functions over plain data. Depends on ``text`` and ``models`` only."""

from cvr.eval.appendix import appendix_rate
from cvr.eval.finding import Finding
from cvr.eval.multiset import added_tokens, dropped_tokens

__all__ = ["Finding", "added_tokens", "appendix_rate", "dropped_tokens"]
