import os
import tempfile
from typing import List, Dict, Any
from batch_models import (
    InspectionSession,
    UploadedImage,
    AssetDetection,
    AssetRelationship,
    RelationshipType,
    BatchResult,
    SystemGroup
)

# Try to import the existing Gemini vision intake helper
try:
    from test_end_to_end import analyze_image_with_gemini
except ImportError:
    analyze_image_with_gemini = None

def run_ai_analysis(filename: str, image_bytes: bytes, use_mock_ai: bool, default_group: SystemGroup) -> Dict[str, Any]:
    """
    Classify an asset using either Mock AI (filename regex) or real Gemini Vision.
    """
    lower = filename.lower()
    
    if use_mock_ai or analyze_image_with_gemini is None:
        # Mock AI logic based on filename keywords
        if "sprinkler" in lower or "fire" in lower:
            return {
                "asset_name": "Sprinkler Head",
                "asset_type": "Sprinkler",
                "system_group": SystemGroup.FIRE,
                "risk_score": 9,
                "condition": "Sprinkler Head Obstruction Check",
                "sop_code": "ELEC_ROUTINE", # Fallback for Fire/Safety
                "confidence": 0.91,
            }
        elif "valve" in lower:
            return {
                "asset_name": "Control Valve",
                "asset_type": "Valve",
                "system_group": SystemGroup.PLUMBING,
                "risk_score": 5,
                "condition": "Valve Accessibility Check",
                "sop_code": "PLUMBING_ROUTINE",
                "confidence": 0.88,
            }
        elif "ac" in lower or "hvac" in lower or "ahu" in lower:
            return {
                "asset_name": "Air Handling Unit",
                "asset_type": "AHU",
                "system_group": SystemGroup.HVAC,
                "risk_score": 7,
                "condition": "Airflow check / normal operation",
                "sop_code": "HVAC_ROUTINE",
                "confidence": 0.86,
            }
        elif "panel" in lower or "electrical" in lower:
            return {
                "asset_name": "Electrical Panel",
                "asset_type": "Panel",
                "system_group": SystemGroup.ELECTRICAL,
                "risk_score": 8,
                "condition": "Panel Safety Check",
                "sop_code": "ELEC_ROUTINE",
                "confidence": 0.87,
            }
        elif "pipe" in lower or "leak" in lower or "water" in lower:
            return {
                "asset_name": "Piping System",
                "asset_type": "Pipe",
                "system_group": SystemGroup.PLUMBING,
                "risk_score": 8,
                "condition": "Leak / Corrosion detected",
                "sop_code": "PLUMBING_MAJOR_LEAK",
                "confidence": 0.89,
            }
        else:
            return {
                "asset_name": "Unknown Asset",
                "asset_type": "Unknown",
                "system_group": default_group or SystemGroup.GENERAL,
                "risk_score": 5,
                "condition": "Manual Review Required",
                "sop_code": "HVAC_ROUTINE",
                "confidence": 0.55,
            }
    
    # Real Gemini Vision analysis
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1] or ".png") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
        
    try:
        data = analyze_image_with_gemini(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
            
    # Parse results and map to models
    leak = data.get("visual_leak_detected", False)
    corr = data.get("visual_corrosion_detected", False)
    valve = data.get("valve_accessible", False)
    sys_grp = data.get("system_group", "General")
    obligations = data.get("obligations_overdue_estimate", 0)
    
    # Map to SOP code (matching single onboarding RL state builder)
    target_code = "HVAC_ROUTINE"
    if sys_grp == "Plumbing":
        if leak and not valve:   target_code = "PLUMBING_MAJOR_LEAK"
        elif obligations > 0:    target_code = "PLUMBING_OBLIGATION_OVERDUE"
        elif corr:               target_code = "PLUMBING_CORROSION"
        elif leak:               target_code = "PLUMBING_MINOR_LEAK"
        else:                    target_code = "PLUMBING_ROUTINE"
    elif "Elect" in sys_grp or sys_grp == "Low Voltage":
        if leak:   target_code = "ELEC_WATER_EXPOSURE"
        elif corr: target_code = "ELEC_CORRODED_PANEL"
        else:      target_code = "ELEC_ROUTINE"
    else:
        if leak and not valve: target_code = "HVAC_LEAK_CONDENSATE"
        elif leak:             target_code = "HVAC_REF_LEAK"
        elif corr:             target_code = "HVAC_OVERHEAT"
        else:                  target_code = "HVAC_ROUTINE"
        
    # Map raw system_group to Enum
    enum_group = SystemGroup.GENERAL
    for val in SystemGroup:
        if val.value.lower() == sys_grp.lower():
            enum_group = val
            break
            
    condition_str = f"Leak: {'Yes' if leak else 'No'}. Corrosion: {'Yes' if corr else 'No'}."
    if data.get("tags"):
        condition_str += f" Tags: {', '.join(data.get('tags'))}."
        
    return {
        "asset_name": data.get("asset_type", "Gemini Asset"),
        "asset_type": data.get("asset_type", "Unknown"),
        "system_group": enum_group,
        "risk_score": data.get("risk_score", 5),
        "condition": condition_str,
        "sop_code": target_code,
        "confidence": data.get("confidence", 0.8),
    }

def merge_duplicate_assets(detections: List[AssetDetection]) -> List[AssetDetection]:
    """
    De-duplicate assets by type, system group, and room location.
    If multiples found, keep the one with higher risk score or higher confidence.
    """
    merged = {}
    for d in detections:
        # Match based on: type, system_group, building, floor, zone, room
        key = (
            d.asset_type.lower(),
            d.system_group.value,
            d.building,
            d.floor,
            d.zone,
            d.room
        )
        if key not in merged:
            merged[key] = d
        else:
            existing = merged[key]
            # Keep higher risk, or higher confidence if risk is equal
            if d.risk_score > existing.risk_score:
                merged[key] = d
            elif d.risk_score == existing.risk_score and d.confidence > existing.confidence:
                merged[key] = d
    return list(merged.values())

def infer_pair_relationship(source: AssetDetection, target: AssetDetection) -> Optional[RelationshipType]:
    """
    Derive cross-system dependencies.
    """
    # Plumbing leak near electrical panel propagates risk
    if (
        source.system_group == SystemGroup.PLUMBING
        and target.system_group in [SystemGroup.ELECTRICAL, SystemGroup.ELECTRICAL_POWER]
        and "leak" in source.condition.lower()
    ):
        return RelationshipType.RISK_PROPAGATES_TO
        
    # Sprinkler controlled by a valve
    if (
        source.system_group == SystemGroup.FIRE
        and "valve" in target.asset_type.lower()
    ):
        return RelationshipType.CONTROLLED_BY
        
    # Fire/life safety monitored by control panel
    if (
        source.system_group == SystemGroup.FIRE
        and "panel" in target.asset_type.lower()
    ):
        return RelationshipType.MONITORED_BY
        
    # HVAC powered by electrical panels
    if (
        source.system_group == SystemGroup.HVAC
        and target.system_group in [SystemGroup.ELECTRICAL, SystemGroup.ELECTRICAL_POWER]
    ):
        return RelationshipType.POWERED_BY
        
    # Standard location sharing
    if source.room == target.room and source.zone == target.zone:
        return RelationshipType.SHARES_ZONE_WITH
        
    return None

def infer_relationships(assets: List[AssetDetection]) -> List[AssetRelationship]:
    """
    Analyze all assets to find links and risk propagation paths.
    """
    relationships = []
    for source in assets:
        for target in assets:
            if source.asset_id == target.asset_id:
                continue
            rel_type = infer_pair_relationship(source, target)
            if rel_type:
                relationships.append(
                    AssetRelationship(
                        source_asset_id=source.asset_id,
                        target_asset_id=target.asset_id,
                        relationship_type=rel_type,
                        confidence=0.85
                    )
                )
    return relationships

def summarize_batch(assets: List[AssetDetection], relationships: List[AssetRelationship]) -> Dict[str, Any]:
    critical_assets = [a for a in assets if a.risk_score >= 8]
    manual_review = [a for a in assets if a.confidence < 0.70]
    
    system_counts = {}
    for a in assets:
        system_counts[a.system_group.value] = system_counts.get(a.system_group.value, 0) + 1
        
    return {
        "total_assets_detected": len(assets),
        "critical_assets": len(critical_assets),
        "manual_review_required": len(manual_review),
        "relationships_detected": len(relationships),
        "system_counts": system_counts,
    }

def process_batch(
    session: InspectionSession,
    images: List[UploadedImage],
    file_contents: List[bytes],
    use_mock_ai: bool,
    progress_callback = None
) -> BatchResult:
    """
    Runs the entire batch intake pipeline.
    """
    detections = []
    
    for idx, (img, content) in enumerate(zip(images, file_contents)):
        img.processing_status = "processing"
        if progress_callback:
            progress_callback(idx / len(images), f"Processing {img.filename}...")
            
        ai_data = run_ai_analysis(
            filename=img.filename,
            image_bytes=content,
            use_mock_ai=use_mock_ai,
            default_group=session.default_system_group
        )
        
        # Instantiate AssetDetection
        detection = AssetDetection(
            image_id=img.image_id,
            asset_name=ai_data["asset_name"],
            asset_type=ai_data["asset_type"],
            system_group=ai_data["system_group"],
            risk_score=ai_data["risk_score"],
            condition=ai_data["condition"],
            sop_code=ai_data["sop_code"],
            confidence=ai_data["confidence"],
            building=session.building,
            floor=session.floor,
            zone=session.zone,
            room=session.room,
            source_filename=img.filename
        )
        detections.append(detection)
        img.processing_status = "processed"
        
    if progress_callback:
        progress_callback(0.95, "Deduplicating assets & inferring relationships...")
        
    merged_assets = merge_duplicate_assets(detections)
    relationships = infer_relationships(merged_assets)
    summary = summarize_batch(merged_assets, relationships)
    
    return BatchResult(
        session=session,
        images=images,
        detections=detections,
        merged_assets=merged_assets,
        relationships=relationships,
        summary=summary
    )
