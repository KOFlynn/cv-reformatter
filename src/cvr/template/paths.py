"""Where the built template lives. A leaf module so the builder, the filler
and the token extractor can share it without importing each other."""

from pathlib import Path

__all__ = ["TEMPLATE_PATH"]

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3] / "templates" / "fictitious_recruitment.docx"
)
