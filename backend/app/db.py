"""
Receipts — Database Persistence Module (M7)

Handles Supabase interactions:
  - Image upload to Storage (bucket: 'images')
  - Receipt insertion (table: 'receipts')
  - SHA-256 cache lookup (M7 caching layer)

Credentials are loaded from the project-root .env file (the same one
provisioned during M2). If SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are
missing, the module raises a clear error — there is no silent fallback.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load .env from project root — works locally; on Vercel env vars are injected
# natively so load_dotenv is a no-op (that is fine).
# ---------------------------------------------------------------------------
_this_file = Path(__file__).resolve()
# Walk up until we find a .env file or exhaust the filesystem
for _candidate in [
    _this_file.parent.parent.parent / ".env",   # monorepo root (local)
    _this_file.parent.parent / ".env",            # backend/ root
    _this_file.parent / ".env",                   # app/ (unlikely but safe)
]:
    if _candidate.exists():
        load_dotenv(_candidate)
        break



class SupabaseConfigError(RuntimeError):
    """Raised when required Supabase credentials are not configured."""


def get_supabase_client() -> Client:
    """Create and return a Supabase client using Service Role credentials.

    Raises SupabaseConfigError if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY
    are not set. There is no silent fallback — missing credentials are a
    hard error, not a soft degradation.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SupabaseConfigError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. "
            f"Checked .env at {_env_path} (exists={_env_path.exists()}). "
            "These credentials were provisioned during M2 — verify "
            "the .env file is present and contains both values."
        )
    return create_client(url, key)


def upload_image_to_storage(image_bytes: bytes, file_ext: str = "jpg") -> str:
    """Upload an image to Supabase Storage and return the public URL."""
    client = get_supabase_client()

    file_id = str(uuid.uuid4())
    file_path = f"{file_id}.{file_ext}"

    # Upload to 'images' bucket
    client.storage.from_("images").upload(
        file_path,
        image_bytes,
        {"content-type": f"image/{file_ext}"},
    )

    # Get public URL
    public_url = client.storage.from_("images").get_public_url(file_path)
    return public_url


def insert_receipt(
    sha256: str,
    phash: str,
    input_type: str,
    source_url: Optional[str],
    original_image_url: Optional[str],
    classification: str,
    evidence_strength: str,
    evidence: list[str],
    interpretation: str,
    status: str,
    error_message: Optional[str],
    processing_time_ms: int,
) -> str:
    """Insert a verified receipt into the Supabase database.

    Returns the UUID of the inserted row.
    """
    client = get_supabase_client()
    row_id = str(uuid.uuid4())

    data = {
        "id": row_id,
        "sha256": sha256,
        "phash": phash,
        "input_type": input_type,
        "source_url": source_url,
        "original_image_url": original_image_url,
        "classification": classification,
        "evidence_strength": evidence_strength,
        "evidence": evidence,
        "interpretation": interpretation,
        "status": status,
        "error_message": error_message,
        "processing_time_ms": processing_time_ms,
    }

    client.table("receipts").insert(data).execute()
    return row_id


def get_receipt_by_sha256(sha256: str) -> Optional[dict]:
    """Check if an image has already been verified by SHA-256.

    Returns the stored receipt row dict on cache hit, None on miss.
    Queries Supabase directly — no in-memory fallback.
    Only returns rows that have successfully completed verification.
    """
    client = get_supabase_client()
    res = client.table("receipts").select("*").eq("sha256", sha256).eq("status", "complete").execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None


def get_receipt_by_id(receipt_id: str) -> Optional[dict]:
    """Retrieve a verified receipt row by UUID."""
    client = get_supabase_client()
    res = client.table("receipts").select("*").eq("id", receipt_id).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None
