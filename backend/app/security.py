"""
Receipts — Input Security Module (M2: Storage Security & Input Validation)

Implements the three Pipeline Input Security requirements from Section 5:
  1. Upload Size Limit (15 MB, rejected before Pillow)
  2. Image Validation (genuine image check via Pillow .verify())
  3. Baseline SSRF Protection (DNS-resolved IP range blocking)

Plus the URL Edge Case validation (HEAD → fallback GET with Range header).

IMPORTANT — Baseline SSRF Protection scope limitation:
This implementation mitigates standard hostname-based and direct-IP SSRF
attacks. It does NOT fully close DNS-rebinding attacks, which would require
pinning the validated resolved IP for the actual outbound connection — this
is explicitly out of scope for this prototype given the timeline, and must
not be described as complete DNS-rebinding protection in any code comments,
documentation, or the pitch materials.
"""

from __future__ import annotations

import io
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB

# Private/reserved IP networks to block for SSRF protection.
# Checked AFTER DNS resolution, not by string-matching hostnames.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),         # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),      # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),     # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local / cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]


class InputValidationError(Exception):
    """Raised when input validation fails. Message is safe to return to client."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ---------------------------------------------------------------------------
# 1. Upload Size Limit
# ---------------------------------------------------------------------------

async def validate_upload_size(content_length: int | None, file_bytes: bytes) -> None:
    """Reject uploads larger than 15 MB BEFORE loading into Pillow.

    Checks Content-Length header first (fast reject), then verifies
    actual byte count as a fallback (Content-Length can be spoofed).
    """
    if content_length is not None and content_length > MAX_UPLOAD_SIZE_BYTES:
        raise InputValidationError(
            f"File too large: {content_length} bytes exceeds "
            f"{MAX_UPLOAD_SIZE_BYTES} byte limit"
        )
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise InputValidationError(
            f"File too large: {len(file_bytes)} bytes exceeds "
            f"{MAX_UPLOAD_SIZE_BYTES} byte limit"
        )


# ---------------------------------------------------------------------------
# 2. Image Validation
# ---------------------------------------------------------------------------

def validate_image(file_bytes: bytes) -> None:
    """Verify the uploaded file is a genuine, well-formed image.

    Uses Pillow's Image.open() followed by .verify() for format validation.
    Malformed or unsupported files raise InputValidationError (→ HTTP 400),
    never an unhandled exception (→ crash is a failure condition).
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
    except (Image.UnidentifiedImageError, SyntaxError, OSError, Exception) as e:
        raise InputValidationError(
            f"Invalid or unsupported image file: {type(e).__name__}"
        )


# ---------------------------------------------------------------------------
# 3. Baseline SSRF Protection
# ---------------------------------------------------------------------------

def _is_ip_blocked(ip_str: str) -> bool:
    """Check if a resolved IP address falls in a blocked network range."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        # If we can't parse the IP, block it defensively.
        return True
    return any(addr in network for network in _BLOCKED_NETWORKS)


def validate_url_scheme_and_resolve(url: str) -> str:
    """Validate URL scheme and check resolved IP against blocked ranges.

    Returns the validated URL (unchanged). Raises InputValidationError
    if the URL uses a non-http(s) scheme or resolves to a blocked IP.

    This check happens AFTER DNS resolution to prevent hostname-based
    SSRF bypass. It does NOT pin the resolved IP for the subsequent
    connection (DNS-rebinding protection is out of scope — see module
    docstring).
    """
    parsed = urlparse(url)

    # Reject non-http(s) schemes
    if parsed.scheme not in ("http", "https"):
        raise InputValidationError(
            f"URL scheme '{parsed.scheme}' is not allowed. "
            "Only http and https URLs are accepted."
        )

    hostname = parsed.hostname
    if not hostname:
        raise InputValidationError("URL has no hostname")

    # Resolve DNS and check all returned IPs
    try:
        addrinfos = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise InputValidationError(f"Could not resolve hostname: {hostname}")

    if not addrinfos:
        raise InputValidationError(f"No DNS records found for: {hostname}")

    for family, type_, proto, canonname, sockaddr in addrinfos:
        ip_str = sockaddr[0]
        if _is_ip_blocked(ip_str):
            raise InputValidationError(
                f"URL resolves to a blocked IP address range"
            )

    return url


# ---------------------------------------------------------------------------
# URL Content-Type Validation (HEAD → fallback GET with Range)
# ---------------------------------------------------------------------------

async def validate_url_content_type(url: str) -> None:
    """Validate that a URL points directly to an image, not a webpage.

    Strategy (per Section 5 Input Validation URL Edge Case):
    1. Issue HTTP HEAD request to check Content-Type.
    2. If HEAD returns 405 or Content-Type is missing/malformed,
       fall back to GET with Range: bytes=0-1023.
    3. If neither yields Content-Type starting with "image/",
       raise InputValidationError (→ HTTP 400).
    """
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        content_type = None

        # Step 1: Try HEAD
        try:
            head_resp = await client.head(url)
            if head_resp.status_code != 405:
                content_type = head_resp.headers.get("content-type", "")
        except httpx.HTTPError:
            pass

        # Step 2: Fallback to GET with Range if HEAD failed or returned 405
        if not content_type:
            try:
                get_resp = await client.get(
                    url,
                    headers={"Range": "bytes=0-1023"},
                )
                content_type = get_resp.headers.get("content-type", "")
            except httpx.HTTPError:
                raise InputValidationError(
                    "Could not determine content type of URL"
                )

        # Step 3: Check Content-Type
        if not content_type or not content_type.strip().lower().startswith("image/"):
            raise InputValidationError(
                "URL must point directly to an image file, not a webpage."
            )


# ---------------------------------------------------------------------------
# URL Image Download (with SSRF check already applied)
# ---------------------------------------------------------------------------

async def download_image_from_url(url: str) -> bytes:
    """Download image bytes from a validated URL.

    SSRF validation and content-type checks must be performed BEFORE
    calling this function. This function enforces the 15 MB size limit
    via streaming to avoid loading oversized files into memory.
    """
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks = []
            total = 0
            async for chunk in response.aiter_bytes(chunk_size=8192):
                total += len(chunk)
                if total > MAX_UPLOAD_SIZE_BYTES:
                    raise InputValidationError(
                        f"Remote file too large: exceeds "
                        f"{MAX_UPLOAD_SIZE_BYTES} byte limit"
                    )
                chunks.append(chunk)
            return b"".join(chunks)
