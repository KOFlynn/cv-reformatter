"""Every selected document through ``reformat`` and ``score``, concurrently.

At most ``concurrency`` documents are in flight at once (each in a worker
thread, since the pipeline is synchronous). A provider that is unavailable
(a 429, an overload, a dropped connection: ``ProviderUnavailable``, raised
once the client's own two retries are spent) is retried with exponential
backoff and jitter, and every retry is counted for the report. A
misconfigured labeller is not retried, and anything else raised is a
defect; either way the document is recorded as errored, which fails the
run, rather than losing every other document's result.

Only the labelling runs concurrently. Everything else (parse, verify,
transform, render and scoring) runs one document at a time under one lock,
which each document gives up only while its labeller is called: python-docx
parses through one module-level lxml parser, and lxml parsers are not safe
to share between threads (seen as a source document intermittently read
as "not a Word file"). The labelling is what waits on the network, so it is
the only part concurrency buys anything for.
"""

import asyncio
import random
import sys
import threading
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
from cvr.eval.run.retries import retry_chars_placed
from cvr.eval.run.score import Scores, score
from cvr.label.errors import ProviderUnavailable
from cvr.models import LabelRun
from cvr.parse import parse
from cvr.pipeline import Labeller, can_retry, reformat
from cvr.tracing import Tracer

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
    # Every attempt's labelling record (the first, then each retry's), the
    # retries fired, the characters they placed (``retry_chars_placed``) and
    # what this run paid for live calls (replays cost nothing).
    label_runs: tuple[LabelRun, ...] = ()
    retries_fired: int = 0
    chars_placed: int = 0
    spent_usd: float = 0.0


def backoff(retry: int, jitter: float) -> float:
    """Seconds to wait before retry number ``retry`` (from 0): the base
    doubled per retry up to the cap, scaled by ``jitter`` in ``[0, 1)`` into
    its upper half, so concurrent workers that hit the limit together do not
    come back together."""
    return min(BACKOFF_CAP, BACKOFF_BASE * 2**retry) * (0.5 + jitter / 2)


# Held by whichever worker is reading or writing a .docx; see the docstring.
_DOCUMENTS = threading.Lock()


@dataclass
class _Unlocked:
    """A labeller called with ``_DOCUMENTS`` released, so other documents'
    pipeline steps proceed while this one waits on its labeller."""

    labeller: Labeller

    @property
    def last_run(self) -> LabelRun | None:
        return label_run_of(self.labeller)

    @property
    def last_exchange(self):
        """What the wrapped labeller sent and got (full-text traces); the
        wrapper is per labelling, so this is never another document's."""
        return getattr(self.labeller, "last_exchange", None)

    @property
    def cached(self) -> bool:
        return getattr(self.labeller, "cached", False) is True

    @property
    def retryable(self) -> bool:
        return can_retry(self.labeller)

    def __call__(self, blocks, **retry):
        _DOCUMENTS.release()
        try:
            return self.labeller(blocks, **retry)
        finally:
            _DOCUMENTS.acquire()


def _reformat_and_score(
    document: Document, labeller: Labeller, tracer: Tracer | None = None
):
    """``reformat`` then ``score``, holding ``_DOCUMENTS`` for everything but
    the labeller call."""
    with _DOCUMENTS:
        output, run = reformat(document.source, _Unlocked(labeller), tracer=tracer)
        scores = score(
            document.candidate, document.source, output, run, document.manifest.headings
        )
        placed = (
            retry_chars_placed(run, parse(document.source).blocks) if run.retries else 0
        )
    return run, scores, placed


@dataclass
class _Counted:
    """A labeller with no cache in front: every call is a live call."""

    labeller: Labeller
    stats: CacheStats

    @property
    def last_run(self) -> LabelRun | None:
        return label_run_of(self.labeller)

    @property
    def last_exchange(self):
        """What the wrapped labeller sent and got (full-text traces); the
        wrapper is per labelling, so this is never another document's."""
        return getattr(self.labeller, "last_exchange", None)

    @property
    def retryable(self) -> bool:
        return can_retry(self.labeller)

    def __call__(self, blocks, **retry):
        self.stats.record_live_call()
        return self.labeller(blocks, **retry)


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
        retry_parts=identity.retry_parts,
        # Only a live labeller that can take a retry is asked for one.
        retryable=getattr(live, "retryable", False) is True,
    )


def _spent(labeller: Labeller, run) -> float:
    """What the document's live calls cost: tracked by the cache when there
    is one, else every attempt was live."""
    live_cost = getattr(labeller, "live_cost", None)
    if isinstance(live_cost, float):
        return live_cost
    return sum(record.cost_usd for record in run.label_runs)


async def _one(
    document: Document,
    make: Callable[[], Labeller],
    semaphore: asyncio.Semaphore,
    sleep: Callable[[float], Awaitable[None]],
    jitter: Callable[[], float],
    tracer: Tracer | None = None,
) -> DocumentResult:
    async with semaphore:
        started = perf_counter()
        retries = 0
        while True:
            labeller = make()
            try:
                run, scores, placed = await asyncio.to_thread(
                    _reformat_and_score, document, labeller, tracer
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
                    label_runs=tuple(run.label_runs),
                    retries_fired=len(run.retries),
                    chars_placed=placed,
                    spent_usd=_spent(labeller, run),
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
    tracer: Tracer | None = None,
) -> list[DocumentResult]:
    semaphore = asyncio.Semaphore(concurrency)
    return await asyncio.gather(
        *(
            _one(document, make, semaphore, sleep, jitter, tracer)
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
    tracer: Tracer | None = None,
) -> tuple[list[DocumentResult], CacheStats]:
    """Run and score every document, in the order given.

    ``live`` builds a document's live labeller; it is called afresh for each
    attempt, and through the cache only on a miss. ``cache=None`` runs with
    no cache at all; ``read_cache=False`` (``--no-cache``) skips lookups but
    still stores what each live call answered. ``tracer`` traces each
    document's Run (one trace per attempt: a retried document leaves its
    failed attempts' traces behind, marked as errors).
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
    results = asyncio.run(_all(documents, makers, concurrency, sleep, jitter, tracer))
    return results, stats
