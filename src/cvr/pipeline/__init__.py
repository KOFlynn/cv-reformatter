"""The pipeline function: one source document in, the branded document and its
``Run`` out.

``reformat`` builds a LangGraph state machine of the five nodes (parse, label,
verify, transform, render) and runs it once, each node called once in that
order, then assembles the ``Run`` from each node's section. The node functions
are the Phase 1 ones, unchanged: each graph node only reads its inputs from
the state and writes its result back. No checkpointer, no streaming. The
labeller is injected: the one node that may reach an LLM is whatever callable
the caller passes, and nothing else here does. Only ``api`` and the eval
runner import this module.
"""

from collections.abc import Callable, Sequence
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from cvr.models import LabellingResult, LabelRun, Run, SourceBlock
from cvr.parse import ParsedDocument, parse
from cvr.render import render
from cvr.transform import TransformResult, transform_content
from cvr.verify import VerifiedDocument, verify

__all__ = ["Labeller", "reformat"]

# Blocks in, a labelling result out. ``RealLabeller`` also records its
# ``LabelRun`` on ``last_run`` after each call; any labeller that does is
# read the same way, and one that does not leaves the Run's label section
# empty.
type Labeller = Callable[[Sequence[SourceBlock]], LabellingResult]


class _State(TypedDict, total=False):
    """What flows between the nodes: each key is written by one node."""

    source: bytes
    parsed: ParsedDocument
    labelling: LabellingResult
    verified: VerifiedDocument
    transformed: TransformResult
    output: bytes


def _build_graph(labeller: Labeller):
    """The five nodes in a line. Built per call so the labeller stays injected
    and the node functions are looked up when they run."""

    def parse_node(state: _State) -> _State:
        return {"parsed": parse(state["source"])}

    def label_node(state: _State) -> _State:
        return {"labelling": labeller(state["parsed"].blocks)}

    def verify_node(state: _State) -> _State:
        return {"verified": verify(state["parsed"].blocks, state["labelling"])}

    def transform_node(state: _State) -> _State:
        return {"transformed": transform_content(state["verified"].content)}

    def render_node(state: _State) -> _State:
        return {
            "output": render(state["transformed"].content, state["verified"].unplaced)
        }

    graph = StateGraph(_State)
    graph.add_node("parse", parse_node)
    graph.add_node("label", label_node)
    graph.add_node("verify", verify_node)
    graph.add_node("transform", transform_node)
    graph.add_node("render", render_node)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "label")
    graph.add_edge("label", "verify")
    graph.add_edge("verify", "transform")
    graph.add_edge("transform", "render")
    graph.add_edge("render", END)
    return graph.compile()


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
    final = _build_graph(labeller).invoke({"source": source})
    parsed, verified, transformed = (
        final["parsed"],
        final["verified"],
        final["transformed"],
    )
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
    return final["output"], run
