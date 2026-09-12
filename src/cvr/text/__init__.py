"""Text canonicalisation shared by every metric and Layout. Standard library only."""

import unicodedata
from types import MappingProxyType

__all__ = ["CONFUSABLES", "canonicalise", "tokenise"]

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

_TRANSLATION = str.maketrans(dict(CONFUSABLES))


def canonicalise(text: str) -> str:
    """NFC, then the confusable table, then whitespace collapse and trim.

    NFC rather than NFKC: NFKC would also rewrite characters that must stay
    (fractions, trademark). Case and spelling are never touched.
    """
    composed = unicodedata.normalize("NFC", text)
    mapped = composed.translate(_TRANSLATION)
    return " ".join(mapped.split())


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
