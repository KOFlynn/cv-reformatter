"""The model comparison record from the runs' own reports.

``python -m cvr.eval.compare reference=a.json reference=b.json reference=c.json
candidate=x.json candidate=y.json candidate=z.json --date YYYY-MM-DD --out
eval/provider-comparison-<date>.json`` folds the ``report.json`` files
``cvr.eval.run`` wrote into the shape of ``eval/model-comparison-2026-10-19.json``:
per side (the first label is the reference, the rest candidates), each run's
gate result, totals, per-layout totals, tokens, cost, wall time and cache use,
then the spread over the runs, how many passed the gate and what the side
cost. Facts only: the notes, the verdict and the maintainer's decision are
written by hand beside them.

Runs are refused, not merged, when they cannot be compared: a different prompt,
schema, retry prompt or additions schema (the whole ``versions`` block), a
different set of documents, different thresholds, a different configuration
within one side, or a run that replayed cached answers (its cost and wall time
are not a live run's). Dev-only, like the rest of ``cvr.eval``; the image's
``.dockerignore`` leaves ``src/cvr/eval/`` out.
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = ["CompareError", "compare", "main"]

# The spread's rows: name and the path into a run's entry.
_SPREAD: list[tuple[str, tuple[str, ...]]] = [
    ("tunable_precision", ("totals", "tunable", "precision")),
    ("tunable_recall", ("totals", "tunable", "recall")),
    ("appendix_rate", ("totals", "appendix_rate")),
    ("structural_precision", ("totals", "structural", "precision")),
    ("structural_recall", ("totals", "structural", "recall")),
    *(
        (name, ("totals", name))
        for name in (
            "punctuation",
            "added",
            "dropped",
            "wrongful_removals",
            "provenance",
            "pii",
            "images",
            "ordering_failures",
            "label_failures",
            "errors",
            "retries",
            "retries_fired",
            "retry_chars_placed",
            "retry_cost_usd",
            "input_tokens",
            "output_tokens",
        )
    ),
    ("cost_usd", ("cost_usd",)),
    ("wall_time_seconds", ("wall_time_seconds",)),
]


class CompareError(ValueError):
    """The reports cannot be folded into one comparison."""


def _dig(data: Mapping[str, Any], path: Sequence[str]) -> Any:
    for key in path:
        data = data[key]
    return data


def _stems(report: Mapping[str, Any]) -> list[str]:
    return sorted(doc["document"] for doc in report["documents"])


def _run(number: int, source: str, report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run": number,
        "source": source,
        "gate": report["gate"],
        "totals": report["totals"],
        "per_layout": report["per_layout"],
        "tokens": report["tokens"],
        "cost_usd": report["cost_usd"]["labelling"],
        "wall_time_seconds": report["wall_time_seconds"],
        "retries": report["retries"],
        "cache": report["cache"],
    }


def _spread(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    spread = {}
    for name, path in _SPREAD:
        values = [_dig(run, path) for run in runs]
        for run, value in zip(runs, values, strict=True):
            if value is None:
                raise CompareError(f"{run['source']} has no value for {name}")
        low, high = min(values), max(values)
        spread[name] = {
            "runs": values,
            "min": low,
            "max": high,
            "range": round(high - low, 4),
        }
    return spread


def _side(config: Mapping[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "config": config,
        "runs": runs,
        "spread": _spread(runs),
        "gates_passed": sum(run["gate"]["passed"] for run in runs),
        "total_cost_usd": round(sum(run["cost_usd"] for run in runs), 4),
    }


def _same(what: str, values: Sequence[tuple[str, Any]]) -> Any:
    """The one value every report shares, or a ``CompareError`` naming the
    first report that differs."""
    first_name, first = values[0]
    for name, value in values[1:]:
        if value != first:
            raise CompareError(
                f"{what} differ: {first_name} has {json.dumps(first, sort_keys=True)}"
                f" but {name} has {json.dumps(value, sort_keys=True)}"
            )
    return first


def compare(
    runs: Sequence[tuple[str, str, Mapping[str, Any]]], *, date: str
) -> dict[str, Any]:
    """The comparison record from ``(label, source, report)`` triples, in
    order; the first label is the reference. Raises ``CompareError`` for
    anything that makes the runs incomparable."""
    if not runs:
        raise CompareError("no reports given")
    by_label: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for label, source, report in runs:
        by_label.setdefault(label, []).append((source, report))
    if len(by_label) < 2:
        raise CompareError("a comparison needs at least two labels")
    every = [(source, report) for _, source, report in runs]

    for source, report in every:
        if report["cache"]["hits"]:
            raise CompareError(
                f"{source} replayed {report['cache']['hits']} cached answers; "
                "rerun it with --no-cache so its cost and wall time are live"
            )
    versions = _same("versions", [(s, r["versions"]) for s, r in every])
    thresholds = _same("thresholds", [(s, r["thresholds"]) for s, r in every])
    stems = _same("documents", [(s, _stems(r)) for s, r in every])

    sides = {}
    for label, members in by_label.items():
        config = _same(
            f"configurations within {label!r}", [(s, r["config"]) for s, r in members]
        )
        sides[label] = _side(
            config,
            [_run(n, s, r) for n, (s, r) in enumerate(members, start=1)],
        )
    configs = list(sides.items())
    for i, (first, side) in enumerate(configs):
        for second, other in configs[i + 1 :]:
            if side["config"] == other["config"]:
                raise CompareError(
                    f"{first!r} and {second!r} carry the same config; "
                    "a mislabelled set is not a comparison"
                )
    reference, *others = sides
    return {
        "date": date,
        "versions": versions,
        "documents_per_run": len(stems),
        "thresholds_applied": thresholds,
        "reference": {"label": reference, **sides[reference]},
        "candidates": {label: sides[label] for label in others},
        "total_cost_usd": {
            label: side["total_cost_usd"] for label, side in sides.items()
        },
    }


def _parse(pairs: Sequence[str]) -> list[tuple[str, str, Mapping[str, Any]]]:
    parsed = []
    for pair in pairs:
        label, separator, path = pair.partition("=")
        if not separator or not label or not path:
            raise CompareError(f"expected <label>=<report.json>, got {pair!r}")
        try:
            report = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CompareError(f"cannot read {path}: {error}") from error
        parsed.append((label, path, report))
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cvr.eval.compare",
        description="Fold eval report.json files into a model comparison record.",
    )
    parser.add_argument(
        "runs",
        nargs="+",
        metavar="LABEL=REPORT",
        help="one run; repeat a label for each of its runs; the first label "
        "is the reference",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args(argv)
    try:
        record = compare(_parse(args.runs), date=args.date)
    except CompareError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for label, side in [
        (record["reference"]["label"], record["reference"]),
        *record["candidates"].items(),
    ]:
        print(
            f"{label}: {side['gates_passed']} of {len(side['runs'])} runs passed, "
            f"${side['total_cost_usd']:.4f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
