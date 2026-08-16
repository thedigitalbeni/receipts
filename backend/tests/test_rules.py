import pytest
import requests
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import socket
from pytest_socket import SocketBlockedError

from app.schemas import (
    AggregatedEvidence,
    C2PAEvidence,
    MetadataEvidence,
    OriginTraceEvidence,
    OriginTraceResult,
    ServiceStatus,
    DuplicateDetectionEvidence,
    EvidenceStrength
)
from app.rules import evaluate_evidence

pytestmark = pytest.mark.disable_socket

def create_base_evidence() -> AggregatedEvidence:
    """Helper to create an empty, default AggregatedEvidence object."""
    return AggregatedEvidence(
        c2pa=C2PAEvidence(),
        origin_trace=OriginTraceEvidence(
            serpapi_status=ServiceStatus.not_called,
            wayback_status=ServiceStatus.not_called,
            results=[]
        ),
        metadata=MetadataEvidence(),
        duplicate_detection=DuplicateDetectionEvidence()
    )


class TestRulesEngine:

    def test_rule_1_ai_generated(self):
        """Rule 1: AI Generated Content."""
        ev = create_base_evidence()
        ev.c2pa.ai_generated = True

        result = evaluate_evidence(ev)

        assert result.classification == "AI-Generated Content"
        assert result.evidence_strength == EvidenceStrength.strong
        assert "C2PA manifest explicitly declares AI generation" in result.evidence
        assert "created or modified by AI" in result.interpretation

    def test_rule_2_camera_original(self):
        """Rule 2: Verified Camera Original."""
        ev = create_base_evidence()
        ev.c2pa.camera_signature = True

        result = evaluate_evidence(ev)

        assert result.classification == "Verified Camera Original"
        assert result.evidence_strength == EvidenceStrength.strong
        assert "Cryptographically signed camera manifest present and valid" in result.evidence
        assert "directly from a camera" in result.interpretation

    @patch("app.rules.datetime")
    def test_rule_3_recirculated(self, mock_datetime):
        """Rule 3: Recirculated (match > 1 year ago)."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        ev = create_base_evidence()
        # 1 year ago would be 2023-05-01. A date before that triggers Rule 3.
        ev.origin_trace.results = [
            OriginTraceResult(
                url="https://example.com/old",
                domain="example.com",
                earliest_wayback_timestamp="2020-01-01T00:00:00+00:00"
            )
        ]

        result = evaluate_evidence(ev)

        assert result.classification == "Recirculated / Out of Context"
        assert result.evidence_strength == EvidenceStrength.strong
        assert "Visually identical image indexed over a year ago (Wayback Machine confirmed)" in result.evidence
        assert "Origin context differs from current claim" in result.evidence
        assert "already circulating before" in result.interpretation

    @patch("app.rules.datetime")
    def test_rule_3_not_triggered_if_recent(self, mock_datetime):
        """Rule 3 should not trigger if earliest timestamp is < 1 year ago."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        ev = create_base_evidence()
        # 6 months ago (recent, does not trigger rule 3)
        ev.origin_trace.results = [
            OriginTraceResult(
                url="https://example.com/recent",
                domain="example.com",
                earliest_wayback_timestamp="2023-12-01T00:00:00+00:00"
            )
        ]

        result = evaluate_evidence(ev)

        # Since it fails Rule 3, it falls back to Rule 5
        assert result.classification == "Unverified — No Provenance Found"
        assert result.evidence_strength == EvidenceStrength.limited

    def test_rule_4_editing_software(self):
        """Rule 4: Post-Processed Image."""
        ev = create_base_evidence()
        ev.metadata.editing_software_detected = True

        result = evaluate_evidence(ev)

        assert result.classification == "Post-Processed Image"
        assert result.evidence_strength == EvidenceStrength.moderate
        assert "Editing software detected in EXIF metadata" in result.evidence
        assert "processed with editing software after capture" in result.interpretation
        # Make sure it only appears once
        assert result.evidence.count("Editing software detected in EXIF metadata") == 1

    def test_rule_5_unverified(self):
        """Rule 5: Fallback when no conditions met."""
        ev = create_base_evidence()

        result = evaluate_evidence(ev)

        assert result.classification == "Unverified — No Provenance Found"
        assert result.evidence_strength == EvidenceStrength.limited
        assert "No C2PA credentials found" in result.evidence
        assert "Metadata stripped" in result.evidence
        assert "No origin trace found" in result.evidence
        assert "available evidence is limited" in result.interpretation

    @patch("app.rules.datetime")
    def test_rule_1_plus_rule_3_multi_match(self, mock_datetime):
        """Rule 1 + Rule 3 multi-match test. Rule 1 wins headline."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        ev = create_base_evidence()
        ev.c2pa.ai_generated = True
        ev.origin_trace.results = [
            OriginTraceResult(
                url="https://example.com/old",
                domain="example.com",
                earliest_wayback_timestamp="2019-01-01T00:00:00+00:00"
            )
        ]

        result = evaluate_evidence(ev)

        assert result.classification == "AI-Generated Content"
        assert result.evidence_strength == EvidenceStrength.strong
        assert "C2PA manifest explicitly declares AI generation" in result.evidence
        assert "Visually identical image indexed over a year ago (Wayback Machine confirmed)" in result.evidence
        assert "Origin context differs from current claim" in result.evidence

    @patch("app.rules.datetime")
    def test_rule_2_plus_rule_3_multi_match(self, mock_datetime):
        """Rule 2 + Rule 3 multi-match test. Rule 2 wins headline."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        ev = create_base_evidence()
        ev.c2pa.camera_signature = True
        ev.origin_trace.results = [
            OriginTraceResult(
                url="https://example.com/old",
                domain="example.com",
                earliest_wayback_timestamp="2019-01-01T00:00:00+00:00"
            )
        ]

        result = evaluate_evidence(ev)

        assert result.classification == "Verified Camera Original"
        assert result.evidence_strength == EvidenceStrength.strong
        assert "Cryptographically signed camera manifest present and valid" in result.evidence
        assert "Visually identical image indexed over a year ago (Wayback Machine confirmed)" in result.evidence
        assert "Origin context differs from current claim" in result.evidence

    @patch("app.rules.datetime")
    def test_rule_4_duplicate_evidence_regression_rule_3_wins(self, mock_datetime):
        """Rule 3 wins, editing software also detected. Evidence appears correctly."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        ev = create_base_evidence()
        ev.origin_trace.results = [
            OriginTraceResult(
                url="https://example.com/old",
                domain="example.com",
                earliest_wayback_timestamp="2019-01-01T00:00:00+00:00"
            )
        ]
        ev.metadata.editing_software_detected = True

        result = evaluate_evidence(ev)

        assert result.classification == "Recirculated / Out of Context"
        assert "Visually identical image indexed over a year ago (Wayback Machine confirmed)" in result.evidence
        assert "Editing software detected in EXIF metadata" in result.evidence
        # Ensure it appears exactly once
        assert result.evidence.count("Editing software detected in EXIF metadata") == 1

    def test_rule_4_winning_outright_evidence_count(self):
        """Rule 4 winning outright. Assert editing software evidence appears exactly once."""
        ev = create_base_evidence()
        ev.metadata.editing_software_detected = True

        result = evaluate_evidence(ev)

        assert result.classification == "Post-Processed Image"
        assert result.evidence_strength == EvidenceStrength.moderate
        assert result.evidence.count("Editing software detected in EXIF metadata") == 1
        assert len(result.evidence) == 1

    def test_network_is_blocked_by_pytest_socket(self):
        """Permanent canary test proving pytest-socket enforcement works."""
        with pytest.raises(SocketBlockedError):
            requests.get("https://google.com")

    # --- New tests for Rule 3 & 4 improvements ---

    @patch("app.rules.datetime")
    def test_rule_3_url_date_triggers_moderate(self, mock_datetime):
        """Rule 3 Scenario B: URL-extracted date > 1 year triggers Moderate."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat

        ev = create_base_evidence()
        ev.origin_trace.results = [
            OriginTraceResult(
                url="https://example.com/2019/03/15/article",
                domain="example.com",
                earliest_wayback_timestamp=None,
                earliest_url_date="2019-03-15T00:00:00+00:00"
            )
        ]

        result = evaluate_evidence(ev)

        assert result.classification == "Recirculated / Out of Context"
        assert result.evidence_strength == EvidenceStrength.moderate
        assert any("URL path suggests image dates to" in e for e in result.evidence)
        assert "already circulating before" in result.interpretation

    @patch("app.rules.datetime")
    def test_rule_3_match_count_without_date_does_not_falsely_recirculate(self, mock_datetime):
        """Match count without temporal proof does NOT falsely trigger Recirculated."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat

        ev = create_base_evidence()
        ev.origin_trace.match_count = 8
        ev.origin_trace.unique_domains = 5
        # No wayback or url_date data (e.g. today's viral image)
        ev.origin_trace.results = [
            OriginTraceResult(url=f"https://site{i}.com/img", domain=f"site{i}.com")
            for i in range(8)
        ]

        result = evaluate_evidence(ev)

        # Should NOT be Recirculated without temporal contradiction
        assert result.classification == "Unverified — No Provenance Found"
        assert result.evidence_strength == EvidenceStrength.limited
        assert "Found across 8 sources on 5 websites" in result.evidence

    def test_camera_metadata_honest_reporting(self):
        """Camera EXIF is reported honestly in evidence, not as Verified Camera Original."""
        ev = create_base_evidence()
        ev.metadata.camera_metadata_detected = True
        ev.metadata.camera_make = "Canon"
        ev.metadata.camera_model = "EOS R5"
        ev.metadata.camera_lens = "RF 24-70mm F2.8 L IS USM"

        result = evaluate_evidence(ev)

        assert result.classification == "Unverified — No Provenance Found"
        assert "Camera metadata present in EXIF: Canon EOS R5 (RF 24-70mm F2.8 L IS USM)" in result.evidence
        assert "Verified Camera Original" not in result.classification

    def test_editing_software_named_reporting(self):
        """Editing software name from EXIF is included in evidence string."""
        ev = create_base_evidence()
        ev.metadata.editing_software_detected = True
        ev.metadata.editing_software_name = "Adobe Photoshop 2024 (Macintosh)"

        result = evaluate_evidence(ev)

        assert result.classification == "Post-Processed Image"
        assert "Editing software detected in EXIF: Adobe Photoshop 2024 (Macintosh)" in result.evidence

    @patch("app.rules.datetime")
    def test_recirculated_plus_postprocessed_multidimensional(self, mock_datetime):
        """Multi-dimensional: Old archived image edited in Photoshop has both findings in receipt."""
        mock_datetime.now.return_value = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.fromisoformat = datetime.fromisoformat

        ev = create_base_evidence()
        ev.origin_trace.results = [
            OriginTraceResult(
                url="https://example.com/archive",
                domain="example.com",
                earliest_wayback_timestamp="2018-06-15T00:00:00+00:00"
            )
        ]
        ev.metadata.editing_software_detected = True
        ev.metadata.editing_software_name = "Adobe Photoshop CC 2018"
        ev.metadata.quantization_software = "Adobe Photoshop (High Quality)"

        result = evaluate_evidence(ev)

        assert result.classification == "Recirculated / Out of Context"
        assert "Visually identical image indexed over a year ago (Wayback Machine confirmed)" in result.evidence
        assert "Editing software detected in EXIF: Adobe Photoshop CC 2018" in result.evidence
        assert "JPEG quantization tables match Adobe Photoshop (High Quality)" in result.evidence

    def test_rule_4_ela_triggers(self):
        """Rule 4: ELA suspicious detection triggers Post-Processed."""
        ev = create_base_evidence()
        ev.metadata.ela_suspicious = True

        result = evaluate_evidence(ev)

        assert result.classification == "Post-Processed Image"
        assert result.evidence_strength == EvidenceStrength.moderate
        assert "Error Level Analysis detected inconsistent compression artifacts" in result.evidence

    def test_rule_4_quantization_triggers(self):
        """Rule 4: Quantization table fingerprint triggers Post-Processed."""
        ev = create_base_evidence()
        ev.metadata.quantization_software = "Adobe Photoshop (High Quality)"

        result = evaluate_evidence(ev)

        assert result.classification == "Post-Processed Image"
        assert result.evidence_strength == EvidenceStrength.moderate
        assert "JPEG quantization tables match Adobe Photoshop (High Quality)" in result.evidence

    def test_rule_4_ela_plus_exif_no_duplicate_classification(self):
        """When both ELA and EXIF detect editing, classification should appear once."""
        ev = create_base_evidence()
        ev.metadata.editing_software_detected = True
        ev.metadata.ela_suspicious = True
        ev.metadata.quantization_software = "GIMP"

        result = evaluate_evidence(ev)

        assert result.classification == "Post-Processed Image"
        assert result.evidence_strength == EvidenceStrength.moderate
        # All three evidence items present
        assert "Editing software detected in EXIF metadata" in result.evidence
        assert "Error Level Analysis detected inconsistent compression artifacts" in result.evidence
        assert "JPEG quantization tables match GIMP" in result.evidence
