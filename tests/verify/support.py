"""Builders shared by the verify tests: a body block, a reference, and a
labelling with only the named fields set."""

from cvr.models import (
    ContentReferences,
    ExperienceReference,
    Labelling,
    Reference,
    RemovalLabel,
    SourceBlock,
)


def block(block_id: str, text: str) -> SourceBlock:
    return SourceBlock(id=block_id, text=text, kind="body")


def ref(block_id: str, quote: str) -> Reference:
    return Reference(block_id=block_id, quote=quote)


def labelling(removals: list[RemovalLabel] | None = None, **fields) -> Labelling:
    """A labelling with the given content fields set and the rest empty."""
    content = {
        "name": None,
        "profile": [],
        "skills": [],
        "education": [],
        "experience": [],
        "certifications": [],
        "additional": [],
    }
    content.update(fields)
    return Labelling(content=ContentReferences(**content), removals=removals or [])


def experience(**fields) -> ExperienceReference:
    entry = {
        "title": None,
        "employer": None,
        "location": None,
        "dates": None,
        "bullets": [],
    }
    entry.update(fields)
    return ExperienceReference(**entry)
