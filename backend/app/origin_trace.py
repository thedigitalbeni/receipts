"""
Receipts — Origin Trace Module (M5)

Performs reverse image search via SerpApi Google Lens, then chains each
matched URL through the Wayback Machine Availability API to retrieve its
earliest archived timestamp. The combined result is the origin_trace
evidence object consumed by the rules engine.

SerpApi Free Tier (verified 2026-08-04 at serpapi.com/pricing):
  - 250 searches per month
  - 50 throughput per hour

Caching Strategy:
  Results are cached permanently by SHA-256 in Supabase. Once cached,
  they are never automatically refreshed or expired. This is the primary
  defense against the limited free-tier quota and API unavailability
  during demo recording.

SerpApi Google Lens API:
  - Endpoint: https://serpapi.com/search
  - engine: "google_lens"
  - url: <publicly accessible image URL>
  - Returns: visual_matches[] with link, source, title, thumbnail, position

Wayback Machine Availability API:
  - Endpoint: https://archive.org/wayback/available?url=<url>
  - No API key required, rate-limited (respect with delays)
  - Returns: archived_snapshots.closest.timestamp (yyyyMMddHHmmss)
"""

import os
import re
import time
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SERPAPI_ENDPOINT = "https://serpapi.com/search"
WAYBACK_ENDPOINT = "https://archive.org/wayback/available"

# Timeouts (seconds)
SERPAPI_TIMEOUT = 15
WAYBACK_TIMEOUT = 10

# Maximum number of visual matches to chain through Wayback
MAX_WAYBACK_LOOKUPS = 5

# Delay between Wayback requests to avoid HTTP 429 rate limiting
WAYBACK_DELAY_SECS = 3.0


def _get_serpapi_key() -> Optional[str]:
    """Read SerpApi key from environment."""
    return os.environ.get("SERPAPI_API_KEY")


# ---------------------------------------------------------------------------
# SerpApi Google Lens
# ---------------------------------------------------------------------------

def _query_serpapi_lens(image_url: str, api_key: str) -> dict:
    """Query SerpApi Google Lens for visual matches.

    Args:
        image_url: Publicly accessible URL of the image to search.
        api_key: SerpApi API key.

    Returns:
        Raw SerpApi JSON response as a dictionary.

    Raises:
        requests.RequestException: On network/HTTP errors.
        ValueError: On non-200 response or missing data.
    """
    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": api_key,
        "no_cache": "false",  # Use SerpApi's own cache to save quota
    }

    response = requests.get(
        SERPAPI_ENDPOINT,
        params=params,
        timeout=SERPAPI_TIMEOUT,
    )

    if response.status_code != 200:
        raise ValueError(
            f"SerpApi returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response.json()


def _extract_visual_matches(serpapi_response: dict) -> list[dict]:
    """Extract and normalize visual matches from SerpApi response.

    Returns a list of dicts with keys: link, source, title, thumbnail, position.
    """
    matches = serpapi_response.get("visual_matches", [])
    results = []

    for match in matches:
        link = match.get("link", "")
        if not link:
            continue

        results.append({
            "link": link,
            "source": match.get("source", ""),
            "title": match.get("title", ""),
            "thumbnail": match.get("thumbnail", ""),
            "position": match.get("position", 0),
        })

    return results


# ---------------------------------------------------------------------------
# URL / Snippet Date Extraction (Wayback fallback)
# ---------------------------------------------------------------------------

# Regex for dates in URL paths: /2019/03/15/ or /2019-03-15/
_URL_DATE_PATTERN = re.compile(
    r'/(?P<year>(?:19|20)\d{2})[/-](?P<month>0[1-9]|1[0-2])[/-](?P<day>0[1-9]|[12]\d|3[01])'
)

# Regex for dates in snippet text: "March 15, 2019" or "15 Mar 2019" or "2019-03-15"
_SNIPPET_DATE_PATTERNS = [
    # "March 15, 2019" or "Mar 15, 2019"
    re.compile(
        r'(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+(?P<day>\d{1,2}),?\s+(?P<year>(?:19|20)\d{2})',
        re.IGNORECASE,
    ),
    # "15 March 2019" or "15 Mar 2019"
    re.compile(
        r'(?P<day>\d{1,2})\s+'
        r'(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
        r'\s+(?P<year>(?:19|20)\d{2})',
        re.IGNORECASE,
    ),
    # ISO: "2019-03-15"
    re.compile(
        r'(?P<year>(?:19|20)\d{2})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12]\d|3[01])'
    ),
]

_MONTH_MAP = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
    'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
    'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}


def _extract_date_from_url(url: str) -> Optional[datetime]:
    """Extract a publication date from a URL path pattern.

    Looks for patterns like /2019/03/15/ or /2019-03-15/ in the URL path.
    Returns a timezone-aware datetime if found, None otherwise.
    """
    match = _URL_DATE_PATTERN.search(url)
    if not match:
        return None

    try:
        year = int(match.group('year'))
        month = int(match.group('month'))
        day = int(match.group('day'))
        return datetime(year, month, day, tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def _extract_date_from_snippet(snippet: str) -> Optional[datetime]:
    """Extract the earliest date from a text snippet.

    Tries multiple date formats commonly found in article snippets.
    Returns a timezone-aware datetime if found, None otherwise.
    """
    if not snippet:
        return None

    earliest: Optional[datetime] = None

    for pattern in _SNIPPET_DATE_PATTERNS:
        for match in pattern.finditer(snippet):
            try:
                year_str = match.group('year')
                month_str = match.group('month')
                day_str = match.group('day')

                year = int(year_str)
                day = int(day_str)

                # Month can be numeric or text
                if month_str.isdigit():
                    month = int(month_str)
                else:
                    month = _MONTH_MAP.get(month_str.lower())
                    if not month:
                        continue

                dt = datetime(year, month, day, tzinfo=timezone.utc)
                if earliest is None or dt < earliest:
                    earliest = dt
            except (ValueError, OverflowError):
                continue

    return earliest


# ---------------------------------------------------------------------------
# Wayback Machine
# ---------------------------------------------------------------------------

def _query_wayback(url: str) -> Optional[dict]:
    """Query Wayback Machine for the earliest archived snapshot of a URL.

    Args:
        url: The URL to look up.

    Returns:
        Dict with 'url', 'timestamp', 'datetime' if archived, None otherwise.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(
                WAYBACK_ENDPOINT,
                params={"url": url, "timestamp": "19700101"},  # earliest possible
                timeout=WAYBACK_TIMEOUT,
            )

            if response.status_code == 429 and attempt < max_retries - 1:
                logger.warning(f"Wayback rate limited (429) for {url}, retrying in {2 ** attempt}s...")
                time.sleep(2 ** attempt)
                continue

            if response.status_code != 200:
                logger.warning(f"Wayback returned HTTP {response.status_code} for {url}")
                return None

            data = response.json()
            snapshots = data.get("archived_snapshots", {})
            closest = snapshots.get("closest")

            if not closest or not closest.get("available"):
                return None

            # Parse timestamp (format: yyyyMMddHHmmss)
            ts_str = closest.get("timestamp", "")
            try:
                dt = datetime.strptime(ts_str, "%Y%m%d%H%M%S").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                dt = None

            return {
                "url": closest.get("url", ""),
                "timestamp": ts_str,
                "datetime": dt.isoformat() if dt else None,
            }

        except requests.RequestException as e:
            logger.warning(f"Wayback request failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None


# ---------------------------------------------------------------------------
# Combined Pipeline
# ---------------------------------------------------------------------------

def _chain_wayback_lookups(visual_matches: list[dict]) -> list[dict]:
    """For each visual match, query Wayback Machine for earliest snapshot.

    Limits to MAX_WAYBACK_LOOKUPS to avoid excessive requests.
    Adds 'wayback' key to each match dict.
    """
    enriched = []

    for i, match in enumerate(visual_matches[:MAX_WAYBACK_LOOKUPS]):
        link = match["link"]
        domain = urlparse(link).netloc

        # Rate-limit Wayback requests to avoid HTTP 429
        if i > 0:
            time.sleep(WAYBACK_DELAY_SECS)

        wayback = _query_wayback(link)

        # Fallback: extract date from URL path if Wayback returned nothing
        url_date = None
        if not wayback:
            extracted = _extract_date_from_url(link)
            if not extracted:
                # Try snippet/title text
                extracted = _extract_date_from_snippet(match.get("title", ""))
            if extracted:
                url_date = extracted.isoformat()

        enriched_match = {
            **match,
            "domain": domain,
            "wayback": wayback,
            "url_date": url_date,
        }
        enriched.append(enriched_match)

    # Include remaining matches without Wayback data
    for match in visual_matches[MAX_WAYBACK_LOOKUPS:]:
        link = match["link"]
        url_date = None
        extracted = _extract_date_from_url(link)
        if not extracted:
            extracted = _extract_date_from_snippet(match.get("title", ""))
        if extracted:
            url_date = extracted.isoformat()

        enriched.append({
            **match,
            "domain": urlparse(link).netloc,
            "wayback": None,
            "url_date": url_date,
        })

    return enriched


def _find_earliest_appearance(enriched_matches: list[dict]) -> Optional[dict]:
    """Find the match with the earliest Wayback timestamp.

    Returns the enriched match dict, or None if no Wayback data exists.
    """
    earliest = None
    earliest_ts = None

    for match in enriched_matches:
        wb = match.get("wayback")
        if wb and wb.get("timestamp"):
            ts = wb["timestamp"]
            if earliest_ts is None or ts < earliest_ts:
                earliest_ts = ts
                earliest = match

    return earliest


def _safe_fallback() -> dict:
    """Return a safe fallback origin_trace when the API is unavailable.

    The rules engine must handle this gracefully — it means no origin
    data is available, which maps to no Rule 3 evidence.
    """
    return {
        "has_matches": False,
        "match_count": 0,
        "visual_matches": [],
        "earliest_appearance": None,
        "error": None,
        "api_used": False,
    }


def query_origin_trace(image_url: str) -> dict:
    """Perform the full origin trace pipeline: SerpApi Lens + Wayback.

    This is the live API call. For cached lookups, use get_origin_trace().

    Args:
        image_url: Publicly accessible URL of the image to search.

    Returns:
        Structured origin_trace dictionary:
          - has_matches: bool — whether any visual matches were found
          - match_count: int — number of visual matches
          - visual_matches: list — enriched matches with Wayback data
          - earliest_appearance: dict | None — the match with earliest Wayback ts
          - error: str | None — error message if the API call failed
          - api_used: bool — whether a real API call was made
    """
    api_key = _get_serpapi_key()
    if not api_key:
        logger.error("SERPAPI_API_KEY not set in environment")
        result = _safe_fallback()
        result["error"] = "SERPAPI_API_KEY not configured"
        return result

    try:
        # Step 1: SerpApi Google Lens
        serpapi_response = _query_serpapi_lens(image_url, api_key)
        visual_matches = _extract_visual_matches(serpapi_response)

        if not visual_matches:
            return {
                "has_matches": False,
                "match_count": 0,
                "visual_matches": [],
                "earliest_appearance": None,
                "error": None,
                "api_used": True,
            }

        # Step 2: Chain Wayback Machine lookups
        enriched = _chain_wayback_lookups(visual_matches)

        # Step 3: Find earliest appearance
        earliest = _find_earliest_appearance(enriched)

        return {
            "has_matches": True,
            "match_count": len(enriched),
            "visual_matches": enriched,
            "earliest_appearance": earliest,
            "error": None,
            "api_used": True,
        }

    except Exception as e:
        logger.error(f"Origin trace failed: {e}")
        result = _safe_fallback()
        result["error"] = str(e)
        return result


def get_origin_trace_summary(origin_trace: dict) -> dict:
    """Extract a rules-engine-friendly summary from origin_trace data.

    Returns:
        - has_online_matches: bool — whether any visual matches exist
        - earliest_timestamp: str | None — ISO timestamp of earliest Wayback hit
        - earliest_url: str | None — URL of earliest match
        - earliest_domain: str | None — domain of earliest match
        - match_count: int — total number of visual matches
    """
    earliest = origin_trace.get("earliest_appearance")

    if earliest and earliest.get("wayback"):
        wb = earliest["wayback"]
        return {
            "has_online_matches": True,
            "earliest_timestamp": wb.get("datetime"),
            "earliest_url": earliest.get("link", ""),
            "earliest_domain": earliest.get("domain", ""),
            "match_count": origin_trace.get("match_count", 0),
        }

    return {
        "has_online_matches": origin_trace.get("has_matches", False),
        "earliest_timestamp": None,
        "earliest_url": None,
        "earliest_domain": None,
        "match_count": origin_trace.get("match_count", 0),
    }


# ---------------------------------------------------------------------------
# Frozen Contract Adapter (Section 2 → OriginTraceEvidence)
# ---------------------------------------------------------------------------
#
# STAGED ASSEMBLY NOTE:
# query_origin_trace() returns an internal shape optimized for the live
# pipeline ({has_matches, match_count, visual_matches, earliest_appearance,
# error, api_used}). The frozen Section 2 contract defines a different
# public shape ({serpapi_status, wayback_status, results}) via the
# OriginTraceEvidence Pydantic model in schemas.py.
#
# to_frozen_contract() maps the internal shape → frozen contract shape.
# This adapter is called by M7's Evidence Aggregation stage. It is NOT
# a contract violation — just staged assembly: M5 builds the raw data,
# M7 maps it into the frozen shape.
#
# MAPPING:
#   internal.api_used + internal.error → serpapi_status (success|error|not_called)
#   internal.earliest_appearance != None → wayback_status (success|error|not_called)
#   internal.visual_matches[].{link, domain, wayback.datetime} → results[]
#
# RULE 3 MATCHING CLARIFICATION:
# The plan's wording "pHash match indexed > 1 year ago" does NOT mean
# M3's local compute_phash()/is_phash_match() is re-run against
# downloaded copies of SerpApi's matched images. Rule 3 in M6 should
# be implemented as:
#   "SerpApi Google Lens found a visual match AND its corresponding
#    Wayback timestamp is more than 1 year old"
# SerpApi's own visual matching algorithm replaces the plan's literal
# "pHash match" language. Local pHash (M3) is used only for
# duplicate_detection against the receipts database, not for origin trace.
# ---------------------------------------------------------------------------

def to_frozen_contract(internal: dict) -> dict:
    """Map internal query_origin_trace() result → frozen OriginTraceEvidence shape.

    The returned dict matches the OriginTraceEvidence Pydantic model
    from schemas.py (Section 2 frozen contract):
        serpapi_status: "success" | "timeout" | "error" | "not_called"
        wayback_status: "success" | "timeout" | "error" | "not_called"
        results: [{url, domain, earliest_wayback_timestamp}, ...]

    Args:
        internal: Return value from query_origin_trace().

    Returns:
        Dict conforming to OriginTraceEvidence shape.
    """
    # --- serpapi_status ---
    if not internal.get("api_used", False):
        error_msg = internal.get("error", "")
        if "not configured" in str(error_msg):
            serpapi_status = "not_called"
        elif "timeout" in str(error_msg).lower() or "timed out" in str(error_msg).lower():
            serpapi_status = "timeout"
        else:
            serpapi_status = "error"
    else:
        serpapi_status = "success"

    # --- wayback_status ---
    has_any_wayback = False
    for match in internal.get("visual_matches", []):
        if match.get("wayback"):
            has_any_wayback = True
            break

    if not internal.get("api_used", False):
        wayback_status = "not_called"
    elif has_any_wayback:
        wayback_status = "success"
    elif internal.get("has_matches", False):
        # SerpApi found matches but Wayback had no data for any of them
        wayback_status = "error"
    else:
        wayback_status = "not_called"

    # --- results ---
    results = []
    all_domains = set()
    for match in internal.get("visual_matches", []):
        wb = match.get("wayback")
        domain = match.get("domain", "")
        if domain:
            all_domains.add(domain)
        results.append({
            "url": match.get("link", ""),
            "domain": domain,
            "earliest_wayback_timestamp": wb.get("datetime") if wb else None,
            "earliest_url_date": match.get("url_date"),
        })

    return {
        "serpapi_status": serpapi_status,
        "wayback_status": wayback_status,
        "results": results,
        "match_count": internal.get("match_count", 0),
        "unique_domains": len(all_domains),
    }

