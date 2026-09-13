"""The template's fixed text is extracted from the built template, minus its
Jinja tags, so the added_tokens whitelist tracks the template rather than a
list somebody once typed."""

from cvr.template import template_text, template_tokens
from cvr.template.build import BANNER, FOOTER, WORDMARK, build_template

JINJA_WORDS = {"if", "for", "in", "endif", "endfor", "entry", "unplaced", "name"}


def test_fixed_text_is_the_headings_wordmark_footer_and_banner():
    text = template_text()
    for expected in (WORDMARK, FOOTER, BANNER, "Key Skills", "Experience"):
        assert expected in text


def test_no_tag_or_tag_content_is_returned():
    text = template_text()
    assert not [t for t in text if "{" in t or "}" in t]
    assert JINJA_WORDS.isdisjoint(template_tokens())


def test_tokens_are_the_tokenised_fixed_text():
    tokens = template_tokens()
    assert "Skills" in tokens
    assert "References" in tokens
    # Punctuation-only fragments such as the date dash carry no token.
    assert not [t for t in tokens if not any(ch.isalnum() for ch in t)]


def test_text_comes_from_the_document_not_a_list(tmp_path):
    # A word added to the template shows up in the extraction with no code
    # change: the whitelist is read from the file, never typed in.
    document = build_template()
    document.add_paragraph("Confidential {{ name }}")
    path = tmp_path / "t.docx"
    document.save(path)
    assert "Confidential" in template_tokens(path)
    assert "Confidential" not in template_tokens()
