"""The PII leak gate: fixture PII values, and their variants, found in the output.

A leaked email is correctly copied source text, so neither the multisets nor
provenance can see it (ADR-0007). This metric searches the output text for
every PII value in the forms it is likely to be re-emitted in, and reports
each occurrence once under the rule that should have removed it.
"""

import re
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

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


def _url(value: str) -> str:
    """The URL with or without scheme, `www.` and a trailing slash: the
    stripped core is what must not appear, and whatever dressing surrounds
    it is reported with it."""
    core = re.sub(r"^(?:https?://)?(?:www\.)?", "", canonicalise(value)).rstrip("/")
    return rf"(?<!\w)(?:https?://)?(?:www\.)?{re.escape(core)}(?!\w)/?"


def _address_line(value: str) -> str:
    # Whitespace collapsed, and optional altogether so a postcode or Eircode
    # printed without its space (`T12AB34`, `D06X0X0`) is the same line.
    words = canonicalise(value).split()
    return _bounded(r"\s*".join(re.escape(word) for word in words))


# How a date of birth is written in a fixture, and how it may be re-emitted.
_DOB_FORMATS = ("%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%B %d, %Y")


def _dob(value: str) -> str:
    """As written, and if the date parses, in ISO and `DD/MM/YYYY` too, plus the
    long and short month-name forms with the day padded or not."""
    written = canonicalise(value)
    forms = {written}
    for fmt in _DOB_FORMATS:
        try:
            born = date(*time.strptime(written, fmt)[:3])
        except ValueError:
            continue
        forms.update(born.strftime(f) for f in ("%Y-%m-%d", "%d/%m/%Y"))
        for month in (born.strftime("%B"), born.strftime("%b")):
            forms.update(
                {f"{born.day} {month} {born.year}", f"{born:%d} {month} {born.year}"}
            )
        break
    return _bounded("|".join(re.escape(form) for form in sorted(forms)))


def _word(value: str) -> str:
    # A plain word, as written and in its own case: `Single` the marital
    # status is not `Single-handedly` the bullet, so a hyphen bounds it too.
    return rf"(?<![\w-]){re.escape(canonicalise(value))}(?![\w-])"


_EMAIL_IN_LINE = re.compile(r"[^\s@]+@[^\s@]+")
_DIGITS = re.compile(r"\d")


def _contact_line(value: str) -> tuple[str, int]:
    """A referee's contact line matched by what it is: the email in it with
    the email variants, the number in it with the phone variants, anything
    else as written."""
    if email := _EMAIL_IN_LINE.search(value):
        return _email(email.group().rstrip(".,;")), re.IGNORECASE
    if len(_DIGITS.findall(value)) >= 6:
        # Drop a `Tel:` label but keep a leading `+`, which names the form.
        return _phone(re.sub(r"^[^\d+]*", "", value)), 0
    return _word(value), 0


def _matchers(pii: PII) -> list[_Matcher]:
    def add(rule: RemovalRule, pattern: str, flags: int = 0) -> None:
        matchers.append(_Matcher(rule, re.compile(pattern, flags)))

    matchers: list[_Matcher] = []
    if pii.phone:
        add(RemovalRule.PHONE, _phone(pii.phone))
    if pii.email:
        add(RemovalRule.EMAIL, _email(pii.email), re.IGNORECASE)
    for line in pii.address:
        add(RemovalRule.ADDRESS, _address_line(line), re.IGNORECASE)
    for url in pii.urls:
        add(RemovalRule.URL, _url(url), re.IGNORECASE)
    if pii.dob:
        add(RemovalRule.DOB, _dob(pii.dob), re.IGNORECASE)
    for detail in (pii.personal.nationality, pii.personal.marital_status):
        if detail:
            add(RemovalRule.PERSONAL, _word(detail))
    for referee in pii.referees:
        for detail in (referee.name, referee.role):
            if detail:
                add(RemovalRule.REFEREE, _word(detail))
        for line in referee.contact:
            add(RemovalRule.REFEREE, *_contact_line(line))
    return matchers


# Most specific first: an occurrence matched under two rules is reported once,
# under the earliest of these. A referee's phone or email is the referee's.
_PRECEDENCE = {
    rule: rank
    for rank, rule in enumerate(
        (
            RemovalRule.REFEREE,
            RemovalRule.EMAIL,
            RemovalRule.URL,
            RemovalRule.PHONE,
            RemovalRule.DOB,
            RemovalRule.ADDRESS,
            RemovalRule.PERSONAL,
        )
    )
}


def _hits_in(where: str, text: str, matchers: Iterable[_Matcher]) -> list[PiiHit]:
    canonical = canonicalise(text)
    matches = sorted(
        (
            (
                _PRECEDENCE[matcher.rule],
                match.start(),
                -match.end(),
                matcher.rule,
                match,
            )
            for matcher in matchers
            for match in matcher.pattern.finditer(canonical)
        ),
        key=lambda item: item[:3],
    )
    taken: list[tuple[int, int]] = []
    hits: list[PiiHit] = []
    for _, start, _, rule, match in matches:
        if any(start < end and match.end() > begin for begin, end in taken):
            continue  # already reported under a more specific rule
        taken.append((start, match.end()))
        hits.append(PiiHit(where=where, rule=rule, what=match.group()))
    return hits


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
