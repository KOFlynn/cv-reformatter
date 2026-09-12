"""Eval metrics: pure functions over plain data. Depends on ``text`` and ``models`` only."""

from cvr.eval.finding import Finding
from cvr.eval.multiset import added_tokens

__all__ = ["Finding", "added_tokens"]
