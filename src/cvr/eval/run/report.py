"""The report: every document's scores summed per metric, per layout, per
tag and per candidate, then the labeller's configuration and versions,
tokens, cost, wall time and cache use; and the gate, which fails the run on
any hard-gate breach or missed threshold and names the metric and the
candidates behind it.

Hard gates are judged per document (one leak anywhere fails the run) and
thresholds on the run's totals, as ticket 10 sets them from whole runs; a
missed threshold still names the candidates that fall short on their own.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from cvr.eval import FieldType, Finding, Tally, appendix_rate, wrongful_removal
from cvr.eval.run.cache import CacheStats, LabellerIdentity
from cvr.eval.run.runner import DocumentResult
from cvr.eval.run.thresholds import Thresholds

__all__ = ["Failure", "Report", "Totals", "build_report", "gate", "totals_of"]


@dataclass(frozen=True)
class Totals:
    """What a group of documents adds up to. Counts are findings (a
    ``Finding``'s count, one per PII hit); rates are derived on output.

    ``wrongful_removals`` keeps each text removed that its rule may not
    remove as ``(rule, canonical text)``, once per occurrence, so the gate
    can name the rule and the text; the report counts them.
    """

    documents: int = 0
    added: int = 0
    dropped: int = 0
    wrongful_removals: tuple[tuple[str, str], ...] = ()
    provenance: int = 0
    punctuation: int = 0
    pii: int = 0
    images: int = 0
    ordering_failures: int = 0
    structural: Tally = field(default_factory=Tally)
    tunable: Tally = field(default_factory=Tally)
    appendix_tokens: int = 0
    content_tokens: int = 0
    label_failures: int = 0
    errors: int = 0
    retries: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "Totals") -> "Totals":
        return Totals(
            **{
                name: getattr(self, name) + getattr(other, name)
                for name in self.__dataclass_fields__
            }
        )

    @property
    def appendix_rate(self) -> float:
        # Token-weighted over the group; the metric counts items, so the
        # two counts stand in for the tokens.
        return appendix_rate(range(self.appendix_tokens), range(self.content_tokens))

    def as_dict(self) -> dict[str, Any]:
        return {
            "documents": self.documents,
            "added": self.added,
            "dropped": self.dropped,
            "wrongful_removals": len(self.wrongful_removals),
            "provenance": self.provenance,
            "pii": self.pii,
            "images": self.images,
            "ordering_failures": self.ordering_failures,
            "structural": _tally(self.structural),
            "tunable": _tally(self.tunable),
            "punctuation": self.punctuation,
            "appendix_rate": _percent(self.appendix_rate),
            "appendix_tokens": self.appendix_tokens,
            "content_tokens": self.content_tokens,
            "label_failures": self.label_failures,
            "errors": self.errors,
            "retries": self.retries,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 4),
        }


def _percent(ratio: float) -> float:
    return round(100 * ratio, 2)


def _tally(tally: Tally) -> dict[str, Any]:
    return {
        "precision": _percent(tally.precision),
        "recall": _percent(tally.recall),
        "hits": tally.hits,
        "actual": tally.actual,
        "expected": tally.expected,
    }


def _count(findings: Iterable[Any]) -> int:
    return sum(getattr(finding, "count", 1) for finding in findings)


def _wrongful(findings: Iterable[Finding]) -> tuple[tuple[str, str], ...]:
    """Each ``removal_precision`` finding as ``(rule, text)``, once per
    occurrence."""
    return tuple(
        wrongful_removal(finding) for finding in findings for _ in range(finding.count)
    )


def totals_of(result: DocumentResult) -> Totals:
    """One document's contribution. An errored document counts as a
    document and an error, and nothing else."""
    run = result.label_run
    usage = Totals(
        documents=1,
        errors=int(result.error is not None),
        retries=result.retries,
        cache_hits=int(result.cache_hit),
        label_failures=int(result.label_failed),
        input_tokens=run.input_tokens if run else 0,
        output_tokens=run.output_tokens if run else 0,
        cost_usd=run.cost_usd if run else 0.0,
    )
    scores = result.scores
    if scores is None:
        return usage
    return usage + Totals(
        added=_count(scores.added),
        dropped=_count(scores.dropped),
        wrongful_removals=_wrongful(scores.removals),
        provenance=_count(scores.provenance),
        punctuation=_count(scores.punctuation),
        pii=len(scores.pii),
        images=_count(scores.images),
        ordering_failures=int(not scores.ordering.correct),
        structural=scores.placement.structural,
        tunable=scores.placement.tunable,
        appendix_tokens=scores.appendix_tokens,
        content_tokens=scores.content_tokens,
    )


@dataclass(frozen=True)
class Failure:
    """One reason the run fails: the metric, what was wrong, and the
    candidates (and documents) it was wrong for."""

    metric: str
    detail: str
    documents: tuple[str, ...]

    @property
    def candidates(self) -> list[str]:
        return sorted({stem.split("__", 1)[0] for stem in self.documents})

    def summary(self) -> str:
        return f"{self.metric}: {self.detail} ({', '.join(self.candidates)})"

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "detail": self.detail,
            "candidates": self.candidates,
            "documents": list(self.documents),
        }


def _stems(
    documents: Mapping[str, Totals], failing: Callable[[Totals], bool]
) -> tuple[str, ...]:
    return tuple(stem for stem, totals in documents.items() if failing(totals))


def _whole(tally: Tally) -> bool:
    return tally.hits == tally.actual == tally.expected


type _Gate = Callable[[Mapping[str, Totals]], list[Failure]]


def _hard(metric: str, detail: str, failing: Callable[[Totals], bool]) -> _Gate:
    """A hard gate with one failure naming every document that breaches it."""

    def judge(documents: Mapping[str, Totals]) -> list[Failure]:
        stems = _stems(documents, failing)
        return [Failure(metric, detail, stems)] if stems else []

    return judge


def _wrongful_removals(documents: Mapping[str, Totals]) -> list[Failure]:
    """One failure per distinct wrongful removal, naming its rule and text
    and every document it was made in, in rule-then-text order."""
    stems: dict[tuple[str, str], list[str]] = defaultdict(list)
    for stem, totals in documents.items():
        for removal in dict.fromkeys(totals.wrongful_removals):
            stems[removal].append(stem)
    return [
        Failure("removal_precision", f'{rule} may not remove "{text}"', tuple(found))
        for (rule, text), found in sorted(stems.items())
    ]


# The hard gates, in the order their failures are reported.
_HARD: list[_Gate] = [
    _hard("errors", "the document did not complete", lambda t: t.errors > 0),
    _hard(
        "added_tokens", "tokens in the output not in the source", lambda t: t.added > 0
    ),
    _hard("dropped_tokens", "source tokens unaccounted for", lambda t: t.dropped > 0),
    _wrongful_removals,
    _hard(
        "provenance_violations",
        "rendered text that is not a source slice",
        lambda t: t.provenance > 0,
    ),
    _hard("pii_leak", "PII values in the output", lambda t: t.pii > 0),
    _hard("image_leak", "images in the output", lambda t: t.images > 0),
    _hard("ordering", "entries out of order", lambda t: t.ordering_failures > 0),
    _hard(
        "placement_accuracy (structural)",
        "structural leaves below 100% precision or recall",
        lambda t: not _whole(t.structural),
    ),
]


def gate(documents: Mapping[str, Totals], thresholds: Thresholds) -> list[Failure]:
    """Every reason the run fails, hard gates first, in a fixed order, from
    each document's totals by stem."""
    total = sum(documents.values(), Totals())
    failures = [failure for judge in _HARD for failure in judge(documents)]
    if thresholds.punctuation_hard and total.punctuation:
        failures.append(
            Failure(
                "punctuation_fidelity",
                "punctuation changed (hard: true)",
                _stems(documents, lambda t: t.punctuation > 0),
            )
        )
    minimum = thresholds.placement_min
    for side in ("precision", "recall"):
        value = 100 * getattr(total.tunable, side)
        if value < minimum:
            failures.append(
                Failure(
                    "placement_accuracy (tunable)",
                    f"{side} {value:.2f}% below the minimum {minimum:g}%",
                    _stems(
                        documents,
                        lambda t, side=side: 100 * getattr(t.tunable, side) < minimum,
                    ),
                )
            )
    maximum = thresholds.appendix_max
    if 100 * total.appendix_rate > maximum:
        failures.append(
            Failure(
                "appendix_rate",
                f"{100 * total.appendix_rate:.2f}% above the maximum {maximum:g}%",
                _stems(documents, lambda t: 100 * t.appendix_rate > maximum),
            )
        )
    return failures


def _groups(
    results: Sequence[DocumentResult], keys: Callable[[DocumentResult], Iterable[str]]
) -> dict[str, Totals]:
    groups: dict[str, Totals] = defaultdict(Totals)
    for result in results:
        for key in keys(result):
            groups[key] += totals_of(result)
    return dict(sorted(groups.items()))


def _document(result: DocumentResult) -> dict[str, Any]:
    """One document's detail: enough to trace any breach without a rerun."""
    scores, run = result.scores, result.label_run
    detail: dict[str, Any] = {
        "document": result.document.stem,
        "candidate": result.document.manifest.candidate_id,
        "layout": result.document.manifest.layout,
        "tags": [str(tag) for tag in result.document.candidate.tags],
        "totals": totals_of(result).as_dict(),
        "error": result.error,
        "label_failed": result.label_failed,
        "failure_reason": run.failure_reason if run else None,
        "cache_hit": result.cache_hit,
        "retries": result.retries,
        "seconds": round(result.seconds, 3),
    }
    if scores is None:
        return detail
    return detail | {
        "findings": {
            name: [_finding(finding) for finding in findings]
            for name, findings in (
                ("added", scores.added),
                ("dropped", scores.dropped),
                ("removals", scores.removals),
                ("provenance", scores.provenance),
                ("punctuation", scores.punctuation),
                ("pii", scores.pii),
                ("images", scores.images),
            )
        },
        "ordering": {
            str(section): {
                "correct": ordering.correct,
                "unmatched": ordering.unmatched,
            }
            for section, ordering in scores.ordering.sections.items()
        },
        "placement": {
            str(field): _tally(scores.placement.by_field[field]) for field in FieldType
        },
        "appendix": list(scores.adapted.appendix),
    }


def _finding(finding: Any) -> dict[str, Any]:
    return {
        name: str(value) if not isinstance(value, int | str) else value
        for name in finding.__slots__
        if (value := getattr(finding, name)) is not None
    }


@dataclass(frozen=True)
class Report:
    """The run's report: breakdowns, labeller, usage, gate."""

    total: Totals
    per_layout: dict[str, Totals]
    per_tag: dict[str, Totals]
    per_candidate: dict[str, Totals]
    identity: LabellerIdentity
    wall_seconds: float
    cache: dict[str, Any]
    thresholds: Thresholds
    failures: list[Failure]
    # What this run paid: live calls only, replayed answers cost nothing.
    spent_usd: float = 0.0
    documents: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def exit_code(self) -> int:
        return 0 if self.passed else 1

    def as_json(self) -> dict[str, Any]:
        """The report in the ticket's order: totals, per layout, per tag,
        per candidate, config, versions, tokens, cost, wall time; then the
        cache, thresholds, the gate and each document's detail."""
        total = self.total
        return {
            "totals": total.as_dict(),
            "per_layout": {k: v.as_dict() for k, v in self.per_layout.items()},
            "per_tag": {k: v.as_dict() for k, v in self.per_tag.items()},
            "per_candidate": {k: v.as_dict() for k, v in self.per_candidate.items()},
            "config": dict(self.identity.config),
            "versions": {
                "prompt": {
                    "version": self.identity.prompt_version,
                    "hash": self.identity.prompt_hash,
                },
                "schema": {
                    "version": self.identity.schema_version,
                    "hash": self.identity.schema_hash,
                },
            },
            "tokens": {"input": total.input_tokens, "output": total.output_tokens},
            "cost_usd": {
                # What the labellings cost when they were made, replayed or
                # not; and what this run paid, live calls only.
                "labelling": round(total.cost_usd, 4),
                "this_run": round(self.spent_usd, 4),
            },
            "wall_time_seconds": round(self.wall_seconds, 1),
            "cache": self.cache,
            "retries": total.retries,
            "thresholds": {
                "placement_accuracy": {"min": self.thresholds.placement_min},
                "appendix_rate": {"max": self.thresholds.appendix_max},
                "punctuation_fidelity": {"hard": self.thresholds.punctuation_hard},
            },
            "gate": {
                "passed": self.passed,
                "failures": [failure.as_dict() for failure in self.failures],
            },
            "documents": self.documents,
        }

    def summary(self) -> list[str]:
        """The verdict and one line per failure, for standard output."""
        if self.passed:
            return [f"PASS: {self.total.documents} documents, every gate held"]
        return [
            (
                f"FAIL: {len(self.failures)} gate failure(s) over "
                f"{self.total.documents} documents"
            ),
            *(f"  {failure.summary()}" for failure in self.failures),
        ]

    def markdown(self) -> str:
        return _markdown(self)


def build_report(
    results: Sequence[DocumentResult],
    identity: LabellerIdentity,
    thresholds: Thresholds,
    stats: CacheStats,
    *,
    cache_enabled: bool,
    cache_read: bool,
    wall_seconds: float,
) -> Report:
    total = sum((totals_of(result) for result in results), Totals())
    spent = sum(
        result.label_run.cost_usd
        for result in results
        if result.label_run is not None and not result.cache_hit
    )
    return Report(
        total=total,
        per_layout=_groups(results, lambda r: [r.document.manifest.layout]),
        per_tag=_groups(
            results, lambda r: [str(tag) for tag in r.document.candidate.tags]
        ),
        per_candidate=_groups(results, lambda r: [r.document.manifest.candidate_id]),
        identity=identity,
        wall_seconds=wall_seconds,
        cache={
            "enabled": cache_enabled,
            "read": cache_read,
            "hits": stats.hits,
            "live_calls": stats.live_calls,
        },
        thresholds=thresholds,
        spent_usd=spent,
        failures=gate({r.document.stem: totals_of(r) for r in results}, thresholds),
        documents=[_document(result) for result in results],
    )


# --- Markdown

_COLUMNS: list[tuple[str, Callable[[Totals], str]]] = [
    ("Docs", lambda t: str(t.documents)),
    ("Added", lambda t: str(t.added)),
    ("Dropped", lambda t: str(t.dropped)),
    ("Wrongful removals", lambda t: str(len(t.wrongful_removals))),
    ("Provenance", lambda t: str(t.provenance)),
    ("PII", lambda t: str(t.pii)),
    ("Images", lambda t: str(t.images)),
    ("Order fails", lambda t: str(t.ordering_failures)),
    ("Structural P/R %", lambda t: _pr(t.structural)),
    ("Tunable P/R %", lambda t: _pr(t.tunable)),
    ("Punctuation", lambda t: str(t.punctuation)),
    ("Appendix %", lambda t: f"{100 * t.appendix_rate:.2f}"),
    ("Label fails", lambda t: str(t.label_failures)),
    ("Errors", lambda t: str(t.errors)),
]


def _pr(tally: Tally) -> str:
    return f"{100 * tally.precision:.2f} / {100 * tally.recall:.2f}"


def _table(label: str, rows: dict[str, Totals]) -> list[str]:
    header = [label, *(name for name, _ in _COLUMNS)]
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
        *(
            "| " + " | ".join([key, *(cell(t) for _, cell in _COLUMNS)]) + " |"
            for key, t in rows.items()
        ),
    ]


def _markdown(report: Report) -> str:
    data = report.as_json()
    total = report.total
    verdict = (
        "**PASS**: every gate held."
        if report.passed
        else f"**FAIL**: {len(report.failures)} gate failure(s); see Gate."
    )
    config = ", ".join(f"{k}={v}" for k, v in data["config"].items())
    versions = data["versions"]
    cache = data["cache"]
    lines = [
        "# Eval report",
        "",
        verdict,
        "",
        "## Totals",
        "",
        *_table("", {"all": total}),
        "",
        "## Per layout",
        "",
        *_table("Layout", report.per_layout),
        "",
        "## Per tag",
        "",
        *_table("Tag", report.per_tag),
        "",
        "## Per candidate",
        "",
        *_table("Candidate", report.per_candidate),
        "",
        "## Labeller and usage",
        "",
        f"- Config: {config}",
        f"- Prompt: {versions['prompt']['version']} ({versions['prompt']['hash']})",
        f"- Schema: {versions['schema']['version']} ({versions['schema']['hash']})",
        f"- Tokens: {total.input_tokens} in, {total.output_tokens} out",
        (
            f"- Cost: ${data['cost_usd']['labelling']:.4f} for the labellings, "
            f"${data['cost_usd']['this_run']:.4f} spent by this run"
        ),
        f"- Wall time: {data['wall_time_seconds']}s",
        (
            f"- Cache: {'on' if cache['enabled'] else 'off'}"
            f"{'' if cache['read'] else ' (reads bypassed)'}, "
            f"{cache['hits']} hits, {cache['live_calls']} live calls"
        ),
        (
            f"- Retries: {total.retries} (provider unavailable: a 429, an "
            "overload or a dropped connection, beyond the client's own two)"
        ),
        "",
        "## Gate",
        "",
        (
            "Thresholds: tunable placement precision and recall at least "
            f"{report.thresholds.placement_min:g}%, appendix rate at most "
            f"{report.thresholds.appendix_max:g}%, punctuation fidelity "
            f"{'hard' if report.thresholds.punctuation_hard else 'soft'}."
        ),
        "",
        *(
            [f"- {failure.summary()}" for failure in report.failures]
            or ["Every gate held."]
        ),
        "",
    ]
    return "\n".join(lines)
