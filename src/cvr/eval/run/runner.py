"""Every selected document through ``reformat`` and ``score``, concurrently.

At most ``concurrency`` documents are in flight at once (each in a worker
thread, since the pipeline is synchronous). A provider that is unavailable
(a 429, an overload, a dropped connection: ``ProviderUnavailable``, raised
once the client's own two retries are spent) is retried with exponential
backoff and jitter, and every retry is counted for the report. A
misconfigured labeller is not retried, and anything else raised is a
defect; either way the document is recorded as errored, which fails the
run, rather than losing every other document's result.
"""

import asyncio
import random
import sys
import traceback
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from time import perf_counter

from cvr.eval.run.cache import (
    CachedLabeller,
    CacheStats,
    LabellerIdentity,
    ResponseCache,
    cache_key,
    label_run_of,
)
from cvr.eval.run.documents import Document
from cvr.eval.run.score import Scores, score
from cvr.label.errors import ProviderUnavailable
from cvr.models import LabelRun
from cvr.pipeline import Labeller, reformat

__all__ = [
    "BACKOFF_BASE",
    "BACKOFF_CAP",
    "CONCURRENCY",
    "MAX_RETRIES",
    "DocumentResult",
    "backoff",
    "run_documents",
]

CONCURRENCY = 4
MAX_RETRIES = 5
BACKOFF_BASE = 2.0  # seconds before the first retry, doubling each time
BACKOFF_CAP = 60.0


@dataclass(frozen=True)
class DocumentResult:
    """One document's outcome: its scores, or the error that stopped it."""

    document: Document
    scores: Scores | None
    label_run: LabelRun | None
    label_failed: bool
    cache_hit: bool
    retries: int
    seconds: float
    error: str | None = None


def backoff(retry: int, jitter: float) -> float:
    """Seconds to wait before retry number ``retry`` (from 0): the base
    doubled per retry up to the cap, scaled by ``jitter`` in ``[0, 1)`` into
    its upper half, so concurrent workers that hit the limit together do not
    come back together."""
    return min(BACKOFF_CAP, BACKOFF_BASE * 2**retry) * (0.5 + jitter / 2)


@dataclass
class _Counted:
    """A labeller with no cache in front: every call is a live call."""

    labeller: Labeller
    stats: CacheStats

    @property
    def last_run(self) -> LabelRun | None:
        return label_run_of(self.labeller)

    def __call__(self, blocks):
        self.stats.record_live_call()
        return self.labeller(blocks)


def _labeller(
    document: Document,
    live: Callable[[Document], Labeller],
    identity: LabellerIdentity,
    cache: ResponseCache | None,
    read_cache: bool,
    stats: CacheStats,
) -> Labeller:
    if cache is None:
        return _Counted(live(document), stats)
    return CachedLabeller(
        live=lambda: live(document),
        cache=cache,
        key=cache_key(identity, document.source),
        stats=stats,
        read=read_cache,
    )


async def _one(
    document: Document,
    make: Callable[[], Labeller],
    semaphore: asyncio.Semaphore,
    sleep: Callable[[float], Awaitable[None]],
    jitter: Callable[[], float],
) -> DocumentResult:
    async with semaphore:
        started = perf_counter()
        retries = 0
        while True:
            labeller = make()
            try:
                output, run = await asyncio.to_thread(
                    reformat, document.source, labeller
                )
                scores = await asyncio.to_thread(
                    score, document.candidate, document.source, output, run
                )
            except ProviderUnavailable as exc:
                if retries < MAX_RETRIES:
                    # Held through the wait: backing off means less load.
                    await sleep(backoff(retries, jitter()))
                    retries += 1
                    continue
                error = f"gave up after {retries} retries: {exc}"
            # Misconfigured, or a defect: recorded (and the traceback printed)
            # so it fails the run without losing every other document's result.
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                error = f"{type(exc).__name__}: {exc}"
            else:
                return DocumentResult(
                    document=document,
                    scores=scores,
                    label_run=run.label,
                    label_failed=run.label_failed,
                    cache_hit=getattr(labeller, "hit", False),
                    retries=retries,
                    seconds=perf_counter() - started,
                )
            return DocumentResult(
                document=document,
                scores=None,
                label_run=None,
                label_failed=False,
                cache_hit=False,
                retries=retries,
                seconds=perf_counter() - started,
                error=error,
            )


async def _all(
    documents: Sequence[Document],
    makers: Sequence[Callable[[], Labeller]],
    concurrency: int,
    sleep: Callable[[float], Awaitable[None]],
    jitter: Callable[[], float],
) -> list[DocumentResult]:
    semaphore = asyncio.Semaphore(concurrency)
    return await asyncio.gather(
        *(
            _one(document, make, semaphore, sleep, jitter)
            for document, make in zip(documents, makers, strict=True)
        )
    )


def run_documents(
    documents: Sequence[Document],
    live: Callable[[Document], Labeller],
    identity: LabellerIdentity,
    *,
    cache: ResponseCache | None,
    read_cache: bool = True,
    concurrency: int = CONCURRENCY,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    jitter: Callable[[], float] = random.random,
) -> tuple[list[DocumentResult], CacheStats]:
    """Run and score every document, in the order given.

    ``live`` builds a document's live labeller; it is called afresh for each
    attempt, and through the cache only on a miss. ``cache=None`` runs with
    no cache at all; ``read_cache=False`` (``--no-cache``) skips lookups but
    still stores what each live call answered.
    """
    stats = CacheStats()
    makers = [
        (
            lambda document=document: _labeller(
                document, live, identity, cache, read_cache, stats
            )
        )
        for document in documents
    ]
    results = asyncio.run(_all(documents, makers, concurrency, sleep, jitter))
    return results, stats
