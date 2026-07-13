"""Public, stateless HTTP API for md2docx."""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from md2docx import convert_markdown

LOGGER = logging.getLogger("md2docx.api")
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", "262144"))
MAX_MARKDOWN_CHARS = int(os.getenv("MAX_MARKDOWN_CHARS", "200000"))
MAX_CONCURRENT_CONVERSIONS = int(os.getenv("MAX_CONCURRENT_CONVERSIONS", "4"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
CONVERSION_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_CONVERSIONS)


class BurstLimiter:
    """In-memory abuse guard for a public, stateless endpoint.

    It retains an IP only for the rolling one-minute window. Deployments that
    need multi-instance protection should put a reverse-proxy rate limit ahead
    of this application.
    """
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, identity: str) -> bool:
        now = time.monotonic()
        hits = self._hits[identity]
        while hits and hits[0] <= now - 60:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_PER_MINUTE:
            return False
        hits.append(now)
        return True


BURST_LIMITER = BurstLimiter()


def _origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="md2docx API",
    description="Stateless Markdown to native Word DOCX conversion.",
    version=os.getenv("RELEASE_VERSION", "1.0.0"),
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
    expose_headers=["X-Request-Id"],
    allow_credentials=False,
)


class ConvertRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=MAX_MARKDOWN_CHARS)
    font: str = Field("Arial", min_length=1, max_length=80)
    base_font: str = Field("Times New Roman", min_length=1, max_length=80)


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@app.middleware("http")
async def protect_request(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            return JSONResponse({"detail": "Invalid Content-Length header."}, status_code=400)
        if declared_size > MAX_REQUEST_BYTES:
            return JSONResponse({"detail": "Request body is too large."}, status_code=413)
    if request.method == "POST":
        body = await request.body()
        if len(body) > MAX_REQUEST_BYTES:
            return JSONResponse({"detail": "Request body is too large."}, status_code=413)
        if not BURST_LIMITER.allow(_client_ip(request)):
            return JSONResponse({"detail": "Too many requests. Try again shortly."}, status_code=429)
    try:
        response = await call_next(request)
    except Exception:
        LOGGER.exception("Unhandled error request_id=%s path=%s", request_id, request.url.path)
        return JSONResponse({"detail": "Internal server error."}, status_code=500)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": "md2docx-api", "version": app.version}


@app.post("/convert")
async def convert(req: ConvertRequest):
    docx_bytes = await _convert_to_docx_bytes(req)
    return Response(
        content=docx_bytes,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": 'attachment; filename="result.docx"'},
    )


@app.post("/convert/base64")
async def convert_base64(req: ConvertRequest):
    docx_bytes = await _convert_to_docx_bytes(req)
    return {
        "filename": "result.docx",
        "mime_type": DOCX_MIME,
        "docx_base64": base64.b64encode(docx_bytes).decode("ascii"),
    }


def _client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if os.getenv("TRUST_PROXY_HEADERS", "false").lower() not in {"1", "true", "yes", "on"}:
        return direct_ip
    trusted = {ip.strip() for ip in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if ip.strip()}
    if direct_ip not in trusted:
        return direct_ip
    return (request.headers.get("x-forwarded-for") or direct_ip).split(",")[0].strip()


async def _convert_to_docx_bytes(req: ConvertRequest) -> bytes:
    try:
        async with CONVERSION_SEMAPHORE:
            return await asyncio.to_thread(convert_markdown, req.markdown, req.font, req.base_font)
    except Exception:
        LOGGER.exception("Conversion failed")
        raise HTTPException(status_code=422, detail="Markdown conversion failed.")
