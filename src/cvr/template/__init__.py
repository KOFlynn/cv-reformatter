"""The Fictitious Recruitment output template: built by script
(``python -m cvr.template.build``), filled by docxtpl, and its fixed text
extracted at run time for the eval metrics.

Depends on ``models`` and ``text`` only; never on ``eval`` or ``golden``.
"""

from cvr.template.fill import fill
from cvr.template.paths import TEMPLATE_PATH
from cvr.template.tokens import template_text, template_tokens

__all__ = ["TEMPLATE_PATH", "fill", "template_text", "template_tokens"]
