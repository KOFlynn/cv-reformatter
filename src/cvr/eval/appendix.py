"""How much of the candidate's content ended up in the review appendix."""

from collections.abc import Iterable

__all__ = ["appendix_rate"]


def appendix_rate(
    appendix_tokens: Iterable[str], source_content_tokens: Iterable[str]
) -> float:
    """Appendix tokens over source content tokens.

    Source content tokens are the source minus rule-removed tokens, so the rate
    does not move with how much contact detail a layout happens to carry.
    No content and no appendix is ``0.0``; an appendix with no content to come
    from is ``1.0`` (every appendix token is unaccounted for, and
    ``added_tokens`` says where it came from) rather than a division error.
    """
    appendix = sum(1 for _ in appendix_tokens)
    content = sum(1 for _ in source_content_tokens)
    if content == 0:
        return 0.0 if appendix == 0 else 1.0
    return appendix / content
