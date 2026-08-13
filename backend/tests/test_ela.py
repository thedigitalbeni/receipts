"""
Receipts — ELA (Error Level Analysis) Unit Tests

Tests the ELA module with synthetic JPEG and PNG images.
No real files needed — all images are generated in-memory with Pillow.
"""

import io
import pytest
from PIL import Image

from app.ela import compute_ela, _empty_result


pytestmark = pytest.mark.disable_socket


class TestELABasics:
    """Core ELA behavior tests."""

    def _make_jpeg(self, width=100, height=100, color=(128, 128, 128), quality=85) -> bytes:
        """Create a simple solid-color JPEG in memory."""
        img = Image.new("RGB", (width, height), color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    def _make_png(self, width=100, height=100, color=(128, 128, 128)) -> bytes:
        """Create a simple solid-color PNG in memory."""
        img = Image.new("RGB", (width, height), color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_jpeg_returns_performed_true(self):
        """ELA should be performed on JPEG images."""
        jpeg = self._make_jpeg()
        result = compute_ela(jpeg)
        assert result["performed"] is True

    def test_png_returns_performed_false(self):
        """ELA should not be performed on PNG images (lossless)."""
        png = self._make_png()
        result = compute_ela(png)
        assert result["performed"] is False
        assert result["is_suspicious"] is False

    def test_empty_result_shape(self):
        """Empty result must have all expected keys."""
        result = _empty_result()
        expected_keys = {"performed", "max_error", "mean_error", "std_error",
                         "suspicious_ratio", "is_suspicious"}
        assert set(result.keys()) == expected_keys

    def test_solid_color_jpeg_not_suspicious(self):
        """A solid-color JPEG should not be flagged as suspicious."""
        jpeg = self._make_jpeg(color=(100, 100, 100))
        result = compute_ela(jpeg)
        assert result["performed"] is True
        # Solid color images have uniform compression — no editing signal
        assert result["is_suspicious"] is False

    def test_invalid_bytes_returns_empty(self):
        """Random bytes should return empty result (not performed)."""
        result = compute_ela(b"not an image at all")
        assert result["performed"] is False

    def test_result_types(self):
        """All result values should have correct types."""
        jpeg = self._make_jpeg()
        result = compute_ela(jpeg)
        assert isinstance(result["performed"], bool)
        assert isinstance(result["max_error"], float)
        assert isinstance(result["mean_error"], float)
        assert isinstance(result["std_error"], float)
        assert isinstance(result["suspicious_ratio"], float)
        assert isinstance(result["is_suspicious"], bool)

    def test_grayscale_jpeg(self):
        """ELA should work on grayscale JPEGs."""
        img = Image.new("L", (50, 50), 128)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        result = compute_ela(buf.getvalue())
        assert result["performed"] is True

    def test_mean_error_nonnegative(self):
        """Mean error should always be >= 0."""
        jpeg = self._make_jpeg()
        result = compute_ela(jpeg)
        assert result["mean_error"] >= 0
        assert result["max_error"] >= 0
        assert result["std_error"] >= 0

    def test_suspicious_ratio_bounded(self):
        """Suspicious ratio should be between 0 and 1."""
        jpeg = self._make_jpeg()
        result = compute_ela(jpeg)
        assert 0 <= result["suspicious_ratio"] <= 1


class TestELAEditedImage:
    """Test ELA with a synthetically edited JPEG (spliced region)."""

    def _make_edited_jpeg(self) -> bytes:
        """Create a JPEG with a spliced region that should trigger ELA.

        We create a low-quality JPEG, then paste a bright rectangle
        and re-save at a different quality — simulating editing.
        """
        # Step 1: Create and save at low quality
        img = Image.new("RGB", (200, 200), (50, 50, 50))
        buf1 = io.BytesIO()
        img.save(buf1, format="JPEG", quality=30)
        buf1.seek(0)
        
        # Step 2: Open, paste a bright block (simulating edit), re-save at high quality
        img2 = Image.open(buf1)
        # Paste a significantly different-colored rectangle
        paste_img = Image.new("RGB", (100, 100), (255, 255, 0))
        img2.paste(paste_img, (50, 50))
        buf2 = io.BytesIO()
        img2.save(buf2, format="JPEG", quality=95)
        return buf2.getvalue()

    def test_edited_jpeg_detected(self):
        """Synthetically edited JPEG should produce higher error levels."""
        edited = self._make_edited_jpeg()
        result = compute_ela(edited)
        assert result["performed"] is True
        # The max_error should be noticeable due to different compression levels
        assert result["max_error"] > 5
