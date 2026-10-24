"""The response cache keys each attempt on its own (ticket 15): a retry's key
moves with the feedback it was sent, the base answer it adds to, the attempt
number and the retry prompt and additions schema; the re-ask of a failed first
answer does not share the failed answer's entry; a cached rerun replays every
attempt with no call."""

from run_support import ORACLE, oracle

from cvr.eval.run.cache import (
    CachedLabeller,
    CacheStats,
    ResponseCache,
    attempt_key,
    cache_key,
)
from cvr.eval.run.documents import document
from cvr.models import Addition, Additions, LabellingFailure, Reference
from cvr.models.feedback import Feedback, UnplacedRun
from cvr.parse import parse

STEM = "c04__single-column"
PARTS = {"retry_prompt_hash": "rp", "additions_hash": "ad"}


def _feedback(start=0, end=5):
    return Feedback(unplaced=[UnplacedRun(block_id="b1", start=start, end=end)])


def _first(source_stem=STEM):
    blocks = parse(document(source_stem).source).blocks
    return oracle(document(source_stem))(blocks)


def test_the_first_attempts_key_is_the_documents_key():
    base = cache_key(ORACLE, document(STEM).source)
    assert attempt_key(base, 1, PARTS) == base


def test_a_retrys_key_moves_with_each_thing_its_answer_depends_on():
    base = cache_key(ORACLE, document(STEM).source)
    first = _first()
    key = attempt_key(base, 2, PARTS, _feedback(), first)
    assert key != base
    assert key == attempt_key(base, 2, PARTS, _feedback(), first)  # stable
    assert key != attempt_key(base, 2, PARTS, _feedback(1, 5), first)  # feedback
    assert key != attempt_key(base, 2, PARTS, _feedback(), _first("c04__two-column"))
    assert key != attempt_key(base, 3, PARTS, _feedback(), first)  # attempt
    assert key != attempt_key(
        base, 2, PARTS | {"additions_hash": "x"}, _feedback(), first
    )
    assert key != attempt_key(
        base, 2, PARTS | {"retry_prompt_hash": "x"}, _feedback(), first
    )
    other = cache_key(ORACLE, document("c04__two-column").source)
    assert key != attempt_key(other, 2, PARTS, _feedback(), first)  # document


def test_the_re_ask_of_a_failed_first_answer_has_its_own_key():
    base = cache_key(ORACLE, document(STEM).source)
    assert attempt_key(base, 2, PARTS) != attempt_key(base, 1, PARTS)
    assert attempt_key(base, 2, PARTS) != attempt_key(base, 3, PARTS)


def test_a_cached_rerun_replays_a_failure_then_its_re_ask_with_no_call(tmp_path):
    blocks = parse(document(STEM).source).blocks
    good = oracle(document(STEM))(blocks)
    failure = LabellingFailure(reason="answer failed schema validation")
    answers = [failure, good]
    calls = []

    def live():
        def labeller(blocks, **retry):
            calls.append(retry)
            return answers[len(calls) - 1]

        return labeller

    cache = ResponseCache(tmp_path)
    for round_ in range(2):
        stats = CacheStats()
        cached = CachedLabeller(live, cache, "k", stats, retryable=True)
        assert cached(blocks) == failure
        assert cached(blocks) == good  # the re-ask is not the stored failure
        assert (stats.hits, stats.live_calls) == ((2, 0) if round_ else (0, 2))
    assert len(calls) == 2
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_different_feedback_is_a_different_entry_and_additions_round_trip(tmp_path):
    blocks = parse(document(STEM).source).blocks
    first = _first()
    bullet = first.content.experience[0].bullets[0]
    reference = Reference(block_id=bullet.block_id, quote=bullet.quote)
    answers = {
        0: Additions(
            additions=[Addition(path="experience[0].bullets", reference=reference)]
        ),
        1: Additions(additions=[]),
    }
    calls = []

    def live():
        def labeller(blocks, *, feedback=None, first=None):
            calls.append(feedback)
            return answers[feedback.unplaced[0].start]

        return labeller

    cache = ResponseCache(tmp_path)
    for _ in range(2):
        cached = CachedLabeller(
            live, cache, "k", CacheStats(), retryable=True, retry_parts=PARTS
        )
        cached.calls = 1  # as if the first attempt had been made
        assert cached(blocks, feedback=_feedback(0), first=first) == answers[0]
        cached.calls = 1
        assert cached(blocks, feedback=_feedback(1), first=first) == answers[1]
    assert len(calls) == 2  # the second round replayed both
    assert len(list(tmp_path.glob("*.json"))) == 2
