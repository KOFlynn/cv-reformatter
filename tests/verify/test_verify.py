"""The verify node: blocks and a labelling result in; verified content, the
flat claim list, removals, rejections and residue out. Hand-written cases,
one per rule of the claim ledger."""

import pytest
from support import block as _block
from support import experience as _experience
from support import labelling as _labelling
from support import ref as _ref

from cvr.models import LabellingFailure, RemovalReference, RemovalRule, Span
from cvr.verify import Claim, Rejection, Residue, VerifiedDocument, verify


def _texts(units) -> list[list[str]]:
    return [[span.text for span in unit.spans] for unit in units]


# --- Exact and canonical matching


def test_exact_match_places_and_slices_raw():
    blocks = [_block("body:0", "Padraig Lonergan")]
    result = verify(blocks, _labelling(name=_ref("body:0", "Padraig Lonergan")))
    assert result.content.name.spans == [
        Span(block_id="body:0", start=0, end=16, text="Padraig Lonergan")
    ]
    assert result.claims == [Claim(path="name", span=result.content.name.spans[0])]
    assert result.residue == [] and result.rejections == []


def test_match_is_on_canonical_text_and_the_raw_slice_keeps_the_curly_character():
    raw = "Led the team\u2019s\u00a0migration"  # curly apostrophe, no-break space
    blocks = [_block("body:0", raw)]
    result = verify(
        blocks, _labelling(profile=[_ref("body:0", "Led the team's migration")])
    )
    [unit] = result.content.profile
    assert unit.spans[0].text == raw
    assert "\u2019" in unit.spans[0].text


def test_match_is_on_a_substring_of_the_block():
    blocks = [_block("body:0", "Skills: QGIS, R (tidyverse)")]
    result = verify(blocks, _labelling(skills=[_ref("body:0", "R (tidyverse)")]))
    [unit] = result.content.skills
    assert unit.spans == [
        Span(block_id="body:0", start=14, end=27, text="R (tidyverse)")
    ]


def test_match_never_case_folds():
    blocks = [_block("body:0", "Microsoft Excel")]
    result = verify(blocks, _labelling(skills=[_ref("body:0", "microsoft excel")]))
    assert result.content.skills == []
    assert result.rejections[0].reason == "unlocatable"


# --- Repeated quotes (c06's duplicated skill)


def test_two_identical_quotes_place_at_two_occurrences():
    blocks = [_block("body:0", "QGIS, Microsoft Excel, R, Microsoft Excel")]
    labelling = _labelling(
        skills=[_ref("body:0", "Microsoft Excel"), _ref("body:0", "Microsoft Excel")]
    )
    result = verify(blocks, labelling)
    starts = [unit.spans[0].start for unit in result.content.skills]
    assert starts == [6, 26]
    assert result.rejections == []


def test_a_third_identical_quote_against_two_occurrences_is_rejected():
    blocks = [_block("body:0", "QGIS, Microsoft Excel, R, Microsoft Excel")]
    labelling = _labelling(skills=[_ref("body:0", "Microsoft Excel")] * 3)
    result = verify(blocks, labelling)
    assert len(result.content.skills) == 2
    assert result.rejections == [
        Rejection(
            path="skills[2]",
            block_id="body:0",
            quote="Microsoft Excel",
            reason="conflict",
        )
    ]


# --- Unlocatable quotes


def test_unlocatable_quote_rejects_exactly_that_leaf():
    blocks = [
        _block("body:0", "Catchment Scientist"),
        _block("body:1", "Slaney Rivers Trust"),
    ]
    labelling = _labelling(
        experience=[
            _experience(
                title=_ref("body:0", "Catchment Scientist"),
                employer=_ref("body:1", "Slaney River Trust"),  # not the source
            )
        ]
    )
    result = verify(blocks, labelling)
    [entry] = result.content.experience
    assert entry.title.spans[0].text == "Catchment Scientist"
    assert entry.employer is None
    assert result.rejections == [
        Rejection(
            path="experience[0].employer",
            block_id="body:1",
            quote="Slaney River Trust",
            reason="unlocatable",
        )
    ]
    # The unmatched source is residue and, being words, unplaced text.
    assert [r.span.text for r in result.residue if not r.separator] == [
        "Slaney Rivers Trust"
    ]


def test_quote_against_an_unknown_block_is_unlocatable():
    result = verify([_block("body:0", "x")], _labelling(name=_ref("body:9", "x")))
    assert result.rejections[0].reason == "unlocatable"


def test_empty_quote_is_unlocatable():
    result = verify([_block("body:0", "x")], _labelling(name=_ref("body:0", "")))
    assert result.rejections[0].reason == "unlocatable"


# --- Removal clipping


def test_removal_at_the_end_of_a_bullet_yields_a_one_piece_prefix():
    # c08's trap: the phone printed at the end of a bullet.
    text = "Acted as the named contact, who reached me directly on my personal mobile 085 555 0177"
    blocks = [_block("body:0", text)]
    labelling = _labelling(
        removals=[
            RemovalReference(rule="RM_PHONE", block_id="body:0", quote="085 555 0177")
        ],
        experience=[_experience(bullets=[_ref("body:0", text)])],
    )
    result = verify(blocks, labelling)
    [unit] = result.content.experience[0].bullets
    assert len(unit.spans) == 1
    assert unit.spans[0].start == 0
    assert unit.spans[0].text == text[: text.index(" 085")]
    assert [r.rule for r in result.removals] == [RemovalRule.PHONE]
    assert result.removals[0].subject.text == "085 555 0177"


def test_removal_mid_range_yields_a_two_piece_multi_span_unit():
    text = "Call me on 085 555 0177 any weekday"
    blocks = [_block("body:0", text)]
    labelling = _labelling(
        removals=[
            RemovalReference(rule="RM_PHONE", block_id="body:0", quote="085 555 0177")
        ],
        additional=[_ref("body:0", text)],
    )
    result = verify(blocks, labelling)
    [unit] = result.content.additional
    assert [span.text for span in unit.spans] == ["Call me on", "any weekday"]
    assert unit.spans[0].end <= unit.spans[1].start
    # Both pieces are claims under the one path.
    assert [claim.path for claim in result.claims] == ["additional[0]"] * 2
    # The whitespace trimmed off the pieces is separator residue.
    assert all(r.separator for r in result.residue)


def test_content_wholly_inside_a_removal_is_rejected_as_removed():
    blocks = [_block("body:0", "padraig.lonergan@example.net")]
    labelling = _labelling(
        removals=[
            RemovalReference(
                rule="RM_EMAIL", block_id="body:0", quote="padraig.lonergan@example.net"
            )
        ],
        additional=[_ref("body:0", "padraig.lonergan@example.net")],
    )
    result = verify(blocks, labelling)
    assert result.content.additional == []
    assert result.rejections[0].reason == "removed"


def test_an_occurrence_inside_a_removal_is_claimed_so_the_next_one_is_tried():
    # A removed range is claimed: "the first unclaimed occurrence" is the
    # one after it.
    blocks = [_block("body:0", "Referee: Dr Excel, a@example.org. Skills: Excel")]
    labelling = _labelling(
        removals=[
            RemovalReference(
                rule="RM_REFEREE",
                block_id="body:0",
                quote="Referee: Dr Excel, a@example.org.",
            )
        ],
        skills=[_ref("body:0", "Excel")],
    )
    result = verify(blocks, labelling)
    [unit] = result.content.skills
    assert unit.spans[0].start == blocks[0].text.rindex("Excel")
    assert result.rejections == []


def test_llm_removal_is_logged_under_its_rule_and_leaves_the_block_placed_around_it():
    blocks = [_block("body:0", "Referee: Dr A Body, a.body@example.org")]
    labelling = _labelling(
        removals=[
            RemovalReference(
                rule="RM_REFEREE",
                block_id="body:0",
                quote="Referee: Dr A Body, a.body@example.org",
            )
        ]
    )
    result = verify(blocks, labelling)
    # The email inside the referee line is already removed: reported once,
    # under the more specific rule.
    assert [r.rule for r in result.removals] == [RemovalRule.REFEREE]
    assert result.residue == []


def test_unlocatable_llm_removal_is_rejected_and_nothing_removed():
    blocks = [_block("body:0", "Nothing to remove here")]
    labelling = _labelling(
        removals=[RemovalReference(rule="RM_DOB", block_id="body:0", quote="01/01/1990")]
    )
    result = verify(blocks, labelling)
    assert result.removals == []
    assert result.rejections == [
        Rejection(
            path="removals[0]",
            block_id="body:0",
            quote="01/01/1990",
            reason="unlocatable",
        )
    ]


# --- Content conflicts


def test_content_conflict_rejects_the_later_claimant_and_leaves_the_range_residue():
    blocks = [_block("body:0", "Alpha beta gamma delta")]
    labelling = _labelling(
        profile=[_ref("body:0", "Alpha beta gamma")],
        additional=[_ref("body:0", "beta gamma delta")],
    )
    result = verify(blocks, labelling)
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
    # The loser's range gets no claim: what the winner does not hold is
    # residue, raw, and being a word it is unplaced text.
    assert [r.span.text for r in result.residue if not r.separator] == [" delta"]


def test_tree_walk_order_decides_who_is_earlier():
    # Additional comes after profile in the walk whatever the list order in
    # the labelling, so profile is the earlier claimant.
    blocks = [_block("body:0", "Alpha beta")]
    labelling = _labelling(
        additional=[_ref("body:0", "Alpha beta")],
        profile=[_ref("body:0", "Alpha beta")],
    )
    result = verify(blocks, labelling)
    assert result.content.profile and not result.content.additional


# --- Fill order


def test_fill_order_is_removals_backstop_content_heading_backstop_coverage(monkeypatch):
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
    verify([_block("body:0", "x")], _labelling())
    assert order == list(stages)


def test_a_content_claim_over_an_email_is_clipped_with_no_llm_removal_labelled():
    # The backstop fills the ledger before content does, so the email is a
    # removal by the time the content claim arrives and the claim is clipped.
    text = "Contact me at padraig.lonergan@example.net for details"
    blocks = [_block("body:0", text)]
    result = verify(blocks, _labelling(additional=[_ref("body:0", text)]))
    [unit] = result.content.additional
    assert [span.text for span in unit.spans] == ["Contact me at", "for details"]
    assert [(r.rule, r.subject.text) for r in result.removals] == [
        (RemovalRule.EMAIL, "padraig.lonergan@example.net")
    ]


# --- Residue


def test_separator_between_two_placed_skills_is_separator_residue():
    blocks = [_block("body:0", "QGIS, Microsoft Excel")]
    labelling = _labelling(
        skills=[_ref("body:0", "QGIS"), _ref("body:0", "Microsoft Excel")]
    )
    result = verify(blocks, labelling)
    assert result.residue == [
        Residue(span=Span(block_id="body:0", start=4, end=6, text=", "), separator=True)
    ]
    assert result.unplaced == []


def test_a_leftover_ampersand_is_unplaced_text():
    blocks = [_block("body:0", "Research & Development")]
    labelling = _labelling(
        skills=[_ref("body:0", "Research"), _ref("body:0", "Development")]
    )
    result = verify(blocks, labelling)
    assert [(r.span.text, r.separator) for r in result.residue] == [(" & ", False)]
    assert [span.text for span in result.unplaced] == [" & "]


def test_all_residue_is_in_the_log_in_block_and_source_order():
    blocks = [_block("body:0", "a, b"), _block("body:1", "unclaimed line")]
    labelling = _labelling(skills=[_ref("body:0", "a"), _ref("body:0", "b")])
    result = verify(blocks, labelling)
    assert [(r.span.block_id, r.span.text, r.separator) for r in result.residue] == [
        ("body:0", ", ", True),
        ("body:1", "unclaimed line", False),
    ]


def test_ledger_records_every_claim_per_block():
    blocks = [_block("body:0", "QGIS, a@example.org")]
    result = verify(blocks, _labelling(skills=[_ref("body:0", "QGIS")]))
    entries = result.ledgers["body:0"]
    assert [(e.start, e.end, e.claimant) for e in entries] == [
        (0, 4, "skills[0]"),
        (6, 19, "RM_EMAIL"),
    ]


# --- Labelling failure


def test_labelling_failure_leaves_every_block_as_residue_and_flags_the_run():
    blocks = [_block("body:0", "Padraig Lonergan"), _block("body:1", "QGIS")]
    result = verify(blocks, LabellingFailure(reason="schema-invalid"))
    assert isinstance(result, VerifiedDocument)
    assert result.label_failed is True
    assert result.content.name is None and result.claims == []
    assert [r.span.text for r in result.residue] == ["Padraig Lonergan", "QGIS"]
    assert [span.text for span in result.unplaced] == ["Padraig Lonergan", "QGIS"]


def test_labelling_failure_still_runs_the_backstop_so_the_appendix_cannot_leak():
    blocks = [_block("body:0", "Email: padraig.lonergan@example.net")]
    result = verify(blocks, LabellingFailure(reason="malformed"))
    assert [r.rule for r in result.removals] == [RemovalRule.EMAIL]
    assert [span.text for span in result.unplaced] == ["Email: "]


def test_a_usable_labelling_is_not_flagged():
    result = verify([_block("body:0", "x")], _labelling())
    assert result.label_failed is False


@pytest.mark.parametrize("quote", ["Padraig Lonergan", "Padraig  Lonergan"])
def test_whitespace_in_the_quote_is_collapsed_before_matching(quote):
    result = verify(
        [_block("body:0", "Padraig Lonergan")], _labelling(name=_ref("body:0", quote))
    )
    assert result.content.name is not None
