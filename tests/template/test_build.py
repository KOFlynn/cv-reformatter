"""The template is built by a script and committed; the two must agree.

Observed only through the dumb ``all_text`` walker: the builder is free to
change how it lays runs out as long as the words and tags come out the same.
"""

import zipfile
from io import BytesIO

from docx_text import all_text

from cvr.template import TEMPLATE_PATH
from cvr.template.build import build_template


def _saved_text(document) -> list[str]:
    buffer = BytesIO()
    document.save(buffer)
    return all_text(buffer.getvalue())


def test_building_twice_yields_identical_text_and_tags():
    assert _saved_text(build_template()) == _saved_text(build_template())


def test_the_committed_template_matches_a_fresh_build():
    # The rule from ADR-0006: never hand-edit the output. A committed file
    # that drifts from the script fails here until it is regenerated.
    assert all_text(TEMPLATE_PATH) == _saved_text(build_template())


def test_the_template_carries_no_images():
    # Branding is text only (ADR-0006), so image_leak's template set is empty.
    with zipfile.ZipFile(TEMPLATE_PATH) as package:
        assert not [n for n in package.namelist() if n.startswith("word/media/")]
