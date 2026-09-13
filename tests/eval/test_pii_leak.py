"""pii_leak: hand-made outputs against a hand-made PII, never a Candidate."""

from cvr.eval import PiiHit, pii_leak
from cvr.models import PII, Personal, Referee, RemovalRule

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
            contact=["padraig.osampla@example.org", "+353 1 555 0100"],
        )
    ],
)

CLEAN = {
    "header": "Fictitious Recruitment",
    "body": "Aoife Nic Shampla\nLed the platform team.\nPython, Airflow",
}


def hits(text: str, pii: PII = PII_VALUES, where: str = "body") -> list[PiiHit]:
    return pii_leak({where: text}, pii)


def test_clean_output_has_no_hits():
    assert pii_leak(CLEAN, PII_VALUES) == []


def test_empty_output_has_no_hits():
    assert pii_leak({}, PII_VALUES) == []
    assert pii_leak({"body": ""}, PII()) == []


def test_the_email_as_written_is_a_hit_under_rm_email_in_the_part_it_appears():
    assert pii_leak(
        {**CLEAN, "header": "Aoife.NicShampla@example.com"}, PII_VALUES
    ) == [
        PiiHit(
            where="header", rule=RemovalRule.EMAIL, what="Aoife.NicShampla@example.com"
        )
    ]


def test_the_email_casefolded_is_a_hit_reported_as_it_appeared():
    assert hits("Contact: AOIFE.NICSHAMPLA@EXAMPLE.COM") == [
        PiiHit(
            where="body", rule=RemovalRule.EMAIL, what="AOIFE.NICSHAMPLA@EXAMPLE.COM"
        )
    ]


def test_the_phone_as_written_and_in_national_and_digits_only_forms_all_hit():
    for form in ("+353 21 4270000", "021 4270000", "0214270000", "+353214270000"):
        assert hits(f"Tel {form} (mobile)") == [
            PiiHit(where="body", rule=RemovalRule.PHONE, what=form)
        ], form


def test_a_different_number_is_not_a_hit():
    assert hits("Tel 021 4270001") == []
    assert hits("Order 10214270000 shipped") == []


def test_the_url_hits_with_or_without_scheme_www_and_trailing_slash():
    for form in (
        "https://www.example.com/aoife-fictional/",
        "http://example.com/aoife-fictional",
        "www.example.com/aoife-fictional",
        "EXAMPLE.com/aoife-fictional",
    ):
        assert hits(f"See {form} for more") == [
            PiiHit(where="body", rule=RemovalRule.URL, what=form)
        ], form


def test_an_address_line_hits_alone_and_a_postcode_hits_without_its_space():
    assert hits("7 Sample Quay, Cork") == [
        PiiHit(where="body", rule=RemovalRule.ADDRESS, what="7 Sample Quay"),
        PiiHit(where="body", rule=RemovalRule.ADDRESS, what="Cork"),
    ]
    assert hits("T12AB34") == [
        PiiHit(where="body", rule=RemovalRule.ADDRESS, what="T12AB34")
    ]
    assert hits("t12 ab34") == [
        PiiHit(where="body", rule=RemovalRule.ADDRESS, what="t12 ab34")
    ]


def test_an_address_line_inside_a_longer_word_or_number_is_not_a_hit():
    assert hits("Corkscrew") == []
    assert hits("T12 AB345") == []


def test_the_dob_hits_as_written_iso_and_dd_mm_yyyy():
    for form in ("14 February 1990", "1990-02-14", "14/02/1990", "14 Feb 1990"):
        assert hits(f"Born {form}") == [
            PiiHit(where="body", rule=RemovalRule.DOB, what=form)
        ], form
    for form in ("2 March 1990", "02 Mar 1990", "1990-03-02"):
        assert hits(f"Born {form}", PII(dob="2 March 1990")) == [
            PiiHit(where="body", rule=RemovalRule.DOB, what=form)
        ], form


def test_a_dob_written_as_iso_is_a_hit_written_long():
    assert hits("Born 14 February 1990", PII(dob="1990-02-14")) == [
        PiiHit(where="body", rule=RemovalRule.DOB, what="14 February 1990")
    ]


def test_an_unparseable_dob_still_hits_as_written():
    pii = PII(dob="Spring '90")
    assert hits("Born Spring '90", pii) == [
        PiiHit(where="body", rule=RemovalRule.DOB, what="Spring '90")
    ]
    assert hits("Born 1990", pii) == []


def test_personal_details_hit_as_written_and_not_inside_a_hyphenated_word():
    assert hits("Nationality: Irish. Status: Single") == [
        PiiHit(where="body", rule=RemovalRule.PERSONAL, what="Irish"),
        PiiHit(where="body", rule=RemovalRule.PERSONAL, what="Single"),
    ]
    # Case carries meaning for a plain word; the bullet is not a leak.
    assert hits("Single-handedly rebuilt the single sign-on") == []


def test_a_referee_name_role_and_contact_lines_each_hit_under_rm_referee():
    assert hits("Dr Pádraig Ó Sampla, Head of Platform, +353 1 555 0100") == [
        PiiHit(where="body", rule=RemovalRule.REFEREE, what="+353 1 555 0100"),
        PiiHit(where="body", rule=RemovalRule.REFEREE, what="Dr Pádraig Ó Sampla"),
        PiiHit(where="body", rule=RemovalRule.REFEREE, what="Head of Platform"),
    ]


def test_a_referee_contact_line_matches_with_the_variants_of_its_kind():
    # The line is a phone or an email as far as the leak is concerned, so the
    # digits-only and casefolded forms count, and one line is one hit.
    assert hits("Ref: 01 555 0100") == [
        PiiHit(where="body", rule=RemovalRule.REFEREE, what="01 555 0100")
    ]
    assert hits("Ref: PADRAIG.OSAMPLA@EXAMPLE.ORG") == [
        PiiHit(
            where="body", rule=RemovalRule.REFEREE, what="PADRAIG.OSAMPLA@EXAMPLE.ORG"
        )
    ]


def test_a_referee_contact_shared_with_the_candidate_is_reported_once_under_rm_referee():
    pii = PII(
        phone="+353 1 555 0100",
        email="padraig.osampla@example.org",
        referees=[
            Referee(
                name="P. Ó Sampla",
                contact=["+353 1 555 0100", "padraig.osampla@example.org"],
            )
        ],
    )
    assert hits("015550100 padraig.osampla@example.org", pii) == [
        PiiHit(where="body", rule=RemovalRule.REFEREE, what="015550100"),
        PiiHit(
            where="body", rule=RemovalRule.REFEREE, what="padraig.osampla@example.org"
        ),
    ]


def test_two_occurrences_are_two_hits():
    assert hits("Cork and Cork again") == [
        PiiHit(where="body", rule=RemovalRule.ADDRESS, what="Cork"),
        PiiHit(where="body", rule=RemovalRule.ADDRESS, what="Cork"),
    ]


def test_hits_are_sorted_by_part_then_rule_then_text():
    out = {
        "footer": "Irish",
        "body": "Cork, 0214270000",
        "header": "Aoife.NicShampla@example.com",
    }
    assert pii_leak(out, PII_VALUES) == [
        PiiHit(where="body", rule=RemovalRule.ADDRESS, what="Cork"),
        PiiHit(where="body", rule=RemovalRule.PHONE, what="0214270000"),
        PiiHit(where="footer", rule=RemovalRule.PERSONAL, what="Irish"),
        PiiHit(
            where="header", rule=RemovalRule.EMAIL, what="Aoife.NicShampla@example.com"
        ),
    ]
