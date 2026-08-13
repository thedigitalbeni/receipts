"""
Receipts — Quantization Fingerprinting & URL Date Extraction Tests

Tests:
  1. JPEG quantization table software detection
  2. URL path date extraction
  3. Snippet text date extraction
"""

import io
import pytest
from datetime import datetime, timezone

from PIL import Image

from app.forensics import detect_software_from_quantization
from app.origin_trace import _extract_date_from_url, _extract_date_from_snippet


pytestmark = pytest.mark.disable_socket


# ---------------------------------------------------------------------------
# Quantization Fingerprinting Tests
# ---------------------------------------------------------------------------

class TestQuantizationFingerprinting:
    """Tests for JPEG quantization table software detection."""

    def _make_jpeg(self, quality=85) -> bytes:
        """Create a simple JPEG at specified quality."""
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    def _make_png(self) -> bytes:
        """Create a simple PNG."""
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_png_returns_none(self):
        """PNG images have no quantization tables."""
        result = detect_software_from_quantization(self._make_png())
        assert result is None

    def test_invalid_bytes_returns_none(self):
        """Invalid bytes should return None gracefully."""
        result = detect_software_from_quantization(b"not an image")
        assert result is None

    def test_jpeg_returns_string_or_none(self):
        """JPEG should return either a software name or None."""
        result = detect_software_from_quantization(self._make_jpeg())
        assert result is None or isinstance(result, str)

    def test_very_high_quality_jpeg(self):
        """Very high quality JPEG (q=99) may trigger professional heuristic."""
        jpeg = self._make_jpeg(quality=99)
        result = detect_software_from_quantization(jpeg)
        # At q=99, Pillow uses very low quantization values
        # May or may not match — just ensure no crash
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# URL Date Extraction Tests
# ---------------------------------------------------------------------------

class TestURLDateExtraction:
    """Tests for extracting dates from URL paths."""

    def test_yyyy_mm_dd_slash(self):
        """Standard blog URL format: /2019/03/15/..."""
        result = _extract_date_from_url("https://example.com/2019/03/15/article-title")
        assert result is not None
        assert result == datetime(2019, 3, 15, tzinfo=timezone.utc)

    def test_yyyy_mm_dd_dash(self):
        """Dash-separated date: /2019-03-15/..."""
        result = _extract_date_from_url("https://example.com/blog/2019-03-15/photo")
        assert result is not None
        assert result == datetime(2019, 3, 15, tzinfo=timezone.utc)

    def test_no_date_in_url(self):
        """URL with no date pattern should return None."""
        result = _extract_date_from_url("https://example.com/photos/cat.jpg")
        assert result is None

    def test_invalid_date(self):
        """Invalid date (month 13) should return None."""
        result = _extract_date_from_url("https://example.com/2019/13/01/bad")
        assert result is None

    def test_year_only_not_matched(self):
        """URL with year only (no month/day) should not match."""
        result = _extract_date_from_url("https://example.com/2019/photos")
        assert result is None

    def test_old_date(self):
        """Date from 2005 should parse correctly."""
        result = _extract_date_from_url("https://news.com/2005/06/20/breaking")
        assert result is not None
        assert result.year == 2005
        assert result.month == 6
        assert result.day == 20


# ---------------------------------------------------------------------------
# Snippet Date Extraction Tests
# ---------------------------------------------------------------------------

class TestSnippetDateExtraction:
    """Tests for extracting dates from text snippets."""

    def test_month_day_year_format(self):
        """'March 15, 2019' format."""
        result = _extract_date_from_snippet("Published on March 15, 2019 by Reuters")
        assert result is not None
        assert result == datetime(2019, 3, 15, tzinfo=timezone.utc)

    def test_abbreviated_month(self):
        """'Mar 15, 2019' format."""
        result = _extract_date_from_snippet("Updated Mar 15, 2019")
        assert result is not None
        assert result.month == 3

    def test_day_month_year_format(self):
        """'15 March 2019' format (European)."""
        result = _extract_date_from_snippet("Article from 15 March 2019")
        assert result is not None
        assert result == datetime(2019, 3, 15, tzinfo=timezone.utc)

    def test_iso_date_format(self):
        """'2019-03-15' format."""
        result = _extract_date_from_snippet("Date: 2019-03-15 | Author: ...")
        assert result is not None
        assert result == datetime(2019, 3, 15, tzinfo=timezone.utc)

    def test_no_date_in_snippet(self):
        """Snippet without dates should return None."""
        result = _extract_date_from_snippet("Breaking news: image goes viral online")
        assert result is None

    def test_empty_snippet(self):
        """Empty string should return None."""
        result = _extract_date_from_snippet("")
        assert result is None

    def test_none_snippet(self):
        """None should return None."""
        result = _extract_date_from_snippet(None)
        assert result is None

    def test_multiple_dates_returns_earliest(self):
        """Multiple dates in snippet should return the earliest."""
        result = _extract_date_from_snippet(
            "Originally published January 5, 2018. Updated March 15, 2019."
        )
        assert result is not None
        assert result == datetime(2018, 1, 5, tzinfo=timezone.utc)
