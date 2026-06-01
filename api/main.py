"""
api/main.py
===========
FastAPI service that wraps md2docx's convert_markdown() function.

Endpoints
---------
POST /convert         – Convert markdown text to .docx; enforces per-key quota.
POST /convert/base64  – Convert markdown text to base64 .docx payload.
GET  /quota           – Current quota usage.
GET  /health          – Liveness probe for Railway / uptime monitors.

Authentication
--------------
Clients pass an optional  X-Api-Key  header.
  • Omitted / "anonymous" → IP-based free tier (5 conversions / month).
  • Free account key      → 25 conversions / month.
  • Pro key               → unlimited.

Quota logic lives in quota.py (Supabase-backed).
"""

from __future__ import annotations

import sys
import os
import base64

# Make the repo root importable when running from inside api/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field

from md2docx import convert_markdown
from api.quota import QuotaService, QuotaExceeded, InvalidApiKey

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="md2docx API",
    description=(
        "Convert Markdown (with Hebrew RTL and LaTeX math) to native Word .docx. "
        "Free tier: 5 conversions/month. Pro: unlimited."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # extension and web UI use CORS
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

quota_service = QuotaService()

# ── Request / response models ─────────────────────────────────────────────────

class ConvertRequest(BaseModel):
    markdown: str = Field(..., description="Markdown source text to convert.")
    font: str = Field("Arial", description="Complex-script (Hebrew) font name.")
    base_font: str = Field("Times New Roman", description="Body and heading font name.")


DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Liveness probe — returns 200 + build info."""
    return {"status": "ok", "service": "md2docx-api", "version": "1.0.0"}


@app.post("/convert")
async def convert(
    req: ConvertRequest,
    request: Request,
    x_api_key: str = Header(default="anonymous"),
):
    """
    Convert Markdown to DOCX.

    Returns the binary .docx file with Content-Disposition: attachment.

    Quota enforcement:
      - anonymous / missing key → 5/month per IP
      - free account key        → 25/month
      - pro key                 → unlimited
    """
    quota_info = await _check_quota(request, x_api_key)
    docx_bytes = _convert_to_docx_bytes(req)

    headers = {
        "Content-Disposition": 'attachment; filename="result.docx"',
        "X-Quota-Remaining": str(quota_info.remaining),
        "X-Quota-Limit": str(quota_info.limit),
    }
    return Response(content=docx_bytes, media_type=DOCX_MIME, headers=headers)


@app.post("/convert/base64")
async def convert_base64(
    req: ConvertRequest,
    request: Request,
    x_api_key: str = Header(default="anonymous"),
):
    """
    Convert Markdown to base64-encoded DOCX.

    This is useful for Office add-ins and browser clients that need to insert
    the DOCX directly into a Word document via ``insertFileFromBase64``.
    """
    quota_info = await _check_quota(request, x_api_key)
    docx_bytes = _convert_to_docx_bytes(req)
    return {
        "filename": "result.docx",
        "mime_type": DOCX_MIME,
        "docx_base64": base64.b64encode(docx_bytes).decode("ascii"),
        "quota": {
            "used": quota_info.used,
            "limit": quota_info.limit,
            "remaining": quota_info.remaining,
            "tier": quota_info.tier,
            "resets_at": quota_info.resets_at,
        },
    }


@app.get("/quota")
async def quota_status(
    request: Request,
    x_api_key: str = Header(default="anonymous"),
):
    """Return current quota usage for an API key / IP."""
    identity = x_api_key if x_api_key != "anonymous" else _client_ip(request)
    try:
        info = await quota_service.get_status(identity, x_api_key)
    except InvalidApiKey:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_api_key", "message": "Invalid API key."},
        )
    return {
        "used": info.used,
        "limit": info.limit,
        "remaining": info.remaining,
        "tier": info.tier,
        "resets_at": info.resets_at,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    """
    Extract client IP with explicit proxy-trust controls.

    By default we do NOT trust client-supplied X-Forwarded-For headers.
    Enable trusted proxy mode with:
      TRUST_PROXY_HEADERS=true
    Optionally restrict trusted proxy source IPs:
      TRUSTED_PROXY_IPS=10.0.0.1,10.0.0.2
    """
    direct_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct_ip

    trust_proxy_headers = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in {
        "1", "true", "yes", "on"
    }
    if not trust_proxy_headers:
        return direct_ip

    trusted_proxy_ips = {
        ip.strip() for ip in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if ip.strip()
    }
    if trusted_proxy_ips and direct_ip not in trusted_proxy_ips:
        return direct_ip

    return forwarded.split(",")[0].strip()


async def _check_quota(request: Request, x_api_key: str):
    """Run quota checks and return quota status or raise an HTTPException."""
    identity = x_api_key if x_api_key != "anonymous" else _client_ip(request)
    try:
        return await quota_service.check_and_consume(identity, x_api_key)
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": str(exc),
                "upgrade_url": "https://md2docx.app/#upgrade",
            },
        )
    except InvalidApiKey:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_api_key", "message": "Invalid API key."},
        )


def _convert_to_docx_bytes(req: ConvertRequest) -> bytes:
    """Convert markdown payload to DOCX bytes and normalize failure handling."""
    try:
        return convert_markdown(
            text=req.markdown,
            font=req.font,
            base_font=req.base_font,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}")
