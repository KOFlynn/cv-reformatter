"""The header/footer Layout: the style matrix's fourth column, observed from the
outside through the dumb text helpers. The shared rules (source coverage,
regeneration, undated entries, literal dates) run over it in ``test_layouts``
because it is in ``LAYOUTS``; this file covers what is specific to the column.
"""

import pytest
from docx_text import all_text, text_by_part

from cvr.golden import CANDIDATES_DIR, LAYOUTS, Candidate, load_candidates

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
