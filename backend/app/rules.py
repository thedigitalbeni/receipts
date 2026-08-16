from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from app.schemas import AggregatedEvidence, EvidenceStrength

class EvaluationResult(BaseModel):
    """The result of applying the Decision Logic to aggregated evidence."""
    classification: str
    evidence_strength: EvidenceStrength
    evidence: list[str]
    interpretation: str

def evaluate_evidence(aggregated_evidence: AggregatedEvidence) -> EvaluationResult:
    """Apply the rules engine to the aggregated evidence.
    
    Implements the Decision Logic defined in Section 2 with multi-dimensional
    evidence accumulation. Classification first-match-wins for headline,
    while all forensic and context findings are transparently preserved.
    """
    classification = None
    evidence_strength = None
    interpretation = None
    evidence_list = []

    # Standalone Forensic Evidence Check
    # Appended immediately regardless of which rule wins the headline.
    if aggregated_evidence.metadata.editing_software_detected:
        sw_name = aggregated_evidence.metadata.editing_software_name
        if sw_name:
            evidence_list.append(f"Editing software detected in EXIF: {sw_name}")
        else:
            evidence_list.append("Editing software detected in EXIF metadata")

    if aggregated_evidence.metadata.ela_suspicious:
        evidence_list.append("Error Level Analysis detected inconsistent compression artifacts")

    if aggregated_evidence.metadata.quantization_software:
        evidence_list.append(
            f"JPEG quantization tables match {aggregated_evidence.metadata.quantization_software}"
        )

    # Standalone Camera Metadata Check (Honest metadata, not cryptographic proof)
    if aggregated_evidence.metadata.camera_metadata_detected and not aggregated_evidence.c2pa.camera_signature:
        make = aggregated_evidence.metadata.camera_make or ""
        model = aggregated_evidence.metadata.camera_model or ""
        lens = aggregated_evidence.metadata.camera_lens or ""
        cam_info = f"{make} {model}".strip()
        if lens:
            cam_info += f" ({lens})"
        if cam_info:
            evidence_list.append(f"Camera metadata present in EXIF: {cam_info}")
        else:
            evidence_list.append("Camera hardware metadata present in EXIF")

    # Rule 1: C2PA explicitly asserts AI generation
    if aggregated_evidence.c2pa.ai_generated:
        if not classification:
            classification = "AI-Generated Content"
            evidence_strength = EvidenceStrength.strong
            interpretation = (
                "This image's embedded credentials confirm it was created or modified by AI. "
                "This is a technical fact, not a judgment on whether the content is misleading."
            )
        evidence_list.append("C2PA manifest explicitly declares AI generation")
    
    # Rule 2: C2PA contains cryptographic camera hardware signature
    if aggregated_evidence.c2pa.camera_signature:
        if not classification:
            classification = "Verified Camera Original"
            evidence_strength = EvidenceStrength.strong
            interpretation = (
                "This image includes a verified, tamper-evident record showing "
                "it came directly from a camera with no undisclosed edits."
            )
        evidence_list.append("Cryptographically signed camera manifest present and valid")

    # Rule 3: Trace finds visual match indexed > 1 year ago (Strict Temporal Contradiction).
    # Requires date confirmation (Wayback Machine or publication date in URL/snippet):
    #   A) Wayback Machine confirms timestamp > 1 year → Strong
    #   B) URL path/snippet date > 1 year → Moderate
    is_rule_3 = False
    rule_3_strength = None
    rule_3_evidence_items = []
    now = datetime.now(timezone.utc)
    one_year_ago = now - timedelta(days=365)
    
    # Scenario A: Wayback-confirmed timestamp > 1 year
    for result in aggregated_evidence.origin_trace.results:
        if result.earliest_wayback_timestamp:
            try:
                ts = result.earliest_wayback_timestamp.replace('Z', '+00:00')
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < one_year_ago:
                    is_rule_3 = True
                    rule_3_strength = EvidenceStrength.strong
                    rule_3_evidence_items.append("Visually identical image indexed over a year ago (Wayback Machine confirmed)")
                    rule_3_evidence_items.append("Origin context differs from current claim")
                    break
            except ValueError:
                continue

    # Scenario B: URL-extracted date > 1 year (fallback when Wayback has no snapshot)
    if not is_rule_3:
        for result in aggregated_evidence.origin_trace.results:
            if result.earliest_url_date:
                try:
                    ts = result.earliest_url_date.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < one_year_ago:
                        is_rule_3 = True
                        rule_3_strength = EvidenceStrength.moderate
                        rule_3_evidence_items.append(
                            f"URL path suggests image dates to {dt.strftime('%B %Y')}"
                        )
                        rule_3_evidence_items.append("Origin context may differ from current claim")
                        break
                except ValueError:
                    continue

    if is_rule_3:
        if not classification:
            classification = "Recirculated / Out of Context"
            evidence_strength = rule_3_strength
            interpretation = (
                "This exact image was already circulating before the current claim about it. "
                "This is a strong signal the current context may be misleading, though "
                "the tool cannot determine intent."
            )
        evidence_list.extend(rule_3_evidence_items)

    # General Web Matches context (if not already covered by Rule 3)
    match_count = aggregated_evidence.origin_trace.match_count
    unique_domains = aggregated_evidence.origin_trace.unique_domains
    if match_count > 0 and not is_rule_3:
        evidence_list.append(
            f"Found across {match_count} source{'s' if match_count != 1 else ''} on {unique_domains} website{'s' if unique_domains != 1 else ''}"
        )

    # Rule 4: editing detected (EXIF software, ELA anomaly, or quantization fingerprint)
    is_rule_4 = (
        aggregated_evidence.metadata.editing_software_detected
        or aggregated_evidence.metadata.ela_suspicious
        or aggregated_evidence.metadata.quantization_software is not None
    )
    if is_rule_4:
        if not classification:
            classification = "Post-Processed Image"
            evidence_strength = EvidenceStrength.moderate
            interpretation = (
                "This file was processed with editing software after capture. "
                "This alone does not indicate the content is false or misleading — "
                "most photos are lightly edited. Treat this as a prompt for closer "
                "scrutiny, not a verdict."
            )

    # Rule 5: Fallback (All checks return empty)
    if not classification:
        classification = "Unverified — No Provenance Found"
        evidence_strength = EvidenceStrength.limited
        interpretation = (
            "No provenance data, prior appearances, or editing signatures were found. "
            "This does not confirm the image is authentic — it means the available "
            "evidence is limited, not that the image is verified true."
        )
        if not evidence_list:
            evidence_list.extend([
                "No C2PA credentials found",
                "Metadata stripped",
                "No origin trace found"
            ])

    # Deduplicate evidence while preserving insertion order
    seen = set()
    deduped_evidence = []
    for item in evidence_list:
        if item not in seen:
            seen.add(item)
            deduped_evidence.append(item)

    return EvaluationResult(
        classification=classification,
        evidence_strength=evidence_strength,
        evidence=deduped_evidence,
        interpretation=interpretation
    )
