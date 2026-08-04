"""
Receipts — Origin Trace Smoke Tests (M5)

Tests the origin trace module using mocked SerpApi and Wayback Machine
responses. No real API calls are made — all network access is blocked
by pytest-socket.

Tests verify:
  1. SerpApi response parsing and visual match extraction
  2. Wayback Machine response parsing and timestamp extraction
  3. Full pipeline with mocked responses
  4. Graceful fallback on API key missing
  5. Graceful fallback on API errors
  6. Summary extraction for rules engine
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from app.origin_trace import (
    _extract_visual_matches,
    _find_earliest_appearance,
    _chain_wayback_lookups,
    _safe_fallback,
    query_origin_trace,
    get_origin_trace_summary,
)


# ---------------------------------------------------------------------------
# Mock Data Fixtures
# ---------------------------------------------------------------------------

MOCK_SERPAPI_RESPONSE = {
    "search_metadata": {
        "id": "test_search_id",
        "status": "Success",
        "json_endpoint": "https://serpapi.com/searches/test.json",
    },
    "visual_matches": [
        {
            "position": 1,
            "title": "Fact-Checked Image - Reuters",
            "link": "https://www.reuters.com/article/fact-check-old-photo",
            "source": "Reuters",
            "thumbnail": "https://example.com/thumb1.jpg",
        },
        {
            "position": 2,
            "title": "Original Photo from 2019 - AP News",
            "link": "https://apnews.com/article/original-photo-2019",
            "source": "AP News",
            "thumbnail": "https://example.com/thumb2.jpg",
        },
        {
            "position": 3,
            "title": "Viral Image Discussion - Reddit",
            "link": "https://www.reddit.com/r/pics/comments/viral_image",
            "source": "Reddit",
            "thumbnail": "https://example.com/thumb3.jpg",
        },
    ],
}

MOCK_SERPAPI_EMPTY = {
    "search_metadata": {"status": "Success"},
    "visual_matches": [],
}

MOCK_WAYBACK_HIT_OLD = {
    "url": "https://www.reuters.com/article/fact-check-old-photo",
    "archived_snapshots": {
        "closest": {
            "status": "200",
            "available": True,
            "url": "https://web.archive.org/web/20190315120000/https://www.reuters.com/article/fact-check-old-photo",
            "timestamp": "20190315120000",
        }
    },
}

MOCK_WAYBACK_HIT_RECENT = {
    "url": "https://apnews.com/article/original-photo-2019",
    "archived_snapshots": {
        "closest": {
            "status": "200",
            "available": True,
            "url": "https://web.archive.org/web/20240101000000/https://apnews.com/article/original-photo-2019",
            "timestamp": "20240101000000",
        }
    },
}

MOCK_WAYBACK_MISS = {
    "url": "https://www.reddit.com/r/pics/comments/viral_image",
    "archived_snapshots": {},
}


# ---------------------------------------------------------------------------
# Visual Match Extraction Tests
# ---------------------------------------------------------------------------

class TestVisualMatchExtraction:
    """Tests for extracting and normalizing visual matches from SerpApi."""

    def test_extracts_all_matches(self):
        """Should extract all visual matches with required fields."""
        matches = _extract_visual_matches(MOCK_SERPAPI_RESPONSE)
        assert len(matches) == 3

    def test_extracts_link_field(self):
        """Each match must have a non-empty link."""
        matches = _extract_visual_matches(MOCK_SERPAPI_RESPONSE)
        for match in matches:
            assert match["link"] != ""

    def test_extracts_source_and_title(self):
        """Each match must have source and title fields."""
        matches = _extract_visual_matches(MOCK_SERPAPI_RESPONSE)
        assert matches[0]["source"] == "Reuters"
        assert "Reuters" in matches[0]["title"]

    def test_handles_empty_response(self):
        """Empty visual_matches should return empty list."""
        matches = _extract_visual_matches(MOCK_SERPAPI_EMPTY)
        assert matches == []

    def test_handles_missing_key(self):
        """Missing visual_matches key should return empty list."""
        matches = _extract_visual_matches({})
        assert matches == []

    def test_skips_matches_without_link(self):
        """Matches without a link should be skipped."""
        response = {
            "visual_matches": [
                {"title": "No Link", "source": "Test"},
                {"title": "Has Link", "link": "https://example.com", "source": "Test"},
            ]
        }
        matches = _extract_visual_matches(response)
        assert len(matches) == 1
        assert matches[0]["link"] == "https://example.com"


# ---------------------------------------------------------------------------
# Wayback Chaining Tests
# ---------------------------------------------------------------------------

class TestWaybackChaining:
    """Tests for Wayback Machine lookup chaining."""

    def test_find_earliest_appearance(self):
        """Should find the match with the earliest Wayback timestamp."""
        enriched = [
            {"link": "a", "wayback": {"timestamp": "20240101000000", "datetime": "2024-01-01T00:00:00+00:00"}},
            {"link": "b", "wayback": {"timestamp": "20190315120000", "datetime": "2019-03-15T12:00:00+00:00"}},
            {"link": "c", "wayback": None},
        ]
        earliest = _find_earliest_appearance(enriched)
        assert earliest is not None
        assert earliest["link"] == "b"

    def test_find_earliest_no_wayback_data(self):
        """Should return None when no Wayback data exists."""
        enriched = [
            {"link": "a", "wayback": None},
            {"link": "b", "wayback": None},
        ]
        earliest = _find_earliest_appearance(enriched)
        assert earliest is None

    def test_find_earliest_single_match(self):
        """Should work with a single match."""
        enriched = [
            {"link": "a", "wayback": {"timestamp": "20200601000000", "datetime": "2020-06-01T00:00:00+00:00"}},
        ]
        earliest = _find_earliest_appearance(enriched)
        assert earliest["link"] == "a"


# ---------------------------------------------------------------------------
# Safe Fallback Tests
# ---------------------------------------------------------------------------

class TestSafeFallback:
    """Tests for the safe fallback dictionary."""

    def test_fallback_structure(self):
        """Fallback must have all expected keys."""
        fallback = _safe_fallback()
        assert fallback["has_matches"] is False
        assert fallback["match_count"] == 0
        assert fallback["visual_matches"] == []
        assert fallback["earliest_appearance"] is None
        assert fallback["error"] is None
        assert fallback["api_used"] is False


# ---------------------------------------------------------------------------
# Full Pipeline Tests (Mocked)
# ---------------------------------------------------------------------------

class TestOriginTracePipeline:
    """Tests for the full origin trace pipeline with mocked API calls."""

    @patch("app.origin_trace._get_serpapi_key", return_value=None)
    def test_no_api_key_returns_fallback(self, mock_key):
        """Missing API key should return safe fallback with error message."""
        result = query_origin_trace("https://example.com/image.jpg")
        assert result["has_matches"] is False
        assert result["api_used"] is False
        assert "not configured" in result["error"]

    @patch("app.origin_trace._get_serpapi_key", return_value="INVALID_KEY")
    @patch("app.origin_trace.requests.get")
    def test_api_error_returns_fallback(self, mock_get, mock_key):
        """HTTP error from SerpApi should return safe fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        mock_get.return_value = mock_response
        
        result = query_origin_trace("https://example.com/image.jpg")
        assert result["has_matches"] is False
        assert result["error"] is not None

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_successful_pipeline_with_matches(self, mock_get, mock_key):
        """Successful pipeline should return enriched matches + earliest."""
        def side_effect(url, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            if "serpapi.com" in url:
                mock_response.json.return_value = MOCK_SERPAPI_RESPONSE
            elif "archive.org" in url:
                # Route to appropriate Wayback mock based on URL param
                params = kwargs.get("params", {})
                target_url = params.get("url", "")
                if "reuters" in target_url:
                    mock_response.json.return_value = MOCK_WAYBACK_HIT_OLD
                elif "apnews" in target_url:
                    mock_response.json.return_value = MOCK_WAYBACK_HIT_RECENT
                else:
                    mock_response.json.return_value = MOCK_WAYBACK_MISS
            
            return mock_response

        mock_get.side_effect = side_effect

        result = query_origin_trace("https://example.com/image.jpg")

        assert result["has_matches"] is True
        assert result["match_count"] == 3
        assert result["api_used"] is True
        assert result["error"] is None

        # Earliest appearance should be the Reuters article (2019)
        earliest = result["earliest_appearance"]
        assert earliest is not None
        assert "reuters" in earliest["link"]
        assert earliest["wayback"]["timestamp"] == "20190315120000"

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_no_visual_matches(self, mock_get, mock_key):
        """No visual matches should return has_matches=False."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_SERPAPI_EMPTY
        mock_get.return_value = mock_response

        result = query_origin_trace("https://example.com/image.jpg")

        assert result["has_matches"] is False
        assert result["match_count"] == 0
        assert result["api_used"] is True

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_network_exception_returns_fallback(self, mock_get, mock_key):
        """Network exception should return safe fallback."""
        mock_get.side_effect = Exception("Connection refused")

        result = query_origin_trace("https://example.com/image.jpg")

        assert result["has_matches"] is False
        assert result["error"] is not None
        assert "Connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Summary Extraction Tests
# ---------------------------------------------------------------------------

class TestOriginTraceSummary:
    """Tests for the rules-engine-friendly summary."""

    def test_summary_with_earliest(self):
        """Summary with earliest appearance should populate all fields."""
        origin_trace = {
            "has_matches": True,
            "match_count": 3,
            "earliest_appearance": {
                "link": "https://www.reuters.com/article/old-photo",
                "domain": "www.reuters.com",
                "wayback": {
                    "timestamp": "20190315120000",
                    "datetime": "2019-03-15T12:00:00+00:00",
                },
            },
        }
        summary = get_origin_trace_summary(origin_trace)

        assert summary["has_online_matches"] is True
        assert summary["earliest_timestamp"] == "2019-03-15T12:00:00+00:00"
        assert "reuters" in summary["earliest_url"]
        assert summary["earliest_domain"] == "www.reuters.com"
        assert summary["match_count"] == 3

    def test_summary_without_wayback(self):
        """Summary without Wayback data should have None timestamps."""
        origin_trace = {
            "has_matches": True,
            "match_count": 2,
            "earliest_appearance": None,
        }
        summary = get_origin_trace_summary(origin_trace)

        assert summary["has_online_matches"] is True
        assert summary["earliest_timestamp"] is None
        assert summary["earliest_url"] is None

    def test_summary_no_matches(self):
        """Summary with no matches should be empty."""
        origin_trace = {
            "has_matches": False,
            "match_count": 0,
            "earliest_appearance": None,
        }
        summary = get_origin_trace_summary(origin_trace)

        assert summary["has_online_matches"] is False
        assert summary["earliest_timestamp"] is None
        assert summary["match_count"] == 0

    def test_summary_from_fallback(self):
        """Summary from safe fallback should be clean."""
        fallback = _safe_fallback()
        summary = get_origin_trace_summary(fallback)

        assert summary["has_online_matches"] is False
        assert summary["earliest_timestamp"] is None
        assert summary["match_count"] == 0
