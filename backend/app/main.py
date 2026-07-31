"""
Receipts — FastAPI Application

Minimal application exposing the OpenAPI schema from the frozen
Pydantic contract models. Feature endpoints are added in later
milestones.
"""

import os

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    InputType,
    VerifyRequest,
    VerifyResponse,
)

app = FastAPI(
    title="Receipts API",
    description="Content verification pipeline for the Receipts project",
    version="0.1.0",
)

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


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
async def verify(
    input_type: InputType = Form(...),
    image_url: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> VerifyResponse:
    """Content verification endpoint.

    Accepts either:
      - input_type="url" + image_url (URL to an image)
      - input_type="file" + file (multipart upload)

    Returns a VerifyResponse with classification results.
    This is a schema-only stub for M0; actual pipeline wired in M7.
    """
    # Stub — will be replaced with real pipeline in M2+
    raise NotImplementedError("Pipeline not yet implemented")
