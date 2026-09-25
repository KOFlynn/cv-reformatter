"""The eval runner: ``python -m cvr.eval.run [--layout X] [--candidate cNN]
[--no-cache]``.

Every generated document (or the filtered subset) goes through ``reformat``
with the real labeller behind the response cache, out through the adapter,
and into every metric. Writes ``eval/report.json`` and ``eval/report.md``
(both gitignored; ticket 10 commits the dated baseline) and exits 1 on any
hard-gate breach or missed threshold from ``eval/thresholds.yaml``, 0
otherwise. The summary on standard output names each failing metric and the
candidates behind it.

Modules: ``documents`` (the generated set and its filters), ``score`` (every
metric over one run), ``cache`` (the response cache), ``runner`` (bounded
concurrency and retry), ``thresholds`` and ``report`` (breakdowns and the
gate). Only this package and ``api`` may import ``cvr.pipeline``.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import Lock
from time import perf_counter

from cvr.eval.run.cache import CACHE_DIR, LabellerIdentity, ResponseCache
from cvr.eval.run.documents import Document, document, generated_stems, select
from cvr.eval.run.report import Report, build_report
from cvr.eval.run.runner import CONCURRENCY, run_documents
from cvr.eval.run.thresholds import EVAL_DIR, THRESHOLDS_FILE, load_thresholds
from cvr.label import (
    PROMPT_HASH,
    PROMPT_VERSION,
    SCHEMA_HASH,
    SCHEMA_VERSION,
    LabellerConfig,
    RealLabeller,
)
from cvr.label.labeller import build_chat_model
from cvr.pipeline import Labeller

__all__ = ["evaluate", "main", "real_labeller"]


def real_labeller() -> tuple[Callable[[Document], Labeller], LabellerIdentity]:
    """The real labeller per document, configured from ``CVR_LABEL_*``, and
    its identity. The chat model is built once, on the first cache miss, so
    a fully cached run needs no API key; each document gets its own
    ``RealLabeller`` so concurrent calls never share a ``last_run``."""
    config = LabellerConfig.from_env()
    lock = Lock()
    built = []

    def live(_: Document) -> Labeller:
        with lock:
            if not built:
                built.append(build_chat_model(config))
        return RealLabeller(config, chat_model=built[0])

    identity = LabellerIdentity(
        config=config.as_dict(),
        prompt_version=PROMPT_VERSION,
        prompt_hash=PROMPT_HASH,
        schema_version=SCHEMA_VERSION,
        schema_hash=SCHEMA_HASH,
    )
    return live, identity


def evaluate(
    stems: Sequence[str],
    live: Callable[[Document], Labeller],
    identity: LabellerIdentity,
    *,
    thresholds_file: Path = THRESHOLDS_FILE,
    cache: ResponseCache | None = None,
    read_cache: bool = True,
    concurrency: int = CONCURRENCY,
) -> Report:
    """Run, score and gate the documents ``stems``."""
    thresholds = load_thresholds(thresholds_file)
    documents = [document(stem) for stem in stems]
    started = perf_counter()
    results, stats = run_documents(
        documents,
        live,
        identity,
        cache=cache,
        read_cache=read_cache,
        concurrency=concurrency,
    )
    return build_report(
        results,
        identity,
        thresholds,
        stats,
        cache_enabled=cache is not None,
        cache_read=cache is not None and read_cache,
        wall_seconds=perf_counter() - started,
    )


def write_report(report: Report, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path, md_path = directory / "report.json", directory / "report.md"
    json_path.write_text(
        json.dumps(report.as_json(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(report.markdown(), encoding="utf-8")
    return json_path, md_path


def main(
    argv: Sequence[str] | None = None,
    *,
    labeller: tuple[Callable[[Document], Labeller], LabellerIdentity] | None = None,
) -> int:
    """The command line. ``labeller`` replaces the real one (tests pass the
    oracle); everything else is exactly what CI runs."""
    parser = argparse.ArgumentParser(
        prog="python -m cvr.eval.run",
        description=(
            "Run every generated document through the pipeline, score it, "
            "write eval/report.json and eval/report.md, and exit 1 on any "
            "hard-gate breach or missed threshold."
        ),
    )
    parser.add_argument(
        "--layout", action="append", default=[], help="only this Layout (repeatable)"
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="only this Candidate, e.g. c04 (repeatable)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="call the LLM for every document; fresh answers still refresh the cache",
    )
    parser.add_argument(
        "--thresholds", type=Path, default=THRESHOLDS_FILE, help="thresholds file"
    )
    parser.add_argument("--out", type=Path, default=EVAL_DIR, help="report directory")
    parser.add_argument(
        "--cache-dir", type=Path, default=CACHE_DIR, help="response cache directory"
    )
    args = parser.parse_args(argv)

    try:
        stems = select(generated_stems(), args.layout, args.candidate)
    except ValueError as exc:
        parser.error(str(exc))
    live, identity = labeller or real_labeller()
    report = evaluate(
        stems,
        live,
        identity,
        thresholds_file=args.thresholds,
        cache=ResponseCache(args.cache_dir),
        read_cache=not args.no_cache,
    )
    json_path, md_path = write_report(report, args.out)
    for line in report.summary():
        print(line)
    print(f"report: {json_path} and {md_path}")
    return report.exit_code
