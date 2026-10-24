"""What the retry loop earned a document: the characters it placed.

The report's "characters placed by a retry" is the unplaced non-separator
characters the retries took out of the appendix (``cvr.verify.retry``'s
progress measure: whitespace and separators count for nothing). A ``Run``
records the characters left after each retry (``RetryRun.unplaced_chars``)
and the runs the first retry was sent (``feedback.unplaced``, ids and
offsets), so the characters before the first retry are counted by reading
those runs out of the parsed blocks. Then::

    placed = sum over retries of max(0, before - after)

where ``before`` is the first attempt's unplaced characters for the first
retry and the previous retry's ``unplaced_chars`` for each later one. With
progress that never goes backwards (a retry only adds) this is the first
attempt's unplaced characters minus the final's. The re-ask of a failed first
answer (``feedback.unusable``) has no "before" (the first attempt placed
nothing and left no unplaced runs to count), so it contributes nothing itself;
the retries after it count from what it left.
"""

from collections.abc import Sequence

from cvr.models import Run, SourceBlock
from cvr.text import SEPARATORS

__all__ = ["retry_chars_placed"]


def _significant(text: str) -> int:
    return sum(1 for char in text if not (char.isspace() or char in SEPARATORS))


def retry_chars_placed(run: Run, blocks: Sequence[SourceBlock]) -> int:
    """The unplaced non-separator characters the Run's retries placed."""
    by_id = {block.id: block for block in blocks}
    placed = 0
    before: int | None = None
    for index, retry in enumerate(run.retries):
        if index == 0 and not retry.feedback.unusable:
            before = sum(
                _significant(by_id[part.block_id].text[part.start : part.end])
                for part in retry.feedback.unplaced
            )
        if before is not None:
            placed += max(0, before - retry.unplaced_chars)
        before = retry.unplaced_chars
    return placed
