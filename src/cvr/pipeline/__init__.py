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
from cvr.tracing import RunTrace, Tracer
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


def _build_graph(labeller: Labeller, trace: RunTrace | None = None):
    """The five nodes in a line. Built per call so the labeller stays injected
    and the node functions are looked up when they run. ``trace`` records one
    span per node visit (and one generation around the labeller call); with
    none, nothing is traced."""
    trace = trace if trace is not None else RunTrace(None)

    def parse_node(state: _State) -> _State:
        with trace.node("parse") as span:
            parsed = parse(state["source"])
            span.finish({"source": state["source"]}, {"parsed": parsed})
        return {"parsed": parsed}

    def label_node(state: _State) -> _State:
        blocks = state["parsed"].blocks
        with trace.node("label") as span:
            before = getattr(labeller, "last_run", None)
            with span.generation() as generation:
                labelling = labeller(blocks)
                last_run = getattr(labeller, "last_run", None)
                # A last_run left over from an earlier call is not this attempt's.
                fresh = last_run if last_run is not before else None
                generation.finish(
                    fresh if isinstance(fresh, LabelRun) else None,
                    attempt=1,
                    # A labeller that replays a stored answer (the eval's
                    # response cache) says so; nothing else sets this.
                    cached=getattr(labeller, "cached", False) is True,
                )
            span.finish({"blocks": blocks}, {"labelling": labelling})
        return {"labelling": labelling}

    def verify_node(state: _State) -> _State:
        with trace.node("verify") as span:
            verified = verify(state["parsed"].blocks, state["labelling"])
            block_ids = {block.id for block in state["parsed"].blocks}
            for rejection in verified.rejections:
                span.rejection(rejection, block_ids)
            span.finish({}, {"verified": verified})
        return {"verified": verified}

    def transform_node(state: _State) -> _State:
        with trace.node("transform") as span:
            transformed = transform_content(state["verified"].content)
            span.finish({}, {"transformed": transformed})
        return {"transformed": transformed}

    def render_node(state: _State) -> _State:
        with trace.node("render") as span:
            output = render(state["transformed"].content, state["verified"].unplaced)
            span.finish({}, {"output": output})
        return {"output": output}

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
    source: bytes,
    labeller: Labeller,
    *,
    run_id: str | None = None,
    tracer: Tracer | None = None,
) -> tuple[bytes, Run]:
    """Reformat the ``.docx`` bytes ``source`` with ``labeller``.

    Always completes with a document for a readable ``.docx``: a labelling
    failure places nothing, and every block's text goes to the review
    appendix under the banner (ADR-0004).

    ``run_id`` is the Run's id when the caller already has one (the API
    issues it before the upload is read, so a rejected upload carries it
    too); otherwise a fresh one is made here.

    ``tracer`` traces the Run in Langfuse, with the run id as the trace id
    (structure only: ids, counts, reasons, timings, tokens, cost). Without
    one, nothing is traced.
    """
    run_id = run_id if run_id is not None else uuid4().hex
    with (tracer or Tracer.disabled()).trace(run_id) as trace:
        final = _build_graph(labeller, trace).invoke({"source": source})
    parsed, verified, transformed = (
        final["parsed"],
        final["verified"],
        final["transformed"],
    )
    last_run = getattr(labeller, "last_run", None)
    run = Run(
        run_id=run_id,
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
