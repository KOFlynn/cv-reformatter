"""The two backstops: patterns for the PII values the LLM might miss, and the
vocabulary of source headings. Both only ever remove; neither places.

Patterns run over canonical text (the verifier maps the matches back to raw
offsets), so a phone number set in no-break spaces matches the same as one
in ordinary spaces. The phone pattern is deliberately shaped around what a
CV prints beside a phone: digits in groups joined by single spaces, dots or
dashes, nine to fifteen of them in all, so a year range (``2019-2022``,
eight digits) and a date range (``2020-01 - 2021-06``, whose groups are
joined by a spaced dash) are never taken for one.

The heading vocabulary is whole-block, case-folded, trailing colon stripped,
``&`` read as ``and``. It is narrow on purpose: a false removal is silent,
a false appendix entry is loud, so a word the vocabulary does not hold goes
to the appendix where a reviewer sees it.
"""

import re

from cvr.models import RemovalRule

__all__ = ["HEADING_VOCABULARY", "heading_key", "pii_matches"]

_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
# A scheme or ``www.``, then anything that is not whitespace or a closing
# bracket; trailing sentence punctuation is given back afterwards.
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+")
_URL_TRAILING = ".,;:!?"
# An optional ``+``, then digit groups; a group may sit in brackets; groups
# are joined by one space, dot or dash. Digit count is checked afterwards.
_PHONE = re.compile(r"(?<![\w+.-])\+?\(?\d+\)?(?:[ .-]\(?\d+\)?)*(?![\w.-])")
_PHONE_DIGITS = range(9, 16)

type Match = tuple[RemovalRule, int, int]


def pii_matches(text: str) -> list[Match]:
    """Every email, phone and URL in ``text`` as ``(rule, start, end)``, in
    the order email, phone, URL and then by position. A span matched by an
    earlier rule is not offered to a later one."""
    matches: list[Match] = []
    for match in _EMAIL.finditer(text):
        matches.append((RemovalRule.EMAIL, match.start(), match.end()))
    for match in _PHONE.finditer(text):
        if sum(char.isdigit() for char in match.group()) in _PHONE_DIGITS:
            matches.append((RemovalRule.PHONE, match.start(), match.end()))
    for match in _URL.finditer(text):
        end = match.end()
        while end > match.start() and text[end - 1] in _URL_TRAILING:
            end -= 1
        matches.append((RemovalRule.URL, match.start(), end))
    taken: list[tuple[int, int]] = []
    kept: list[Match] = []
    for rule, start, end in matches:
        if any(start < t_end and t_start < end for t_start, t_end in taken):
            continue
        taken.append((start, end))
        kept.append((rule, start, end))
    return kept


def heading_key(text: str) -> str:
    """The form a block's text is looked up in the vocabulary by."""
    key = " ".join(text.replace("&", " and ").split()).casefold()
    return key.rstrip(" :")


# The four Layouts' headings, common synonyms, and document titles. Held as
# keys so the lookup and the listing cannot disagree.
HEADING_VOCABULARY = frozenset(
    heading_key(heading)
    for heading in (
        # document titles
        "Curriculum Vitae",
        "CV",
        "Resume",
        "R\u00e9sum\u00e9",
        # single-column
        "Profile",
        "Key Skills",
        "Education",
        "Experience",
        "Certifications",
        "Additional Information",
        "References",
        # two-column
        "Contact",
        "Academic Background",
        "Referees",
        "Summary",
        "Skills",
        "Work History",
        "Other Information",
        # text-box
        "About Me",
        "Core Competencies",
        "Professional Experience",
        "Education and Training",
        # header-footer
        "Personal Statement",
        "Technical Skills",
        "Employment",
        "Further Information",
        "Qualifications",
        # common synonyms, by template section
        "Personal Profile",
        "Professional Profile",
        "Professional Summary",
        "Career Summary",
        "Career Profile",
        "Objective",
        "Career Objective",
        "Skills and Competencies",
        "Key Competencies",
        "Competencies",
        "Technical Competencies",
        "Areas of Expertise",
        "Skills Summary",
        "Education and Qualifications",
        "Academic Qualifications",
        "Academic History",
        "Training",
        "Work Experience",
        "Employment History",
        "Career History",
        "Professional Background",
        "Relevant Experience",
        "Certifications and Training",
        "Professional Certifications",
        "Professional Development",
        "Courses",
        "Additional Info",
        "Personal Details",
        "Personal Information",
        "Contact Details",
        "Contact Information",
    )
)
