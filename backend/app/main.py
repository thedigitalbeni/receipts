"""
Receipts — FastAPI Application (M7: End-to-End Backend Pipeline)

Implements:
  - /health endpoint
  - /verify endpoint with full verification pipeline:
    * IP rate limiting (10 req/min per IP via slowapi)
    * Upload size limit (15 MB, rejected before Pillow)
    * Image format validation (Pillow .verify())
    * Baseline SSRF protection (post-DNS IP range blocking)
    * URL content-type validation (HEAD → fallback GET w/ Range)
    * SHA-256 cache short-circuit (return cached result if already processed)
    * M3 Local Forensics (EXIF + pHash)
    * M4 Provenance (C2PA manifest → ai_generated / camera_signature)
    * M5 Origin Trace (SerpApi Google Lens + Wayback Machine)
    * M6 Rules Engine (evaluate_evidence → classification)
    * Database persistence (single INSERT, no UPDATE — RLS-safe)
  - CORS (strict origins from env var, no wildcard)
"""

import os
import time
import hashlib
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
    AggregatedEvidence,
    C2PAEvidence,
    MetadataEvidence,
    DuplicateDetectionEvidence,
    EvidenceStrength,
)
from app.security import (
    InputValidationError,
    validate_upload_size,
    validate_image,
    validate_url_scheme_and_resolve,
    validate_url_content_type,
    download_image_from_url,
    extract_social_image_url,
)
from app.forensics import compute_phash, extract_exif
# Fix #1: Import the actual functions from provenance.py (not the
# non-existent c2pa_maps_to_rule_1_or_2).
from app.provenance import extract_c2pa_manifest, detect_ai_generation, detect_camera_signature
from app.origin_trace import query_origin_trace, to_frozen_contract
from app.rules import evaluate_evidence
# Fix #6: Import get_receipt_by_sha256 for the SHA-256 cache layer.
from app.db import upload_image_to_storage, insert_receipt, get_receipt_by_sha256

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

    Pipeline flow:
      1. Input validation (M2)
      2. SHA-256 cache check — return immediately if already processed
      3. Local Forensics: EXIF + pHash (M3)
      4. Provenance: C2PA manifest (M4)
      5. Origin Trace: SerpApi + Wayback (M5)
      6. Rules Engine: evaluate_evidence (M6)
      7. Database persistence: single INSERT with status="complete"
    """
    image_bytes: bytes

    if input_type == InputType.url:
        # --- URL path ---
        if not image_url:
            raise InputValidationError("image_url is required when input_type is 'url'")

        # 1. SSRF protection: validate scheme and resolved IP ranges
        validate_url_scheme_and_resolve(image_url)

        # 2. Content-type validation: HEAD → fallback GET w/ Range
        try:
            await validate_url_content_type(image_url)
        except InputValidationError as e:
            # If it's not a direct image, attempt social link extraction
            image_url = await extract_social_image_url(image_url)
            # Re-run full security validation on the extracted URL
            validate_url_scheme_and_resolve(image_url)
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

    # --- SHA-256 Cache Check (Fix #6) ---
    sha256_hash = hashlib.sha256(image_bytes).hexdigest()

    cached_row = get_receipt_by_sha256(sha256_hash)
    if cached_row:
        # Cache hit — return stored result immediately without re-running
        # the pipeline. This avoids burning SerpApi quota and C2PA cycles
        # for images we've already fully verified.
        
        # Safe fallback in case older DB rows have missing evidence_strength
        raw_strength = cached_row.get("evidence_strength")
        if not raw_strength:
            raw_strength = "Limited"
            
        try:
            strength = EvidenceStrength(raw_strength)
        except ValueError:
            strength = EvidenceStrength.limited

        return VerifyResponse(
            id=cached_row["id"],
            classification=cached_row["classification"] or "Unverified — No Provenance Found",
            evidence_strength=strength,
            evidence=cached_row["evidence"] or [],
            interpretation=cached_row["interpretation"] or "",
            processing_time_ms=cached_row["processing_time_ms"] or 0,
            receipt_image_url=f"/api/receipt/{cached_row['id']}",
            cached=True,
        )

    # --- Full Pipeline (cache miss) ---
    start_time = time.time()

    # Step 1: Local Forensics (M3)
    phash_val = compute_phash(image_bytes)
    exif_data = extract_exif(image_bytes)

    # Step 2: Provenance (M4)
    # Fix #1: Use detect_ai_generation() and detect_camera_signature()
    # from provenance.py to populate C2PAEvidence fields directly.
    c2pa_manifest = extract_c2pa_manifest(image_bytes)
    is_ai = detect_ai_generation(c2pa_manifest) if c2pa_manifest else False
    is_camera = detect_camera_signature(c2pa_manifest) if c2pa_manifest else False

    # Step 3: Origin Trace (M5)
    # Get a public URL for SerpApi to fetch.
    if input_type == InputType.url and image_url:
        public_url = image_url
    else:
        # File upload: upload to Supabase Storage to get a public URL.
        public_url = upload_image_to_storage(image_bytes)

    # Fix #3: query_origin_trace() takes exactly 1 argument (image_url).
    # phash_val is NOT used by origin_trace — SerpApi does its own visual
    # matching. phash_val is used only for local duplicate detection (M3)
    # and is stored in the DB row for future pHash-based deduplication.
    origin_trace_raw = query_origin_trace(public_url)
    origin_trace_evidence = to_frozen_contract(origin_trace_raw)

    # Step 4: Evidence Aggregation & Rules Engine (M6)
    # Fix #2: Use correct frozen-contract field names from schemas.py.
    # Fix #5: Use M3's editing_software_detected from the EXIF dict
    # directly — extract_exif() already checks 14 editors via
    # _detect_editing_software(). Do not re-implement.
    aggregated_evidence = AggregatedEvidence(
        c2pa=C2PAEvidence(
            has_manifest=bool(c2pa_manifest),
            ai_generated=is_ai,
            camera_signature=is_camera,
            raw_manifest=c2pa_manifest,
        ),
        metadata=MetadataEvidence(
            has_exif=bool(exif_data),
            raw_exif=exif_data if exif_data else None,
            editing_software_detected=exif_data.get("editing_software_detected", False)
                if exif_data else False,
        ),
        origin_trace=origin_trace_evidence,
        duplicate_detection=DuplicateDetectionEvidence(
            phash=phash_val,
            matches_found=False,
        ),
    )

    evaluation_result = evaluate_evidence(aggregated_evidence)

    processing_time_ms = int((time.time() - start_time) * 1000)

    # Step 5: Database Persistence (M7)
    # Single INSERT with status="complete". No early "processing" row,
    # so no UPDATE is needed — Section 5 RLS (INSERT + SELECT only) holds.
    row_id = insert_receipt(
        sha256=sha256_hash,
        phash=phash_val,
        input_type=input_type.value,
        source_url=image_url if input_type == InputType.url else None,
        original_image_url=public_url,
        classification=evaluation_result.classification,
        evidence_strength=evaluation_result.evidence_strength.value,
        evidence=evaluation_result.evidence,
        interpretation=evaluation_result.interpretation,
        status="complete",
        error_message=None,
        processing_time_ms=processing_time_ms,
    )

    return VerifyResponse(
        id=row_id,
        classification=evaluation_result.classification,
        evidence_strength=evaluation_result.evidence_strength,
        evidence=evaluation_result.evidence,
        interpretation=evaluation_result.interpretation,
        processing_time_ms=processing_time_ms,
        receipt_image_url=f"/api/receipt/{row_id}",
        cached=False,
    )
