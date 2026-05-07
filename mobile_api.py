import os
import tempfile
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json

# Import our core logic
from test_end_to_end import analyze_image_with_gemini
from ticket_manager import create_ticket, get_open_tickets, update_ticket_status

app = FastAPI(title="InsureMEP Mobile API", version="1.0.0")

# Enable CORS for mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class TicketUpdate(BaseModel):
    ticket_id: str
    status: str
    notes: str

class TicketCreate(BaseModel):
    asset_id: str
    description: str
    sop_code: str
    location: str

@app.get("/")
async def root():
    return {"message": "InsureMEP Mobile API is operational", "status": "online"}

@app.post("/analyze")
async def analyze_asset(image: UploadFile = File(...)):
    """
    Receives an image from the mobile app, runs Gemini Vision AI analysis,
    and returns structured risk data.
    """
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Save to a temporary file for analysis
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        shutil.copyfileobj(image.file, tmp)
        tmp_path = tmp.name

    try:
        # Run our Gemini Vision ETL
        result = analyze_image_with_gemini(tmp_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/tickets")
async def list_tickets():
    """Returns a summary of open tickets."""
    # We'll parse the string output from get_open_tickets into a more JSON-friendly format
    # In a real app, we'd refactor get_open_tickets to return a list of dicts.
    # For now, we'll call the existing function.
    tickets_str = get_open_tickets()
    return {"raw_output": tickets_str}

@app.post("/create-ticket")
async def create_new_ticket(ticket: TicketCreate):
    """Creates a new maintenance ticket."""
    result = create_ticket(
        asset_id=ticket.asset_id,
        description=ticket.description,
        sop_code=ticket.sop_code,
        location=ticket.location
    )
    return {"message": result}

@app.post("/update-ticket")
async def update_existing_ticket(update: TicketUpdate):
    """Updates status or closes a ticket."""
    result = update_ticket_status(
        ticket_id=update.ticket_id,
        new_status=update.status,
        notes=update.notes
    )
    return {"message": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
