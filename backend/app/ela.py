"""
Receipts — Error Level Analysis (ELA) Module

Detects image editing by analyzing JPEG compression artifacts.
When a JPEG is re-saved, edited regions compress differently than
the original content, creating detectable error level discrepancies.

This technique works even when all EXIF metadata has been stripped,
making it a critical complement to metadata-based detection (Rule 4).

Algorithm:
  1. Re-compress the JPEG at a known quality level (95%)
  2. Compute the absolute pixel-level difference between original and re-compressed
  3. Edited regions show anomalously high error levels
  4. Flag as suspicious if >15% of pixels exceed 2σ from the mean error

Limitations:
  - Only works on JPEGs (PNG is lossless, no compression artifacts)
  - Images re-saved many times may show uniform high error (false positive)
  - Very high-quality originals (quality 98+) may show minimal error (false negative)
"""

from __future__ import annotations

import io
import math
from typing import Any

from PIL import Image


def compute_ela(image_bytes: bytes, quality: int = 95) -> dict[str, Any]:
    """Perform Error Level Analysis on an image.

    Args:
        image_bytes: Raw image file bytes.
        quality: JPEG re-compression quality level (1-100). Default 95.

    Returns:
        Dictionary with ELA results:
          - performed: bool — False if image is not JPEG
          - max_error: float — Peak error value (0-255)
          - mean_error: float — Average error across all pixels
          - std_error: float — Standard deviation of errors
          - suspicious_ratio: float — Ratio of pixels above threshold
          - is_suspicious: bool — True if editing likely detected
    """
    try:
        original = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return _empty_result()

    # ELA only works on JPEG — PNG/WebP are lossless or use different compression
    fmt = original.format
    if fmt not in ("JPEG", "MPO"):
        return _empty_result()

    # Convert to RGB if needed (some JPEGs are CMYK or grayscale)
    if original.mode not in ("RGB", "L"):
        try:
            original = original.convert("RGB")
        except Exception:
            return _empty_result()

    # Re-compress at the specified quality level
    buffer = io.BytesIO()
    try:
        original.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        recompressed = Image.open(buffer)
    except Exception:
        return _empty_result()

    # Ensure both images are the same size and mode
    if original.size != recompressed.size:
        return _empty_result()

    if original.mode != recompressed.mode:
        recompressed = recompressed.convert(original.mode)

    # Compute pixel-level absolute differences
    width, height = original.size
    orig_pixels = original.load()
    recomp_pixels = recompressed.load()

    errors: list[float] = []
    is_rgb = original.mode == "RGB"

    for y in range(height):
        for x in range(width):
            if is_rgb:
                r1, g1, b1 = orig_pixels[x, y]
                r2, g2, b2 = recomp_pixels[x, y]
                # Average channel difference
                diff = (abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)) / 3.0
            else:
                # Grayscale
                diff = abs(orig_pixels[x, y] - recomp_pixels[x, y])
            errors.append(diff)

    if not errors:
        return _empty_result()

    # Statistics
    n = len(errors)
    mean_error = sum(errors) / n
    max_error = max(errors)

    # Standard deviation
    variance = sum((e - mean_error) ** 2 for e in errors) / n
    std_error = math.sqrt(variance)

    # Suspicious ratio: pixels exceeding mean + 2σ
    threshold = mean_error + 2 * std_error
    suspicious_count = sum(1 for e in errors if e > threshold)
    suspicious_ratio = suspicious_count / n

    # Decision: suspicious if >15% of pixels show anomalous error levels
    # AND the max error is significant (>30, to avoid flagging minor
    # re-compression artifacts)
    is_suspicious = suspicious_ratio > 0.15 and max_error > 30

    return {
        "performed": True,
        "max_error": round(max_error, 2),
        "mean_error": round(mean_error, 2),
        "std_error": round(std_error, 2),
        "suspicious_ratio": round(suspicious_ratio, 4),
        "is_suspicious": is_suspicious,
    }


def _empty_result() -> dict[str, Any]:
    """Return an empty ELA result (not performed)."""
    return {
        "performed": False,
        "max_error": 0.0,
        "mean_error": 0.0,
        "std_error": 0.0,
        "suspicious_ratio": 0.0,
        "is_suspicious": False,
    }
