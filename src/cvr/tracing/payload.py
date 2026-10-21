"""The one place that decides what a trace may carry: a pure function from a
node's inputs and outputs to the fields a span is given.

In structure mode (the default) a span carries ids, counts, reasons from
closed vocabularies, timings, tokens and cost, never candidate text. In
``full`` mode (the CI eval and local runs, synthetic fixtures only) the same
spans also carry the blocks, the rendered prompt messages, the raw answer and
the rejections' quotes; that is the only difference, and it is made here. Everything leaves through :func:`allowlisted`,
which drops any key not in :data:`ALLOWED_KEYS`, so a new field reaches a
trace only if someone adds its name there on purpose. The mask hook
(``cvr.tracing.client``) applies the same allowlist a second time, to
whatever the SDK is about to write.

The functions read the nodes' own result objects by attribute and import
nothing from the node packages (tracing is below the nodes in the layout:
``pipeline`` may depend on it, the nodes may not).
"""

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal

from cvr.models import LabelExchange, Labelling, LabelRun

__all__ = [
    "ALLOWED_KEYS",
    "FULL_KEYS",
    "Mode",
    "allowed_keys",
    "allowlisted",
    "generation_payload",
    "node_payload",
    "rejection_payload",
]

# Every metadata key a span may carry. Counts and closed-vocabulary names
# only; "attempt" is the 1-based labelling attempt.
ALLOWED_KEYS = frozenset(
    {
        "run_id",
        "attempt",
        # parse
        "source_bytes",
        "block_count",
        "image_count",
        "normalisation_count",
        # label
        "label_failed",
        "reference_count",
        "removal_reference_count",
        # verify
        "claim_count",
        "removal_count",
        "rejection_count",
        "rejected_unlocatable",
        "rejected_conflict",
        "rejected_removed",
        "residue_count",
        "unplaced_count",
        # transform
        "date_count",
        "split_count",
        # render
        "output_bytes",
        # rejection events (path is a tree address such as "experience[0].bullets[1]")
        "path",
        "block_id",
        "reason",
        # generation
        "provider",
        "effort",
        "temperature",
        "prompt_version",
        "schema_version",
        "content_hash",
        # the marker the export filter looks for
        "source",
    }
)

type Mode = Literal["structure", "full"]

# What full mode adds: the one metadata key that carries text (a rejection's
# quote) and the top-level keys of the structured inputs and outputs.
FULL_KEYS = frozenset({"quote", "blocks", "messages", "answer"})

# The vocabulary of the verifier's rejection reasons, for a fixed set of keys.
_REJECTION_REASONS = ("unlocatable", "conflict", "removed")


def allowed_keys(mode: Mode) -> frozenset[str]:
    return ALLOWED_KEYS | FULL_KEYS if mode == "full" else ALLOWED_KEYS


def allowlisted(fields: Mapping[str, Any], mode: Mode = "structure") -> dict[str, Any]:
    """``fields`` without any key that is not on the allowlist for ``mode``."""
    keys = allowed_keys(mode)
    return {key: value for key, value in fields.items() if key in keys}


def _blocks(blocks: Any) -> list[dict[str, str]]:
    return [
        {"id": block.id, "kind": str(block.kind), "text": block.text}
        for block in blocks
    ]


def _count(value: Any) -> int:
    return len(value) if value is not None else 0


def _reference_count(labelling: Any) -> int:
    """How many references a labelling holds, counted by walking the model's
    fields (no text is read)."""
    if not isinstance(labelling, Labelling):
        return 0
    return _walk_references(labelling.content)


def _walk_references(node: Any) -> int:
    # A Reference is the only model with a ``quote``; everything else is a
    # container of them.
    if hasattr(node, "quote"):
        return 1
    if node is None or isinstance(node, str | int | float | bool):
        return 0
    if isinstance(node, Sequence):
        return sum(_walk_references(item) for item in node)
    fields = getattr(type(node), "model_fields", None)
    if fields is None:
        return 0
    return sum(_walk_references(getattr(node, name)) for name in fields)


def node_payload(
    node: str,
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    *,
    mode: Mode = "structure",
) -> dict[str, Any]:
    """The span fields for one visit of ``node``, from the node's inputs and
    outputs as the pipeline holds them. Returns the keyword arguments for the
    observation (``metadata`` only, in structure mode; in full mode also the
    blocks parse found and label was given, as ``output`` and ``input``)."""
    facts: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    if node == "parse":
        parsed = outputs["parsed"]
        facts = {
            "source_bytes": len(inputs["source"]),
            "block_count": _count(parsed.blocks),
            "image_count": _count(parsed.images),
            "normalisation_count": _count(parsed.normalisations),
        }
        if mode == "full":
            extra["output"] = {"blocks": _blocks(parsed.blocks)}
    elif node == "label":
        labelling = outputs["labelling"]
        failed = not isinstance(labelling, Labelling)
        facts = {
            "block_count": _count(inputs["blocks"]),
            "label_failed": failed,
            "reference_count": _reference_count(labelling),
            "removal_reference_count": 0 if failed else _count(labelling.removals),
        }
        if mode == "full":
            extra["input"] = {"blocks": _blocks(inputs["blocks"])}
    elif node == "verify":
        verified = outputs["verified"]
        by_reason = Counter(r.reason for r in verified.rejections)
        facts = {
            "label_failed": verified.label_failed,
            "claim_count": _count(verified.claims),
            "removal_count": _count(verified.removals),
            "rejection_count": _count(verified.rejections),
            **{
                f"rejected_{reason}": by_reason[reason] for reason in _REJECTION_REASONS
            },
            "residue_count": _count(verified.residue),
            "unplaced_count": _count(verified.unplaced),
        }
    elif node == "transform":
        transformed = outputs["transformed"]
        facts = {
            "date_count": _count(transformed.date_map),
            "split_count": _count(transformed.split_map),
        }
    elif node == "render":
        facts = {"output_bytes": len(outputs["output"])}
    return {"metadata": allowlisted(facts, mode), **extra}


def rejection_payload(
    rejection: Any, block_ids: Collection[str], *, mode: Mode = "structure"
) -> dict[str, Any]:
    """One rejection as an event: where in the tree, which block, why. The
    quote only in full mode. The block id is the model's, so it is reported only when it is
    one of ``block_ids`` (the parsed blocks'); otherwise it is ``unknown``."""
    facts: dict[str, Any] = {
        "path": rejection.path,
        "block_id": (
            rejection.block_id if rejection.block_id in block_ids else "unknown"
        ),
        "reason": rejection.reason,
    }
    if mode == "full":
        facts["quote"] = rejection.quote
    return {"metadata": allowlisted(facts, mode)}


def generation_payload(
    label_run: LabelRun | None,
    *,
    attempt: int,
    exchange: LabelExchange | None = None,
    mode: Mode = "structure",
) -> dict[str, Any]:
    """The generation's fields for one labelling attempt: the model, its
    tokens and the cost the project's own price table gave (the labeller
    records both on its ``LabelRun``). A labeller that records no ``LabelRun``
    (the test oracles) still gets a generation, with the attempt alone. In
    full mode the generation also carries the rendered prompt messages as its
    input and the raw answer as its output, when the labeller kept them."""
    texts: dict[str, Any] = {}
    if mode == "full" and exchange is not None:
        texts["input"] = {"messages": exchange.messages}
        if exchange.answer is not None:
            texts["output"] = {"answer": exchange.answer}
    if label_run is None:
        return {"metadata": allowlisted({"attempt": attempt}), **texts}
    config = label_run.config
    model = config.get("model")
    return {
        **texts,
        "model": model if isinstance(model, str) else None,
        "usage_details": {
            "input": label_run.input_tokens,
            "output": label_run.output_tokens,
        },
        "cost_details": {"total": label_run.cost_usd},
        "metadata": allowlisted(
            {
                "attempt": attempt,
                "provider": config.get("provider"),
                "effort": config.get("effort"),
                "temperature": config.get("temperature"),
                "prompt_version": label_run.prompt_version,
                "schema_version": label_run.schema_version,
                "content_hash": label_run.content_hash,
                "label_failed": label_run.label_failed,
            }
        ),
    }
