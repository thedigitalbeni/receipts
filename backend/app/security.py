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
import re
import socket
from urllib.parse import urlparse, urljoin

import httpx
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_HTML_FETCH_BYTES = 2 * 1024 * 1024    # 2 MB
HTML_FETCH_TIMEOUT_SECS = 3.0

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
# Magic Byte Image Sniffing
# ---------------------------------------------------------------------------

def _is_image_bytes(chunk: bytes) -> bool:
    """Check initial magic bytes for known image formats."""
    if len(chunk) < 4:
        return False
    # JPEG: starts with \xFF\xD8\xFF
    if chunk.startswith(b"\xff\xd8\xff"):
        return True
    # PNG: starts with \x89PNG\r\n\x1a\n
    if chunk.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    # WebP: RIFF....WEBP
    if chunk.startswith(b"RIFF") and len(chunk) >= 12 and chunk[8:12] == b"WEBP":
        return True
    # GIF: GIF87a or GIF89a
    if chunk.startswith(b"GIF87a") or chunk.startswith(b"GIF89a"):
        return True
    # HEIC / HEIF / AVIF: ftypheic, ftypmif1, ftypmsf1, ftypheix, ftypavif
    if len(chunk) >= 12 and chunk[4:8] == b"ftyp":
        brand = chunk[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1", b"avif"):
            return True
    return False


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
# URL Content-Type & Magic Byte Validation
# ---------------------------------------------------------------------------

async def validate_url_content_type(url: str) -> None:
    """Validate that a URL points directly to an image, not a webpage.

    Strategy:
    1. Issue HTTP HEAD request. If 200 and Content-Type starts with 'image/', pass immediately.
    2. If HEAD returns 403, 400, 404, 405, redirects, or non-image content-type (common on CDNs),
       fall back to streaming the first chunk (up to 4096 bytes) via GET.
    3. Verify Content-Type header OR image magic bytes on the first chunk.
    """
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=False,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    ) as client:
        redirects = 0
        current_url = url
        while redirects <= 5:
            # Step 1: Try HEAD probe first
            try:
                head_resp = await client.head(current_url)
                if head_resp.status_code in (301, 302, 303, 307, 308) and "location" in head_resp.headers:
                    next_url = urljoin(current_url, head_resp.headers["location"])
                    current_url = validate_url_scheme_and_resolve(next_url)
                    redirects += 1
                    continue

                if head_resp.status_code == 200:
                    ct = head_resp.headers.get("content-type", "").strip().lower()
                    if ct.startswith("image/"):
                        return
            except httpx.HTTPError:
                pass

            # Step 2: Fallback to streaming initial bytes via GET
            try:
                async with client.stream("GET", current_url) as stream_resp:
                    if stream_resp.status_code in (301, 302, 303, 307, 308) and "location" in stream_resp.headers:
                        next_url = urljoin(current_url, stream_resp.headers["location"])
                        current_url = validate_url_scheme_and_resolve(next_url)
                        redirects += 1
                        continue

                    stream_resp.raise_for_status()
                    ct = stream_resp.headers.get("content-type", "").strip().lower()
                    if ct.startswith("image/"):
                        return

                    # Read first chunk to check magic bytes
                    first_chunk = b""
                    async for chunk in stream_resp.aiter_bytes(chunk_size=4096):
                        first_chunk = chunk
                        break

                    if _is_image_bytes(first_chunk):
                        return

                    raise InputValidationError(
                        f"URL must point directly to an image file, not a webpage. Got: {ct or 'non-image'}"
                    )
            except httpx.HTTPError as e:
                raise InputValidationError(f"Could not connect to image URL: {e}")

        raise InputValidationError("Too many redirects")


# ---------------------------------------------------------------------------
# URL Image Download (with SSRF check and urljoin redirects)
# ---------------------------------------------------------------------------

async def download_image_from_url(url: str) -> bytes:
    """Download image bytes from a validated URL.

    SSRF validation and content-type checks must be performed BEFORE
    calling this function. This function enforces the 15 MB size limit
    via streaming to avoid loading oversized files into memory.
    """
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=False,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    ) as client:
        redirects = 0
        current_url = url
        while redirects <= 5:
            async with client.stream("GET", current_url) as response:
                if response.status_code in (301, 302, 303, 307, 308) and "location" in response.headers:
                    next_url = urljoin(current_url, response.headers["location"])
                    current_url = validate_url_scheme_and_resolve(next_url)
                    redirects += 1
                    continue
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
        raise InputValidationError("Too many redirects")


# ---------------------------------------------------------------------------
# Social Link Extraction
# ---------------------------------------------------------------------------

async def extract_social_image_url(url: str) -> str:
    """Fetch HTML from URL and extract og:image or twitter:image.
    
    Assumes SSRF validation (validate_url_scheme_and_resolve) has already
    been performed on the URL.
    """
    html_content = b""
    async with httpx.AsyncClient(
        timeout=HTML_FETCH_TIMEOUT_SECS,
        follow_redirects=False,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    ) as client:
        try:
            redirects = 0
            current_url = url
            while redirects <= 5:
                async with client.stream("GET", current_url) as response:
                    if response.status_code in (301, 302, 303, 307, 308) and "location" in response.headers:
                        next_url = urljoin(current_url, response.headers["location"])
                        current_url = validate_url_scheme_and_resolve(next_url)
                        redirects += 1
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type.lower():
                        raise InputValidationError(f"Expected HTML page for social link extraction, got {content_type}")
                    
                    total = 0
                    chunks = []
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        total += len(chunk)
                        if total > MAX_HTML_FETCH_BYTES:
                            raise InputValidationError(
                                f"HTML content too large: exceeds {MAX_HTML_FETCH_BYTES} byte limit"
                            )
                        chunks.append(chunk)
                    html_content = b"".join(chunks)
                    break
            if redirects > 5:
                raise InputValidationError("Too many redirects")
        except httpx.HTTPError as e:
            raise InputValidationError(f"Could not fetch HTML: {e}")
            
    html_text = html_content.decode("utf-8", errors="ignore")
    
    # Match <meta property="og:image" content="..."> or name="twitter:image"
    og_match = re.search(
        r'<meta[^>]+(?:property|name)=[\'"]?(?:og:image|twitter:image)[\'"]?[^>]*content=[\'"]([^\'"]+)[\'"]',
        html_text, re.IGNORECASE
    )
    if og_match:
        return urljoin(current_url, og_match.group(1).replace("&amp;", "&"))
        
    # Match <meta content="..." property="og:image">
    og_match_rev = re.search(
        r'<meta[^>]*content=[\'"]([^\'"]+)[\'"][^>]+(?:property|name)=[\'"]?(?:og:image|twitter:image)[\'"]?',
        html_text, re.IGNORECASE
    )
    if og_match_rev:
        return urljoin(current_url, og_match_rev.group(1).replace("&amp;", "&"))
        
    raise InputValidationError("No social image metadata found in HTML.")

