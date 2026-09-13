"""The header/footer Layout: the style matrix's fourth column, observed from the
outside through the dumb text helpers. The shared rules (source coverage,
regeneration, undated entries, literal dates) run over it in ``test_layouts``
because it is in ``LAYOUTS``; this file covers what is specific to the column.
"""

import pytest
from docx_text import all_text, text_by_part

from cvr.golden import CANDIDATES_DIR, LAYOUTS, Candidate, load_candidates
from cvr.text import canonicalise

CANDIDATES = load_candidates(CANDIDATES_DIR)


def c01() -> Candidate:
    (candidate,) = [c for c in CANDIDATES if c.id == "c01"]
    return candidate


def layout():
    (found,) = [layout for layout in LAYOUTS if layout.name == "header-footer"]
    return found


def test_header_footer_is_registered_last_in_matrix_order():
    assert LAYOUTS[-1].name == "header-footer"


def test_header_footer_uses_its_heading_vocabulary():
    texts = all_text(layout().generate(c01()).document)
    for heading in (
        "Personal Statement",
        "Technical Skills",
        "Qualifications",
        "Employment",
    ):
        assert heading in texts


# --- The contact block is split across the header and footer parts.


def texts_in(parts: dict[str, list[str]], prefix: str) -> str:
    return "".join(
        text
        for name, texts in parts.items()
        if name.startswith(prefix)
        for text in texts
    )


@pytest.mark.parametrize("candidate", CANDIDATES, ids=[c.id for c in CANDIDATES])
def test_phone_and_email_are_in_the_header_and_nowhere_else(candidate):
    parts = text_by_part(layout().generate(candidate).document)
    header = texts_in(parts, "word/header")
    body = texts_in(parts, "word/document.xml")
    footer = texts_in(parts, "word/footer")
    for value in (candidate.pii.phone, candidate.pii.email):
        assert value in header
        assert value not in body
        assert value not in footer


@pytest.mark.parametrize("candidate", CANDIDATES, ids=[c.id for c in CANDIDATES])
def test_address_and_urls_are_in_the_footer_and_nowhere_else(candidate):
    parts = text_by_part(layout().generate(candidate).document)
    header = texts_in(parts, "word/header")
    body = texts_in(parts, "word/document.xml")
    footer = texts_in(parts, "word/footer")
    for value in (*candidate.pii.address, *candidate.pii.urls):
        assert value in footer
        assert value not in body
        assert value not in header


def test_manifest_records_the_contact_block_as_header_footer():
    assert layout().generate(c01()).manifest.contact_block == "header-footer"


# --- Dates, bullets, order and confusables.


def c01_with(**first_experience_overrides) -> Candidate:
    data = c01().model_dump()
    data["content"]["experience"][0].update(first_experience_overrides)
    data["tags"] = []
    return Candidate.model_validate(data)


def test_c01_dates_bullets_and_both_sections_reversed():
    generated = layout().generate(c01())
    texts = all_text(generated.document)
    # Raw text: the bullet is a literal en dash, which canonicalising would fold.
    assert "2022-03 to 2026-07" in texts
    assert "– Python" in texts
    manifest = generated.manifest
    assert manifest.experience_order == [2, 1, 0]
    assert manifest.education_order == [1, 0]
    first_start = [
        d
        for d in manifest.dates
        if d.section == "experience" and d.entry == 0 and d.which == "start"
    ]
    assert [d.printed for d in first_start] == ["2022-03"]


def test_prints_a_year_only_date_as_the_year():
    candidate = c01_with(start={"year": 2020, "expected": "2020"})
    texts = all_text(layout().generate(candidate).document)
    assert "2020 to 2026-07" in texts


def test_education_is_the_very_bottom_of_the_body():
    parts = text_by_part(layout().generate(c01()).document)
    body = [canonicalise(text) for text in parts["word/document.xml"]]
    qualifications = body.index("Qualifications")
    # Every other heading comes before it, and nothing but education after it.
    for heading in ("Personal Statement", "Technical Skills", "Employment"):
        assert body.index(heading) < qualifications
    institutions = [canonicalise(e.institution) for e in c01().content.education]
    assert all(body.index(i) > qualifications for i in institutions)
    assert body[-1] == canonicalise(f"– {c01().content.education[0].details[-1]}")
