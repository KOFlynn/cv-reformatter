"""The header/footer Layout: the style matrix's fourth column, observed from the
outside through the dumb text helpers. The shared rules (source coverage,
regeneration, undated entries, literal dates) run over it in ``test_layouts``
because it is in ``LAYOUTS``; this file covers what is specific to the column.
"""

import pytest
from docx_text import all_text, text_by_part

from cvr.golden import CANDIDATES_DIR, LAYOUTS, Candidate, Tag, load_candidates
from cvr.text import canonicalise

CANDIDATES = load_candidates(CANDIDATES_DIR)


def c01() -> Candidate:
    (candidate,) = [c for c in CANDIDATES if c.id == "c01"]
    return candidate


def header_footer():
    (found,) = [layout for layout in LAYOUTS if layout.name == "header-footer"]
    return found


def test_header_footer_is_registered_last_in_matrix_order():
    assert LAYOUTS[-1].name == "header-footer"


def test_header_footer_uses_its_heading_vocabulary():
    texts = all_text(header_footer().generate(c01()).document)
    for heading in (
        "Personal Statement",
        "Technical Skills",
        "Qualifications",
        "Employment",
    ):
        assert heading in texts


# --- The contact block is split across the header and footer parts.


def part_text(parts: dict[str, list[str]], prefix: str) -> str:
    """The canonicalised text of every part whose name starts with ``prefix``."""
    return canonicalise(
        " ".join(
            text
            for name, texts in parts.items()
            if name.startswith(prefix)
            for text in texts
        )
    )


PARTS = {"header": "word/header", "body": "word/document.xml", "footer": "word/footer"}


@pytest.mark.parametrize("candidate", CANDIDATES, ids=[c.id for c in CANDIDATES])
@pytest.mark.parametrize(
    ("home", "select"),
    [
        ("header", lambda pii: [pii.phone, pii.email]),
        # The address as printed, its lines together: a town on its own is a
        # place the body may say as a work location, as pii_leak allows.
        ("footer", lambda pii: [" ".join(pii.address), *pii.urls]),
    ],
    ids=["phone-and-email", "address-and-urls"],
)
def test_contact_values_are_in_their_part_and_nowhere_else(candidate, home, select):
    parts = text_by_part(header_footer().generate(candidate).document)
    # The pii-in-bullet trap prints the phone inside a body bullet on purpose.
    also_in_body = (
        {canonicalise(candidate.pii.phone)}
        if Tag.PII_IN_BULLET in candidate.tags
        else set()
    )
    for value in map(canonicalise, select(candidate.pii)):
        for part, prefix in PARTS.items():
            expected = part == home or (part == "body" and value in also_in_body)
            assert (value in part_text(parts, prefix)) is expected, (
                f"{candidate.id}: {value!r} "
                f"{'missing from' if part == home else 'found in'} {part}"
            )


def test_manifest_records_the_contact_block_as_header_footer():
    assert header_footer().generate(c01()).manifest.contact_block == "header-footer"


# --- Dates, bullets, order and confusables.


def c01_with(**first_experience_overrides) -> Candidate:
    data = c01().model_dump()
    data["content"]["experience"][0].update(first_experience_overrides)
    data["tags"] = []
    return Candidate.model_validate(data)


def test_c01_dates_bullets_and_both_sections_reversed():
    generated = header_footer().generate(c01())
    texts = all_text(generated.document)
    assert "2022-03 to 2026-07" in texts
    # Raw text: the bullet is a literal en dash, which canonicalising would
    # fold, followed by a zero-width space, which it would strip.
    assert "– " + chr(0x200B) + "Python" in texts
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
    texts = all_text(header_footer().generate(candidate).document)
    assert "2020 to 2026-07" in texts


def test_education_is_the_very_bottom_of_the_body():
    parts = text_by_part(header_footer().generate(c01()).document)
    body = [canonicalise(text) for text in parts["word/document.xml"]]
    qualifications = body.index("Qualifications")
    # Every other heading comes before it, and nothing but education after it.
    for heading in ("Personal Statement", "Technical Skills", "Employment"):
        assert body.index(heading) < qualifications
    institutions = [canonicalise(e.institution) for e in c01().content.education]
    assert all(body.index(i) > qualifications for i in institutions)
    assert body[-1] == canonicalise(f"– {c01().content.education[0].details[-1]}")


def test_curls_apostrophes_and_lists_the_confusables_it_injected():
    data = c01().model_dump()
    data["content"]["skills"][0] = "Bob's Toolkit"
    candidate = Candidate.model_validate(data)
    generated = header_footer().generate(candidate)
    texts = all_text(generated.document)
    assert "Sinéad O’Sampla" in texts
    assert "– " + chr(0x200B) + "Bob’s Toolkit" in texts
    assert not any("'" in text for text in texts)
    # Zero-width spaces are injected too, and everything is from the table:
    # both as U+XXXX, sorted, and nothing else.
    assert any("\u200b" in text for text in texts)
    assert generated.manifest.confusables == ["U+200B", "U+2019"]


def test_manifest_lists_only_confusables_actually_injected():
    data = c01().model_dump()
    data["content"]["name"] = "Sinead Sampla"
    data["tags"] = []
    manifest = header_footer().generate(Candidate.model_validate(data)).manifest
    assert manifest.confusables == ["U+200B"]


def test_confusables_do_not_break_source_coverage_of_the_curled_text():
    data = c01().model_dump()
    data["content"]["skills"][0] = "Bob's Toolkit"
    candidate = Candidate.model_validate(data)
    texts = [
        canonicalise(t) for t in all_text(header_footer().generate(candidate).document)
    ]
    assert any("Bob's Toolkit" in text for text in texts)
