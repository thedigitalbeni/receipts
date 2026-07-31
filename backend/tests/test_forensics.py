"""
Receipts — Forensics Smoke Tests (M3: Local Forensics)

Tests that pHash and EXIF extraction return correctly typed
dictionaries from real test images. All tests are purely local —
no network access required.
"""

import os
import pytest
from app.forensics import (
    compute_phash,
    phash_hamming_distance,
    is_phash_match,
    extract_exif,
    PHASH_MATCH_THRESHOLD,
)

# Path to test assets
TEST_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "test_assets",
)


def _load_test_image(filename: str) -> bytes:
    """Load a test image from the test_assets directory."""
    path = os.path.join(TEST_ASSETS_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f"Test asset not found: {path}")
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# pHash Tests
# ---------------------------------------------------------------------------

class TestPHash:
    """Tests for perceptual hashing."""

    def test_compute_phash_returns_hex_string(self):
        """pHash must return a hex string of the expected length."""
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        phash = compute_phash(image_bytes)

        assert isinstance(phash, str), f"Expected str, got {type(phash)}"
        # Default hash_size=8 → 64 bits → 16 hex chars
        assert len(phash) == 16, f"Expected 16-char hex, got {len(phash)}: {phash}"
        # Must be valid hex
        int(phash, 16)

    def test_same_image_produces_identical_hash(self):
        """The same image bytes must produce the same hash."""
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        hash1 = compute_phash(image_bytes)
        hash2 = compute_phash(image_bytes)
        assert hash1 == hash2

    def test_different_images_produce_different_hashes(self):
        """Different images should produce different hashes."""
        bytes_a = _load_test_image("c2pa_candidate.jpg")
        bytes_b = _load_test_image("clean_no_provenance.jpg")
        hash_a = compute_phash(bytes_a)
        hash_b = compute_phash(bytes_b)
        assert hash_a != hash_b, "Different images produced identical hashes"

    def test_hamming_distance_self_is_zero(self):
        """Hamming distance of an image against itself must be 0."""
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        phash = compute_phash(image_bytes)
        assert phash_hamming_distance(phash, phash) == 0

    def test_hamming_distance_different_images_is_nonzero(self):
        """Hamming distance between different images must be > 0."""
        bytes_a = _load_test_image("c2pa_candidate.jpg")
        bytes_b = _load_test_image("clean_no_provenance.jpg")
        hash_a = compute_phash(bytes_a)
        hash_b = compute_phash(bytes_b)
        distance = phash_hamming_distance(hash_a, hash_b)
        assert distance > 0, "Different images have hamming distance 0"

    def test_is_phash_match_self(self):
        """An image always matches itself."""
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        phash = compute_phash(image_bytes)
        assert is_phash_match(phash, phash) is True

    def test_is_phash_match_different_images(self):
        """Sufficiently different images should not match."""
        bytes_a = _load_test_image("c2pa_candidate.jpg")
        bytes_b = _load_test_image("clean_no_provenance.jpg")
        hash_a = compute_phash(bytes_a)
        hash_b = compute_phash(bytes_b)
        # These are completely different images, should exceed threshold
        assert is_phash_match(hash_a, hash_b) is False

    def test_threshold_is_documented(self):
        """PHASH_MATCH_THRESHOLD must be set and reasonable."""
        assert isinstance(PHASH_MATCH_THRESHOLD, int)
        assert PHASH_MATCH_THRESHOLD > 0
        # For a 64-bit hash, threshold should be << 64
        assert PHASH_MATCH_THRESHOLD < 32


# ---------------------------------------------------------------------------
# EXIF Tests
# ---------------------------------------------------------------------------

class TestEXIF:
    """Tests for EXIF metadata extraction."""

    def test_extract_exif_returns_dict(self):
        """extract_exif must always return a dict."""
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        result = extract_exif(image_bytes)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    def test_exif_contains_editing_software_key(self):
        """Result must always contain 'editing_software_detected' bool."""
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        result = extract_exif(image_bytes)
        assert "editing_software_detected" in result
        assert isinstance(result["editing_software_detected"], bool)

    def test_exif_values_are_serializable(self):
        """All EXIF values must be JSON-serializable (no raw bytes)."""
        import json
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        result = extract_exif(image_bytes)
        # This will raise TypeError if any value is not serializable
        json.dumps(result)

    def test_exif_empty_for_no_metadata(self):
        """An image with no EXIF should return dict with editing_software_detected=False."""
        image_bytes = _load_test_image("clean_no_provenance.jpg")
        result = extract_exif(image_bytes)
        assert isinstance(result, dict)
        assert result["editing_software_detected"] is False

    def test_exif_with_c2pa_image(self):
        """C2PA test image should have some EXIF data."""
        image_bytes = _load_test_image("c2pa_ai_candidate.jpg")
        result = extract_exif(image_bytes)
        assert isinstance(result, dict)
        # Should have at least the editing_software_detected key
        assert "editing_software_detected" in result

    def test_exif_tag_names_are_strings(self):
        """All EXIF tag names (keys) must be strings."""
        image_bytes = _load_test_image("c2pa_ai_candidate.jpg")
        result = extract_exif(image_bytes)
        for key in result:
            assert isinstance(key, str), f"Non-string key: {key!r}"


# ---------------------------------------------------------------------------
# Combined Forensics Tests
# ---------------------------------------------------------------------------

class TestForensicsPipeline:
    """Integration-like tests verifying both modules work on the same image."""

    def test_all_test_assets_produce_valid_forensics(self):
        """Every test asset should produce a valid pHash and EXIF dict."""
        test_images = [
            "c2pa_candidate.jpg",
            "c2pa_ai_candidate.jpg",
            "clean_no_provenance.jpg",
            "rule2_camera_candidate.jpg",
        ]
        for filename in test_images:
            image_bytes = _load_test_image(filename)

            phash = compute_phash(image_bytes)
            assert isinstance(phash, str), f"{filename}: pHash not a string"
            assert len(phash) == 16, f"{filename}: pHash wrong length"

            exif = extract_exif(image_bytes)
            assert isinstance(exif, dict), f"{filename}: EXIF not a dict"
            assert "editing_software_detected" in exif, (
                f"{filename}: missing editing_software_detected"
            )
