import os
import sqlite3
import uuid
from datetime import datetime
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "insuremep_sops.db")

def init_tickets_db():
    """Initializes the tickets table in the SOP database if it does not exist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            description TEXT NOT NULL,
            sop_code TEXT,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
        
        try:
            cursor.execute("ALTER TABLE tickets ADD COLUMN notes TEXT;")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE tickets ADD COLUMN location TEXT DEFAULT 'Unknown';")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE tickets ADD COLUMN assign_id TEXT DEFAULT 'Unassigned';")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
            
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def search_sops(keyword: str) -> str:
    """
    Search the standard operating procedures (SOP) catalog by a keyword or condition.
    Use this to find the appropriate sop_code before creating a maintenance ticket.
    
    Args:
        keyword: A search term describing the issue, e.g., 'leak', 'airflow', 'corrosion'.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query = f"%{keyword}%"
        cursor.execute("""
            SELECT sop_code, sop_name, condition_type, recommended_action, priority_level 
            FROM sop_catalog 
            WHERE condition_type LIKE ? OR sop_name LIKE ? OR recommended_action LIKE ?
        """, (query, query, query))
        results = cursor.fetchall()
    except Exception as e:
        return f"Error querying database: {e}"
    finally:
        if 'conn' in locals():
            conn.close()
    
    if not results:
        return f"No SOPs found matching keyword: '{keyword}'"
        
    output = f"Found {len(results)} matching SOP(s):\n"
    for row in results:
        output += f"- SOP Code: {row[0]} | Name: {row[1]} | Condition: {row[2]} | Action: {row[3]} | Priority: {row[4]}\n"
    return output

def create_ticket(asset_id: str, description: str, sop_code: str, location: str = 'Unknown', assign_id: str = 'Unassigned') -> str:
    """
    Create a maintenance ticket for an asset and link it to an SOP code.
    
    Args:
        asset_id: The ID or name of the asset having the issue.
        description: A brief description of the problem.
        sop_code: The exact SOP code (e.g., HVAC_LEAK_CONDENSATE) that dictates how to fix it.
        location: The physical location of the asset (e.g., Room 1152, Roof).
    """
    init_tickets_db()  # Ensure table exists
    ticket_id = f"TCK-{str(uuid.uuid4())[:8].upper()}"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tickets (ticket_id, asset_id, description, sop_code, location, assign_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, asset_id, description, sop_code, location, assign_id))
        conn.commit()
    except Exception as e:
        return f"Error creating ticket: {e}"
    finally:
        if 'conn' in locals():
            conn.close()
    
    return f"Successfully created ticket {ticket_id} for asset {asset_id}. Linked SOP: {sop_code}."

def get_open_tickets() -> str:
    """
    Retrieve a list of all currently OPEN maintenance tickets.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_id, asset_id, description, sop_code, location, assign_id, status, notes, created_at FROM tickets WHERE status = 'OPEN'")
        results = cursor.fetchall()
    except Exception as e:
        return f"Error retrieving tickets: {e}"
    finally:
        if 'conn' in locals():
            conn.close()
            
    if not results:
        return "No OPEN tickets found."
        
    output = f"Found {len(results)} OPEN ticket(s):\n"
    for row in results:
        output += f"- Ticket: {row[0]} | Asset: {row[1]} | Desc: {row[2]} | SOP: {row[3]} | Loc: {row[4]} | Assign ID: {row[5]} | Date: {row[8]}\n"
    return output

def update_ticket_status(ticket_id: str, new_status: str, notes: str) -> str:
    """
    Update the status of an existing ticket (e.g., to 'CLOSED' or 'VERIFIED') and append notes.
    
    Args:
        ticket_id: The ID of the ticket to update (e.g., TCK-1234ABCD).
        new_status: The new status string (e.g., 'CLOSED').
        notes: Verification details or work completion notes.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verify ticket exists
        cursor.execute("SELECT ticket_id FROM tickets WHERE ticket_id = ?", (ticket_id,))
        if not cursor.fetchone():
            return f"Error: Ticket {ticket_id} not found."
            
        cursor.execute("""
            UPDATE tickets 
            SET status = ?, notes = ?
            WHERE ticket_id = ?
        """, (new_status.upper(), notes, ticket_id))
        conn.commit()
    except Exception as e:
        return f"Error updating ticket: {e}"
    finally:
        if 'conn' in locals():
            conn.close()
            
    return f"Successfully updated ticket {ticket_id} to status '{new_status.upper()}'. Notes appended."

def clear_all_tickets() -> str:
    """
    Delete all tickets from the database. Use with caution!
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tickets")
        conn.commit()
    except Exception as e:
        return f"Error clearing tickets: {e}"
    finally:
        if 'conn' in locals():
            conn.close()
    return "All tickets have been cleared from the system."

def get_ticket_details(ticket_id: str) -> str:
    """
    Retrieve full details of a specific maintenance ticket by its ID (e.g., TCK-A9C51EE6).
    Use this tool to find details about a ticket, such as who is assigned to it, the SOP linked, location, status, or description.
    
    Args:
        ticket_id: The unique ID of the ticket to retrieve.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.ticket_id, t.asset_id, t.description, t.sop_code, t.location, t.assign_id, t.status, t.notes, t.created_at,
                   s.sop_name, s.priority_level, s.recommended_action
            FROM tickets t
            LEFT JOIN sop_catalog s ON t.sop_code = s.sop_code
            WHERE t.ticket_id = ?
        """, (ticket_id.strip(),))
        row = cursor.fetchone()
    except Exception as e:
        return f"Error retrieving ticket details: {e}"
    finally:
        if 'conn' in locals():
            conn.close()
            
    if not row:
        return f"Ticket {ticket_id} not found."
        
    output = f"Ticket Details for {row[0]}:\n"
    output += f"- Asset ID: {row[1]}\n"
    output += f"- Description: {row[2]}\n"
    output += f"- SOP Code: {row[3]} | SOP Name: {row[9] or 'N/A'} | Recommended Action: {row[11] or 'N/A'}\n"
    output += f"- Location: {row[4]}\n"
    output += f"- Assignee (Assign ID): {row[5]}\n"
    output += f"- Status: {row[6]}\n"
    output += f"- Notes: {row[7] or 'None'}\n"
    output += f"- Created At: {row[8]}\n"
    return output

# Run table init automatically when imported
init_tickets_db()
