"""The source-side models the parser emits and every later node reads:
``SourceBlock``, ``Span``, ``Image``, ``Removal`` and ``Normalisation``."""

import pytest
from pydantic import ValidationError

from cvr.models import (
    Image,
    Normalisation,
    NormalisationRule,
    Removal,
    RemovalRule,
    SourceBlock,
    Span,
)


def test_source_block_is_an_address_a_text_and_a_kind():
    block = SourceBlock(id="table:0:r0:c1:3", text="Python, Go", kind="table")
    assert (block.id, block.text, block.kind) == (
        "table:0:r0:c1:3",
        "Python, Go",
        "table",
    )


def test_source_block_kind_is_closed():
    with pytest.raises(ValidationError):
        SourceBlock(id="body:0", text="x", kind="paragraph")


def test_span_is_a_raw_slice_of_a_block():
    span = Span(block_id="body:3", start=2, end=8, text="thon, ")
    assert span.text == "Python, Go"[2:8]


def test_span_text_must_be_as_long_as_the_slice_it_names():
    # Length is what the model can check without the block; whether the text
    # is the slice is the verifier's job.
    with pytest.raises(ValidationError, match="slice"):
        Span(block_id="body:3", start=2, end=8, text="Python, Go")


def test_span_must_be_non_empty_and_forward():
    with pytest.raises(ValidationError):
        Span(block_id="body:3", start=4, end=4, text="")
    with pytest.raises(ValidationError):
        Span(block_id="body:3", start=-1, end=1, text="ab")


def test_image_is_a_part_a_content_hash_and_a_size():
    image = Image(part="word/media/image1.png", sha256="ab" * 32, size=1234)
    assert image.part == "word/media/image1.png"
    assert image.size == 1234


def test_removal_takes_a_span_or_an_image():
    span = Span(block_id="body:1", start=0, end=3, text="abc")
    image = Image(part="word/media/image1.png", sha256="ab" * 32, size=1)
    assert Removal(rule=RemovalRule.EMAIL, subject=span).subject == span
    assert Removal(rule=RemovalRule.PHOTO, subject=image).subject == image
    assert Removal(rule="RM_PHONE", subject=span).rule is RemovalRule.PHONE


def test_normalisation_names_the_rule_the_block_and_the_characters_stripped():
    event = Normalisation(
        rule=NormalisationRule.INVISIBLE, block_id="body:4", characters=["\u00ad"]
    )
    assert event.rule == "NORM_INVISIBLE"
    assert event.characters == ["\u00ad"]
    with pytest.raises(ValidationError):
        Normalisation(rule="NORM_CASE", block_id="body:4", characters=[])
