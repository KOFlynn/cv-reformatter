"""The report learns the retry loop (ticket 15): retries fired, characters
placed by a retry and retry cost, per layout, per tag, per candidate and in
the totals; tokens and cost sum every attempt; the thresholds are untouched."""

from pipeline.oracle import omit_first_bullet
from run_support import C04, ORACLE, oracle

from cvr.eval.run.cache import ResponseCache
from cvr.eval.run.documents import document
from cvr.eval.run.report import Totals, build_report
from cvr.eval.run.retries import retry_chars_placed
from cvr.eval.run.runner import run_documents
from cvr.eval.run.thresholds import Thresholds
from cvr.models import (
    Addition,
    Additions,
    LabelRun,
    Reference,
    RetryRun,
    Run,
    SourceBlock,
)
from cvr.models.feedback import Feedback, UnplacedRun


def _record(cost: float, tokens: int) -> LabelRun:
    return LabelRun(
        config={"model": "m"},
        prompt_version="p1",
        prompt_hash="ph",
        schema_version="s1",
        schema_hash="sh",
        content_hash="ch",
        input_tokens=tokens,
        output_tokens=tokens // 10,
        cost_usd=cost,
    )


FIRST, RETRY = _record(0.02, 1000), _record(0.005, 300)


class Retrying:
    """Misses the first bullet, adds it on a retry; the retry is cheaper."""

    def __init__(self, document):
        self.perfect = oracle(document)
        self.last_run = None

    def __call__(self, blocks, *, feedback=None, first=None):
        full = self.perfect(blocks)
        if feedback is None:
            self.last_run = FIRST
            return omit_first_bullet(full)
        self.last_run = RETRY
        bullet = full.content.experience[0].bullets[0]
        return Additions(
            additions=[
                Addition(
                    path="experience[0].bullets",
                    reference=Reference(block_id=bullet.block_id, quote=bullet.quote),
                )
            ]
        )


def _live(document):
    return Retrying(document)


_live.retryable = True

THRESHOLDS = Thresholds(placement_min=0, appendix_max=100, punctuation_hard=False)


def _report(tmp_path, live=_live, stems=C04):
    results, stats = run_documents(
        [document(stem) for stem in stems], live, ORACLE, cache=ResponseCache(tmp_path)
    )
    report = build_report(
        results,
        ORACLE,
        THRESHOLDS,
        stats,
        cache_enabled=True,
        cache_read=True,
        wall_seconds=1.0,
    )
    return results, report


def test_totals_sum_every_attempt_and_the_three_columns_are_per_document(tmp_path):
    results, report = _report(tmp_path)
    total = report.total
    assert total.retries_fired == 4  # one retry in each of four Layouts
    assert total.retry_chars_placed == sum(r.chars_placed for r in results) > 0
    assert all(r.chars_placed > 0 for r in results)
    assert total.retry_cost_usd == 4 * RETRY.cost_usd
    assert total.cost_usd == 4 * (FIRST.cost_usd + RETRY.cost_usd)
    assert total.input_tokens == 4 * (FIRST.input_tokens + RETRY.input_tokens)
    assert total.output_tokens == 4 * (FIRST.output_tokens + RETRY.output_tokens)
    assert report.spent_usd == total.cost_usd  # every attempt was live
    assert report.passed


def test_the_columns_appear_per_layout_per_tag_per_candidate_and_in_the_json(tmp_path):
    _, report = _report(tmp_path)
    data = report.as_json()
    cells = [
        data["totals"],
        *data["per_layout"].values(),
        *data["per_candidate"].values(),
    ]
    cells += list(data["per_tag"].values())
    for cell in cells:
        assert cell["retries_fired"] == cell["documents"]
        assert cell["retry_chars_placed"] > 0
        assert cell["retry_cost_usd"] == round(cell["documents"] * RETRY.cost_usd, 4)
    assert set(data["per_layout"]) == {
        "header-footer",
        "single-column",
        "text-box",
        "two-column",
    }
    assert data["per_candidate"]["c04"]["retries_fired"] == 4
    assert data["totals"]["cost_usd"] == round(4 * (FIRST.cost_usd + RETRY.cost_usd), 4)
    assert {d["attempts"] for d in data["documents"]} == {2}


def test_the_markdown_has_the_three_columns_in_every_table(tmp_path):
    _, report = _report(tmp_path)
    tables = [
        line
        for line in report.markdown().splitlines()
        if line.startswith("|") and "Retries fired" in line
    ]
    assert len(tables) == 4  # totals, layout, tag, candidate
    for line in tables:
        assert "Placed by retry" in line
        assert "Retry cost $" in line
    assert "characters placed" in report.markdown()


def test_a_cached_rerun_reports_the_same_retries_and_spends_nothing(tmp_path):
    _, first = _report(tmp_path)
    results, second = _report(tmp_path, live=_never)
    for name in ("retries_fired", "retry_chars_placed", "retry_cost_usd", "cost_usd"):
        assert getattr(second.total, name) == getattr(first.total, name)
    assert second.spent_usd == 0
    assert second.cache["live_calls"] == 0
    assert second.cache["hits"] == 8
    assert all(r.cache_hit for r in results)


def _never(document):
    raise AssertionError("a cached rerun made a call")


_never.retryable = True


def test_a_document_without_retries_adds_zero_to_the_columns(tmp_path):
    def live(document):
        return oracle(document)

    _, report = _report(tmp_path, live=live, stems=C04[:1])
    total = report.total
    assert (total.retries_fired, total.retry_chars_placed, total.retry_cost_usd) == (
        0,
        0,
        0,
    )
    assert Totals() + total == total


# --- characters placed by a retry

BLOCKS = [
    SourceBlock(id="b1", text="Fluent in German; ", kind="body"),
    SourceBlock(id="b2", text="Driving licence", kind="body"),
]


def _retry(unplaced_chars, runs=(), unusable=False):
    return RetryRun(
        feedback=Feedback(
            unusable=unusable,
            unplaced=[UnplacedRun(block_id=b, start=s, end=e) for b, s, e in runs],
        ),
        unplaced_chars=unplaced_chars,
    )


def test_no_retry_places_nothing():
    assert retry_chars_placed(Run(run_id="r"), BLOCKS) == 0


def test_chars_placed_is_before_the_first_retry_minus_after_the_last():
    # b1 "Fluent in German; " has 14 letters (the ';' and spaces are not
    # counted), b2 "Driving licence" has 14.
    run = Run(run_id="r", retries=[_retry(14, [("b1", 0, 18), ("b2", 0, 15)])])
    assert retry_chars_placed(run, BLOCKS) == 14
    two = Run(
        run_id="r",
        retries=[_retry(14, [("b1", 0, 18), ("b2", 0, 15)]), _retry(0)],
    )
    assert retry_chars_placed(two, BLOCKS) == 28


def test_a_retry_that_made_no_progress_placed_nothing():
    run = Run(run_id="r", retries=[_retry(14, [("b2", 0, 15)])])
    assert retry_chars_placed(run, BLOCKS) == 0


def test_the_re_ask_of_a_failed_first_answer_counts_from_what_it_left():
    run = Run(
        run_id="r",
        retries=[_retry(14, unusable=True), _retry(0)],
    )
    assert retry_chars_placed(run, BLOCKS) == 14  # the re-ask itself counts 0
