"""Bounded concurrency, and retry with exponential backoff and jitter when
the provider is unavailable (a 429 once the client's own retries are spent),
every retry counted."""

import threading
import time

import pytest
from run_support import ORACLE, oracle

from cvr.eval.run import runner
from cvr.eval.run.documents import document
from cvr.eval.run.report import totals_of
from cvr.eval.run.runner import (
    BACKOFF_BASE,
    BACKOFF_CAP,
    MAX_RETRIES,
    backoff,
    run_documents,
)
from cvr.label import LabellerMisconfigured, ProviderUnavailable

STEM = "c04__single-column"


class Sleeps:
    """An ``asyncio.sleep`` stand-in that records and does not wait."""

    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _flaky(failures: int, error=ProviderUnavailable):
    """A labeller factory whose first ``failures`` calls raise ``error``."""
    calls = []

    def live(doc):
        def labeller(blocks):
            calls.append(1)
            if len(calls) <= failures:
                raise error("429 Too Many Requests")
            return oracle(doc)(blocks)

        return labeller

    return live, calls


def test_backoff_doubles_to_the_cap_with_jitter_in_its_upper_half():
    assert backoff(0, 0.0) == BACKOFF_BASE / 2
    assert backoff(0, 1.0) == pytest.approx(BACKOFF_BASE)
    assert [backoff(n, 1.0) for n in range(3)] == pytest.approx(
        [BACKOFF_BASE, 2 * BACKOFF_BASE, 4 * BACKOFF_BASE]
    )
    assert backoff(30, 1.0) == pytest.approx(BACKOFF_CAP)
    assert BACKOFF_CAP / 2 <= backoff(30, 0.3) <= BACKOFF_CAP


def test_a_rate_limited_document_is_retried_and_the_retries_counted():
    live, calls = _flaky(2)
    sleeps = Sleeps()
    (result,), _ = run_documents(
        [document(STEM)], live, ORACLE, cache=None, sleep=sleeps, jitter=lambda: 0.5
    )
    assert result.error is None and result.scores is not None
    assert result.retries == 2 and len(calls) == 3
    assert sleeps.delays == [backoff(0, 0.5), backoff(1, 0.5)]
    assert totals_of(result).retries == 2


def test_a_document_still_rate_limited_after_every_retry_is_an_error():
    live, calls = _flaky(MAX_RETRIES + 1)
    sleeps = Sleeps()
    (result,), _ = run_documents(
        [document(STEM)], live, ORACLE, cache=None, sleep=sleeps
    )
    assert result.scores is None
    assert result.error.startswith(f"gave up after {MAX_RETRIES} retries")
    assert result.retries == MAX_RETRIES == len(sleeps.delays)
    assert len(calls) == MAX_RETRIES + 1


def test_a_misconfigured_labeller_is_not_retried(capsys):
    live, calls = _flaky(1, LabellerMisconfigured)
    sleeps = Sleeps()
    (result,), _ = run_documents(
        [document(STEM)], live, ORACLE, cache=None, sleep=sleeps
    )
    assert result.error.startswith("LabellerMisconfigured")
    assert result.retries == 0 and sleeps.delays == [] and len(calls) == 1
    assert "LabellerMisconfigured" in capsys.readouterr().err


def test_no_more_than_the_bound_are_in_flight_at_once():
    lock = threading.Lock()
    in_flight = [0]
    peak = [0]

    def live(doc):
        def labeller(blocks):
            with lock:
                in_flight[0] += 1
                peak[0] = max(peak[0], in_flight[0])
            time.sleep(0.05)
            with lock:
                in_flight[0] -= 1
            return oracle(doc)(blocks)

        return labeller

    stems = [
        f"{candidate}__single-column" for candidate in ("c01", "c02", "c03", "c04")
    ]
    results, _ = run_documents(
        [document(stem) for stem in stems], live, ORACLE, cache=None, concurrency=2
    )
    assert peak[0] <= 2
    assert [result.document.stem for result in results] == stems
    assert runner.CONCURRENCY == 4


def test_only_the_labelling_runs_concurrently(monkeypatch):
    """python-docx shares one lxml parser across threads, so everything but
    the labeller call runs one document at a time, while labellers overlap."""
    lock = threading.Lock()
    in_flight = {"label": 0, "score": 0}
    peak = {"label": 0, "score": 0}

    def tracked(kind, seconds, call):
        with lock:
            in_flight[kind] += 1
            peak[kind] = max(peak[kind], in_flight[kind])
        try:
            time.sleep(seconds)
            return call()
        finally:
            with lock:
                in_flight[kind] -= 1

    score = runner.score
    monkeypatch.setattr(
        runner, "score", lambda *args: tracked("score", 0.05, lambda: score(*args))
    )

    def live(doc):
        return lambda blocks: tracked("label", 0.5, lambda: oracle(doc)(blocks))

    stems = [f"c0{n}__single-column" for n in range(1, 5)]
    results, _ = run_documents([document(s) for s in stems], live, ORACLE, cache=None)
    assert all(result.error is None for result in results)
    assert peak["score"] == 1
    assert peak["label"] > 1
