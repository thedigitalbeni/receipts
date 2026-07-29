"""
Receipts — FastAPI Application (M0: Contract Freeze)

Minimal application exposing the OpenAPI schema from the frozen
Pydantic contract models. Feature endpoints are added in later
milestones.
"""

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

# CORS — strict origins; localhost for dev, production domain added later.
# Wildcard (*) is explicitly rejected per Section 5.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
