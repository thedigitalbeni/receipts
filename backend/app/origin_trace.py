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
  - No API key required, no rate limit
  - Returns: archived_snapshots.closest.timestamp (yyyyMMddHHmmss)
"""

import os
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
# Wayback Machine
# ---------------------------------------------------------------------------

def _query_wayback(url: str) -> Optional[dict]:
    """Query Wayback Machine for the earliest archived snapshot of a URL.

    Args:
        url: The URL to look up.

    Returns:
        Dict with 'url', 'timestamp', 'datetime' if archived, None otherwise.
    """
    try:
        response = requests.get(
            WAYBACK_ENDPOINT,
            params={"url": url, "timestamp": "19700101"},  # earliest possible
            timeout=WAYBACK_TIMEOUT,
        )

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

        wayback = _query_wayback(link)
        enriched_match = {
            **match,
            "domain": domain,
            "wayback": wayback,
        }
        enriched.append(enriched_match)

    # Include remaining matches without Wayback data
    for match in visual_matches[MAX_WAYBACK_LOOKUPS:]:
        enriched.append({
            **match,
            "domain": urlparse(match["link"]).netloc,
            "wayback": None,
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
