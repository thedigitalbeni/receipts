"""
Receipts — C2PA Provenance Module (M4)

Extracts and interprets C2PA (Content Credentials) manifests from images
using c2pa-python. Determines whether the manifest indicates AI generation
(Rule 1) or a non-AI provenance signature such as a camera capture (Rule 2).

c2pa-python v0.37.2 API:
  - Reader.try_create(path_or_stream) → Reader | None
  - reader.json() → JSON string of all manifests
  - reader.get_active_manifest() → active manifest label

Rule mapping logic:
  Rule 1 (AI-Generated): The active manifest's assertions contain a
    c2pa.actions action with digitalSourceType matching any of the IPTC
    NewsCodes URIs for algorithmic/AI-generated media.
  Rule 2 (Camera/Non-AI Signature): A valid C2PA manifest is present but
    does NOT contain any AI-generation markers.
"""

import io
import json
import tempfile
import os
from typing import Optional

import c2pa

# ---------------------------------------------------------------------------
# IPTC Digital Source Type URIs that indicate AI generation
# See: https://cv.iptc.org/newscodes/digitalsourcetype/
# ---------------------------------------------------------------------------
AI_DIGITAL_SOURCE_TYPES = {
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia",
    "http://cv.iptc.org/newscodes/digitalsourcetype/algorithmicMedia",
    # Also match the https variants
    "https://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "https://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia",
    "https://cv.iptc.org/newscodes/digitalsourcetype/algorithmicMedia",
}

# Action types that indicate AI-based creation
AI_ACTION_TYPES = {
    "c2pa.created",  # Generic creation — must check digitalSourceType
}


def extract_c2pa_manifest(image_bytes: bytes) -> Optional[dict]:
    """Extract C2PA manifest from image bytes.

    Uses c2pa-python's Reader.try_create to parse embedded C2PA/JUMBF
    data. Returns None if no manifest is found (no exception raised).

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Parsed manifest dictionary if C2PA data is present, None otherwise.
    """
    # c2pa-python requires a file path or a seekable stream.
    # Write to a temp file to guarantee compatibility.
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        reader = c2pa.Reader.try_create(tmp_path)
        if reader is None:
            return None

        manifest_json = reader.json()
        return json.loads(manifest_json)
    finally:
        os.unlink(tmp_path)


def detect_ai_generation(manifest: dict) -> bool:
    """Check whether the active manifest declares AI generation.

    Inspects the active manifest's assertions for c2pa.actions entries
    whose digitalSourceType matches known IPTC URIs for algorithmic /
    trained-algorithmic media.

    Args:
        manifest: Parsed C2PA manifest dictionary (from extract_c2pa_manifest).

    Returns:
        True if the manifest explicitly declares AI generation, False otherwise.
    """
    active_label = manifest.get("active_manifest")
    if not active_label:
        return False

    manifests = manifest.get("manifests", {})
    active = manifests.get(active_label)
    if not active:
        return False

    for assertion in active.get("assertions", []):
        label = assertion.get("label", "")

        # Check c2pa.actions (v1 and v2)
        if label.startswith("c2pa.actions"):
            data = assertion.get("data", {})
            for action in data.get("actions", []):
                # Check digitalSourceType on the action itself
                dst = action.get("digitalSourceType", "")
                if dst in AI_DIGITAL_SOURCE_TYPES:
                    return True

                # Some manifests nest digitalSourceType in parameters
                params = action.get("parameters", {})
                dst_param = params.get("digitalSourceType", "")
                if dst_param in AI_DIGITAL_SOURCE_TYPES:
                    return True

    return False


def get_c2pa_summary(image_bytes: bytes) -> dict:
    """Extract C2PA data and classify it for the rules engine.

    Returns a structured dictionary that the rules engine can consume:
      - has_manifest: bool — whether any C2PA data was found
      - ai_generated: bool — whether Rule 1 (AI generation) is indicated
      - camera_signature: bool — whether Rule 2 (non-AI C2PA) is indicated
      - claim_generator: str — the software that created the manifest
      - signature_issuer: str — the certificate issuer
      - raw_manifest: dict — the full parsed manifest (for Evidence array)

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Summary dictionary. If no manifest is found, has_manifest is False
        and all other fields are empty/False.
    """
    manifest = extract_c2pa_manifest(image_bytes)

    if manifest is None:
        return {
            "has_manifest": False,
            "ai_generated": False,
            "camera_signature": False,
            "claim_generator": "",
            "signature_issuer": "",
            "raw_manifest": None,
        }

    is_ai = detect_ai_generation(manifest)

    # Extract claim_generator and signature_issuer from active manifest
    active_label = manifest.get("active_manifest", "")
    active = manifest.get("manifests", {}).get(active_label, {})
    claim_generator = active.get("claim_generator", "")
    sig_info = active.get("signature_info", {})
    signature_issuer = sig_info.get("issuer", "")

    return {
        "has_manifest": True,
        "ai_generated": is_ai,
        "camera_signature": not is_ai,  # Non-AI C2PA = Rule 2
        "claim_generator": claim_generator,
        "signature_issuer": signature_issuer,
        "raw_manifest": manifest,
    }
