from cvr.eval import Finding, added_tokens

SOURCE = ["Led", "the", "team", "Python", "Python"]
TEMPLATE = ["Experience", "Skills"]


def test_clean_output_has_no_findings():
    output = ["Python", "Led", "the", "team", "Experience", "Python", "Skills"]
    assert added_tokens(SOURCE, output, TEMPLATE, []) == []


def test_a_token_from_nowhere_is_a_finding_counted_in_the_output():
    output = [*SOURCE, "invented"]
    assert added_tokens(SOURCE, output, TEMPLATE, []) == [
        Finding(what="invented", count=1, where="output")
    ]


def test_one_more_copy_than_the_source_has_is_a_finding_of_the_excess():
    output = [*SOURCE, "Python", "Python"]
    assert added_tokens(SOURCE, output, TEMPLATE, []) == [
        Finding(what="Python", count=2, where="output")
    ]


def test_template_tokens_are_permitted_once_per_template_occurrence():
    output = [*SOURCE, "Experience", "Experience"]
    assert added_tokens(SOURCE, output, TEMPLATE, []) == [
        Finding(what="Experience", count=1, where="output")
    ]


def test_the_rendered_side_of_a_mapped_date_is_permitted():
    date_map = [("March 2022", "03/2022"), ("Summer 2020", "Summer 2020")]
    output = [*SOURCE, "03/2022", "Summer", "2020"]
    assert added_tokens(SOURCE, output, TEMPLATE, date_map) == []


def test_the_source_side_of_a_mapped_date_is_not_permitted_by_the_map():
    output = [*SOURCE, "March", "2022"]
    assert added_tokens(SOURCE, output, TEMPLATE, [("March 2022", "03/2022")]) == [
        Finding(what="2022", count=1, where="output"),
        Finding(what="March", count=1, where="output"),
    ]


def test_empty_inputs_give_no_findings():
    assert added_tokens([], [], [], []) == []


def test_findings_are_sorted_by_token():
    output = [*SOURCE, "zeta", "alpha", "Mid", "alpha"]
    assert added_tokens(SOURCE, output, TEMPLATE, []) == [
        Finding(what="Mid", count=1, where="output"),
        Finding(what="alpha", count=2, where="output"),
        Finding(what="zeta", count=1, where="output"),
    ]
