"""verify with a retry's additions: path-addressed references resolved
against what the first answer placed, then run through the same claim ledger,
after the first answer's references. Without additions nothing changes (the
rest of this directory proves that)."""

from support import additions as _additions
from support import block as _block
from support import experience as _experience
from support import labelling as _labelling
from support import ref as _ref

from cvr.models import LabellingFailure, RemovalReference, Span
from cvr.verify import Claim, Rejection, verify


def _texts(units) -> list[list[str]]:
    return [[span.text for span in unit.spans] for unit in units]


# --- Where an addition's span goes


def test_an_addition_to_a_bullet_list_is_appended_to_that_entrys_bullets():
    blocks = [
        _block("body:0", "Catchment Scientist"),
        _block("body:1", "Sampled rivers"),
        _block("body:2", "Wrote reports"),
    ]
    first = _labelling(
        experience=[
            _experience(
                title=_ref("body:0", "Catchment Scientist"),
                bullets=[_ref("body:1", "Sampled rivers")],
            )
        ]
    )
    extra = _additions(("experience[0].bullets", _ref("body:2", "Wrote reports")))
    result = verify(blocks, first, additions=extra)
    [entry] = result.content.experience
    assert _texts(entry.bullets) == [["Sampled rivers"], ["Wrote reports"]]
    assert result.rejections == [] and result.unplaced == []
    claim = Claim(path="experience[0].bullets[1]", span=entry.bullets[1].spans[0])
    assert claim in result.claims


def test_an_addition_to_a_top_level_list_is_appended():
    blocks = [_block("body:0", "QGIS"), _block("body:1", "R")]
    first = _labelling(skills=[_ref("body:0", "QGIS")])
    result = verify(
        blocks, first, additions=_additions(("skills", _ref("body:1", "R")))
    )
    assert _texts(result.content.skills) == [["QGIS"], ["R"]]


def test_an_addition_to_a_list_the_first_answer_left_empty_starts_the_list():
    blocks = [_block("body:0", "Certified Drone Pilot")]
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(
            ("certifications", _ref("body:0", "Certified Drone Pilot"))
        ),
    )
    assert _texts(result.content.certifications) == [["Certified Drone Pilot"]]


def test_an_addition_to_an_empty_leaf_fills_it():
    blocks = [_block("body:0", "Catchment Scientist"), _block("body:1", "Slaney Trust")]
    first = _labelling(
        experience=[_experience(employer=_ref("body:1", "Slaney Trust"))]
    )
    result = verify(
        blocks,
        first,
        additions=_additions(
            ("experience[0].title", _ref("body:0", "Catchment Scientist"))
        ),
    )
    [entry] = result.content.experience
    assert _texts([entry.title]) == [["Catchment Scientist"]]
    assert _texts([entry.employer]) == [["Slaney Trust"]]
    assert result.rejections == []


def test_a_leaf_the_first_answer_could_not_place_is_still_empty_and_addressable():
    blocks = [_block("body:0", "Padraig Lonergan")]
    first = _labelling(name=_ref("body:0", "Padraig Lonergen"))  # misquoted
    result = verify(
        blocks,
        first,
        additions=_additions(("name", _ref("body:0", "Padraig Lonergan"))),
    )
    assert _texts([result.content.name]) == [["Padraig Lonergan"]]
    assert [r.reason for r in result.rejections] == ["unlocatable"]
    assert result.unplaced == []


def test_an_addition_as_a_new_entry_follows_the_first_answers_entries():
    blocks = [
        _block("body:0", "Hydrologist"),
        _block("body:1", "Fieldworker"),
        _block("body:2", "Jan 2015 - Dec 2016"),
        _block("body:3", "Counted fish"),
    ]
    first = _labelling(experience=[_experience(title=_ref("body:0", "Hydrologist"))])
    result = verify(
        blocks,
        first,
        additions=_additions(
            ("experience[1].title", _ref("body:1", "Fieldworker")),
            ("experience[1].dates", _ref("body:2", "Jan 2015 - Dec 2016")),
            ("experience[1].bullets", _ref("body:3", "Counted fish")),
        ),
    )
    first_entry, new = result.content.experience
    assert _texts([first_entry.title]) == [["Hydrologist"]]
    assert _texts([new.title]) == [["Fieldworker"]]
    assert _texts([new.dates]) == [["Jan 2015 - Dec 2016"]]
    assert _texts(new.bullets) == [["Counted fish"]]
    assert result.rejections == [] and result.unplaced == []


def test_a_new_education_entry_works_alike():
    blocks = [
        _block("body:0", "UCD"),
        _block("body:1", "BSc"),
        _block("body:2", "First class"),
    ]
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(
            ("education[0].institution", _ref("body:0", "UCD")),
            ("education[0].qualification", _ref("body:1", "BSc")),
            ("education[0].details", _ref("body:2", "First class")),
        ),
    )
    [entry] = result.content.education
    assert _texts([entry.institution, entry.qualification]) == [["UCD"], ["BSc"]]
    assert _texts(entry.details) == [["First class"]]


def test_a_new_entry_whose_every_addition_is_lost_is_not_left_behind_empty():
    blocks = [_block("body:0", "Hydrologist")]
    result = verify(
        blocks,
        _labelling(experience=[_experience(title=_ref("body:0", "Hydrologist"))]),
        additions=_additions(("experience[1].title", _ref("body:0", "Hydrologist"))),
    )
    assert len(result.content.experience) == 1
    assert [r.reason for r in result.rejections] == ["conflict"]


# --- bad_path


def test_a_leaf_the_first_answer_filled_is_bad_path():
    blocks = [_block("body:0", "Padraig Lonergan"), _block("body:1", "Other Name")]
    result = verify(
        blocks,
        _labelling(name=_ref("body:0", "Padraig Lonergan")),
        additions=_additions(("name", _ref("body:1", "Other Name"))),
    )
    assert _texts([result.content.name]) == [["Padraig Lonergan"]]
    assert result.rejections == [
        Rejection(path="name", block_id="body:1", quote="Other Name", reason="bad_path")
    ]
    # Nothing was claimed, so the block is still unplaced text.
    assert [span.text for span in result.unplaced] == ["Other Name"]


def test_an_out_of_range_entry_index_is_bad_path():
    blocks = [_block("body:0", "Hydrologist")]
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(
            ("experience[1].title", _ref("body:0", "Hydrologist")),  # 0 is next
            ("education[3].details", _ref("body:0", "Hydrologist")),
        ),
    )
    assert result.content.experience == [] and result.content.education == []
    assert [(r.path, r.reason) for r in result.rejections] == [
        ("experience[1].title", "bad_path"),
        ("education[3].details", "bad_path"),
    ]


def test_an_unknown_field_or_a_malformed_path_is_bad_path():
    blocks = [_block("body:0", "x")]
    paths = [
        "nickname",
        "experience[0].salary",
        "experience[0]",
        "experience.title",
        "experience[-1].title",
        "experience[x].title",
        "skills[0]",
        "education[0].bullets",
        "",
        " skills",
    ]
    result = verify(
        blocks,
        _labelling(experience=[_experience()]),
        additions=_additions(*((path, _ref("body:0", "x")) for path in paths)),
    )
    # B1: a path is recorded only if it fits the path grammar (known field
    # names, brackets and digits); free text is recorded as ``unknown``.
    recorded = {
        "skills[0]": "skills[0]",
        "education[0].bullets": "education[0].bullets",
    }
    assert [(r.path, r.reason) for r in result.rejections] == [
        (recorded.get(path, "unknown"), "bad_path") for path in paths
    ]
    assert result.claims == []


def test_a_free_text_path_is_never_recorded_in_a_rejection():
    blocks = [_block("body:0", "x")]
    paths = ["Padraig Lonergan", "name; drop", "experience[0].Padraig", "a@b.example"]
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(*((path, _ref("body:0", "x")) for path in paths)),
    )
    assert [r.path for r in result.rejections] == ["unknown"] * len(paths)
    assert all(r.reason == "bad_path" for r in result.rejections)


def test_an_entry_index_of_more_than_four_digits_is_bad_path_not_an_error():
    blocks = [_block("body:0", "x")]
    huge = f"experience[{'9' * 5000}].title"
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(
            (huge, _ref("body:0", "x")),
            ("experience[12345].title", _ref("body:0", "x")),
        ),
    )
    assert [(r.path, r.reason) for r in result.rejections] == [
        ("unknown", "bad_path"),
        ("experience[12345].title", "bad_path"),
    ]
    assert result.content.experience == []


def test_a_bad_path_addition_does_not_open_a_new_entry():
    blocks = [_block("body:0", "Hydrologist"), _block("body:1", "Fieldworker")]
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(
            ("experience[0].salary", _ref("body:0", "Hydrologist")),
            ("experience[1].title", _ref("body:1", "Fieldworker")),
        ),
    )
    assert result.content.experience == []
    assert [r.reason for r in result.rejections] == ["bad_path", "bad_path"]


# --- The ledger rules, unchanged


def test_an_addition_overlapping_a_first_answer_claim_loses_as_a_conflict():
    blocks = [_block("body:0", "Alpha beta gamma delta")]
    result = verify(
        blocks,
        _labelling(profile=[_ref("body:0", "Alpha beta gamma")]),
        additions=_additions(("additional", _ref("body:0", "beta gamma delta"))),
    )
    assert _texts(result.content.profile) == [["Alpha beta gamma"]]
    assert result.content.additional == []
    assert result.rejections == [
        Rejection(
            path="additional[0]",
            block_id="body:0",
            quote="beta gamma delta",
            reason="conflict",
        )
    ]
    assert [span.text for span in result.unplaced] == [" delta"]


def test_the_first_answer_wins_even_when_the_addition_is_earlier_in_the_tree():
    # skills precedes additional in tree-walk order, but an addition is placed
    # after every reference of the first answer.
    blocks = [_block("body:0", "Alpha beta")]
    result = verify(
        blocks,
        _labelling(additional=[_ref("body:0", "Alpha beta")]),
        additions=_additions(("skills", _ref("body:0", "Alpha beta"))),
    )
    assert _texts(result.content.additional) == [["Alpha beta"]]
    assert result.content.skills == []


def test_an_addition_inside_a_removal_is_rejected_as_removed():
    blocks = [_block("body:0", "Phone 0851234567"), _block("body:1", "QGIS")]
    first = _labelling(
        removals=[
            RemovalReference(rule="RM_PHONE", block_id="body:0", quote="0851234567")
        ]
    )
    result = verify(
        blocks, first, additions=_additions(("skills", _ref("body:0", "0851234567")))
    )
    assert result.content.skills == []
    assert [(r.path, r.reason) for r in result.rejections] == [("skills[0]", "removed")]


def test_an_addition_overlapping_a_removal_is_clipped():
    blocks = [_block("body:0", "Mobile 0851234567 available")]
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(("additional", _ref("body:0", "0851234567 available"))),
    )
    assert _texts(result.content.additional) == [["available"]]


def test_two_additions_of_a_repeated_quote_take_successive_occurrences():
    blocks = [_block("body:0", "R, Python, R")]
    result = verify(
        blocks,
        _labelling(),
        additions=_additions(
            ("skills", _ref("body:0", "R")), ("skills", _ref("body:0", "R"))
        ),
    )
    assert [u.spans[0].start for u in result.content.skills] == [0, 11]


def test_an_unlocatable_addition_is_rejected_unlocatable_and_places_nothing():
    result = verify(
        [_block("body:0", "QGIS")],
        _labelling(),
        additions=_additions(("skills", _ref("body:0", "ArcGIS"))),
    )
    assert [(r.path, r.reason) for r in result.rejections] == [
        ("skills[0]", "unlocatable")
    ]


# --- Coverage and the rest of the contract


def test_coverage_holds_with_additions():
    blocks = [
        _block("body:0", "Hydrologist, Email: a.b@example.org"),
        _block("body:1", "Sampled rivers and lakes"),
        _block("body:2", "Counted fish; stray words"),
    ]
    result = verify(
        blocks,
        _labelling(experience=[_experience(title=_ref("body:0", "Hydrologist"))]),
        additions=_additions(
            ("experience[0].bullets", _ref("body:1", "Sampled rivers and lakes")),
            ("experience[0].bullets", _ref("body:2", "Counted fish")),
            ("experience[0].bullets", _ref("body:2", "Counted fish")),  # held already
            ("nope", _ref("body:2", "stray")),  # bad_path
        ),
    )
    for block in blocks:
        taken = [0] * len(block.text)
        for entry in result.ledgers.get(block.id, []):
            for i in range(entry.start, entry.end):
                taken[i] += 1
        for item in result.residue:
            if item.span.block_id == block.id:
                for i in range(item.span.start, item.span.end):
                    taken[i] += 1
        assert taken == [1] * len(block.text), block.id
    assert [r.reason for r in result.rejections] == ["conflict", "bad_path"]


def test_the_fill_order_is_unchanged_with_additions(monkeypatch):
    import cvr.verify as module

    order: list[str] = []
    stages = (
        "_verify_removals",
        "_regex_backstop",
        "_verify_content",
        "_heading_backstop",
        "_coverage",
    )
    for name in stages:
        original = getattr(module, name)

        def recording(*args, _name=name, _original=original, **kwargs):
            order.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, recording)
    verify(
        [_block("body:0", "x")],
        _labelling(),
        additions=_additions(("skills", _ref("body:0", "x"))),
    )
    assert order == list(stages)


def test_no_additions_and_empty_additions_behave_as_today():
    blocks = [_block("body:0", "Alpha beta"), _block("body:1", "QGIS")]
    first = _labelling(
        profile=[_ref("body:0", "Alpha")], skills=[_ref("body:1", "QGIS")]
    )
    plain = verify(blocks, first)
    assert verify(blocks, first, additions=None) == plain
    assert verify(blocks, first, additions=_additions()) == plain


def test_the_first_answer_is_never_changed_by_additions():
    blocks = [_block("body:0", "Alpha"), _block("body:1", "Beta")]
    first = _labelling(profile=[_ref("body:0", "Alpha")])
    before = first.model_dump()
    verify(blocks, first, additions=_additions(("skills", _ref("body:1", "Beta"))))
    assert first.model_dump() == before


def test_additions_to_a_failed_first_answer_build_on_an_empty_tree():
    blocks = [_block("body:0", "Padraig Lonergan")]
    result = verify(
        blocks,
        LabellingFailure(reason="malformed"),
        additions=_additions(("name", _ref("body:0", "Padraig Lonergan"))),
    )
    assert _texts([result.content.name]) == [["Padraig Lonergan"]]
    assert result.label_failed is True
    assert result.claims == [
        Claim(
            path="name",
            span=Span(block_id="body:0", start=0, end=16, text="Padraig Lonergan"),
        )
    ]
