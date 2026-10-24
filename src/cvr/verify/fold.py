"""``fold``: the first answer with a retry's placed additions written into
it, so the next retry is shown the tree the verifier has, not only the one the
model first gave. Pure; depends on ``models`` and the path grammar of
``verify`` only.

Why: a retry's paths address the verified tree (a list to append to, a leaf to
fill, the next entry index to open a new entry). Shown only the first answer, a
second retry would believe the next free experience entry is still
``len(first.experience)`` after a first retry opened it, and its addition
would be merged into that entry. Folding the placed additions of every earlier
retry in puts the entries a retry opened in the prompt, at the indices verify
will use.

Only additions that verify placed are folded (``VerifiedDocument.placed``): a
rejected one placed nothing, and an entry whose only additions were rejected is
dropped by verify, so folding it would show an entry that does not exist.
``verify`` itself still runs over the unfolded first answer plus every
addition, in order, so the first answer wins every conflict.

Edge: a first-answer leaf that verify rejected is empty to verify but filled in
the first answer's tree; a placed addition into it replaces the rejected
reference in the fold (the reference placed nothing). Paths of the first
answer, which hints use, are unchanged by folding, which only appends and
fills.
"""

from collections.abc import Iterable

from cvr.models import (
    Addition,
    EducationReference,
    ExperienceReference,
    Labelling,
    Reference,
)
from cvr.verify import _ENTRY_LEAVES, _ENTRY_LISTS, _ENTRY_PATH, _TOP_LEAF, _TOP_LISTS

__all__ = ["fold"]


def fold(base: Labelling, additions: Iterable[Addition]) -> Labelling:
    """``base`` with each addition written where its path says, in order. A
    path that addresses nothing (which a placed addition never does) is
    skipped. ``base`` is not modified."""
    content = base.content.model_copy(deep=True)
    for addition in additions:
        reference: Reference = addition.reference
        path = addition.path
        if path == _TOP_LEAF:
            content.name = reference
        elif path in _TOP_LISTS:
            getattr(content, path).append(reference)
        elif (match := _ENTRY_PATH.fullmatch(path)) is not None:
            kind, digits, field = match.groups()
            index = int(digits)
            entries = getattr(content, kind)
            if index > len(entries) or (
                field != _ENTRY_LISTS[kind] and field not in _ENTRY_LEAVES[kind]
            ):
                continue
            if index == len(entries):
                entries.append(_new_entry(kind))
            entry = entries[index]
            if field == _ENTRY_LISTS[kind]:
                getattr(entry, field).append(reference)
            else:
                setattr(entry, field, reference)
    return base.model_copy(update={"content": content})


def _new_entry(kind: str) -> ExperienceReference | EducationReference:
    if kind == "experience":
        return ExperienceReference(
            title=None, employer=None, location=None, dates=None, bullets=[]
        )
    return EducationReference(
        institution=None, qualification=None, dates=None, details=[]
    )
