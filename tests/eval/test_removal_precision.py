"""removal_precision: hand-made removal logs against a hand-made PII and
heading list, never a Candidate."""

import pytest

from cvr.eval import Finding, removal_precision, wrongful_removal
from cvr.models import PII, Image, Personal, Referee, Removal, RemovalRule, Span

PII_VALUES = PII(
    phone="+353 21 4270000",
    email="Aoife.NicShampla@example.com",
    address=["7 Sample Quay", "Cork", "T12 AB34"],
    urls=["https://www.example.com/aoife-fictional/"],
    dob="14 February 1990",
    personal=Personal(nationality="Irish", marital_status="Single"),
    referees=[
        Referee(
            name="Dr Pádraig Ó Sampla",
            role="Head of Platform",
            contact=["padraig.osampla@example.org", "Tel: +353 1 555 0100"],
        )
    ],
)
HEADINGS = ["Profile", "Work History", "Education & Training", "References"]


def removal(rule: RemovalRule, text: str, block_id: str = "body:0") -> Removal:
    return Removal(
        rule=rule, subject=Span(block_id=block_id, start=0, end=len(text), text=text)
    )


def judged(*removals: Removal) -> list[Finding]:
    return removal_precision(removals, PII_VALUES, HEADINGS)


ALLOWED = [
    (RemovalRule.PHONE, "+353 21 4270000"),
    (RemovalRule.EMAIL, "Aoife.NicShampla@example.com"),
    (RemovalRule.ADDRESS, "7 Sample Quay"),
    (RemovalRule.ADDRESS, "T12 AB34"),
    (RemovalRule.URL, "https://www.example.com/aoife-fictional/"),
    (RemovalRule.DOB, "14 February 1990"),
    (RemovalRule.PERSONAL, "Irish"),
    (RemovalRule.PERSONAL, "Single"),
    (RemovalRule.REFEREE, "Dr Pádraig Ó Sampla"),
    (RemovalRule.REFEREE, "Head of Platform"),
    (RemovalRule.REFEREE, "padraig.osampla@example.org"),
    (RemovalRule.REFEREE, "Tel: +353 1 555 0100"),
    (RemovalRule.HEADING, "Work History"),
    (RemovalRule.HEADING, "Education & Training"),
]


@pytest.mark.parametrize(("rule", "text"), ALLOWED, ids=lambda v: str(v))
def test_an_allowed_value_removed_under_its_own_rule_passes(rule, text):
    assert judged(removal(rule, text)) == []


def test_an_empty_log_passes():
    assert removal_precision([], PII_VALUES, HEADINGS) == []
    assert removal_precision([], PII(), []) == []


def test_a_content_line_removed_under_rm_personal_is_a_finding():
    text = "EU citizen; no visa required for Ireland"
    assert judged(removal(RemovalRule.PERSONAL, text, "body:39")) == [
        Finding(where="body:39", what=f"RM_PERSONAL: {text}", count=1)
    ]


def test_an_allowed_value_removed_under_the_wrong_rule_is_a_finding():
    # The candidate's own phone is PII, but not the email's to remove; the
    # heading is removable, but not as a referee.
    assert judged(
        removal(RemovalRule.EMAIL, "+353 21 4270000", "header:0"),
        removal(RemovalRule.REFEREE, "References", "body:48"),
    ) == [
        Finding(where="body:48", what="RM_REFEREE: References", count=1),
        Finding(where="header:0", what="RM_EMAIL: +353 21 4270000", count=1),
    ]


def test_a_partial_removal_of_an_allowed_value_passes():
    # One address line of several, a referee's phone out of its contact
    # line, the phone out of the end of a bullet it was printed in.
    assert (
        judged(
            removal(RemovalRule.ADDRESS, "Cork"),
            removal(RemovalRule.REFEREE, "+353 1 555 0100"),
            removal(RemovalRule.PHONE, "4270000"),
        )
        == []
    )


def test_matching_is_on_canonical_text():
    # A phone in no-break spaces, a curled apostrophe, surrounding
    # whitespace: the canonical forms are what is compared.
    pii = PII(phone="087 123 4567", personal=Personal(nationality="Côte d'Ivoire"))
    assert (
        removal_precision(
            [
                removal(RemovalRule.PHONE, "087 123 4567"),
                removal(RemovalRule.PERSONAL, " Côte d’Ivoire "),
            ],
            pii,
            [],
        )
        == []
    )


def test_matching_is_case_sensitive_as_the_source_prints_the_value():
    assert judged(removal(RemovalRule.PERSONAL, "IRISH")) == [
        Finding(where="body:0", what="RM_PERSONAL: IRISH", count=1)
    ]


def test_a_removal_longer_than_the_value_is_a_finding():
    # The value plus content beside it is not covered by the value.
    assert judged(removal(RemovalRule.PERSONAL, "Irish citizen, fluent German")) == [
        Finding(
            where="body:0", what="RM_PERSONAL: Irish citizen, fluent German", count=1
        )
    ]


def test_a_heading_the_layout_did_not_write_is_a_finding():
    assert removal_precision(
        [removal(RemovalRule.HEADING, "Languages")], PII_VALUES, HEADINGS
    ) == [Finding(where="body:0", what="RM_HEADING: Languages", count=1)]
    assert removal_precision(
        [removal(RemovalRule.HEADING, "Profile")], PII_VALUES, []
    ) == [Finding(where="body:0", what="RM_HEADING: Profile", count=1)]


def test_a_rule_with_no_value_allows_nothing():
    assert removal_precision([removal(RemovalRule.PHONE, "087")], PII(), []) == [
        Finding(where="body:0", what="RM_PHONE: 087", count=1)
    ]


def test_a_whitespace_only_removal_removes_nothing_and_passes():
    assert judged(removal(RemovalRule.PERSONAL, "  ")) == []


def test_an_image_removal_is_out_of_scope():
    photo = Removal(
        rule=RemovalRule.PHOTO,
        subject=Image(part="word/media/image1.png", sha256="ab" * 32, size=10),
    )
    assert judged(photo) == []


def test_repeated_removals_of_the_same_text_in_one_block_are_counted():
    text = "Fluent German"
    assert judged(
        removal(RemovalRule.PERSONAL, text), removal(RemovalRule.PERSONAL, text)
    ) == [Finding(where="body:0", what=f"RM_PERSONAL: {text}", count=2)]


def test_findings_are_sorted_by_block_then_rule_and_text():
    assert judged(
        removal(RemovalRule.PERSONAL, "Zebra", "body:9"),
        removal(RemovalRule.PERSONAL, "Apple", "body:9"),
        removal(RemovalRule.DOB, "Mango", "body:1"),
    ) == [
        Finding(where="body:1", what="RM_DOB: Mango", count=1),
        Finding(where="body:9", what="RM_PERSONAL: Apple", count=1),
        Finding(where="body:9", what="RM_PERSONAL: Zebra", count=1),
    ]


def test_a_finding_reads_back_as_its_rule_and_text():
    text = "EU citizen; no visa required for Ireland: yes"
    (finding,) = judged(removal(RemovalRule.PERSONAL, text))
    assert wrongful_removal(finding) == (RemovalRule.PERSONAL, text)
