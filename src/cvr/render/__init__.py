"""The render node and its inverse.

``render`` fills the committed template from transform's
``TransformedContent`` and the Run's unplaced Spans (``render.render``).
``adapt`` walks a rendered document back to leaves by field type, the
adapter the eval metrics are fed from real output through
(``render.adapter``): the template's own headings and paragraph styles, and
the same composite-line conventions in reverse.

Depends on ``cvr.models``, ``cvr.template`` and ``cvr.transform``; never on
``verify``, ``parse``, ``label`` or ``eval``.
"""

from cvr.render.adapter import Adapted, adapt
from cvr.render.render import render

__all__ = ["Adapted", "adapt", "render"]
