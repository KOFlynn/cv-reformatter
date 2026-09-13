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
