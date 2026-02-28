"""
api/main.py
===========
FastAPI service that wraps md2docx's convert_markdown() function.

Endpoints
---------
POST /convert   – Convert markdown text to .docx; enforces per-key quota.
GET  /health    – Liveness probe for Railway / uptime monitors.

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

# Make the repo root importable when running from inside api/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field

from md2docx import convert_markdown
from api.quota import QuotaService, QuotaExceeded

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
    # Resolve identity: prefer API key, fall back to client IP
    identity = x_api_key if x_api_key != "anonymous" else _client_ip(request)

    try:
        quota_info = await quota_service.check_and_consume(identity, x_api_key)
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": str(exc),
                "upgrade_url": "https://md2docx.app/#upgrade",
            },
        )

    # Run the conversion (pure Python, no disk I/O)
    try:
        docx_bytes = convert_markdown(
            text=req.markdown,
            font=req.font,
            base_font=req.base_font,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}")

    headers = {
        "Content-Disposition": 'attachment; filename="result.docx"',
        "X-Quota-Remaining": str(quota_info.remaining),
        "X-Quota-Limit": str(quota_info.limit),
    }
    return Response(content=docx_bytes, media_type=DOCX_MIME, headers=headers)


@app.get("/quota")
async def quota_status(
    request: Request,
    x_api_key: str = Header(default="anonymous"),
):
    """Return current quota usage for an API key / IP."""
    identity = x_api_key if x_api_key != "anonymous" else _client_ip(request)
    info = await quota_service.get_status(identity, x_api_key)
    return {
        "used": info.used,
        "limit": info.limit,
        "remaining": info.remaining,
        "tier": info.tier,
        "resets_at": info.resets_at,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    """Extract real client IP, honouring X-Forwarded-For from Railway proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
