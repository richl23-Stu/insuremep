from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid

class InspectionMode(str, Enum):
    SAME_ASSET_BATCH = "same_asset_batch"
    SAME_SYSTEM_BATCH = "same_system_batch"
    MIXED_SYSTEM_BATCH = "mixed_system_batch"
    ROOM_SCAN = "room_scan"
    FLOOR_SCAN = "floor_scan"

class SystemGroup(str, Enum):
    HVAC = "HVAC"
    ELECTRICAL = "Electrical"
    ELECTRICAL_POWER = "Electrical/Power"
    FIRE = "Fire/Life Safety"
    PLUMBING = "Plumbing"
    CONTROLS = "Controls/OT"
    ELEVATOR = "Elevator"
    ENVIRONMENTAL = "Environmental"
    MECHANICAL = "Mechanical"
    STRUCTURAL = "Structural"
    MEDICAL_GAS = "Medical Gas"
    FOOD_SERVICE = "Food Service"
    LOW_VOLTAGE = "Low Voltage"
    SECURITY = "Security"
    ROOFING = "Roofing"
    GENERAL = "General"
    UNKNOWN = "Unknown"

class RelationshipType(str, Enum):
    LOCATED_IN = "located_in"
    CONNECTED_TO = "connected_to"
    CONTROLLED_BY = "controlled_by"
    FED_BY = "fed_by"
    POWERS = "powers"
    POWERED_BY = "powered_by"
    MONITORED_BY = "monitored_by"
    PROTECTED_BY = "protected_by"
    RISK_PROPAGATES_TO = "risk_propagates_to"
    SHARES_ZONE_WITH = "shares_zone_with"

class UploadedImage(BaseModel):
    image_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_path: Optional[str] = None
    processing_status: str = "pending"

class InspectionSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_name: str
    building: str
    floor: str
    zone: str
    room: Optional[str] = None
    inspection_mode: InspectionMode
    default_system_group: Optional[SystemGroup] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AssetDetection(BaseModel):
    detection_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    image_id: str
    asset_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str
    asset_type: str
    system_group: SystemGroup
    risk_score: int
    condition: str
    sop_code: str
    confidence: float
    bbox: Optional[Dict[str, int]] = None
    building: str
    floor: str
    zone: str
    room: Optional[str] = None
    source_filename: str

class AssetRelationship(BaseModel):
    source_asset_id: str
    target_asset_id: str
    relationship_type: RelationshipType
    confidence: float = 0.85

class BatchResult(BaseModel):
    session: InspectionSession
    images: List[UploadedImage]
    detections: List[AssetDetection]
    merged_assets: List[AssetDetection]
    relationships: List[AssetRelationship]
    summary: Dict[str, Any]
