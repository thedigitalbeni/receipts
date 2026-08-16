"""
Receipts — Local Forensics Module (M3: EXIF & pHash)

Implements:
  1. Perceptual hashing (pHash) via imagehash library
  2. EXIF metadata extraction via Pillow (pure Python, no system binaries)

These are purely local operations — no network access, no external APIs.
"""

from __future__ import annotations

import io
from typing import Any

import imagehash
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS, IFD


# ---------------------------------------------------------------------------
# Perceptual Hashing (pHash)
# ---------------------------------------------------------------------------

# pHash Hamming distance threshold for declaring two images as "matching"
# (i.e., visually identical / near-duplicate).
#
# Justification:
#   - imagehash uses hash_size=8 by default, producing a 64-bit hash.
#   - Dr. Neal Krawetz (Hacker Factor, the original pHash reference cited
#     by the imagehash library README) states for 64-bit hashes:
#       "A distance of zero indicates that it is likely a very similar
#        picture. A distance of 5 means a few things may be different,
#        but they are probably still close enough to be similar. But a
#        distance of 10 or more? That's probably a very different picture."
#     Source: https://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html
#   - Community guidance corroborates: ≤5 is the standard near-duplicate
#     threshold for 64-bit pHash in deduplication and reverse-image-search
#     applications.
#   - We use a threshold of 10 (not 5) because our use case is detecting
#     recirculated images that may have undergone social-media compression,
#     watermarking, cropping, or format conversion — transformations that
#     increase Hamming distance beyond the near-duplicate range but still
#     represent the "same" image in a fact-checking context.
PHASH_MATCH_THRESHOLD = 10


def compute_phash(image_bytes: bytes, hash_size: int = 8) -> str:
    """Compute a perceptual hash (pHash) from image bytes.

    Args:
        image_bytes: Raw image file bytes.
        hash_size: The hash grid dimension. Default 8 produces a 64-bit hash.

    Returns:
        Hex string representation of the pHash (e.g., "8a0303f6df3ec8cd").
    """
    img = Image.open(io.BytesIO(image_bytes))
    h = imagehash.phash(img, hash_size=hash_size)
    return str(h)


def phash_hamming_distance(hash_a: str, hash_b: str) -> int:
    """Compute the Hamming distance between two pHash hex strings.

    Args:
        hash_a: First pHash hex string.
        hash_b: Second pHash hex string.

    Returns:
        Number of differing bits (0 = identical, higher = more different).
    """
    a = imagehash.hex_to_hash(hash_a)
    b = imagehash.hex_to_hash(hash_b)
    return a - b


def is_phash_match(hash_a: str, hash_b: str) -> bool:
    """Check if two pHashes are within the match threshold.

    Uses PHASH_MATCH_THRESHOLD (Hamming distance ≤ 10) — see the
    threshold documentation above for justification.
    """
    return bool(phash_hamming_distance(hash_a, hash_b) <= PHASH_MATCH_THRESHOLD)


# ---------------------------------------------------------------------------
# EXIF Metadata Extraction (Pure Python via Pillow)
# ---------------------------------------------------------------------------

# Section 3 requirement: Must use Pillow's Image.getexif() (including
# the GPS IFD via get_ifd()). Must NOT use PyExifTool or any library
# requiring a system-level binary (Perl/exiftool), to preserve
# zero-DevOps deployment on Render.


def _decode_exif_value(value: Any) -> Any:
    """Attempt to decode EXIF values to JSON-serializable types."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return repr(value)
    if isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, tuple):
        return [_decode_exif_value(v) for v in value]
    return str(value)


def extract_exif(image_bytes: bytes) -> dict[str, Any]:
    """Extract EXIF metadata from image bytes.

    Returns a dictionary with human-readable tag names as keys.
    Includes the GPS IFD if present. Returns an empty dict if
    the image has no EXIF data or is not a format that supports EXIF.

    The returned dictionary includes:
    - editing_software_detected (bool)
    - editing_software_name (str | None)
    - camera_metadata_detected (bool)
    - camera_make (str | None)
    - camera_model (str | None)
    - camera_lens (str | None)
    - date_taken (str | None)
    """
    result: dict[str, Any] = {
        "editing_software_detected": False,
        "editing_software_name": None,
        "camera_metadata_detected": False,
        "camera_make": None,
        "camera_model": None,
        "camera_lens": None,
        "date_taken": None,
    }

    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_data = img.getexif()
    except Exception:
        return result

    if not exif_data:
        return result

    # Standard EXIF tags
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, f"Unknown_{tag_id}")
        result[tag_name] = _decode_exif_value(value)

    # Exif IFD (contains DateTimeOriginal, LensModel, etc.)
    try:
        exif_ifd = exif_data.get_ifd(IFD.Exif)
        if exif_ifd:
            for tag_id, value in exif_ifd.items():
                tag_name = TAGS.get(tag_id, f"Exif_{tag_id}")
                if tag_name not in result:
                    result[tag_name] = _decode_exif_value(value)
    except Exception:
        pass

    # GPS IFD (per Section 3 requirement: extract via get_ifd())
    try:
        gps_ifd = exif_data.get_ifd(IFD.GPSInfo)
        if gps_ifd:
            gps_data = {}
            for tag_id, value in gps_ifd.items():
                tag_name = GPSTAGS.get(tag_id, f"GPSUnknown_{tag_id}")
                gps_data[tag_name] = _decode_exif_value(value)
            if gps_data:
                result["GPSInfo"] = gps_data
    except Exception:
        pass

    # Detect editing software
    is_edited, software_name = _detect_editing_software(result)
    result["editing_software_detected"] = is_edited
    result["editing_software_name"] = software_name

    # Extract camera metadata
    cam_meta = extract_camera_metadata(result)
    result.update(cam_meta)

    return result


# Known editing software identifiers checked against EXIF metadata tags
_KNOWN_EDITORS = [
    "photoshop",
    "lightroom",
    "adobe",
    "gimp",
    "capture one",
    "affinity",
    "darktable",
    "rawtherapee",
    "luminar",
    "paintshop",
    "paint.net",
    "pixelmator",
    "snapseed",
    "vsco",
    "canva",
    "pixlr",
    "photoscape",
    "topaz",
    "inshot",
    "facetune",
    "meitu",
    "prisma",
    "remini",
    "polarr",
    "afterlight",
    "picsart",
    "fotor",
    "corel",
    "photopea",
    "photofiltre",
    "skylum",
    "nik collection",
    "dxo",
    "apple photos",
    "photos.app",
    "google photos editor",
]


def _detect_editing_software(exif_dict: dict[str, Any]) -> tuple[bool, str | None]:
    """Check EXIF metadata for known editing software signatures.

    Checks the "Software", "ProcessingSoftware", "Creator", "History",
    "DocumentID", and "ImageDescription" tags.
    """
    tags_to_check = ["Software", "ProcessingSoftware", "Creator", "History", "DocumentID", "ImageDescription"]
    for tag in tags_to_check:
        value = exif_dict.get(tag)
        if value and isinstance(value, str):
            value_lower = value.lower()
            for editor in _KNOWN_EDITORS:
                if editor in value_lower:
                    return True, value.strip()
    return False, None


def extract_camera_metadata(exif_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract camera hardware metadata from EXIF tags.

    Looks for standard hardware fields (Make, Model, LensModel, DateTimeOriginal)
    to determine if genuine camera tags are present.
    """
    make = exif_dict.get("Make")
    model = exif_dict.get("Model")
    lens = exif_dict.get("LensModel") or exif_dict.get("Lens") or exif_dict.get("Exif_LensModel")
    date_taken = exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime") or exif_dict.get("Exif_DateTimeOriginal")

    if isinstance(lens, (list, tuple)):
        lens = " ".join(str(x) for x in lens)

    has_camera_hardware = bool(make or model)

    return {
        "camera_metadata_detected": has_camera_hardware,
        "camera_make": str(make).strip() if make else None,
        "camera_model": str(model).strip() if model else None,
        "camera_lens": str(lens).strip() if lens else None,
        "date_taken": str(date_taken).strip() if date_taken else None,
    }


# ---------------------------------------------------------------------------
# JPEG Quantization Table Fingerprinting
# ---------------------------------------------------------------------------
#
# Different software uses characteristic JPEG quantization tables.
# These tables survive EXIF stripping because they're part of the JPEG
# data stream itself (not metadata). By comparing the first few values
# of the luminance quantization table against known signatures, we can
# identify which software saved the file.
#
# References:
#   - Farid, H. "Digital Image Forensics" (2016)
#   - FotoForensics quantization table database
#   - IJG libjpeg reference tables

# Known luminance quantization table signatures.
# Each entry maps the first 8 values of the luminance QT to software name.
# Values are from the zig-zag ordered quantization table.
_KNOWN_QUANTIZATION_SIGNATURES: dict[tuple[int, ...], str] = {
    # Adobe Photoshop Quality 12 (Maximum)
    (1, 1, 1, 1, 1, 1, 1, 1): "Adobe Photoshop (Maximum Quality)",
    # Adobe Photoshop Quality 10-11
    (2, 1, 1, 2, 3, 5, 6, 7): "Adobe Photoshop (High Quality)",
    # Adobe Photoshop Quality 8-9
    (3, 2, 2, 3, 4, 6, 8, 10): "Adobe Photoshop (Medium-High Quality)",
    # Adobe Photoshop Quality 6-7
    (4, 3, 3, 4, 6, 10, 12, 14): "Adobe Photoshop (Medium Quality)",
    # GIMP default (uses IJG libjpeg tables, quality 85)
    (5, 3, 4, 4, 4, 3, 5, 4): "GIMP",
    # Instagram re-compression (quality ~72)
    (7, 5, 5, 7, 10, 16, 21, 25): "Instagram/Facebook",
    # Twitter re-compression (quality ~85)
    (5, 3, 3, 5, 7, 12, 15, 18): "Twitter",
    # WhatsApp compression
    (8, 6, 5, 8, 12, 20, 26, 31): "WhatsApp",
}

# Broader pattern matching: check if the first value (DC coefficient
# quantizer) falls in ranges characteristic of specific software.
_PHOTOSHOP_DC_RANGE = range(1, 5)    # Quality 7-12
_LIGHTROOM_DC_RANGE = range(1, 4)    # Typically very high quality


def detect_software_from_quantization(image_bytes: bytes) -> str | None:
    """Detect editing software from JPEG quantization tables.

    Compares the image's luminance quantization table against known
    software signatures. Returns the software name if matched, None otherwise.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Software name string if a known signature is found, None otherwise.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return None

    # Only JPEGs have quantization tables
    if img.format not in ("JPEG", "MPO"):
        return None

    # Pillow exposes quantization tables as a dict: {table_id: list[int]}
    qt = getattr(img, "quantization", None)
    if not qt or not isinstance(qt, dict):
        return None

    # Get the luminance table (usually table 0)
    lum_table = qt.get(0)
    if not lum_table or len(lum_table) < 8:
        return None

    # Extract the first 8 values as a fingerprint
    fingerprint = tuple(lum_table[:8])

    # Exact match against known signatures
    if fingerprint in _KNOWN_QUANTIZATION_SIGNATURES:
        return _KNOWN_QUANTIZATION_SIGNATURES[fingerprint]

    # Fuzzy match: check if values are close to known signatures
    # (within ±1 per position, to handle slight variations)
    for known_sig, software in _KNOWN_QUANTIZATION_SIGNATURES.items():
        if all(abs(a - b) <= 1 for a, b in zip(fingerprint, known_sig)):
            return software

    # Heuristic: very low DC quantizer (1-2) with non-standard table
    # suggests high-quality professional editing software
    if lum_table[0] <= 2 and lum_table[1] <= 2:
        return "Professional editing software (unknown)"

    return None

