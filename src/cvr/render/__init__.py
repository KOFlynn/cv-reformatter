"""The render node.

``render`` fills the committed template from transform's
``TransformedContent`` and the Run's unplaced Spans (``render.render``). Its
inverse, the adapter, lives in ``cvr.eval.adapter``: only the eval reads a
rendered document back, and ``eval`` stays out of the runtime image.

Depends on ``cvr.models`` and ``cvr.template``; never on another node or on
``eval``.
"""

from cvr.render.render import render

__all__ = ["render"]
