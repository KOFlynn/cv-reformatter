"""``PayingLabeller``: the wrapper both servers put around the labeller so a
call that fails on a later attempt can still say what earlier ones cost."""

import pytest

from cvr.models import LabelRun
from cvr.pipeline import PayingLabeller, can_retry


def _run() -> LabelRun:
    return LabelRun.model_construct()


class Recording:
    """Takes ``feedback`` (so it can retry) and keeps ``last_run`` as the real
    labeller does."""

    marker = "kept"

    def __init__(self, runs):
        self._runs = list(runs)
        self.last_run = None

    def __call__(self, blocks, *, feedback=None, first=None):
        self.last_run = self._runs.pop(0)
        return ("answer", blocks, feedback)


class Raising:
    last_run = None

    def __call__(self, blocks, *, feedback=None, first=None):
        raise RuntimeError("down")


def test_each_returned_label_run_is_noted_and_the_answer_passes_through():
    first, second = _run(), _run()
    paying = PayingLabeller(Recording([first, second]))

    assert paying(["b"]) == ("answer", ["b"], None)
    paying(["b"], feedback="f")

    assert paying.paid == [first, second]


def test_a_label_run_seen_again_is_noted_once():
    stale = _run()
    inner = Recording([stale])
    paying = PayingLabeller(inner)

    paying(["b"])
    inner._runs.append(stale)  # the next call leaves the same last_run
    paying(["b"])

    assert paying.paid == [stale]


def test_a_labeller_without_last_run_notes_nothing():
    paying = PayingLabeller(lambda blocks: "x")
    paying(["b"])
    assert paying.paid == []


def test_a_call_that_raises_notes_nothing_and_keeps_earlier_payments():
    first = _run()
    inner = Recording([first])
    paying = PayingLabeller(inner)
    paying(["b"])

    paying._labeller = Raising()
    with pytest.raises(RuntimeError):
        paying(["b"], feedback="f")

    assert paying.paid == [first]


def test_retryable_follows_can_retry_of_the_wrapped_labeller():
    assert PayingLabeller(Recording([])).retryable is True
    assert PayingLabeller(lambda blocks: "x").retryable is False


def test_a_labeller_declaring_retryable_is_followed():
    class Declines(Recording):
        retryable = False

    class Accepts:
        retryable = True

        def __call__(self, blocks):
            return "x"

    assert PayingLabeller(Declines([])).retryable is False
    assert PayingLabeller(Accepts()).retryable is True


def test_the_wrapper_is_judged_by_its_own_retryable_flag():
    assert can_retry(PayingLabeller(Recording([]))) is True
    assert can_retry(PayingLabeller(lambda blocks: "x")) is False


def test_other_attributes_are_the_wrapped_labellers():
    inner = Recording([])
    paying = PayingLabeller(inner)
    inner.last_run = _run()

    assert paying.marker == "kept"
    assert paying.last_run is inner.last_run
    with pytest.raises(AttributeError):
        getattr(paying, "nothing_here")  # noqa: B009
