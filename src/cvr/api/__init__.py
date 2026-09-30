"""The API: the service a caller, a browser and Phase 3's MCP server all use.

``create_app(labeller=None)`` builds the FastAPI application with two
routes, ``POST /reformat`` (a ``.docx`` in, the reformatted ``.docx`` out,
``X-Run-Id`` on every response) and ``GET /health``; ``python -m cvr.api``
serves it with uvicorn. It calls the pipeline function and adds nothing to
the document. The transform log goes to standard output (``cvr.api.log``);
no endpoint returns a run, a log or a list of anything (ADR-0004, ADR-0009).
"""

from cvr.api.app import DOCX_MEDIA_TYPE, RUN_ID_HEADER, create_app

__all__ = ["DOCX_MEDIA_TYPE", "RUN_ID_HEADER", "create_app"]
