"""
Receipts — API and Database Contract Schemas (M0: Contract Freeze)

These Pydantic models define the single source of truth for:
  - POST /verify request payload
  - POST /verify response payload
  - Aggregated Evidence Object (Section 2)
  - receipts database row (Section 5)

Frontend TypeScript types are mechanically generated from these models
via FastAPI's auto-generated OpenAPI schema. Do not hand-author parallel
TypeScript type definitions.

FROZEN CONTRACT: These schemas must not change without explicit human
approval, even if a later milestone reveals a more convenient shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InputType(str, Enum):
    url = "url"
    file = "file"


class EvidenceStrength(str, Enum):
    strong = "Strong"
    moderate = "Moderate"
    limited = "Limited"


class ReceiptStatus(str, Enum):
    processing = "processing"
    complete = "complete"
    failed = "failed"


class ServiceStatus(str, Enum):
    """Per-service status for external API calls within evidence collection."""
    success = "success"
    timeout = "timeout"
    error = "error"
    not_called = "not_called"


# ---------------------------------------------------------------------------
# Aggregated Evidence Object (Section 2)
# ---------------------------------------------------------------------------

class C2PAEvidence(BaseModel):
    """Raw C2PA manifest data extracted from the image.

    Empty dict ({}) when no C2PA manifest is found. Populated with
    manifest fields when a valid C2PA manifest is present.
    """
    has_manifest: bool = False
    ai_generated: bool = False
    camera_signature: bool = False
    manufacturer: Optional[str] = None
    claim_generator: Optional[str] = None
    raw_manifest: Optional[dict] = None


class OriginTraceResult(BaseModel):
    """A single matching URL from reverse image search with Wayback data."""
    url: str
    domain: str
    earliest_wayback_timestamp: Optional[str] = None


class OriginTraceEvidence(BaseModel):
    """Origin trace evidence with per-service status tracking (Section 2)."""
    serpapi_status: ServiceStatus = ServiceStatus.not_called
    wayback_status: ServiceStatus = ServiceStatus.not_called
    results: list[OriginTraceResult] = Field(default_factory=list)


class MetadataEvidence(BaseModel):
    """EXIF metadata extraction results.

    Empty when metadata is stripped or not present.
    """
    has_exif: bool = False
    editing_software_detected: bool = False
    editing_software_name: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    date_taken: Optional[str] = None
    gps_present: bool = False
    raw_exif: Optional[dict] = None


class DuplicateDetectionEvidence(BaseModel):
    """Perceptual hash duplicate detection results."""
    phash: Optional[str] = None
    matches_found: bool = False
    closest_match_distance: Optional[int] = None
    closest_match_receipt_id: Optional[str] = None


class AggregatedEvidence(BaseModel):
    """The complete aggregated evidence object (Section 2).

    Every stage in Evidence Collection must populate its corresponding
    key, even if empty, so Evidence Aggregation always receives a
    consistent shape.
    """
    c2pa: C2PAEvidence = Field(default_factory=C2PAEvidence)
    origin_trace: OriginTraceEvidence = Field(default_factory=OriginTraceEvidence)
    metadata: MetadataEvidence = Field(default_factory=MetadataEvidence)
    duplicate_detection: DuplicateDetectionEvidence = Field(
        default_factory=DuplicateDetectionEvidence
    )


# ---------------------------------------------------------------------------
# POST /verify — Request Schema
# ---------------------------------------------------------------------------

class VerifyRequest(BaseModel):
    """POST /verify request payload.

    Exactly one of `image_url` or file upload (handled via multipart form)
    must be provided. When submitting a URL, set input_type to "url" and
    provide image_url. When uploading a file, the file is sent as multipart
    form data alongside input_type="file".
    """
    input_type: InputType
    image_url: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /verify — Response Schema
# ---------------------------------------------------------------------------

class VerifyResponse(BaseModel):
    """POST /verify response payload.

    Returned after the verification pipeline completes (or fails).
    The `id` field is the UUID of the saved receipts row, used to
    construct the receipt image URL: /api/receipt/{id}
    """
    id: str = Field(description="UUID of the saved receipts row")
    classification: str = Field(
        description=(
            'One of: "AI-Generated Content", "Verified Camera Original", '
            '"Recirculated / Out of Context", "Post-Processed Image", '
            '"Unverified — No Provenance Found"'
        )
    )
    evidence_strength: EvidenceStrength
    evidence: list[str] = Field(
        description="Itemized list of all matched evidence findings"
    )
    interpretation: str = Field(
        description="Plain-language sentence contextualizing the classification"
    )
    processing_time_ms: int
    receipt_image_url: str = Field(
        description="URL to the server-generated receipt image: /api/receipt/{id}"
    )
    cached: bool = Field(
        default=False,
        description="True if this result was served from the SHA-256 cache"
    )


# ---------------------------------------------------------------------------
# Database Row Schema (Section 5)
# ---------------------------------------------------------------------------

class ReceiptRow(BaseModel):
    """Represents a row in the `receipts` database table (Section 5).

    This is a Pydantic mirror of the SQL schema for type-safe
    serialization/deserialization. The actual table is created in
    Supabase during M2.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID primary key"
    )
    sha256: str = Field(description="SHA-256 hash, unique, indexed (cache key)")
    phash: Optional[str] = Field(
        default=None,
        description="Perceptual hash, indexed (recirculation matching)"
    )
    input_type: InputType
    source_url: Optional[str] = None
    original_image_url: Optional[str] = Field(
        default=None,
        description="Supabase-hosted copy of the submitted image"
    )
    classification: Optional[str] = None
    evidence_strength: Optional[EvidenceStrength] = None
    evidence: Optional[list[str]] = Field(
        default=None,
        description="Itemized technical findings (stored as JSONB)"
    )
    interpretation: Optional[str] = None
    status: ReceiptStatus = ReceiptStatus.processing
    error_message: Optional[str] = Field(
        default=None,
        description="Populated when status is 'failed'"
    )
    processing_time_ms: Optional[int] = None
    receipt_schema_version: int = Field(
        default=1,
        description="Schema version for forward compatibility"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
