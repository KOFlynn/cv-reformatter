"""Layouts observed from the outside: Candidate in, document and manifest out,
seen only through the dumb ``all_text`` and ``image_count`` helpers."""

import pytest
from docx_text import all_text, image_count

from cvr.golden import CANDIDATES_DIR, LAYOUTS, Candidate, Tag, load_candidates
from cvr.golden.layouts import BulletPlacement, Decisions
from cvr.text import canonicalise

CANDIDATES = load_candidates(CANDIDATES_DIR)
PAIRS = [(candidate, layout) for candidate in CANDIDATES for layout in LAYOUTS]
PAIR_IDS = [layout.stem(candidate) for candidate, layout in PAIRS]
LAYOUT_IDS = [layout.name for layout in LAYOUTS]


def c01() -> Candidate:
    (candidate,) = [c for c in CANDIDATES if c.id == "c01"]
    return candidate


def layout_named(name: str):
    (layout,) = [layout for layout in LAYOUTS if layout.name == name]
    return layout


def content_strings(candidate: Candidate) -> list[str]:
    """Every string the pipeline must reproduce: each leaf of the content."""
    content = candidate.content
    strings = [content.name, *content.profile, *content.skills]
    for entry in content.experience:
        strings += [entry.title, entry.employer, *entry.bullets]
        if entry.location:
            strings.append(entry.location)
    for entry in content.education:
        strings += [entry.institution, entry.qualification, *entry.details]
    strings += [*content.certifications, *content.additional]
    return strings


def pii_values(candidate: Candidate) -> list[str]:
    """Every string a removal rule must delete."""
    pii = candidate.pii
    values = [pii.phone, pii.email, *pii.address, *pii.urls, pii.dob]
    values += [pii.personal.nationality, pii.personal.marital_status]
    for referee in pii.referees:
        values += [referee.name, referee.role, *referee.contact]
    return [value for value in values if value]


def assert_each_appears(values: list[str], texts: list[str], where: str) -> None:
    canonical = [canonicalise(text) for text in texts]
    missing = [
        value
        for value in values
        if not any(canonicalise(value) in text for text in canonical)
    ]
    assert not missing, f"{where}: not found in the document: {missing}"


# --- Source coverage


@pytest.mark.slow
@pytest.mark.parametrize(("candidate", "layout"), PAIRS, ids=PAIR_IDS)
def test_every_content_string_appears_in_the_document(candidate, layout):
    generated = layout.generate(candidate)
    texts = all_text(generated.document)
    assert_each_appears(content_strings(candidate), texts, f"{candidate.id} content")


@pytest.mark.slow
@pytest.mark.parametrize(("candidate", "layout"), PAIRS, ids=PAIR_IDS)
def test_every_pii_value_appears_in_the_document(candidate, layout):
    generated = layout.generate(candidate)
    texts = all_text(generated.document)
    assert_each_appears(pii_values(candidate), texts, f"{candidate.id} PII")


# --- The photo


@pytest.mark.slow
@pytest.mark.parametrize(("candidate", "layout"), PAIRS, ids=PAIR_IDS)
def test_only_two_column_documents_carry_an_image_and_exactly_one(candidate, layout):
    generated = layout.generate(candidate)
    expected = 1 if layout.name == "two-column" else 0
    assert image_count(generated.document) == expected
    assert generated.manifest.photo is (expected == 1)


# --- The manifest


def manifest_strings(manifest) -> list[str]:
    """Every string value anywhere in the manifest, walked with no schema."""
    found: list[str] = []

    def walk(value):
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(manifest.model_dump(mode="json"))
    return found


@pytest.mark.slow
@pytest.mark.parametrize(("candidate", "layout"), PAIRS, ids=PAIR_IDS)
def test_manifest_carries_no_candidate_content_except_printed_dates(candidate, layout):
    manifest = layout.generate(candidate).manifest
    printed = {date.printed for date in manifest.dates}
    leaves = content_strings(candidate) + pii_values(candidate)
    leaves += [
        date.expected
        for entry in [*candidate.content.experience, *candidate.content.education]
        for date in (entry.start, entry.end)
        if date is not None
    ]
    leaked = [
        (leaf, value)
        for value in manifest_strings(manifest)
        if value not in printed
        for leaf in leaves
        if leaf in value
    ]
    assert not leaked


@pytest.mark.slow
@pytest.mark.parametrize(("candidate", "layout"), PAIRS, ids=PAIR_IDS)
def test_manifest_records_every_entry_and_every_date_once(candidate, layout):
    manifest = layout.generate(candidate).manifest
    content = candidate.content
    assert sorted(manifest.experience_order) == list(range(len(content.experience)))
    assert sorted(manifest.education_order) == list(range(len(content.education)))
    expected_dates = {
        (section, index, which)
        for section, entries in (
            ("experience", content.experience),
            ("education", content.education),
        )
        for index, entry in enumerate(entries)
        for which, date in (("start", entry.start), ("end", entry.end))
        if date is not None
    }
    recorded = [(d.section, d.entry, d.which) for d in manifest.dates]
    assert sorted(recorded) == sorted(expected_dates)
    assert manifest.candidate_id == candidate.id
    assert manifest.layout == layout.name
    assert len(manifest.fragments) == len(candidate.unplaceable)


@pytest.mark.slow
@pytest.mark.parametrize(("candidate", "layout"), PAIRS, ids=PAIR_IDS)
def test_generating_twice_in_memory_gives_identical_bytes(candidate, layout):
    first = layout.generate(candidate)
    second = layout.generate(candidate)
    assert first.document == second.document
    assert first.manifest == second.manifest


# --- Shared rules, exercised on a Candidate built for the purpose because c01
# --- carries neither an undated entry nor a literal date.


def c01_with(**first_experience_overrides) -> Candidate:
    data = c01().model_dump()
    data["content"]["experience"][0].update(first_experience_overrides)
    data["tags"] = []
    return Candidate.model_validate(data)


@pytest.mark.parametrize("layout", LAYOUTS, ids=LAYOUT_IDS)
def test_undated_entries_are_emitted_after_dated_ones(layout):
    candidate = c01_with(start=None, end=None)
    generated = layout.generate(candidate)
    manifest = generated.manifest
    assert manifest.experience_order[-1] == 0
    assert not any(
        date.section == "experience" and date.entry == 0 for date in manifest.dates
    )
    # And in the document itself, not only in the generator's own account: the
    # undated title comes after every dated title in the body's own order.
    texts = all_text(generated.document)
    titles = [entry.title for entry in candidate.content.experience]
    positions = [texts.index(title) for title in titles]
    assert positions[0] > max(positions[1:])


@pytest.mark.parametrize("layout", LAYOUTS, ids=LAYOUT_IDS)
def test_literal_dates_are_printed_verbatim(layout):
    literal = "Summer 2020"
    candidate = c01_with(start={"literal": literal, "expected": literal})
    generated = layout.generate(candidate)
    (start,) = [
        d
        for d in generated.manifest.dates
        if d.section == "experience" and d.entry == 0 and d.which == "start"
    ]
    assert start.printed == literal
    assert any(literal in text for text in all_text(generated.document))


@pytest.mark.parametrize("layout", LAYOUTS, ids=LAYOUT_IDS)
def test_present_end_date_is_printed(layout):
    candidate = c01_with(end={"present": True, "expected": "Present"})
    generated = layout.generate(candidate)
    assert any("Present" in text for text in all_text(generated.document))


@pytest.mark.parametrize("layout", LAYOUTS, ids=LAYOUT_IDS)
def test_unplaceable_fragments_appear_and_are_placed_in_the_manifest(layout):
    data = c01().model_dump()
    data["unplaceable"] = ["Page 1 of 2", "I hereby declare the above is true."]
    candidate = Candidate.model_validate(data)
    generated = layout.generate(candidate)
    assert_each_appears(
        candidate.unplaceable, all_text(generated.document), "fragments"
    )
    assert [f.index for f in generated.manifest.fragments] == [0, 1]
    assert all(f.location for f in generated.manifest.fragments)


@pytest.mark.parametrize("layout", LAYOUTS, ids=LAYOUT_IDS)
def test_pii_in_bullet_prints_the_phone_at_the_end_of_the_marked_bullet(layout):
    # The marked bullet is the first one that ends without a full stop: the
    # fixture holds the expected text, so the phone is added at print time.
    data = c01().model_dump()
    data["content"]["experience"][0]["bullets"] = [
        "Ran the on-call rota for the platform team.",
        "Took escalations directly on my own mobile",
    ]
    data["tags"] = ["pii-in-bullet"]
    candidate = Candidate.model_validate(data)
    generated = layout.generate(candidate)
    texts = [canonicalise(text) for text in all_text(generated.document)]
    printed = canonicalise(
        f"Took escalations directly on my own mobile {candidate.pii.phone}"
    )
    assert any(text.endswith(printed) for text in texts), texts
    assert generated.manifest.pii_in_bullet == BulletPlacement(experience=0, bullet=1)


@pytest.mark.parametrize("layout", LAYOUTS, ids=LAYOUT_IDS)
def test_without_the_tag_no_bullet_carries_the_phone(layout):
    candidate = c01()
    assert Tag.PII_IN_BULLET not in candidate.tags
    generated = layout.generate(candidate)
    phone = canonicalise(candidate.pii.phone)
    bullets = [
        canonicalise(bullet)
        for entry in candidate.content.experience
        for bullet in entry.bullets
    ]
    texts = [canonicalise(text) for text in all_text(generated.document)]
    assert not any(
        text.endswith(phone) and any(bullet in text for bullet in bullets)
        for text in texts
    )
    assert generated.manifest.pii_in_bullet is None


def test_the_tag_without_a_bullet_ending_open_is_an_error():
    data = c01().model_dump()
    data["tags"] = ["pii-in-bullet"]
    candidate = Candidate.model_validate(data)
    with pytest.raises(ValueError, match="pii-in-bullet"):
        LAYOUTS[0].generate(candidate)


def test_a_layout_may_only_record_confusables_from_the_shared_table():
    decisions = Decisions(contact_block="body-top")
    decisions.injected("\u2019")
    assert decisions.confusables == {"\u2019"}
    with pytest.raises(ValueError):
        decisions.injected("'")


# --- The single-column Layout: the style matrix's control column.


def test_single_column_c01_dates_appear_in_document_and_manifest():
    generated = layout_named("single-column").generate(c01())
    texts = all_text(generated.document)
    assert "March 2022 - July 2026" in texts
    first_start = [
        d
        for d in generated.manifest.dates
        if d.section == "experience" and d.entry == 0 and d.which == "start"
    ]
    assert [d.printed for d in first_start] == ["March 2022"]


def test_single_column_prints_a_year_only_date_as_the_year():
    candidate = c01_with(start={"year": 2020, "expected": "2020"})
    texts = all_text(layout_named("single-column").generate(candidate).document)
    assert "2020 - July 2026" in texts


def test_single_column_uses_its_heading_vocabulary():
    texts = all_text(layout_named("single-column").generate(c01()).document)
    for heading in ("Profile", "Key Skills", "Education", "Experience"):
        assert heading in texts


def test_single_column_is_clean_and_unscrambled():
    generated = layout_named("single-column").generate(c01())
    joined = "".join(all_text(generated.document))
    # No confusables: canonicalising changes nothing but whitespace.
    assert canonicalise(joined) == " ".join(joined.split())
    # Bullets come from Word list numbering, never a literal glyph.
    assert "•" not in joined
    manifest = generated.manifest
    assert manifest.confusables == []
    assert manifest.photo is False
    assert manifest.contact_block == "body-top"
    assert manifest.experience_order == [0, 1, 2]
    assert manifest.education_order == [0, 1]


# --- The two-column table Layout: the style matrix's second column.


def test_two_column_uses_its_heading_vocabulary():
    texts = all_text(layout_named("two-column").generate(c01()).document)
    for heading in ("Summary", "Skills", "Academic Background", "Work History"):
        assert heading in texts


def test_two_column_c01_dates_bullets_and_scramble():
    generated = layout_named("two-column").generate(c01())
    texts = all_text(generated.document)
    # ``MM/YYYY`` dates joined by an en dash, a literal bullet glyph in the text.
    assert "03/2022 – 07/2026" in texts
    assert "• Python" in texts
    manifest = generated.manifest
    assert manifest.contact_block == "left-column"
    assert manifest.experience_order == [2, 1, 0]
    assert manifest.education_order == [0, 1]
    first_start = [
        d
        for d in manifest.dates
        if d.section == "experience" and d.entry == 0 and d.which == "start"
    ]
    assert [d.printed for d in first_start] == ["03/2022"]


def test_two_column_prints_a_year_only_date_as_the_year():
    candidate = c01_with(start={"year": 2020, "expected": "2020"})
    texts = all_text(layout_named("two-column").generate(candidate).document)
    assert "2020 – 07/2026" in texts


def test_two_column_curls_quotes_and_lists_the_confusables_it_injected():
    data = c01().model_dump()
    data["content"]["profile"] = ['Known as "the fixer" on the team.']
    data["content"]["skills"][0] = "Bob's Toolkit"
    candidate = Candidate.model_validate(data)
    generated = layout_named("two-column").generate(candidate)
    texts = all_text(generated.document)
    assert "Known as “the fixer” on the team." in texts
    assert "• Bob’s Toolkit" in texts
    assert "Sinéad O’Sampla" in texts
    assert "• PostgreSQL" in texts  # untouched text is untouched
    # Only what was injected, as U+XXXX, sorted; c01 has a range so the en dash too.
    assert generated.manifest.confusables == ["U+2013", "U+2019", "U+201C", "U+201D"]


def test_two_column_manifest_lists_only_confusables_actually_injected():
    data = c01().model_dump()
    data["content"]["name"] = "Sinead Sampla"
    data["tags"] = []
    manifest = (
        layout_named("two-column").generate(Candidate.model_validate(data)).manifest
    )
    assert manifest.confusables == ["U+2013"]
