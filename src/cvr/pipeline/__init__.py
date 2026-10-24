"""The pipeline function: one source document in, the branded document and its
``Run`` out.

``reformat`` builds a LangGraph state machine of the five nodes (parse, label,
verify, transform, render) and runs it, then assembles the ``Run`` from each
node's section. The node functions are the Phase 1 ones: each graph node only
reads its inputs from the state and writes its result back. No checkpointer,
no streaming.

One conditional edge leaves verify (ticket 14): back to label while the retry
rules (``cvr.verify.retry``) say so, else on to transform. A retry sends the
model every block, its first answer and the **Feedback**, and verify then runs
over the first answer plus the additions of every successful retry so far. A
failed first attempt is re-asked with the first prompt (a retry's answer
cannot carry removals) and counts against N. A labelling failure or a provider
outage on a retry keeps the previous result; an outage on the first attempt
raises. So label and verify repeat, only on a retry; the other nodes run once.

The labeller is injected: the one node that may reach an LLM is whatever
callable the caller passes, and nothing else here does. Only ``api`` and the
eval runner import this module.
"""

import inspect
from collections.abc import Callable, Sequence
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from cvr.label.errors import ProviderUnavailable
from cvr.models import (
    Addition,
    Additions,
    LabelExchange,
    Labelling,
    LabellingFailure,
    LabellingResult,
    LabelRun,
    RetryRejection,
    RetryRun,
    Run,
    SourceBlock,
    safe_path,
)
from cvr.models.feedback import Feedback
from cvr.parse import ParsedDocument, parse
from cvr.render import render
from cvr.tracing import RunTrace, Tracer
from cvr.transform import TransformResult, transform_content
from cvr.verify import Rejection, VerifiedDocument, verify
from cvr.verify.retry import (
    Outcome,
    RetryDecision,
    build_feedback,
    decide_retry,
    retry_max,
    unplaced_chars,
)

__all__ = ["Labeller", "can_retry", "reformat", "retry_max"]

# Blocks in, a labelling result out. ``RealLabeller`` also records its
# ``LabelRun`` on ``last_run`` after each call; any labeller that does is
# read the same way, and one that does not leaves the Run's label section
# empty. A labeller that also takes ``feedback`` and ``first`` keywords
# (``RealLabeller``) can be retried; one that takes the blocks alone makes
# one attempt.
type Labeller = Callable[..., LabellingResult | Additions]


class _State(TypedDict, total=False):
    """What flows between the nodes. ``attempt`` counts the labelling
    attempts made; ``base`` is the answer the retries add to (the first
    answer, or, when that was a failure, the first usable re-ask);
    ``additions`` every successful retry's additions so far, in order;
    ``verified`` the current result (a failed or unavailable retry leaves it
    as it was); ``feedback`` what the next attempt is told, absent before the
    first."""

    source: bytes
    parsed: ParsedDocument
    attempt: int
    labelling: LabellingResult | Additions | None
    outcome: Outcome
    base: Labelling | None
    base_fresh: bool
    base_rejections: list[Rejection]
    additions: list[Addition]
    first_label: LabelRun | None
    retry_label: LabelRun | None
    verified: VerifiedDocument
    unplaced: int
    decision: RetryDecision
    feedback: Feedback
    retries: list[RetryRun]
    transformed: TransformResult
    output: bytes


def can_retry(labeller: Labeller) -> bool:
    """Whether ``labeller`` can be asked for a retry: it accepts ``feedback``
    (``RealLabeller`` does). One that takes the blocks alone, as the test
    oracles do, makes one attempt and the loop never runs. A wrapper that
    forwards retries only sometimes (the eval runner's) says so with a boolean
    ``retryable`` attribute, which wins."""
    declared = getattr(labeller, "retryable", None)
    if isinstance(declared, bool):
        return declared
    try:
        parameters = inspect.signature(labeller).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        p.name == "feedback" or p.kind is inspect.Parameter.VAR_KEYWORD
        for p in parameters
    )


def _new_rejections(
    previous: Sequence[Rejection], current: Sequence[Rejection]
) -> list[Rejection]:
    """The rejections ``current`` has beyond ``previous``: a retry's own."""
    remaining = list(previous)
    new = []
    for rejection in current:
        if rejection in remaining:
            remaining.remove(rejection)
        else:
            new.append(rejection)
    return new


def _failed(answer: object) -> bool:
    return isinstance(answer, LabellingFailure)


def _build_graph(
    labeller: Labeller, trace: RunTrace | None = None, max_retries: int | None = None
):
    """The five nodes, with the conditional edge from verify back to label.
    Built per call so the labeller stays injected and the node functions are
    looked up when they run. ``trace`` records one span per node visit (and
    one generation per labelling attempt); with none, nothing is traced.

    ``max_retries`` is N. Left out, it is read from ``CVR_RETRY_MAX`` here,
    once per Run, so ``reformat`` keeps its signature (the spec adds only the
    tracer to it); the API and the eval runner also read it once at start-up,
    only so a bad value fails there and not on the first document. A labeller
    that cannot take feedback gets none."""
    trace = trace if trace is not None else RunTrace(None)
    limit = retry_max() if max_retries is None else max_retries
    if not can_retry(labeller):
        limit = 0

    def parse_node(state: _State) -> _State:
        with trace.node("parse") as span:
            parsed = parse(state["source"])
            span.finish({"source": state["source"]}, {"parsed": parsed})
        return {"parsed": parsed}

    def call(blocks: Sequence[SourceBlock], state: _State, attempt: int, span):
        """One labelling call inside its generation: the first attempt, a
        re-ask of a failed first answer (the first prompt again, so the
        removals come with it) or an additions retry. Returns the answer and
        the ``LabelRun`` it recorded, or ``(None, None)`` for an outage on a
        retry (an outage on the first attempt propagates)."""
        feedback = state.get("feedback")
        base = state.get("base")
        before = getattr(labeller, "last_run", None)
        try:
            with span.generation() as generation:
                if feedback is None or base is None:
                    answer = labeller(blocks)
                else:
                    answer = labeller(blocks, feedback=feedback, first=base)
                last_run = getattr(labeller, "last_run", None)
                # A last_run left over from an earlier call is not this attempt's.
                fresh = last_run if last_run is not before else None
                exchange = getattr(labeller, "last_exchange", None)
                generation.finish(
                    fresh if isinstance(fresh, LabelRun) else None,
                    attempt=attempt,
                    # A labeller that replays a stored answer (the eval's
                    # response cache) says so; nothing else sets this.
                    cached=getattr(labeller, "cached", False) is True,
                    exchange=(
                        exchange
                        if fresh is not None and isinstance(exchange, LabelExchange)
                        else None
                    ),
                )
        except ProviderUnavailable:
            if feedback is None:
                raise
            return None, None
        return answer, last_run if isinstance(last_run, LabelRun) else None

    def label_node(state: _State) -> _State:
        blocks = state["parsed"].blocks
        attempt = state.get("attempt", 0) + 1
        with trace.node("label") as span:
            answer, label_run = call(blocks, state, attempt, span)
            update: _State = {"attempt": attempt, "labelling": answer}
            if attempt == 1:
                update["first_label"] = label_run
                update["outcome"] = "failed" if _failed(answer) else "ok"
                update["base"] = None if _failed(answer) else answer
                update["base_fresh"] = True
                update["additions"] = []
            else:
                update["retry_label"] = label_run
                update["base_fresh"] = False
                if answer is None:
                    update["outcome"] = "outage"
                elif _failed(answer):
                    update["outcome"] = "failed"
                elif state["base"] is None:
                    # The re-ask of a failed first attempt: a fresh base.
                    update |= {"outcome": "ok", "base": answer, "base_fresh": True}
                else:
                    update["outcome"] = "ok"
                    update["additions"] = [*state["additions"], *answer.additions]
            span.finish({"blocks": blocks}, {"labelling": answer, "attempt": attempt})
        return update

    def verify_node(state: _State) -> _State:
        blocks = state["parsed"].blocks
        attempt, outcome = state["attempt"], state["outcome"]
        previous = state.get("verified")
        with trace.node("verify") as span:
            if attempt == 1:
                verified = verify(blocks, state["labelling"])
            elif outcome == "ok":
                additions = state["additions"]
                verified = verify(
                    blocks,
                    state["base"],
                    Additions(additions=additions) if additions else None,
                )
            else:
                verified = previous  # a failed or unavailable retry: keep it
            changed = verified is not previous
            block_ids = {block.id for block in blocks}
            own = (
                _new_rejections(
                    [] if attempt == 1 or state["base_fresh"] else previous.rejections,
                    verified.rejections,
                )
                if changed
                else []
            )
            for rejection in own:
                span.rejection(rejection, block_ids)
            unplaced = unplaced_chars(verified)
            decision = decide_retry(
                verified if outcome == "ok" else None,
                state.get("unplaced"),
                attempt,
                limit,
                outcome,
            )
            update: _State = {
                "verified": verified,
                "unplaced": unplaced,
                "decision": decision,
            }
            if attempt > 1:
                update["retries"] = [
                    *state.get("retries", []),
                    RetryRun(
                        label=state.get("retry_label"),
                        feedback=state["feedback"],
                        rejections=[
                            RetryRejection(
                                path=safe_path(r.path),
                                # The model's block id is reported only if it is real.
                                block_id=r.block_id
                                if r.block_id in block_ids
                                else "unknown",
                                reason=r.reason,
                            )
                            for r in own
                        ],
                        unplaced_chars=unplaced,
                    ),
                ]
            if outcome == "ok" and state["base_fresh"]:
                update["base_rejections"] = list(verified.rejections)
            if decision.retry:
                # Hints come only from the base answer's own rejections: an
                # addition's path addresses the additions, not the base the
                # labeller looks hints up in.
                update["feedback"] = build_feedback(
                    verified,
                    hints_from=update.get(
                        "base_rejections", state.get("base_rejections", [])
                    ),
                )
            span.retry_decision(decision.retry, decision.reason, attempt, unplaced)
            span.finish({}, {"verified": verified, "attempt": attempt})
        return update

    def route(state: _State) -> str:
        return "label" if state["decision"].retry else "transform"

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
    graph.add_conditional_edges(
        "verify", route, {"label": "label", "transform": "transform"}
    )
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
    appendix under the banner (ADR-0004). While unplaced text remains, up to
    N retries (``CVR_RETRY_MAX``, default 2) ask the labeller to place it; the
    Run's ``label`` section is the first attempt and ``retries`` the rest.

    ``run_id`` is the Run's id when the caller already has one (the API
    issues it before the upload is read, so a rejected upload carries it
    too); otherwise a fresh one is made here.

    ``tracer`` traces the Run in Langfuse, with the run id as the trace id
    (structure by default: ids, counts, reasons, timings, tokens, cost; the
    tracer's ``full`` mode adds the text, for synthetic fixtures only). Without
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
    run = Run(
        run_id=run_id,
        label=final["first_label"],
        normalisations=parsed.normalisations,
        removals=[*parsed.removals, *verified.removals],
        ledgers=verified.ledgers,
        residue=verified.residue,
        label_failed=verified.label_failed,
        date_map=transformed.date_map,
        split_map=transformed.split_map,
        retries=final.get("retries", []),
    )
    return final["output"], run
