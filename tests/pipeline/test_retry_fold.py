"""S5: the retry prompt shows the first answer with every earlier retry's
placed additions folded in, so two successive retries that each open a new
entry end up with two entries, and a later retry that appends to an entry an
earlier one opened lands in that entry. Verify still runs over the unfolded
first answer plus every addition, in order."""

import pytest
from pipeline_support import document
from retry_support import damaged, perfect, scripted

from cvr.eval.adapter import adapt
from cvr.models import Addition, Additions, Labelling, Reference
from cvr.pipeline import reformat

STEM = "c04__single-column"


@pytest.fixture(autouse=True)
def _default_n(monkeypatch):
    monkeypatch.delenv("CVR_RETRY_MAX", raising=False)


def _keep_first_job_only(labelling: Labelling) -> Labelling:
    experience = labelling.content.experience[:1]
    content = labelling.content.model_copy(update={"experience": experience})
    return labelling.model_copy(update={"content": content})


def _addition(path: str, reference: Reference) -> Addition:
    return Addition(path=path, reference=reference)


def _run(*steps):
    doc = document(STEM)
    labeller, chat = scripted(*steps)
    output, run = reformat(doc.source, labeller)
    return chat, run, adapt(output).content


def test_two_retries_each_opening_a_new_entry_make_two_entries():
    full = perfect(STEM)
    second_job, third_job = full.content.experience[1], full.content.experience[2]
    chat, run, content = _run(
        damaged(STEM, _keep_first_job_only),
        Additions(additions=[_addition("experience[1].title", second_job.title)]),
        # the model was shown two entries, so the next free index is 2
        Additions(additions=[_addition("experience[2].title", third_job.title)]),
    )
    assert len(run.retries) == 2
    assert [r.rejections for r in run.retries] == [[], []]
    assert len(chat.payload(1)["first_answer"]["content"]["experience"]) == 1
    # the second retry is shown the entry the first one opened
    shown = chat.payload(2)["first_answer"]["content"]["experience"]
    assert len(shown) == 2
    assert shown[1]["title"] == second_job.title.model_dump()
    assert {e.title for e in content.experience} >= {
        second_job.title.quote,
        third_job.title.quote,
    }
    assert len(content.experience) == 3


def test_a_later_retry_appending_to_an_opened_entry_lands_in_that_entry():
    full = perfect(STEM)
    second_job = full.content.experience[1]
    _chat, run, content = _run(
        damaged(STEM, _keep_first_job_only),
        Additions(additions=[_addition("experience[1].title", second_job.title)]),
        Additions(
            additions=[_addition("experience[1].bullets", second_job.bullets[0])]
        ),
    )
    assert [r.rejections for r in run.retries] == [[], []]
    entry = next(e for e in content.experience if e.title == second_job.title.quote)
    assert second_job.bullets[0].quote in entry.bullets
    assert len(content.experience) == 2


def test_verify_still_runs_over_the_unfolded_first_answer():
    """The first answer wins every conflict: a retry's addition addressing a
    leaf the first answer filled is bad_path even though the prompt shows the
    folded tree."""
    full = perfect(STEM)
    first_job = full.content.experience[0]
    other = full.content.experience[1]
    _, run, _ = _run(
        damaged(STEM, _keep_first_job_only),
        Additions(additions=[_addition("experience[0].title", other.title)]),
    )
    assert [r.reason for r in run.retries[0].rejections] == ["bad_path"]
    assert run.retries[0].rejections[0].path == "experience[0].title"
    assert first_job.title is not None
