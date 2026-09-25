"""``python -m cvr.api``: serve the API with uvicorn.

Environment variables (both optional):

==================  ================================================
``CVR_API_HOST``    interface to bind (default ``127.0.0.1``; a
                    container sets ``0.0.0.0``)
``CVR_API_PORT``    port to listen on (default ``8000``)
==================  ================================================

The labeller reads its own ``CVR_LABEL_*`` variables and
``ANTHROPIC_API_KEY`` (``cvr.label.config``), on the first document.
"""

import os
from collections.abc import Mapping

import uvicorn

from cvr.api import create_app

__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "ENV_HOST", "ENV_PORT", "address", "main"]

ENV_HOST = "CVR_API_HOST"
ENV_PORT = "CVR_API_PORT"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def address(env: Mapping[str, str] | None = None) -> tuple[str, int]:
    """The host and port to serve on, from the environment or the defaults."""
    source: Mapping[str, str] = os.environ if env is None else env
    return (
        source.get(ENV_HOST) or DEFAULT_HOST,
        int(source.get(ENV_PORT) or DEFAULT_PORT),
    )


def main() -> None:
    host, port = address()
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
