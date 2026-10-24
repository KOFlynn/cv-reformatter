"""The retry rules: pure functions of a verified result. When to retry
(``decide_retry``), what to tell the labeller (``build_feedback``) and how
much unplaced text is left (``unplaced_chars``, the progress measure). Lives
in ``verify`` because every input is a ``VerifiedDocument``; depends on
``models`` and ``text`` only, never on ``pipeline`` (which wires it).

N, the most retries a Run may make, is read in one place, ``retry_max``,
from ``CVR_RETRY_MAX`` (default 2).
"""

import os
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Literal

from cvr.models.feedback import Feedback, UnlocatableHint, UnplacedRun
from cvr.text import significant_chars
from cvr.verify import Rejection, VerifiedDocument

__all__ = [
    "DEFAULT_RETRY_MAX",
    "ENV_RETRY_MAX",
    "Outcome",
    "RetryDecision",
    "build_feedback",
    "decide_retry",
    "retry_max",
    "unplaced_chars",
]

ENV_RETRY_MAX = "CVR_RETRY_MAX"
DEFAULT_RETRY_MAX = 2

# How the attempt just made ended: a usable answer, a labelling failure, or a
# provider outage (``ProviderUnavailable``; there is then no verified result).
Outcome = Literal["ok", "failed", "outage"]


def retry_max(env: Mapping[str, str] | None = None) -> int:
    """N from ``CVR_RETRY_MAX``: a whole number of retries, 0 or more
    (0 turns the retry off); unset or empty means 2. Anything else raises
    ``ValueError`` naming the variable."""
    source: Mapping[str, str] = os.environ if env is None else env
    raw = (source.get(ENV_RETRY_MAX) or "").strip()
    if not raw:
        return DEFAULT_RETRY_MAX
    if not raw.isascii() or not raw.isdigit():
        raise ValueError(f"{ENV_RETRY_MAX} must be a whole number, 0 or more")
    return int(raw)


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """``retry`` and the reason, a fixed string for the trace event:
    ``unplaced_text`` or ``first_attempt_failed`` (retry);
    ``nothing_unplaced``, ``no_progress``, ``attempts_exhausted``,
    ``retry_failed`` or ``outage`` (stop)."""

    retry: bool
    reason: str


def unplaced_chars(verified: VerifiedDocument) -> int:
    """The non-separator characters of the unplaced residue: the progress
    measure. Separator-only residue counts for nothing."""
    return sum(significant_chars(span.text) for span in verified.unplaced)


def decide_retry(
    verified: VerifiedDocument | None,
    previous_unplaced: int | None,
    attempts: int,
    max_retries: int,
    outcome: Outcome = "ok",
) -> RetryDecision:
    """Whether to make another attempt after the one just made.

    ``verified`` is the result of that attempt (``None`` only for an outage,
    which has none); ``previous_unplaced`` the ``unplaced_chars`` after the
    attempt before it (``None`` on the first); ``attempts`` the attempts made
    so far, that one included; ``max_retries`` is N. A retry is allowed while
    ``attempts <= max_retries``. A failed or unavailable retry stops the loop
    (the caller keeps the previous result); a failed first attempt is retried.
    """
    if outcome == "outage":
        return RetryDecision(False, "outage")
    if outcome == "failed":
        if attempts > 1:
            return RetryDecision(False, "retry_failed")
        if attempts > max_retries:
            return RetryDecision(False, "attempts_exhausted")
        return RetryDecision(True, "first_attempt_failed")
    if verified is None:
        raise ValueError("an attempt that ended ok has a verified result")
    unplaced = unplaced_chars(verified)
    if unplaced == 0:
        return RetryDecision(False, "nothing_unplaced")
    if previous_unplaced is not None and unplaced >= previous_unplaced:
        return RetryDecision(False, "no_progress")
    if attempts > max_retries:
        return RetryDecision(False, "attempts_exhausted")
    return RetryDecision(True, "unplaced_text")


def build_feedback(
    verified: VerifiedDocument, hints_from: Collection[Rejection] | None = None
) -> Feedback:
    """What to tell the labeller about ``verified``: every unplaced
    (non-separator) run by block and offsets, and the ``unlocatable``
    rejections in blocks that hold unplaced text as hints, by path. A
    ``conflict``, ``removed`` or ``bad_path`` rejection is never feedback,
    nor is an unlocatable removal (``removals[i]``: an addition cannot
    address it). No text: the labeller has the blocks. A labelling failure
    is ``unusable``; its unplaced runs are the whole document.

    ``hints_from``, when given, limits the hints to rejections in it: after a
    retry, ``verified`` also holds the additions' rejections, whose paths
    address the additions and not the first answer the labeller looks hints up
    in, so the caller passes the first answer's own rejections (the unplaced
    runs are sent whole either way)."""
    runs = [
        UnplacedRun(block_id=span.block_id, start=span.start, end=span.end)
        for span in verified.unplaced
    ]
    blocks = {run.block_id for run in runs}
    hints = [
        UnlocatableHint(path=r.path, block_id=r.block_id)
        for r in verified.rejections
        if r.reason == "unlocatable"
        and (hints_from is None or r in hints_from)
        and r.block_id in blocks
        and not r.path.startswith("removals[")
    ]
    return Feedback(unusable=verified.label_failed, unplaced=runs, unlocatable=hints)
