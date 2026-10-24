"""The eval runner and the retry loop (ticket 14): retries and the re-ask of a
failed first answer are live calls, never cached, and a labeller that cannot
take a retry is never given one. (The cache key, the report and the cost
totals learn about retries in ticket 15.)"""

from typing import ClassVar

import pytest
from pipeline.oracle import omit_first_bullet
from run_support import ORACLE, oracle

from cvr.eval.run.cache import CachedLabeller, CacheStats, ResponseCache, cache_key
from cvr.eval.run.documents import document
from cvr.eval.run.runner import run_documents
from cvr.models import (
    Addition,
    Additions,
    LabellingFailure,
    LabelRun,
    Reference,
)
from cvr.models.feedback import Feedback
from cvr.parse import parse

STEM = "c04__single-column"
LABEL_RUN = LabelRun(
    config={"model": "m"},
    prompt_version="p1",
    prompt_hash="ph",
    schema_version="s1",
    schema_hash="sh",
    content_hash="ch",
    input_tokens=10,
)


class Retrying:
    """Misses the first bullet, then adds it when asked; counts its calls."""

    calls: ClassVar[list[str]] = []

    def __init__(self, document):
        self.perfect = oracle(document)
        self.last_run = None

    def __call__(self, blocks, *, feedback=None, first=None):
        self.last_run = LABEL_RUN
        full = self.perfect(blocks)
        if feedback is None:
            type(self).calls.append("first")
            return omit_first_bullet(full)
        type(self).calls.append("retry")
        bullet = full.content.experience[0].bullets[0]
        return Additions(
            additions=[
                Addition(
                    path="experience[0].bullets",
                    reference=Reference(block_id=bullet.block_id, quote=bullet.quote),
                )
            ]
        )


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    Retrying.calls = []
    monkeypatch.delenv("CVR_RETRY_MAX", raising=False)


def _live(retryable: bool):
    def live(document):
        return Retrying(document)

    live.retryable = retryable
    return live


def test_a_retry_through_the_runner_is_live_and_fixes_the_document(tmp_path):
    cache = ResponseCache(tmp_path)
    (result,), stats = run_documents([document(STEM)], _live(True), ORACLE, cache=cache)
    assert Retrying.calls == ["first", "retry"]
    assert result.error is None
    assert result.scores.appendix_tokens == 0
    # the first attempt is cached, the retry is not: one live call per attempt
    assert stats.live_calls == 2
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_a_cached_first_attempt_still_gets_a_live_retry(tmp_path):
    cache = ResponseCache(tmp_path)
    run_documents([document(STEM)], _live(True), ORACLE, cache=cache)
    Retrying.calls = []
    (result,), stats = run_documents([document(STEM)], _live(True), ORACLE, cache=cache)
    assert Retrying.calls == ["retry"]
    assert (stats.hits, stats.live_calls) == (1, 1)
    assert result.cache_hit
    assert result.scores.appendix_tokens == 0


def test_without_a_cache_the_retry_is_live_too():
    _, stats = run_documents([document(STEM)], _live(True), ORACLE, cache=None)
    assert Retrying.calls == ["first", "retry"]
    assert stats.live_calls == 2


def test_a_labeller_that_cannot_retry_is_never_given_one(tmp_path):
    def live(document):
        return lambda blocks: omit_first_bullet(oracle(document)(blocks))

    for cache in (None, ResponseCache(tmp_path)):
        (result,), _ = run_documents([document(STEM)], live, ORACLE, cache=cache)
        assert result.error is None
        assert result.scores.appendix_tokens > 0  # left in the appendix


def test_the_re_ask_of_a_failed_first_answer_is_not_the_cached_failure(tmp_path):
    blocks = parse(document(STEM).source).blocks
    failure = LabellingFailure(reason="answer failed schema validation")
    answers = [failure, oracle(document(STEM))(blocks)]
    live_calls = []

    def live():
        def labeller(blocks, *, feedback=None, first=None):
            live_calls.append(1)
            return answers[len(live_calls) - 1]

        return labeller

    cache = ResponseCache(tmp_path)
    cached = CachedLabeller(live, cache, "k", CacheStats(), retryable=True)
    assert cached(blocks) == failure
    again = cached(blocks)  # the re-ask: live, not the stored failure
    assert again != failure
    assert len(live_calls) == 2
    assert cache.get("k") is not None
    stored, _ = cache.get("k")
    assert stored == failure  # the cache still holds the first answer only


def test_the_cache_key_is_untouched_by_retries():
    source = document(STEM).source
    assert cache_key(ORACLE, source) == cache_key(ORACLE, bytes(source))


def test_a_retry_call_is_not_marked_cached(tmp_path):
    blocks = parse(document(STEM).source).blocks
    cache = ResponseCache(tmp_path)
    perfect = oracle(document(STEM))

    def live():
        def labeller(blocks, *, feedback=None, first=None):
            return perfect(blocks) if feedback is None else Additions(additions=[])

        return labeller

    for _ in range(2):  # the second round starts from a hit
        cached = CachedLabeller(live, cache, "k", CacheStats(), retryable=True)
        cached(blocks)
        first_was_replayed = cached.cached
        cached(blocks, feedback=Feedback(), first=perfect(blocks))
        assert cached.cached is False
    assert first_was_replayed is True
    assert cached.hit is True  # sticky: the document's first attempt was a hit
