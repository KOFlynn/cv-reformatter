"""Text canonicalisation shared by every metric and Layout. Standard library only."""

import string
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from types import MappingProxyType

__all__ = [
    "CONFUSABLES",
    "SEPARATORS",
    "Canonical",
    "canonicalise",
    "canonicalise_with_offsets",
    "is_separator_residue",
    "tokenise",
]

# Character -> replacement. Layouts inject traps from this same table so the
# traps and the canonicaliser cannot disagree.
CONFUSABLES = MappingProxyType(
    {
        # single quotes and single guillemets
        "\u2018": "'",  # left single quotation mark
        "\u2019": "'",  # right single quotation mark
        "\u201a": "'",  # single low-9 quotation mark
        "\u201b": "'",  # single high-reversed-9 quotation mark
        "\u2039": "'",  # single left-pointing angle quotation mark
        "\u203a": "'",  # single right-pointing angle quotation mark
        # double quotes and double guillemets
        "\u201c": '"',  # left double quotation mark
        "\u201d": '"',  # right double quotation mark
        "\u201e": '"',  # double low-9 quotation mark
        "\u201f": '"',  # double high-reversed-9 quotation mark
        "\u00ab": '"',  # left-pointing double angle quotation mark
        "\u00bb": '"',  # right-pointing double angle quotation mark
        # dashes
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2012": "-",  # figure dash
        "\u2011": "-",  # non-breaking hyphen
        "\u2212": "-",  # minus sign
        # ellipsis
        "\u2026": "...",  # horizontal ellipsis
        # exotic spaces
        "\u00a0": " ",  # no-break space
        "\u202f": " ",  # narrow no-break space
        "\u2009": " ",  # thin space
        "\u200a": " ",  # hair space
        "\u3000": " ",  # ideographic space
        # invisibles
        "\u200b": "",  # zero width space
        "\u200c": "",  # zero width non-joiner
        "\u200d": "",  # zero width joiner
        "\u00ad": "",  # soft hyphen
        "\ufeff": "",  # byte order mark
        "\u2060": "",  # word joiner
    }
)

_CONFUSABLE_TRANSLATION = str.maketrans(dict(CONFUSABLES))

# The replacement classes of the table whose members are separators: the
# invisibles (mapped to nothing) are not, they are deleted before residue
# is ever looked at.
_SEPARATOR_REPLACEMENTS = frozenset({"'", '"', "-", " "})

# Characters that carry no content on their own. A run of residue made only
# of these is separator residue, not unplaced text. The quote marks, dashes
# and exotic spaces are the table's own, read from it so the two cannot
# disagree; the rest of Unicode's whitespace is `str.isspace`'s business in
# `is_separator_residue`. `&` is deliberately absent: it is a word in "M&S"
# and in "Research & Development", so `&` standing alone is unplaced text.
SEPARATORS = frozenset(
    string.whitespace
    + ",;:|/\\()[]."
    + "-"
    + "\u2022\u00b7\u25e6\u25aa\u2023\u25cb\u25a0"  # bullet glyphs
    + "\uf0b7\uf0a7\uf0d8\uf0fc\uf076"  # Symbol-font Private-Use-Area bullets
    + "'\""
    + "".join(
        char
        for char, mapped in CONFUSABLES.items()
        if mapped in _SEPARATOR_REPLACEMENTS
    )
)


def canonicalise(text: str) -> str:
    """NFC, then the confusable table, then whitespace collapse and trim.

    NFC rather than NFKC: NFKC would also rewrite characters that must stay
    (fractions, trademark). Case and spelling are never touched.
    """
    composed = unicodedata.normalize("NFC", text)
    mapped = composed.translate(_CONFUSABLE_TRANSLATION)
    return " ".join(mapped.split())


@dataclass(frozen=True, slots=True)
class Canonical:
    """`canonicalise(raw)` together with the canonical-to-raw offset map.

    `offsets[i]` is the raw index where the source of canonical character
    `i` begins and `ends[i]` the raw index just past it. Both are needed:
    a composed letter, an ellipsis or a collapsed run of whitespace is one
    canonical character from several raw ones, so the end of a slice cannot
    be found from a start alone.
    """

    raw: str
    text: str
    offsets: tuple[int, ...]
    ends: tuple[int, ...]

    def raw_slice(self, start: int, end: int) -> str:
        """The raw text behind canonical `[start, end)`.

        A contiguous raw range, so deleted invisibles and collapsed whitespace
        inside it come back too.
        """
        if start >= end:
            return ""
        return self.raw[self.offsets[start] : self.ends[end - 1]]


def canonicalise_with_offsets(text: str) -> Canonical:
    """`canonicalise`, keeping the map from canonical to raw index as it goes.

    The map is built during canonicalisation, never reconstructed after it:
    NFC composes each base-plus-marks sequence onto the base's raw index,
    the table substitutes one-to-one, one-to-many (ellipsis) or one-to-zero
    (invisibles), and a run of whitespace collapses onto its first raw
    character. Same string as `canonicalise`, asserted over the golden set.
    """
    chars: list[str] = []
    offsets: list[int] = []
    ends: list[int] = []
    pending: tuple[int, int] | None = None  # raw range of whitespace not yet emitted
    for start, end, composed in _composed_sequences(text):
        for char in composed.translate(_CONFUSABLE_TRANSLATION):
            if char.isspace():
                pending = (pending[0], end) if pending else (start, end)
            else:
                if pending and chars:
                    chars.append(" ")
                    offsets.append(pending[0])
                    ends.append(pending[1])
                pending = None
                chars.append(char)
                offsets.append(start)
                ends.append(end)
    return Canonical(
        raw=text, text="".join(chars), offsets=tuple(offsets), ends=tuple(ends)
    )


def _composed_sequences(text: str) -> Iterator[tuple[int, int, str]]:
    """Cut `text` into the smallest pieces NFC composes independently and
    compose each: `(raw start, raw end, composed)`.

    A cut is tried at every starter (a character with combining class
    zero) and kept only where composing the two sides apart gives what
    composing them together gives, so a base and its marks stay in one
    piece and so do the rare starters that compose with each other (Hangul
    jamo, some Indic two-part vowel signs). The pieces therefore compose to
    the string `canonicalise` gives.
    """
    cuts = [
        i for i, char in enumerate(text) if i > 0 and unicodedata.combining(char) == 0
    ]
    cuts.append(len(text))
    start = 0
    for cut, after in zip(cuts, [*cuts[1:], None]):
        if after is not None:
            apart = _nfc(text[start:cut]) + _nfc(text[cut:after])
            if apart != _nfc(text[start:after]):
                continue  # the two sides compose with each other: no cut here
        if cut > start:
            yield start, cut, _nfc(text[start:cut])
        start = cut


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def is_separator_residue(text: str) -> bool:
    """Every character of `text` is a separator, so it is residue but not
    unplaced text.

    Whitespace is whatever `str.isspace` says, the same notion `canonicalise`
    collapses, so an en space counts as it would there. Empty text is
    trivially separator residue.
    """
    return all(char.isspace() or char in SEPARATORS for char in text)


def _is_punctuation(char: str) -> bool:
    # Unicode punctuation only (categories P*), not symbols: `+` in `C++`,
    # currency signs and the trademark sign survive on a token edge.
    return unicodedata.category(char).startswith("P")


def _strip_edges(token: str) -> str:
    start = 0
    end = len(token)
    while start < end and _is_punctuation(token[start]):
        start += 1
    while end > start and _is_punctuation(token[end - 1]):
        end -= 1
    return token[start:end]


def tokenise(text: str) -> list[str]:
    """Canonicalise, split on whitespace, strip punctuation from token edges
    only, drop empties.

    Interior punctuation is kept, so `C++`, `O'Flynn`, `node.js` and
    `2019-2022` survive intact. A lone bullet glyph strips to nothing and
    disappears; there is no separate glyph rule.
    """
    tokens = (_strip_edges(token) for token in canonicalise(text).split())
    return [token for token in tokens if token]
