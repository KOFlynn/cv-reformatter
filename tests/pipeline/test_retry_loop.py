"""The retry loop through ``reformat``, with the scripted fake (the real
``RealLabeller`` over a fake chat model that says what the script says): a
perfect first attempt makes no retry; a flawed one fixed by a retry places the
text; a true fragment costs exactly one retry; N is respected; a failed or
unavailable retry keeps the previous result; a failed first attempt is
re-asked; an outage on the first attempt still raises."""

import pytest
from oracle import UNLOCATABLE, unlocatable_title
from pipeline_support import document, score
from retry_support import (
    bullet_additions,
    damaged,
    drop_first_bullets,
    perfect,
    scripted,
)

from cvr.label.errors import ProviderUnavailable
from cvr.label.versions import PROMPT_TEXT, RETRY_TEXT
from cvr.models import Addition, Additions, Labelling, Reference
from cvr.pipeline import reformat
from cvr.text import canonicalise

STEM = "c04__single-column"
FRAGMENT_STEM = "c09__single-column"


@pytest.fixture(autouse=True)
def _default_n(monkeypatch):
    monkeypatch.delenv("CVR_RETRY_MAX", raising=False)


def _reformat(stem, labeller):
    doc = document(stem)
    output, run = reformat(doc.source, labeller)
    return (
        output,
        run,
        score(doc.candidate, doc.source, output, run, doc.manifest.headings),
    )


def _clean(scores) -> bool:
    return not scores.added and not scores.dropped and scores.appendix_tokens == 0


def _text(fragment: str) -> str:
    return canonicalise(fragment)


# --- the retry fires only when it should


def test_a_perfect_first_attempt_makes_no_retry():
    labeller, chat = scripted(perfect(STEM))
    _, run, scores = _reformat(STEM, labeller)
    assert chat.schemas == [Labelling]
    assert run.retries == []
    assert run.unplaced == []
    assert _clean(scores)


def test_a_flawed_first_attempt_fixed_by_a_retry_places_the_text():
    full = perfect(STEM)
    labeller, chat = scripted(
        damaged(STEM, drop_first_bullets(1)), bullet_additions(full, 0)
    )
    _, run, scores = _reformat(STEM, labeller)

    assert chat.schemas == [Labelling, Additions]
    assert chat.calls[0][1][0].content == PROMPT_TEXT
    assert chat.calls[1][1][0].content == RETRY_TEXT
    assert run.unplaced == []
    assert _clean(scores)
    (retry,) = run.retries
    assert retry.feedback.unusable is False
    assert [u.block_id for u in retry.feedback.unplaced]  # what it was asked
    assert retry.unplaced_chars == 0
    assert retry.rejections == []
    assert retry.label is not None and retry.label.input_tokens == 1000
    # the Run's label section stays the first attempt
    assert run.label is not None
    assert run.label.prompt_version != retry.label.prompt_version


def test_a_true_fragment_costs_exactly_one_retry():
    # c09 carries text no field can hold: the retry places nothing, so the loop
    # stops after one, though N is two.
    labeller, chat = scripted(perfect(FRAGMENT_STEM), Additions(additions=[]))
    _, run, _ = _reformat(FRAGMENT_STEM, labeller)
    assert chat.schemas == [Labelling, Additions]
    assert len(run.retries) == 1
    assert run.unplaced  # still in the appendix
    assert run.retries[0].unplaced_chars > 0


# --- N


def _three_missing():
    full = perfect(STEM)
    return full, damaged(STEM, drop_first_bullets(3))


def test_n_is_respected_by_default_two():
    full, first = _three_missing()
    labeller, chat = scripted(
        first, bullet_additions(full, 0), bullet_additions(full, 1)
    )
    _, run, scores = _reformat(STEM, labeller)
    assert chat.schemas == [Labelling, Additions, Additions]
    assert len(run.retries) == 2
    assert [r.unplaced_chars for r in run.retries] == sorted(
        (r.unplaced_chars for r in run.retries), reverse=True
    )
    assert len(run.unplaced) == 1  # the third bullet is left for the appendix
    assert len(scores.dropped) == 0  # it is in the document, in the appendix


def test_additions_accumulate_across_retries():
    full, first = _three_missing()
    labeller, _ = scripted(first, bullet_additions(full, 0), bullet_additions(full, 1))
    _, run, _ = _reformat(STEM, labeller)
    bullets = full.content.experience[0].bullets
    left = {_text(s.text) for s in run.unplaced}
    # bullets 0 and 1 were added by retries 1 and 2 and both stayed placed
    assert all(_text(bullets[i].quote) not in left for i in (0, 1))
    assert any(_text(bullets[2].quote) in text for text in left)


def test_a_larger_n_goes_on_until_nothing_is_unplaced(monkeypatch):
    monkeypatch.setenv("CVR_RETRY_MAX", "3")
    full, first = _three_missing()
    labeller, _ = scripted(
        first,
        bullet_additions(full, 0),
        bullet_additions(full, 1),
        bullet_additions(full, 2),
    )
    _, run, scores = _reformat(STEM, labeller)
    assert len(run.retries) == 3
    assert run.unplaced == []
    assert _clean(scores)


def test_n_zero_turns_the_retry_off(monkeypatch):
    monkeypatch.setenv("CVR_RETRY_MAX", "0")
    labeller, chat = scripted(damaged(STEM, drop_first_bullets(1)))
    _, run, _ = _reformat(STEM, labeller)
    assert chat.schemas == [Labelling]
    assert run.retries == []
    assert run.unplaced


def test_a_bad_n_fails_loudly(monkeypatch):
    monkeypatch.setenv("CVR_RETRY_MAX", "two")
    labeller, _ = scripted(perfect(STEM))
    with pytest.raises(ValueError, match="CVR_RETRY_MAX"):
        _reformat(STEM, labeller)


# --- a retry that fails keeps the previous result


def _previous_result(monkeypatch):
    """The first attempt alone (N = 0): what a failed retry must leave."""
    monkeypatch.setenv("CVR_RETRY_MAX", "0")
    labeller, _ = scripted(damaged(STEM, drop_first_bullets(1)))
    result = _reformat(STEM, labeller)
    monkeypatch.delenv("CVR_RETRY_MAX")
    return result


def test_a_malformed_retry_answer_keeps_the_previous_result(monkeypatch):
    _, previous, previous_scores = _previous_result(monkeypatch)
    labeller, chat = scripted(damaged(STEM, drop_first_bullets(1)), "malformed")
    _, run, scores = _reformat(STEM, labeller)

    assert chat.schemas == [Labelling, Additions]
    assert run.residue == previous.residue
    assert run.ledgers == previous.ledgers
    assert scores.appendix_tokens == previous_scores.appendix_tokens
    (retry,) = run.retries  # the failed attempt is recorded
    assert retry.label is not None
    assert retry.label.label_failed is True
    assert retry.label.failure_reason
    assert retry.rejections == []
    assert retry.unplaced_chars > 0


def test_an_outage_on_a_retry_keeps_the_previous_result(monkeypatch):
    _, previous, previous_scores = _previous_result(monkeypatch)
    labeller, _ = scripted(damaged(STEM, drop_first_bullets(1)), "outage")
    _, run, scores = _reformat(STEM, labeller)

    assert run.residue == previous.residue
    assert scores.appendix_tokens == previous_scores.appendix_tokens
    (retry,) = run.retries
    assert retry.label is None  # there was no answer to record
    assert retry.feedback.unplaced
    assert run.label is not None and run.label.label_failed is False


def test_a_failed_retry_after_progress_keeps_the_progress():
    full, first = _three_missing()
    labeller, _ = scripted(first, bullet_additions(full, 0), "malformed")
    _, run, _ = _reformat(STEM, labeller)
    assert len(run.retries) == 2
    first_retry, second = run.retries
    assert second.label.label_failed
    # the second retry changed nothing: same unplaced count as after the first
    assert second.unplaced_chars == first_retry.unplaced_chars
    assert len(run.unplaced) == 2  # bullets 1 and 2 still unplaced, 0 kept


# --- a failed first attempt


def test_a_failed_first_attempt_is_re_asked_with_the_first_prompt():
    labeller, chat = scripted("malformed", perfect(STEM))
    _, run, scores = _reformat(STEM, labeller)

    # a retry cannot carry removals, so the whole document is asked for again
    assert chat.schemas == [Labelling, Labelling]
    assert [call[1][0].content for call in chat.calls] == [PROMPT_TEXT, PROMPT_TEXT]
    assert _clean(scores)
    assert run.unplaced == []
    assert run.label is not None and run.label.label_failed is True  # the first
    assert run.label_failed is False  # the document is placed
    (retry,) = run.retries
    assert retry.feedback.unusable is True
    assert retry.label is not None and retry.label.label_failed is False
    # its removals came with it: no PII value reached the document
    assert not scores.pii
    assert any(r.rule.name != "PHOTO" for r in run.removals)


def test_a_failed_first_attempt_that_fails_again_is_the_banner_document():
    labeller, chat = scripted("malformed", "malformed")
    _, run, _ = _reformat(STEM, labeller)
    assert len(chat.calls) == 2  # not three: a failed retry stops the loop
    assert run.label_failed is True
    assert run.unplaced
    (retry,) = run.retries
    assert retry.label.label_failed


def test_a_failed_first_attempt_with_n_zero_is_not_retried(monkeypatch):
    monkeypatch.setenv("CVR_RETRY_MAX", "0")
    labeller, chat = scripted("malformed")
    _, run, _ = _reformat(STEM, labeller)
    assert len(chat.calls) == 1
    assert run.label_failed is True
    assert run.retries == []


def test_an_outage_on_the_first_attempt_still_raises():
    labeller, chat = scripted("outage")
    with pytest.raises(ProviderUnavailable):
        _reformat(STEM, labeller)
    assert len(chat.calls) == 1


# --- the hints come from the base answer only


def test_hints_come_only_from_the_first_answer_not_from_earlier_additions():
    full = perfect(STEM)
    first = damaged(STEM, lambda l: unlocatable_title(drop_first_bullets(3)(l)))
    title_block = first.content.experience[0].title.block_id
    junk = Additions(
        additions=[
            *bullet_additions(full, 0).additions,
            Addition(
                path="experience[0].title",
                reference=Reference(block_id=title_block, quote="Nonexistent Title"),
            ),
        ]
    )
    labeller, chat = scripted(first, junk, bullet_additions(full, 1))
    _, run, _ = _reformat(STEM, labeller)

    assert len(run.retries) == 2
    first_hints = chat.payload(1)["feedback"]["unlocatable"]
    second_hints = chat.payload(2)["feedback"]["unlocatable"]
    assert [h.get("quote") for h in first_hints] == [UNLOCATABLE]
    # the addition's own unlocatable rejection (same path) is not a hint
    assert [h.get("quote") for h in second_hints] == [UNLOCATABLE]
    # and the base answer is sent unchanged each time
    assert chat.payload(1)["first_answer"] == chat.payload(2)["first_answer"]
    assert [r.reason for r in run.retries[0].rejections] == ["unlocatable"]
