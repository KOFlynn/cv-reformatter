"""The FastAPI application: ``POST /reformat`` and ``GET /health``, nothing
else.

Every response carries ``X-Run-Id``, issued by middleware before the
request is read, so a refused upload or a failed run is as traceable as a
success; an accepted upload's Run is given the same id. Every
``/reformat`` request writes its transform log to standard output
(``cvr.api.log``); ``/health`` writes nothing, since the probe calls it
every few seconds.

``/reformat`` is for callers holding the shared key: the ``X-API-Key``
header must equal ``CVR_API_KEY`` (compared in constant time), or the
request is a 401. The service fails closed: with ``CVR_API_KEY`` unset or
empty, every ``/reformat`` is a 503. The upload must state its length and
stay under ``MAX_UPLOAD_BYTES``, or it is a 411 or a 413. All three are
decided in middleware, from the headers alone, before the body is read and
before a labeller is built or called; neither key is ever logged.
``/health`` needs no key, for the platform's probes.

The labeller is injected for tests. Without one, the real labeller is
built from ``LabellerConfig`` once per process, on the first document
rather than at import or startup, so ``/health`` never constructs it,
never needs a key, and a missing key shows as a 500 on ``/reformat``
rather than a replica that will not start.
"""

import hmac
import logging
import os
import threading
import zipfile
from io import BytesIO
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from cvr.api.log import request_lines, write_lines
from cvr.label import (
    LabellerConfig,
    LabellerMisconfigured,
    ProviderUnavailable,
    RealLabeller,
)
from cvr.models import LabelRun
from cvr.pipeline import Labeller, reformat

__all__ = [
    "API_KEY_HEADER",
    "DOCX_MEDIA_TYPE",
    "ENV_API_KEY",
    "MAX_UPLOAD_BYTES",
    "RUN_ID_HEADER",
    "content_disposition",
    "create_app",
    "output_filename",
]

RUN_ID_HEADER = "X-Run-Id"
API_KEY_HEADER = "X-API-Key"
ENV_API_KEY = "CVR_API_KEY"
# The whole request body, multipart framing included. A golden-set document
# is about 40 KB; a CV with photos is a few hundred.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
logger = logging.getLogger(__name__)


def output_filename(upload_name: str | None) -> str:
    """``<stem>-reformatted.docx`` from the uploaded file's name, with any
    directory a client sent stripped and ``.docx`` matched in any case."""
    name = (upload_name or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem = name[: -len(".docx")] if name.lower().endswith(".docx") else name
    return f"{stem}-reformatted.docx"


def content_disposition(filename: str) -> str:
    """An attachment header for ``filename``: printable ASCII in
    ``filename`` (anything else, and quote marks and backslashes, as ``_``),
    and the exact name in ``filename*`` whenever that changed it."""
    safe = "".join(c if " " <= c <= "~" and c not in '"\\' else "_" for c in filename)
    header = f'attachment; filename="{safe}"'
    if safe != filename:
        header += f"; filename*=UTF-8''{quote(filename)}"
    return header


def _is_docx(filename: str | None, body: bytes) -> bool:
    """A ``.docx`` name on a zip archive; anything else is refused before the
    pipeline sees it (ADR-0003: ``.docx`` only)."""
    return (filename or "").lower().endswith(".docx") and zipfile.is_zipfile(
        BytesIO(body)
    )


def _describe(exc: Exception) -> str:
    """An exception as the summary line's ``error``."""
    return f"{type(exc).__name__}: {exc}"


def _last_run(labeller: Labeller) -> LabelRun | None:
    """The labeller's record of its last call, when it keeps one (as
    ``RealLabeller`` does, resetting it at the start of each call)."""
    last_run = getattr(labeller, "last_run", None)
    return last_run if isinstance(last_run, LabelRun) else None


def _refusal(request: Request, expected_key: str) -> tuple[int, str, str] | None:
    """Why a ``/reformat`` request is refused from its headers alone, as
    (status, detail for the caller, error for the log), or None to let it
    through. The key is checked first, so a caller without it learns
    nothing about the size rule."""
    if not expected_key:
        return (
            503,
            "the service is not configured",
            f"{ENV_API_KEY} is not set; /reformat is closed",
        )
    sent = request.headers.get(API_KEY_HEADER, "")
    if not hmac.compare_digest(sent.encode(), expected_key.encode()):
        return 401, f"a valid {API_KEY_HEADER} header is required", "bad API key"
    length = request.headers.get("content-length")
    if length is None or not length.isdigit():
        return 411, "Content-Length is required", "no Content-Length"
    if int(length) > MAX_UPLOAD_BYTES:
        return (
            413,
            f"uploads are limited to {MAX_UPLOAD_BYTES} bytes",
            f"upload of {length} bytes is over the cap",
        )
    return None


class _LabellerSource:
    """The labeller the app uses: the injected one, or the real one built
    from the environment on first use and kept for the process."""

    def __init__(self, labeller: Labeller | None) -> None:
        self._labeller = labeller
        self._lock = threading.Lock()

    def get(self) -> Labeller:
        with self._lock:
            if self._labeller is None:
                self._labeller = RealLabeller(LabellerConfig.from_env())
            return self._labeller


def create_app(labeller: Labeller | None = None) -> FastAPI:
    """The application, labelling with ``labeller`` or, when none is given,
    with the real labeller built from ``CVR_LABEL_*`` on the first document.
    The key ``/reformat`` expects is ``CVR_API_KEY`` as it is when the app is
    created. FastAPI's generated ``/docs``, ``/redoc`` and ``/openapi.json``
    are off: the service has two routes and no others."""
    app = FastAPI(
        title="cv-reformatter", docs_url=None, redoc_url=None, openapi_url=None
    )
    expected_key = os.environ.get(ENV_API_KEY, "")
    source = _LabellerSource(labeller)
    # One document at a time: the labeller records its LabelRun on itself
    # (``last_run``), so two interleaved calls would swap each other's.
    one_at_a_time = threading.Lock()

    @app.middleware("http")
    async def attach_run_id(request: Request, call_next):
        run_id = uuid4().hex
        request.state.run_id = run_id
        request.state.run = None
        request.state.error = None
        request.state.label = None
        refusal = (
            _refusal(request, expected_key) if request.url.path == "/reformat" else None
        )
        try:
            if refusal is not None:
                status, detail, request.state.error = refusal
                response = JSONResponse({"detail": detail}, status_code=status)
            else:
                response = await call_next(request)
        except Exception as exc:
            logger.exception("run %s failed", run_id)
            request.state.error = _describe(exc)
            response = JSONResponse(
                {"detail": "internal error", "run_id": run_id}, status_code=500
            )
        response.headers[RUN_ID_HEADER] = run_id
        if request.url.path == "/reformat":
            try:
                write_lines(
                    request_lines(
                        run_id,
                        response.status_code,
                        run=request.state.run,
                        label=request.state.label,
                        error=request.state.error,
                    )
                )
            except Exception:
                # The response, and its run id, still go back to the caller.
                logger.exception("run %s: the transform log was not written", run_id)
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness. Never touches the labeller."""
        return {"status": "ok"}

    @app.post("/reformat")
    def reformat_document(
        request: Request, file: Annotated[UploadFile, File()]
    ) -> Response:
        """The uploaded ``.docx`` reformatted into the template. A labelling
        failure is still a 200: the document, with every block under the
        review banner (ADR-0004)."""
        body = file.file.read()
        if not _is_docx(file.filename, body):
            request.state.error = "not a .docx"
            raise HTTPException(415, "upload a .docx file")
        try:
            labeller = source.get()
            with one_at_a_time:
                try:
                    output, run = reformat(body, labeller, run_id=request.state.run_id)
                except Exception:
                    # A node after the labeller failed, or the labeller did:
                    # whatever the labelling cost is still logged.
                    request.state.label = _last_run(labeller)
                    raise
        except ProviderUnavailable as exc:
            request.state.error = _describe(exc)
            raise HTTPException(
                503, "the labelling provider is unavailable; try again later"
            ) from exc
        except LabellerMisconfigured as exc:
            request.state.error = _describe(exc)
            raise HTTPException(500, "the labeller is misconfigured") from exc
        request.state.run = run
        return Response(
            content=output,
            media_type=DOCX_MEDIA_TYPE,
            headers={
                "Content-Disposition": content_disposition(
                    output_filename(file.filename)
                )
            },
        )

    return app
