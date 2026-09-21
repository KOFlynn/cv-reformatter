"""Every embedded image, by content hash, whatever part refers to it.

Word stores every picture in the package as its own part under
``word/media/``, whether it is drawn in the body, a table cell, a header, a
footer or a text box, and however many places refer to it. Walking the
package rather than the references is what makes "every image in every part"
one rule with nothing to forget; the ``image_count`` helper the golden tests
observe through counts the same way.
"""

import hashlib
import io
import zipfile

from cvr.models import Image

__all__ = ["collect"]

_MEDIA = "word/media/"


def collect(data: bytes) -> list[Image]:
    """One ``Image`` per media part, in part-name order."""
    images: list[Image] = []
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        for name in sorted(package.namelist()):
            if not name.startswith(_MEDIA):
                continue
            content = package.read(name)
            images.append(
                Image(
                    part=name,
                    sha256=hashlib.sha256(content).hexdigest(),
                    size=len(content),
                )
            )
    return images
