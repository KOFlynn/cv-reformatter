"""The image leak gate: a photo is not text, so no token metric can see it."""

from collections import Counter
from collections.abc import Iterable

from cvr.eval.finding import Finding

__all__ = ["image_leak"]


def image_leak(
    output_image_hashes: Iterable[str], template_image_hashes: Iterable[str]
) -> list[Finding]:
    """Every output image whose content hash is not one of the template's own.

    Membership, not multiplicity: the template's logo repeated in every
    section header is still the template's image. A foreign hash is one
    finding with its count; the hash is whatever digest the caller took of
    the image bytes, compared as an opaque string.
    """
    template = set(template_image_hashes)
    foreign = Counter(h for h in output_image_hashes if h not in template)
    return sorted(
        Finding(what=digest, count=count, where="output")
        for digest, count in foreign.items()
    )
