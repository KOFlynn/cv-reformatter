"""The PII leak gate: fixture PII values, and their variants, found in the output.

A leaked email is correctly copied source text, so neither the multisets nor
provenance can see it (ADR-0007). This metric searches the output text for
every PII value in the forms it is likely to be re-emitted in, and reports
each occurrence once under the rule that should have removed it.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cvr.models import PII, RemovalRule
from cvr.text import canonicalise

__all__ = ["PiiHit", "pii_leak"]


@dataclass(frozen=True, order=True, kw_only=True, slots=True)
class PiiHit:
    """One occurrence of a PII value in the output. Sorted by ``where``, then
    ``rule``, then ``what``, like ``Finding``; two occurrences of the same value
    in the same part are two equal hits, never one with a count.

    ``where`` is the part of the output the value appeared in (the key of the
    text mapping); ``what`` is the text as matched, canonicalised, so the
    reader sees the form it leaked in rather than the fixture value.
    """

    where: str
    rule: RemovalRule
    what: str


@dataclass(frozen=True)
class _Matcher:
    rule: RemovalRule
    pattern: re.Pattern[str]


def _bounded(pattern: str) -> str:
    # Not inside a longer word or number: `Dublin 6` is not in `Dublin 60`.
    return rf"(?<!\w){pattern}(?!\w)"


def _email(value: str) -> str:
    return _bounded(re.escape(canonicalise(value)))


# The golden set's locales. A number written with one of these codes also
# matches in its national form, and a number written nationally also matches
# behind any of them.
_COUNTRY_CODES = ("353", "44", "49", "91")
# What may sit between the digits of a printed phone number.
_SEP = r"[\s().-]*"


def _phone(value: str) -> str:
    """Digits-only matching: the number's digits in order, any separators
    between them, in international (`+353`, `00353`), national leading-zero
    and bare forms, and not inside a longer run of digits."""
    digits = re.sub(r"\D", "", value)
    written = value.strip()
    if written.startswith("00"):
        written, digits = f"+{written[2:]}", digits[2:]
    code = next((c for c in _COUNTRY_CODES if written.startswith(f"+{c}")), None)
    if code is not None:
        national = digits[len(code) :].lstrip("0")
        codes = code
    elif digits.startswith("0"):
        national = digits[1:]
        codes = "|".join(_COUNTRY_CODES)
    else:
        return rf"(?<![\d+])(?:\+|00)?{_SEP.join(digits)}(?!\d)"
    prefix = rf"(?:(?:\+|00)?(?:{codes}){_SEP}(?:\(0\){_SEP}|0{_SEP})?|0{_SEP})?"
    return rf"(?<![\d+]){prefix}{_SEP.join(national)}(?!\d)"


def _matchers(pii: PII) -> list[_Matcher]:
    matchers: list[_Matcher] = []
    if pii.phone:
        matchers.append(_Matcher(RemovalRule.PHONE, re.compile(_phone(pii.phone))))
    if pii.email:
        matchers.append(
            _Matcher(RemovalRule.EMAIL, re.compile(_email(pii.email), re.IGNORECASE))
        )
    return matchers


def _hits_in(where: str, text: str, matchers: Iterable[_Matcher]) -> list[PiiHit]:
    canonical = canonicalise(text)
    return [
        PiiHit(where=where, rule=matcher.rule, what=match.group())
        for matcher in matchers
        for match in matcher.pattern.finditer(canonical)
    ]


def pii_leak(output_text: Mapping[str, str], pii: PII) -> list[PiiHit]:
    """Every occurrence of a PII value, or a variant of one, in the output.

    ``output_text`` maps each part of the output document (body, header,
    footer) to its text; both sides are canonicalised before matching.
    """
    matchers = _matchers(pii)
    return sorted(
        hit
        for where, text in output_text.items()
        for hit in _hits_in(where, text, matchers)
    )
