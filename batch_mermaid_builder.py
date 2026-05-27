import re
from batch_models import BatchResult

def clean_id(value: str) -> str:
    value = str(value)
    value = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    if not value:
        value = "node"
    if value[0].isdigit():
        value = "N_" + value
    return value

def risk_class(score: int) -> str:
    if score >= 8:
        return "critical"
    if score >= 5:
        return "warning"
    return "normal"

def build_batch_mermaid(result: BatchResult) -> str:
    session = result.session
    
    building_id = clean_id(f"building_{session.building}")
    floor_id = clean_id(f"floor_{session.floor}")
    zone_id = clean_id(f"zone_{session.zone}")
    room_id = clean_id(f"room_{session.room or 'unknown'}")
    
    lines = ["flowchart LR"]
    
    # Render location nodes with clean visual formatting
    lines.append(f'{building_id}["🏫 Building: {session.building}"]')
    lines.append(f'{floor_id}["🏗️ Floor: {session.floor}"]')
    lines.append(f'{zone_id}["Zone: {session.zone}"]')
    lines.append(f"{building_id} --> {floor_id}")
    lines.append(f"{floor_id} --> {zone_id}")
    
    if session.room:
        lines.append(f'{room_id}["📍 Room: {session.room}"]')
        lines.append(f"{zone_id} --> {room_id}")
        location_parent = room_id
    else:
        location_parent = zone_id
        
    # Map assets
    asset_id_to_node = {}
    for asset in result.merged_assets:
        node_id = clean_id(asset.asset_id)
        asset_id_to_node[asset.asset_id] = node_id
        
        # Build clean string labels
        label = (
            f"<b>{asset.asset_name}</b><br/>"
            f"Type: {asset.asset_type}<br/>"
            f"System: {asset.system_group.value}<br/>"
            f"Risk: {asset.risk_score}/10<br/>"
            f"SOP: {asset.sop_code}"
        )
        lines.append(f'{node_id}["{label}"]')
        lines.append(f"{location_parent} --> {node_id}")
        lines.append(f"class {node_id} {risk_class(asset.risk_score)};")
        
    # Map inferred edges
    for rel in result.relationships:
        src_node = asset_id_to_node.get(rel.source_asset_id)
        tgt_node = asset_id_to_node.get(rel.target_asset_id)
        if src_node and tgt_node:
            lines.append(f'{src_node} -- "{rel.relationship_type.value}" --> {tgt_node}')
            
    # Apply standard styling definitions
    lines.append("classDef location fill:#e8f1ff,stroke:#2563eb,stroke-width:2px,color:#111827;")
    lines.append("classDef critical fill:#fee2e2,stroke:#dc2626,stroke-width:3px,color:#111827;")
    lines.append("classDef warning fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#111827;")
    lines.append("classDef normal fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#111827;")
    
    # Style locations
    loc_nodes = [building_id, floor_id, zone_id]
    if session.room:
        loc_nodes.append(room_id)
    lines.append(f"class {','.join(loc_nodes)} location;")
    
    return "\n".join(lines)
