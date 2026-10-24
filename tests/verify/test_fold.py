"""``fold``: the first answer with placed additions written in, by the same
path grammar verify resolves."""

from support import additions as _additions
from support import block as _block
from support import experience as _experience
from support import labelling as _labelling
from support import ref as _ref

from cvr.verify import verify
from cvr.verify.fold import fold


def test_a_list_is_appended_a_leaf_filled_and_a_new_entry_opened():
    base = _labelling(skills=[_ref("body:0", "QGIS")])
    extra = _additions(
        ("skills", _ref("body:1", "R")),
        ("name", _ref("body:2", "Jo")),
        ("experience[0].title", _ref("body:3", "Analyst")),
        ("experience[0].bullets", _ref("body:4", "Built things")),
        ("education[0].institution", _ref("body:5", "College")),
    )
    folded = fold(base, extra.additions)
    content = folded.content
    assert [r.quote for r in content.skills] == ["QGIS", "R"]
    assert content.name.quote == "Jo"
    assert [e.title.quote for e in content.experience] == ["Analyst"]
    assert [r.quote for r in content.experience[0].bullets] == ["Built things"]
    assert [e.institution.quote for e in content.education] == ["College"]
    # the base is untouched
    assert [r.quote for r in base.content.skills] == ["QGIS"]
    assert base.content.experience == []


def test_a_path_that_addresses_nothing_is_skipped():
    base = _labelling()
    extra = _additions(
        ("experience[3].title", _ref("body:0", "x")),
        ("nickname", _ref("body:0", "x")),
        ("experience[0].salary", _ref("body:0", "x")),
    )
    assert fold(base, extra.additions) == base


def test_folding_the_placed_additions_gives_the_tree_verify_built():
    blocks = [
        _block("body:0", "Catchment Scientist"),
        _block("body:1", "Sampled rivers"),
        _block("body:2", "Hydrologist"),
        _block("body:3", "Nonsense"),
    ]
    base = _labelling(
        experience=[_experience(title=_ref("body:0", "Catchment Scientist"))]
    )
    extra = _additions(
        ("experience[0].bullets", _ref("body:1", "Sampled rivers")),
        ("experience[1].title", _ref("body:2", "Hydrologist")),
        ("experience[2].title", _ref("body:3", "missing quote")),  # rejected
    )
    result = verify(blocks, base, additions=extra)
    assert [a.path for a in result.placed] == [
        "experience[0].bullets",
        "experience[1].title",
    ]
    folded = fold(base, result.placed)
    assert len(folded.content.experience) == len(result.content.experience) == 2
    assert verify(blocks, folded).unplaced == result.unplaced
