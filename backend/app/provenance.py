"""
Receipts — C2PA Provenance Module (M4)

Extracts and interprets C2PA (Content Credentials) manifests from images
using c2pa-python. Determines whether the manifest indicates AI generation
(Rule 1) or a non-AI provenance signature (Rule 2).

c2pa-python v0.37.2 API:
  - Reader.try_create(path_or_stream) → Reader | None
  - reader.json() → JSON string of all manifests
  - reader.get_active_manifest() → active manifest label

Rule mapping logic:
  Rule 1 (AI-Generated): The active manifest's assertions contain a
    c2pa.actions action with digitalSourceType matching any of the IPTC
    NewsCodes URIs for algorithmic/AI-generated media.
  Rule 2 (Camera Signature): The active manifest's assertions contain a
    digitalSourceType indicating camera/device capture. Note: no available
    test asset currently demonstrates this live — Rule 2 is validated
    via M6 unit tests using mocked evidence. The provenance module
    correctly detects the field when present.
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

# ---------------------------------------------------------------------------
# IPTC Digital Source Type URIs that indicate camera/device capture
# See: https://cv.iptc.org/newscodes/digitalsourcetype/
# ---------------------------------------------------------------------------
CAMERA_DIGITAL_SOURCE_TYPES = {
    "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
    "https://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",
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


def _get_all_digital_source_types(manifest: dict) -> set[str]:
    """Extract all digitalSourceType values from the active manifest.

    Searches c2pa.actions assertions for digitalSourceType fields,
    both at the action level and nested within parameters.

    Returns:
        Set of all digitalSourceType URI strings found.
    """
    result = set()
    active_label = manifest.get("active_manifest")
    if not active_label:
        return result

    active = manifest.get("manifests", {}).get(active_label)
    if not active:
        return result

    for assertion in active.get("assertions", []):
        label = assertion.get("label", "")
        if label.startswith("c2pa.actions") or "actions" in label:
            data = assertion.get("data", {})
            for action in data.get("actions", []):
                dst = action.get("digitalSourceType")
                if isinstance(dst, str) and dst.strip():
                    result.add(dst.strip())
                elif isinstance(dst, list):
                    for d in dst:
                        if isinstance(d, str) and d.strip():
                            result.add(d.strip())

                params = action.get("parameters", {})
                if isinstance(params, dict):
                    dst_param = params.get("digitalSourceType")
                    if isinstance(dst_param, str) and dst_param.strip():
                        result.add(dst_param.strip())
                    elif isinstance(dst_param, list):
                        for d in dst_param:
                            if isinstance(d, str) and d.strip():
                                result.add(d.strip())

    return result


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
    return bool(_get_all_digital_source_types(manifest) & AI_DIGITAL_SOURCE_TYPES)


def detect_camera_signature(manifest: dict) -> bool:
    """Check whether the active manifest declares camera/device capture.

    Inspects the active manifest's assertions for c2pa.actions entries
    whose digitalSourceType matches IPTC URIs for digital capture
    (camera hardware attestation).

    Note: No currently available test asset demonstrates this live.
    Rule 2 is validated via M6 unit tests using mocked evidence.
    This function correctly detects the field when present.

    Args:
        manifest: Parsed C2PA manifest dictionary (from extract_c2pa_manifest).

    Returns:
        True if the manifest declares camera/device capture, False otherwise.
    """
    return bool(_get_all_digital_source_types(manifest) & CAMERA_DIGITAL_SOURCE_TYPES)


def get_c2pa_summary(image_bytes: bytes) -> dict:
    """Extract C2PA data and classify it for the rules engine.

    Returns a structured dictionary that the rules engine can consume:
      - has_manifest: bool — whether any C2PA data was found
      - ai_generated: bool — whether Rule 1 (AI generation) is indicated
      - camera_signature: bool — whether Rule 2 (camera capture) is indicated
        (True only for genuine camera/device digitalSourceType, not merely
        "has C2PA but not AI")
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
    is_camera = detect_camera_signature(manifest)

    # Extract claim_generator and signature_issuer from active manifest
    active_label = manifest.get("active_manifest", "")
    active = manifest.get("manifests", {}).get(active_label, {})
    claim_generator = active.get("claim_generator", "")
    sig_info = active.get("signature_info", {})
    signature_issuer = sig_info.get("issuer", "")

    return {
        "has_manifest": True,
        "ai_generated": is_ai,
        "camera_signature": is_camera,
        "claim_generator": claim_generator,
        "signature_issuer": signature_issuer,
        "raw_manifest": manifest,
    }

