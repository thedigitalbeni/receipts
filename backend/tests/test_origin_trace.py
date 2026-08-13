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
    to_frozen_contract,
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


# ---------------------------------------------------------------------------
# Specific Failure Mode Tests (429, 5xx, Timeout)
# ---------------------------------------------------------------------------

class TestSpecificFailureModes:
    """Verify that 429, 500, 503, and timeout all produce the same
    catch-log-degrade behavior as the 401 case (safe fallback with error).

    All HTTP error status codes go through _query_serpapi_lens() which raises
    ValueError for any non-200, caught by query_origin_trace()'s except
    block. Timeout raises requests.exceptions.Timeout, also caught. All
    produce the same safe fallback dict with error string — identical
    degradation behavior.
    """

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_http_429_rate_limit(self, mock_get, mock_key):
        """HTTP 429 (Too Many Requests) returns safe fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_get.return_value = mock_response

        result = query_origin_trace("https://example.com/image.jpg")

        assert result["has_matches"] is False
        assert result["api_used"] is False
        assert result["error"] is not None
        assert "429" in result["error"]

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_http_500_server_error(self, mock_get, mock_key):
        """HTTP 500 (Internal Server Error) returns safe fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        result = query_origin_trace("https://example.com/image.jpg")

        assert result["has_matches"] is False
        assert result["api_used"] is False
        assert result["error"] is not None
        assert "500" in result["error"]

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_http_503_service_unavailable(self, mock_get, mock_key):
        """HTTP 503 (Service Unavailable) returns safe fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_get.return_value = mock_response

        result = query_origin_trace("https://example.com/image.jpg")

        assert result["has_matches"] is False
        assert result["api_used"] is False
        assert result["error"] is not None
        assert "503" in result["error"]

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_request_timeout(self, mock_get, mock_key):
        """requests.Timeout (>SERPAPI_TIMEOUT) returns safe fallback."""
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout(
            "Connection to serpapi.com timed out. (connect timeout=15)"
        )

        result = query_origin_trace("https://example.com/image.jpg")

        assert result["has_matches"] is False
        assert result["api_used"] is False
        assert result["error"] is not None
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()

    @patch("app.origin_trace._get_serpapi_key", return_value="test_key")
    @patch("app.origin_trace.requests.get")
    def test_all_failure_modes_share_same_shape(self, mock_get, mock_key):
        """All failure modes produce identical dict structure (same keys)."""
        import requests as req

        failure_modes = [
            # (side_effect, response_factory)
            (None, lambda: MagicMock(status_code=401, text="Unauthorized")),
            (None, lambda: MagicMock(status_code=429, text="Rate limited")),
            (None, lambda: MagicMock(status_code=500, text="Server error")),
            (req.exceptions.Timeout("timeout"), None),
            (Exception("Connection refused"), None),
        ]

        results = []
        for side_effect, response_factory in failure_modes:
            if side_effect:
                mock_get.side_effect = side_effect
            else:
                mock_get.side_effect = None
                mock_get.return_value = response_factory()

            result = query_origin_trace("https://example.com/image.jpg")
            results.append(result)

        # All must have identical keys
        expected_keys = {"has_matches", "match_count", "visual_matches",
                         "earliest_appearance", "error", "api_used"}
        for r in results:
            assert set(r.keys()) == expected_keys
            assert r["has_matches"] is False
            assert r["api_used"] is False
            assert r["error"] is not None


# ---------------------------------------------------------------------------
# Frozen Contract Adapter Tests
# ---------------------------------------------------------------------------

class TestFrozenContractAdapter:
    """Tests for to_frozen_contract() mapping internal → Section 2 shape."""

    def test_successful_pipeline_maps_correctly(self):
        """Successful SerpApi + Wayback should map to success statuses."""
        internal = {
            "has_matches": True,
            "match_count": 3,
            "visual_matches": [
                {"link": "https://reuters.com/a", "domain": "reuters.com",
                 "wayback": {"datetime": "2019-03-15T12:00:00+00:00", "timestamp": "20190315120000"}, "url_date": None},
                {"link": "https://apnews.com/b", "domain": "apnews.com",
                 "wayback": None, "url_date": None},
                {"link": "https://reddit.com/c", "domain": "reddit.com",
                 "wayback": {"datetime": "2024-01-01T00:00:00+00:00", "timestamp": "20240101000000"}, "url_date": None},
            ],
            "earliest_appearance": {"link": "https://reuters.com/a"},
            "error": None,
            "api_used": True,
        }
        frozen = to_frozen_contract(internal)

        assert frozen["serpapi_status"] == "success"
        assert frozen["wayback_status"] == "success"
        assert len(frozen["results"]) == 3
        assert frozen["results"][0]["url"] == "https://reuters.com/a"
        assert frozen["results"][0]["domain"] == "reuters.com"
        assert frozen["results"][0]["earliest_wayback_timestamp"] == "2019-03-15T12:00:00+00:00"
        assert frozen["results"][1]["earliest_wayback_timestamp"] is None

    def test_no_api_key_maps_to_not_called(self):
        """Missing API key → serpapi_status=not_called."""
        internal = _safe_fallback()
        internal["error"] = "SERPAPI_API_KEY not configured"
        frozen = to_frozen_contract(internal)

        assert frozen["serpapi_status"] == "not_called"
        assert frozen["wayback_status"] == "not_called"
        assert frozen["results"] == []

    def test_api_error_maps_to_error(self):
        """HTTP 429/5xx → serpapi_status=error."""
        internal = _safe_fallback()
        internal["error"] = "SerpApi returned HTTP 429: Rate limited"
        frozen = to_frozen_contract(internal)

        assert frozen["serpapi_status"] == "error"

    def test_timeout_maps_to_timeout(self):
        """Timeout → serpapi_status=timeout."""
        internal = _safe_fallback()
        internal["error"] = "Connection timed out after 15s"
        frozen = to_frozen_contract(internal)

        assert frozen["serpapi_status"] == "timeout"

    def test_matches_but_no_wayback(self):
        """SerpApi matches with no Wayback hits → wayback_status=error."""
        internal = {
            "has_matches": True,
            "match_count": 2,
            "visual_matches": [
                {"link": "https://example.com/a", "domain": "example.com", "wayback": None, "url_date": None},
                {"link": "https://example.com/b", "domain": "example.com", "wayback": None, "url_date": None},
            ],
            "earliest_appearance": None,
            "error": None,
            "api_used": True,
        }
        frozen = to_frozen_contract(internal)

        assert frozen["serpapi_status"] == "success"
        assert frozen["wayback_status"] == "error"

    def test_contract_keys_match_pydantic_model(self):
        """Frozen output keys must match OriginTraceEvidence model fields."""
        internal = _safe_fallback()
        frozen = to_frozen_contract(internal)

        # Keys must be exactly {serpapi_status, wayback_status, results, match_count, unique_domains}
        assert set(frozen.keys()) == {"serpapi_status", "wayback_status", "results", "match_count", "unique_domains"}

    def test_results_item_keys_match_pydantic_model(self):
        """Each result item must match OriginTraceResult model fields."""
        internal = {
            "has_matches": True,
            "match_count": 1,
            "visual_matches": [
                {"link": "https://example.com/a", "domain": "example.com",
                 "wayback": {"datetime": "2020-01-01T00:00:00+00:00"}, "url_date": None},
            ],
            "earliest_appearance": None,
            "error": None,
            "api_used": True,
        }
        frozen = to_frozen_contract(internal)

        # Each result must have exactly {url, domain, earliest_wayback_timestamp, earliest_url_date}
        assert len(frozen["results"]) == 1
        assert set(frozen["results"][0].keys()) == {"url", "domain", "earliest_wayback_timestamp", "earliest_url_date"}


# ---------------------------------------------------------------------------
# Automated Rule 3 Candidate Pipeline Test (M5 DoD criterion 4)
#
# Loads the real cached SerpApi result from test_assets/ and runs it
# through the full adapter → rules engine pipeline. The cached JSON was
# captured from a live SerpApi query on 2026-08-05 and documented in
# test_assets/README.md.
#
# Note: The cached JSON has wayback=None for all matches because the
# Wayback API calls during caching didn't preserve timestamps in the
# internal dict that was serialized. The README documents manual
# verification confirming earliest Wayback appearance at sola.network
# on 2020-11-01. This test injects that documented timestamp into the
# first match so the full pipeline path (adapter + rules) can be
# exercised, while clearly documenting why the injection is needed.
# ---------------------------------------------------------------------------

class TestRule3CandidatePipeline:
    """Automated end-to-end test using the real Rule 3 cached data."""

    CACHED_RESULT_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "test_assets", "rule3_serpapi_result.json"
    )

    def _load_cached_result(self) -> dict:
        with open(self.CACHED_RESULT_PATH) as f:
            return json.load(f)

    def test_cached_json_exists_and_is_valid(self):
        """Verify the cached Rule 3 SerpApi result file exists and loads."""
        data = self._load_cached_result()
        assert data["has_matches"] is True
        assert data["match_count"] >= 1
        assert data["api_used"] is True
        assert len(data["visual_matches"]) >= 1

    def test_cached_result_has_expected_domains(self):
        """Verify cached result contains domains documented in README."""
        data = self._load_cached_result()
        domains = {m.get("domain") for m in data["visual_matches"]}
        # README documents these specific domains
        assert "sola.network" in domains or "austinpartyride.com" in domains

    @patch("app.rules.datetime")
    def test_rule3_candidate_triggers_recirculated_classification(self, mock_datetime):
        """Full pipeline test: cached SerpApi data → adapter → rules engine → Rule 3.

        The cached JSON lacks wayback timestamps (they weren't preserved
        during serialization). The README documents manual verification
        confirming earliest Wayback appearance at sola.network on
        2020-11-01. We inject this documented timestamp into the first
        match's wayback field so the adapter and rules engine see the
        same data the manual verification confirmed.

        This test exercises the exact code path that /verify uses:
          internal dict → to_frozen_contract() → AggregatedEvidence → evaluate_evidence()
        """
        from app.schemas import (
            AggregatedEvidence, C2PAEvidence, MetadataEvidence,
            OriginTraceEvidence, OriginTraceResult, DuplicateDetectionEvidence,
            ServiceStatus,
        )
        from app.rules import evaluate_evidence

        mock_datetime.now.return_value = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat

        # Load real cached SerpApi result
        data = self._load_cached_result()

        # Inject the documented Wayback timestamp (manually verified,
        # documented in README: "earliest appearance: 2020-11-01 at sola.network")
        sola_match = None
        for m in data["visual_matches"]:
            if m.get("domain") == "sola.network":
                sola_match = m
                break
        if sola_match is None:
            # Use first match if sola.network not found
            sola_match = data["visual_matches"][0]

        sola_match["wayback"] = {
            "url": f"https://web.archive.org/web/20201101/{sola_match.get('link', '')}",
            "timestamp": "20201101000000",
            "datetime": "2020-11-01T00:00:00+00:00",
        }

        # Run through the exact pipeline path: internal → adapter → evidence → rules
        frozen = to_frozen_contract(data)

        # Build AggregatedEvidence exactly as main.py does
        origin_trace_evidence = OriginTraceEvidence(**frozen)

        aggregated = AggregatedEvidence(
            c2pa=C2PAEvidence(),
            metadata=MetadataEvidence(),
            origin_trace=origin_trace_evidence,
            duplicate_detection=DuplicateDetectionEvidence(),
        )

        result = evaluate_evidence(aggregated)

        # Assert Rule 3 fires
        assert result.classification == "Recirculated / Out of Context"
        assert any("Visually identical image indexed over a year ago" in e for e in result.evidence)
        assert any("Origin context" in e for e in result.evidence)
