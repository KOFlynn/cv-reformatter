import dataclasses

import pytest

from cvr.eval import Finding


def test_finding_carries_what_count_and_where():
    finding = Finding(what="invented", count=2, where="output")
    assert (finding.what, finding.count, finding.where) == ("invented", 2, "output")


def test_finding_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Finding(what="x", count=1, where="output").count = 2


def test_findings_sort_by_where_then_what_then_count():
    findings = [
        Finding(what="b", count=1, where="source"),
        Finding(what="a", count=2, where="source"),
        Finding(what="z", count=1, where="output"),
        Finding(what="a", count=1, where="source"),
    ]
    assert sorted(findings) == [
        Finding(what="z", count=1, where="output"),
        Finding(what="a", count=1, where="source"),
        Finding(what="a", count=2, where="source"),
        Finding(what="b", count=1, where="source"),
    ]
