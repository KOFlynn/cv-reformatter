"""The response cache: a second run with an identical key makes no labeller
call, ``--no-cache`` makes every call, and anything the answer depends on
changes the key."""

from dataclasses import replace

import pytest
from run_support import ORACLE, oracle

from cvr.eval.run.cache import CachedLabeller, CacheStats, ResponseCache, cache_key
from cvr.eval.run.documents import document
from cvr.eval.run.runner import run_documents
from cvr.models import LabellingFailure, LabelRun
from cvr.parse import parse

STEMS = ["c04__single-column", "c04__two-column"]

LABEL_RUN = LabelRun(
    config={"model": "m"},
    prompt_version="p1",
    prompt_hash="ph",
    schema_version="s1",
    schema_hash="sh",
    content_hash="ch",
    input_tokens=1000,
    output_tokens=500,
    cost_usd=0.014,
)


class Counting:
    """A labeller that counts its calls and records a ``LabelRun``."""

    calls = 0

    def __init__(self, document):
        self.oracle = oracle(document)
        self.last_run = None

    def __call__(self, blocks):
        type(self).calls += 1
        self.last_run = LABEL_RUN
        return self.oracle(blocks)


@pytest.fixture
def counting():
    Counting.calls = 0
    return Counting


def _run(documents, cache, counting, read=True):
    return run_documents(documents, counting, ORACLE, cache=cache, read_cache=read)


def test_a_second_run_with_an_identical_key_makes_no_labeller_call(tmp_path, counting):
    documents = [document(stem) for stem in STEMS]
    cache = ResponseCache(tmp_path)
    first, first_stats = _run(documents, cache, counting)
    assert counting.calls == 2
    assert (first_stats.hits, first_stats.live_calls) == (0, 2)

    second, second_stats = _run(documents, cache, counting)
    assert counting.calls == 2
    assert (second_stats.hits, second_stats.live_calls) == (2, 0)
    assert all(result.cache_hit for result in second)
    # The replayed answer scores exactly as the live one did, and the Run
    # carries the LabelRun recorded when the answer was made.
    for live, replayed in zip(first, second, strict=True):
        assert replayed.scores.placement == live.scores.placement
        assert replayed.scores.adapted == live.scores.adapted
        assert replayed.label_run == live.label_run == LABEL_RUN


def test_no_cache_bypasses_the_lookup_and_refreshes_the_entry(tmp_path, counting):
    documents = [document(STEMS[0])]
    cache = ResponseCache(tmp_path)
    _run(documents, cache, counting)
    results, stats = _run(documents, cache, counting, read=False)
    assert counting.calls == 2
    assert (stats.hits, stats.live_calls) == (0, 1)
    assert not results[0].cache_hit
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_without_a_cache_every_call_is_live_and_nothing_is_written(tmp_path, counting):
    documents = [document(STEMS[0])]
    for _ in range(2):
        _, stats = run_documents(documents, counting, ORACLE, cache=None)
        assert stats.live_calls == 1
    assert counting.calls == 2


def test_the_key_moves_with_the_config_the_prompt_the_schema_and_the_source():
    source = document(STEMS[0]).source
    key = cache_key(ORACLE, source)
    assert cache_key(ORACLE, bytes(source)) == key
    changed = [
        replace(ORACLE, config={**ORACLE.config, "effort": "high"}),
        replace(ORACLE, config={**ORACLE.config, "model": "other"}),
        replace(ORACLE, prompt_hash="other"),
        replace(ORACLE, schema_hash="other"),
    ]
    keys = {cache_key(identity, source) for identity in changed}
    keys.add(cache_key(ORACLE, document(STEMS[1]).source))
    assert key not in keys and len(keys) == 5
    # A version label alone is not the content, and does not move the key.
    assert cache_key(replace(ORACLE, prompt_version="bumped"), source) == key


def test_a_labelling_failure_is_cached_and_replayed_as_one(tmp_path):
    blocks = parse(document(STEMS[0]).source).blocks
    failure = LabellingFailure(reason="answer failed schema validation")
    live_calls = []

    def live():
        def labeller(blocks):
            live_calls.append(1)
            return failure

        return labeller

    for _ in range(2):
        cached = CachedLabeller(live, ResponseCache(tmp_path), "k", CacheStats())
        assert cached(blocks) == failure
        assert cached.last_run is None
    assert live_calls == [1]


def test_a_provider_error_is_not_cached(tmp_path):
    blocks = parse(document(STEMS[0]).source).blocks

    def live():
        def labeller(blocks):
            raise RuntimeError("provider down")

        return labeller

    cached = CachedLabeller(live, ResponseCache(tmp_path), "k", CacheStats())
    with pytest.raises(RuntimeError):
        cached(blocks)
    assert list(tmp_path.iterdir()) == []
