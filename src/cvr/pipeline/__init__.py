"""The pipeline function: one source document in, the branded document and its
``Run`` out.

``reformat`` calls parse, label, verify, transform and render once each, in
that order, and assembles the ``Run`` from each node's section. The node
boundaries are the LangGraph nodes of Phase 2, so the swap is a change of
orchestration and not of code. The labeller is injected: the one node that
may reach an LLM is whatever callable the caller passes, and nothing else
here does. Only ``api`` and the eval runner import this module.
"""

from collections.abc import Callable, Sequence
from uuid import uuid4

from cvr.models import LabellingResult, LabelRun, Run, SourceBlock
from cvr.parse import parse
from cvr.render import render
from cvr.transform import transform_content
from cvr.verify import verify

__all__ = ["Labeller", "reformat"]

# Blocks in, a labelling result out. ``RealLabeller`` also records its
# ``LabelRun`` on ``last_run`` after each call; any labeller that does is
# read the same way, and one that does not leaves the Run's label section
# empty.
type Labeller = Callable[[Sequence[SourceBlock]], LabellingResult]


def reformat(
    source: bytes, labeller: Labeller, *, run_id: str | None = None
) -> tuple[bytes, Run]:
    """Reformat the ``.docx`` bytes ``source`` with ``labeller``.

    Always completes with a document for a readable ``.docx``: a labelling
    failure places nothing, and every block's text goes to the review
    appendix under the banner (ADR-0004).

    ``run_id`` is the Run's id when the caller already has one (the API
    issues it before the upload is read, so a rejected upload carries it
    too); otherwise a fresh one is made here.
    """
    parsed = parse(source)
    labelling = labeller(parsed.blocks)
    verified = verify(parsed.blocks, labelling)
    transformed = transform_content(verified.content)
    output = render(transformed.content, verified.unplaced)
    last_run = getattr(labeller, "last_run", None)
    run = Run(
        run_id=run_id if run_id is not None else uuid4().hex,
        label=last_run if isinstance(last_run, LabelRun) else None,
        normalisations=parsed.normalisations,
        removals=[*parsed.removals, *verified.removals],
        ledgers=verified.ledgers,
        residue=verified.residue,
        label_failed=verified.label_failed,
        date_map=transformed.date_map,
        split_map=transformed.split_map,
    )
    return output, run
