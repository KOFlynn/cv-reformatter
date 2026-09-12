from cvr.eval import Finding, dropped_tokens

SOURCE = ["Led", "the", "team", "Python", "Python", "087", "5550123", "Motto"]
OUTPUT = ["Python", "Led", "the", "team", "Experience", "Python"]
REMOVED = ["087", "5550123"]
APPENDIX = ["Motto"]


def test_clean_output_has_no_findings():
    assert dropped_tokens(SOURCE, OUTPUT, REMOVED, APPENDIX) == []


def test_a_token_that_vanished_is_a_finding_counted_in_the_source():
    output = [token for token in OUTPUT if token != "team"]
    assert dropped_tokens(SOURCE, output, REMOVED, APPENDIX) == [
        Finding(what="team", count=1, where="source")
    ]


def test_one_fewer_copy_than_the_source_has_is_a_finding_of_the_shortfall():
    output = [*OUTPUT]
    output.remove("Python")
    assert dropped_tokens(SOURCE, output, REMOVED, APPENDIX) == [
        Finding(what="Python", count=1, where="source")
    ]


def test_a_removed_token_that_is_not_in_the_removal_log_is_a_finding():
    assert dropped_tokens(SOURCE, OUTPUT, [], APPENDIX) == [
        Finding(what="087", count=1, where="source"),
        Finding(what="5550123", count=1, where="source"),
    ]


def test_an_appendix_token_that_is_not_in_the_appendix_is_a_finding():
    assert dropped_tokens(SOURCE, OUTPUT, REMOVED, []) == [
        Finding(what="Motto", count=1, where="source")
    ]


def test_a_removed_token_that_also_appears_in_content_is_counted_with_multiplicity():
    # "Dublin" is both an address line and a job location: two in the source,
    # one rendered, one removed. Nothing is dropped.
    source = ["Dublin", "Dublin"]
    assert dropped_tokens(source, ["Dublin"], ["Dublin"], []) == []
    assert dropped_tokens(source, [], ["Dublin"], []) == [
        Finding(what="Dublin", count=1, where="source")
    ]


def test_empty_inputs_give_no_findings():
    assert dropped_tokens([], [], [], []) == []


def test_findings_are_sorted_by_token():
    source = [*SOURCE, "zeta", "alpha", "Mid", "alpha"]
    assert dropped_tokens(source, OUTPUT, REMOVED, APPENDIX) == [
        Finding(what="Mid", count=1, where="source"),
        Finding(what="alpha", count=2, where="source"),
        Finding(what="zeta", count=1, where="source"),
    ]
