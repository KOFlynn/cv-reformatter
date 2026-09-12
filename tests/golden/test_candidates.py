from cvr.golden import CANDIDATES_DIR, Tag, load_candidates


def test_candidates_directory_loads_c01():
    candidates = load_candidates(CANDIDATES_DIR)
    ids = [candidate.id for candidate in candidates]
    assert "c01" in ids


def test_c01_has_every_section_and_contact_detail_the_ticket_asks_for():
    (c01,) = [c for c in load_candidates(CANDIDATES_DIR) if c.id == "c01"]
    content, pii = c01.content, c01.pii
    assert (
        content.profile
        and content.skills
        and content.certifications
        and content.additional
    )
    assert len(content.education) >= 2
    assert len(content.experience) >= 3
    assert all(entry.bullets for entry in content.experience)
    assert pii.phone and pii.email and pii.address and len(pii.urls) == 1
    assert c01.unplaceable == []
    assert c01.tags == [Tag.PUNCTUATION_IN_NAME]
