"""The Fictitious Recruitment output template: built by script
(``python -m cvr.template.build``), filled by docxtpl, and its fixed text
extracted at run time for the eval metrics.

Depends on ``models`` and ``text`` only; never on ``eval`` or ``golden``.
"""

from cvr.template.paths import TEMPLATE_PATH

__all__ = ["TEMPLATE_PATH"]
