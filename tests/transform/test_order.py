"""Entry order: end date descending, Present first, then start date
descending, then source order."""

from cvr.transform.dates import NormalisedDate
from cvr.transform.order import Ranked, order


def _date(
    value: str, year: int | None, month: int | None = None, present: bool = False
) -> NormalisedDate:
    return NormalisedDate(
        value=value, year=year, month=month, present=present, literal=False
    )


def _entry(
    name: str, index: int, start: NormalisedDate | None, end: NormalisedDate | None
) -> Ranked[str]:
    return Ranked(item=name, start=start, end=end, index=index)


def test_present_sorts_first() -> None:
    present = _entry(
        "present", 0, _date("01/2020", 2020, 1), _date("Present", None, present=True)
    )
    past = _entry("past", 1, _date("01/2010", 2010, 1), _date("12/2015", 2015, 12))
    assert order([past, present]) == ["present", "past"]


def test_two_present_roles_order_by_start_descending() -> None:
    later = _entry(
        "later", 0, _date("06/2022", 2022, 6), _date("Present", None, present=True)
    )
    earlier = _entry(
        "earlier", 1, _date("01/2020", 2020, 1), _date("Present", None, present=True)
    )
    assert order([earlier, later]) == ["later", "earlier"]


def test_concurrent_roles_with_equal_dates_keep_source_order() -> None:
    first = _entry("first", 0, _date("01/2020", 2020, 1), _date("12/2020", 2020, 12))
    second = _entry("second", 1, _date("01/2020", 2020, 1), _date("12/2020", 2020, 12))
    assert order([second, first]) == ["first", "second"]


def test_year_only_sorts_as_january_but_prints_no_month() -> None:
    year_only = _entry("year-only", 0, None, _date("2020", 2020))
    january = _entry("january", 1, None, _date("01/2020", 2020, 1))
    december = _entry("december", 2, None, _date("12/2019", 2019, 12))
    # year-only and january both rank as (2020, month 1): source order (the
    # index) breaks the tie, so year-only (index 0) sorts ahead of january.
    ranked = order([december, january, year_only])
    assert ranked == ["year-only", "january", "december"]
    assert year_only.end.value == "2020"  # never printed with a month


def test_undated_entry_sorts_last_in_source_order() -> None:
    dated = _entry("dated", 0, None, _date("01/2020", 2020, 1))
    undated_first = _entry("undated-first", 1, None, None)
    undated_second = _entry("undated-second", 2, None, None)
    assert order([undated_second, dated, undated_first]) == [
        "dated",
        "undated-first",
        "undated-second",
    ]


def test_end_descending_beats_start_descending() -> None:
    # a earlier start but a later end must still sort ahead of a later start
    # with an earlier end: the end date is the primary key.
    early_start_late_end = _entry(
        "early-start-late-end", 0, _date("01/2021", 2021, 1), _date("01/2023", 2023, 1)
    )
    late_start_early_end = _entry(
        "late-start-early-end", 1, _date("06/2022", 2022, 6), _date("06/2022", 2022, 6)
    )
    assert order([late_start_early_end, early_start_late_end]) == [
        "early-start-late-end",
        "late-start-early-end",
    ]
