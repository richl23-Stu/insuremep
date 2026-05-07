import os
import sqlite3
import numpy as np
import strawberry
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional

# Import existing backend logic
from test_end_to_end import analyze_image_with_gemini
from rl_prototype_env import InsureMEPEnv, actions, action_names, get_q
from ticket_manager import create_ticket

# Initialize FastAPI
app = FastAPI(title="InsureMEP Mobile API", description="Headless backend for iOS/Mobile Apps")

# Allow mobile devices to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. GraphQL Schema for Live Tickets ---

@strawberry.type
class Ticket:
    ticket_id: str
    asset_id: str
    description: str
    sop_code: str
    location: str
    status: str
    notes: Optional[str]
    created_at: str

@strawberry.type
class Query:
    @strawberry.field
    def open_tickets(self) -> List[Ticket]:
        try:
            conn = sqlite3.connect('insuremep_sops.db')
            cursor = conn.cursor()
            cursor.execute("SELECT ticket_id, asset_id, description, sop_code, location, status, notes, created_at FROM tickets WHERE status = 'OPEN'")
            rows = cursor.fetchall()
            return [
                Ticket(
                    ticket_id=r[0], asset_id=r[1], description=r[2],
                    sop_code=r[3], location=r[4], status=r[5], notes=r[6], created_at=r[7]
                ) for r in rows
            ]
        except Exception as e:
            return []
        finally:
            if 'conn' in locals():
                conn.close()

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")


# --- 2. REST API for Photo Onboarding (Camera integration) ---

@app.post("/api/onboard_asset")
async def onboard_asset(
    file: UploadFile = File(...),
    location: str = Form("Unknown Mobile Location")
):
    """
    Mobile endpoint: Receives an image directly from the iOS camera,
    runs the Gemini + RL logic, and creates a ticket.
    """
    # Save the file temporarily
    tmp_path = f"temp_{file.filename}"
    with open(tmp_path, "wb") as buffer:
        buffer.write(await file.read())
        
    try:
        # 1. Gemini Vision Analysis
        vision_result = analyze_image_with_gemini(tmp_path)
        
        # 2. Extract Data
        sys_grp = vision_result.get("system_group", "General")
        risk_score = vision_result.get("risk_score", 5)
        obligations = vision_result.get("obligations_overdue_estimate", 0)
        leak = vision_result.get("visual_leak_detected", False)
        corrosion = vision_result.get("visual_corrosion_detected", False)
        warranty = vision_result.get("is_under_warranty", False)
        valve_acc = vision_result.get("valve_accessible", False)
        
        # 3. RL Logic Mapping
        r_level = 0 if risk_score < 5 else (1 if risk_score < 8 else 2)
        oblig_bucket = 0 if obligations == 0 else (1 if obligations <= 3 else 2)
        
        state_vector = (
            sys_grp, r_level, 0, 1, 
            1 if leak else 0, 1 if corrosion else 0,
            1, oblig_bucket, 1 if warranty else 0, 1 if valve_acc else 0
        )
        
        # Map to State Code for DB lookup (simplified for mobile API)
        target_code = "HVAC_ROUTINE"
        if sys_grp == "Plumbing":
            if leak and not valve_acc: target_code = "PLUMBING_MAJOR_LEAK"
            elif leak: target_code = "PLUMBING_MINOR_LEAK"
        elif "Elect" in sys_grp:
            if leak: target_code = "ELEC_WATER_EXPOSURE"
        else:
            if leak: target_code = "HVAC_LEAK_CONDENSATE"
            elif corrosion: target_code = "HVAC_OVERHEAT"
            
        # RL inference
        q_values = [get_q(state_vector, a) for a in actions]
        best_action_idx = int(np.argmax(q_values))
        recommended_action = action_names[best_action_idx]
        
        # 4. Auto-Create Ticket
        desc = f"Mobile Upload: {vision_result.get('observations', 'N/A')}. RL: {recommended_action}."
        asset = vision_result.get("asset_type", "Mobile_Asset")
        ticket_res = create_ticket(asset, desc, target_code, location)
        
        return {
            "status": "success",
            "message": "Asset analyzed and ticket created successfully via mobile API",
            "vision_analysis": vision_result,
            "rl_recommendation": recommended_action,
            "ticket_creation_log": ticket_res
        }
        
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    import uvicorn
    # Start the Mobile API Server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
