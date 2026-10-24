"""Feedback: what verification tells the labeller before a retry. Ids,
offsets and paths only, never text: the labeller reads the text from the
blocks it already holds, and the Run records the feedback as it is."""

from pydantic import Field

from cvr.models import StrictModel


class UnplacedRun(StrictModel):
    """A run of unplaced text, ``block.text[start:end]``."""

    block_id: str
    start: int = Field(ge=0)
    end: int


class UnlocatableHint(StrictModel):
    """A first-answer reference rejected ``unlocatable``, by its path."""

    path: str
    block_id: str


class Feedback(StrictModel):
    """``unusable``: the previous answer was a labelling failure, so there
    is no first answer to add to."""

    unusable: bool = False
    unplaced: list[UnplacedRun] = Field(default_factory=list)
    unlocatable: list[UnlocatableHint] = Field(default_factory=list)
