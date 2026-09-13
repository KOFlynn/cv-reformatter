"""The placeholder photo: generated in code, never read from a committed file,
and byte-identical on every call so the document SHA is stable."""

import io

from docx import Document
from docx.shared import Emu

from cvr.golden.layouts.photo import placeholder_photo

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_placeholder_photo_is_a_png():
    assert placeholder_photo().startswith(PNG_SIGNATURE)


def test_placeholder_photo_is_identical_on_every_call():
    assert placeholder_photo() == placeholder_photo()


def test_placeholder_photo_is_taller_than_wide_and_readable_by_python_docx():
    picture = Document().add_picture(io.BytesIO(placeholder_photo()))
    assert isinstance(picture.width, Emu)
    assert picture.height > picture.width
