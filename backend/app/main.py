"""
Receipts — FastAPI Application (M2: Storage Security & Input Validation)

Implements:
  - /health endpoint
  - /verify endpoint with full input validation pipeline:
    * IP rate limiting (10 req/min per IP via slowapi)
    * Upload size limit (15 MB, rejected before Pillow)
    * Image format validation (Pillow .verify())
    * Baseline SSRF protection (post-DNS IP range blocking)
    * URL content-type validation (HEAD → fallback GET w/ Range)
  - CORS (strict origins from env var, no wildcard)
"""

import os
import logging

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.schemas import (
    InputType,
    VerifyResponse,
)
from app.security import (
    InputValidationError,
    validate_upload_size,
    validate_image,
    validate_url_scheme_and_resolve,
    validate_url_content_type,
    download_image_from_url,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate Limiter (Section 5: 10 req/min per IP on /verify)
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Receipts API",
    description="Content verification pipeline for the Receipts project",
    version="0.1.0",
)
app.state.limiter = limiter

# CORS — strict origins from env var; wildcard (*) is explicitly rejected
# per Section 5. In production, CORS_ORIGINS must contain the exact Vercel
# domain. Falls back to localhost:3000 for local development.
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(InputValidationError)
async def input_validation_error_handler(
    request: Request, exc: InputValidationError
) -> JSONResponse:
    """Return clean 400 for all input validation failures.

    A crash or unhandled exception is always a failure condition —
    this handler ensures validation errors degrade to a clean HTTP 400.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return 429 when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Max 10 requests per minute."},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
@limiter.limit("10/minute")
async def verify(
    request: Request,
    input_type: InputType = Form(...),
    image_url: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> VerifyResponse | JSONResponse:
    """Content verification endpoint.

    Accepts either:
      - input_type="url" + image_url (URL to an image)
      - input_type="file" + file (multipart upload)

    M2 implements full input validation and security checks.
    Pipeline processing (M3-M6) and database persistence (M7) are
    wired in later milestones. For now, valid inputs return a
    stubbed 200 OK to satisfy the M2 Definition of Done.
    """
    image_bytes: bytes

    if input_type == InputType.url:
        # --- URL path ---
        if not image_url:
            raise InputValidationError("image_url is required when input_type is 'url'")

        # 1. SSRF protection: validate scheme and resolved IP ranges
        validate_url_scheme_and_resolve(image_url)

        # 2. Content-type validation: HEAD → fallback GET w/ Range
        await validate_url_content_type(image_url)

        # 3. Download image (streaming, with 15 MB limit)
        image_bytes = await download_image_from_url(image_url)

    elif input_type == InputType.file:
        # --- File upload path ---
        if not file:
            raise InputValidationError("file is required when input_type is 'file'")

        # 1. Size check via Content-Length header (fast reject)
        content_length = file.size
        # Read file bytes
        image_bytes = await file.read()

        # 2. Size check on actual bytes (Content-Length can be spoofed)
        await validate_upload_size(content_length, image_bytes)

    else:
        raise InputValidationError(f"Invalid input_type: {input_type}")

    # 3. Image format validation (applies to both paths)
    validate_image(image_bytes)

    # --- M2 stub: valid image accepted ---
    # Real pipeline (M3-M7) will replace this return.
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "message": "Image validated successfully",
            "size_bytes": len(image_bytes),
        },
    )
