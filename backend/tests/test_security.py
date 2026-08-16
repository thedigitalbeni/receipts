"""
Receipts — Security & Input Validation Unit Tests
"""

import io
import pytest
from PIL import Image

from app.security import (
    _is_image_bytes,
    _is_ip_blocked,
    validate_image,
    validate_upload_size,
    InputValidationError,
)

pytestmark = pytest.mark.disable_socket


class TestSecurityValidation:

    def test_magic_bytes_detection(self):
        """Test magic byte image sniffer on various formats."""
        # JPEG
        assert _is_image_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")
        # PNG
        assert _is_image_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        # WebP
        assert _is_image_bytes(b"RIFF\x20\x00\x00\x00WEBPVP8 ")
        # GIF
        assert _is_image_bytes(b"GIF89a\x01\x00\x01\x00")
        # HEIC
        assert _is_image_bytes(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00")
        # Non-image HTML / text
        assert not _is_image_bytes(b"<!DOCTYPE html><html>")
        assert not _is_image_bytes(b"{\"error\": \"forbidden\"}")
        assert not _is_image_bytes(b"")

    def test_ssrf_blocked_ips(self):
        """Test private/reserved IP blocking."""
        assert _is_ip_blocked("127.0.0.1")
        assert _is_ip_blocked("10.0.0.1")
        assert _is_ip_blocked("192.168.1.1")
        assert _is_ip_blocked("172.16.0.1")
        assert _is_ip_blocked("169.254.169.254")
        assert _is_ip_blocked("::1")
        # Public IP should not be blocked
        assert not _is_ip_blocked("8.8.8.8")
        assert not _is_ip_blocked("104.26.12.31")

    def test_validate_upload_size(self):
        """Test upload size limit enforcement."""
        def _run(coro):
            try:
                coro.send(None)
            except StopIteration as e:
                return e.value

        # Under limit
        _run(validate_upload_size(1000, b"x" * 1000))
        # Over limit
        with pytest.raises(InputValidationError):
            _run(validate_upload_size(16 * 1024 * 1024, b"x"))
        with pytest.raises(InputValidationError):
            _run(validate_upload_size(None, b"x" * (16 * 1024 * 1024)))

    def test_validate_image_valid_and_invalid(self):
        """Test Pillow image validation."""
        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        valid_bytes = buf.getvalue()

        # Should pass
        validate_image(valid_bytes)

        # Invalid bytes should raise InputValidationError
        with pytest.raises(InputValidationError):
            validate_image(b"not an image at all")
