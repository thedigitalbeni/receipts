"""
Receipts — C2PA Provenance Smoke Tests (M4)

Tests that c2pa-python correctly parses test assets and that the
provenance module correctly classifies them:
  - c2pa_ai_candidate.jpg → Rule 1 (AI-Generated): has trainedAlgorithmicMedia
  - c2pa_candidate.jpg / rule2_camera_candidate.jpg → Has manifest, but
    NO camera digitalSourceType (these are c2pa-rs test fixtures, not
    camera hardware attestations). Rule 2 is validated via M6 unit tests.
  - clean_no_provenance.jpg → No manifest (Rule 5)

All tests are purely local — no network access required.
"""

import os
import json
import pytest
from app.provenance import (
    extract_c2pa_manifest,
    detect_ai_generation,
    detect_camera_signature,
    get_c2pa_summary,
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
# Manifest Extraction Tests
# ---------------------------------------------------------------------------

class TestManifestExtraction:
    """Tests for raw C2PA manifest extraction."""

    def test_ai_candidate_has_manifest(self):
        """c2pa_ai_candidate.jpg must contain a C2PA manifest."""
        image_bytes = _load_test_image("c2pa_ai_candidate.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        assert manifest is not None, "Expected C2PA manifest, got None"
        assert "active_manifest" in manifest
        assert "manifests" in manifest

    def test_c2pa_fixture_has_manifest(self):
        """c2pa_candidate.jpg (c2pa-rs test fixture) must contain a C2PA manifest.

        Note: This asset has a valid manifest but is NOT a camera signature.
        It is a software test fixture from make_test_images/c2pa-rs.
        """
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        assert manifest is not None, "Expected C2PA manifest, got None"
        assert "active_manifest" in manifest

    def test_c2pa_fixture_backup_has_manifest(self):
        """rule2_camera_candidate.jpg (c2pa-rs test fixture) must contain a C2PA manifest."""
        image_bytes = _load_test_image("rule2_camera_candidate.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        assert manifest is not None, "Expected C2PA manifest, got None"

    def test_clean_image_has_no_manifest(self):
        """clean_no_provenance.jpg must NOT contain a C2PA manifest."""
        image_bytes = _load_test_image("clean_no_provenance.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        assert manifest is None, f"Expected None, got manifest: {manifest}"

    def test_manifest_is_json_serializable(self):
        """Extracted manifest must be fully JSON-serializable."""
        image_bytes = _load_test_image("c2pa_ai_candidate.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        # This will raise TypeError if any value is not serializable
        json.dumps(manifest)


# ---------------------------------------------------------------------------
# AI Detection Tests
# ---------------------------------------------------------------------------

class TestAIDetection:
    """Tests for AI generation detection within C2PA manifests."""

    def test_ai_candidate_detected_as_ai(self):
        """c2pa_ai_candidate.jpg (Adobe Firefly) must be detected as AI-generated.

        This asset carries:
          action: c2pa.created
          digitalSourceType: trainedAlgorithmicMedia
          claim_generator: Adobe_Firefly
        """
        image_bytes = _load_test_image("c2pa_ai_candidate.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        assert manifest is not None
        assert detect_ai_generation(manifest) is True

    def test_c2pa_fixture_not_detected_as_ai(self):
        """c2pa_candidate.jpg (c2pa-rs test fixture) must NOT be detected as AI.

        This asset carries:
          action: c2pa.opened + c2pa.color_adjustments
          No digitalSourceType field
          claim_generator: make_test_images/c2pa-rs
        """
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        assert manifest is not None
        assert detect_ai_generation(manifest) is False

    def test_c2pa_fixture_backup_not_detected_as_ai(self):
        """rule2_camera_candidate.jpg (c2pa-rs test fixture) must NOT be detected as AI."""
        image_bytes = _load_test_image("rule2_camera_candidate.jpg")
        manifest = extract_c2pa_manifest(image_bytes)
        assert manifest is not None
        assert detect_ai_generation(manifest) is False

    def test_c2pa_fixtures_not_detected_as_camera(self):
        """c2pa-rs test fixtures must NOT be detected as camera signatures.

        These assets have valid C2PA manifests but no digitalSourceType
        of any kind — they are software test fixtures, not camera hardware
        attestations. camera_signature must be False for both.
        """
        for filename in ["c2pa_candidate.jpg", "rule2_camera_candidate.jpg"]:
            image_bytes = _load_test_image(filename)
            manifest = extract_c2pa_manifest(image_bytes)
            assert manifest is not None
            assert detect_camera_signature(manifest) is False, (
                f"{filename}: detected as camera but has no camera digitalSourceType"
            )


# ---------------------------------------------------------------------------
# Summary Tests (get_c2pa_summary — the rules engine interface)
# ---------------------------------------------------------------------------

class TestC2PASummary:
    """Tests for the high-level summary used by the rules engine."""

    def test_ai_candidate_summary(self):
        """AI candidate must produce has_manifest=True, ai_generated=True."""
        image_bytes = _load_test_image("c2pa_ai_candidate.jpg")
        summary = get_c2pa_summary(image_bytes)

        assert summary["has_manifest"] is True
        assert summary["ai_generated"] is True
        assert summary["camera_signature"] is False
        assert "Adobe_Firefly" in summary["claim_generator"]
        assert summary["raw_manifest"] is not None

    def test_c2pa_fixture_summary(self):
        """c2pa-rs test fixture: has_manifest=True, but camera_signature=False.

        This asset has a valid C2PA manifest (make_test_images/c2pa-rs)
        but no camera/device digitalSourceType. It is NOT a camera
        hardware attestation. camera_signature must be False.
        """
        image_bytes = _load_test_image("c2pa_candidate.jpg")
        summary = get_c2pa_summary(image_bytes)

        assert summary["has_manifest"] is True
        assert summary["ai_generated"] is False
        assert summary["camera_signature"] is False  # No camera digitalSourceType
        assert summary["claim_generator"] != ""
        assert summary["raw_manifest"] is not None

    def test_clean_image_summary(self):
        """Clean image must produce has_manifest=False, everything else empty."""
        image_bytes = _load_test_image("clean_no_provenance.jpg")
        summary = get_c2pa_summary(image_bytes)

        assert summary["has_manifest"] is False
        assert summary["ai_generated"] is False
        assert summary["camera_signature"] is False
        assert summary["claim_generator"] == ""
        assert summary["raw_manifest"] is None

    def test_summary_keys_are_complete(self):
        """Summary must always contain all expected keys."""
        expected_keys = {
            "has_manifest",
            "ai_generated",
            "camera_signature",
            "claim_generator",
            "signature_issuer",
            "raw_manifest",
        }
        for filename in ["c2pa_ai_candidate.jpg", "c2pa_candidate.jpg", "clean_no_provenance.jpg"]:
            image_bytes = _load_test_image(filename)
            summary = get_c2pa_summary(image_bytes)
            assert set(summary.keys()) == expected_keys, (
                f"{filename}: Missing keys: {expected_keys - set(summary.keys())}"
            )
