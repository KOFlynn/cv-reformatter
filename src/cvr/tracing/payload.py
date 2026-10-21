"""The one place that decides what a trace may carry: a pure function from a
node's inputs and outputs to the fields a span is given.

In structure mode (the only mode, until ticket 09 adds ``full``) a span
carries ids, counts, reasons from closed vocabularies, timings, tokens and
cost, never candidate text. Everything leaves through :func:`allowlisted`,
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
from typing import Any

from cvr.models import Labelling, LabelRun

__all__ = [
    "ALLOWED_KEYS",
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
        "cached",
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

# The vocabulary of the verifier's rejection reasons, for a fixed set of keys.
_REJECTION_REASONS = ("unlocatable", "conflict", "removed")


def allowlisted(fields: Mapping[str, Any]) -> dict[str, Any]:
    """``fields`` without any key that is not on the allowlist."""
    return {key: value for key, value in fields.items() if key in ALLOWED_KEYS}


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
    node: str, inputs: Mapping[str, Any], outputs: Mapping[str, Any]
) -> dict[str, Any]:
    """The span fields for one visit of ``node``, from the node's inputs and
    outputs as the pipeline holds them. Returns the keyword arguments for the
    observation (``metadata`` only, in structure mode)."""
    facts: dict[str, Any] = {}
    if node == "parse":
        parsed = outputs["parsed"]
        facts = {
            "source_bytes": len(inputs["source"]),
            "block_count": _count(parsed.blocks),
            "image_count": _count(parsed.images),
            "normalisation_count": _count(parsed.normalisations),
        }
    elif node == "label":
        labelling = outputs["labelling"]
        failed = not isinstance(labelling, Labelling)
        facts = {
            "block_count": _count(inputs["blocks"]),
            "label_failed": failed,
            "reference_count": _reference_count(labelling),
            "removal_reference_count": 0 if failed else _count(labelling.removals),
        }
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
    return {"metadata": allowlisted(facts)}


def rejection_payload(rejection: Any, block_ids: Collection[str]) -> dict[str, Any]:
    """One rejection as an event: where in the tree, which block, why. Never
    the quote. The block id is the model's, so it is reported only when it is
    one of ``block_ids`` (the parsed blocks'); otherwise it is ``unknown``."""
    return {
        "metadata": allowlisted(
            {
                "path": rejection.path,
                "block_id": (
                    rejection.block_id if rejection.block_id in block_ids else "unknown"
                ),
                "reason": rejection.reason,
            }
        )
    }


def generation_payload(
    label_run: LabelRun | None, *, attempt: int, cached: bool = False
) -> dict[str, Any]:
    """The generation's fields for one labelling attempt: the model, its
    tokens and the cost the project's own price table gave (the labeller
    records both on its ``LabelRun``). A labeller that records no ``LabelRun``
    (the test oracles) still gets a generation, with the attempt alone.

    ``cached`` marks an answer replayed from the eval's response cache: no
    call was made, so the generation carries zero tokens and zero cost
    (the run's own totals still show what the stored answer cost)."""
    if label_run is None:
        facts = {"attempt": attempt, **({"cached": True} if cached else {})}
        return {"metadata": allowlisted(facts)}
    config = label_run.config
    model = config.get("model")
    return {
        "model": model if isinstance(model, str) else None,
        "usage_details": {
            "input": 0 if cached else label_run.input_tokens,
            "output": 0 if cached else label_run.output_tokens,
        },
        "cost_details": {"total": 0.0 if cached else label_run.cost_usd},
        "metadata": allowlisted(
            {
                "attempt": attempt,
                "cached": cached,
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
