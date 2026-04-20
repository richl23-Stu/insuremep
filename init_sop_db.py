import sqlite3
import uuid
import uuid
from datetime import datetime

DB_PATH = 'insuremep_sops.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop table if exists for fresh init
    cursor.execute('DROP TABLE IF EXISTS sop_catalog')
    
    # 1. CORE SOP CATALOG SCHEMA
    cursor.execute("""
    CREATE TABLE sop_catalog (
        sop_id TEXT PRIMARY KEY,
        sop_code TEXT UNIQUE NOT NULL,
        sop_name TEXT NOT NULL,
        system_group TEXT NOT NULL,
        condition_type TEXT NOT NULL,
        recommended_action TEXT,
        priority_level INT NOT NULL CHECK (priority_level BETWEEN 1 AND 10),
        safety_critical BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # SOPs Data extracted from "SOPs Assets Scenarios" (HVAC 12 Scenarios Sample)
    hvac_scenarios = [
        ("HVAC_NO_AIRFLOW", "No Airflow SOP", "check power, thermostat, filter, duct, compressor", "inspect / maintenance", 7),
        ("HVAC_WEAK_AIRFLOW", "Weak Airflow SOP", "check filter, duct blockage, fan speed", "inspect", 5),
        ("HVAC_TEMP_NOT_REACHING", "Temperature Not Reaching Setpoint SOP", "check refrigerant, compressor, sensor calibration", "maintenance", 7),
        ("HVAC_LEAK_CONDENSATE", "HVAC Leak (condensate) SOP", "inspect drain, clear blockage, check pan", "urgent if near electrical", 8),
        ("HVAC_REF_LEAK", "Refrigerant Leak SOP", "locate leak, seal, recharge, test", "urgent repair", 9),
        ("HVAC_COMP_FAIL", "Compressor Failure SOP", "power check, relay, replace compressor", "urgent repair", 9),
        ("HVAC_OVERHEAT", "Overheating Unit SOP", "airflow, load, cooling system", "inspect", 8),
        ("HVAC_SENSOR_ERR", "Sensor Malfunction SOP", "recalibrate, replace sensor", "maintenance", 6),
        ("HVAC_ROUTINE", "Routine HVAC Check", "clean filters, check fan belt", "inspect", 2)
    ]
    
    plumbing_scenarios = [
        ("PLUMBING_MINOR_LEAK", "Minor Plumbing Leak", "tighten fittings, replace gasket", "maintenance", 4),
        ("PLUMBING_MAJOR_LEAK", "Major Plumbing Burst", "shut off main valve, replace pipe", "urgent repair", 9),
        ("PLUMBING_CORROSION", "Pipe Rust/Corrosion", "inspect for thickness loss, replace segment", "inspect", 6),
        ("PLUMBING_OBLIGATION_OVERDUE", "Overdue Plumbing Maintenance", "flush/descale system, verify warranty requirements", "maintenance", 7),
        ("PLUMBING_ROUTINE", "Routine Plumbing Check", "check water pressure", "inspect", 2)
    ]
    
    electrical_scenarios = [
        ("ELEC_CORRODED_PANEL", "Panel Corrosion SOP", "lockout tagout, inspect for arching, replace", "urgent repair", 9),
        ("ELEC_WATER_EXPOSURE", "Water Near Electrical SOP", "immediate power shutoff, dry area", "urgent if near electrical", 10),
        ("ELEC_ROUTINE", "Routine Electrical Check", "thermal scan, check breaker torque", "inspect", 2)
    ]
    
    all_scenarios = hvac_scenarios + plumbing_scenarios + electrical_scenarios
    
    insert_query = """
    INSERT INTO sop_catalog 
    (sop_id, sop_code, sop_name, system_group, condition_type, recommended_action, priority_level, safety_critical)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    for row in all_scenarios:
        sop_code, sop_name, condition, action, priority = row
        # Flag as safety critical if priority >= 8 or 'urgent' is in action
        safety_critical = priority >= 8 or 'urgent' in action.lower()
        
        sys_group = "General"
        if "HVAC" in sop_code: sys_group = "HVAC"
        elif "PLUMBING" in sop_code: sys_group = "Plumbing"
        elif "ELEC" in sop_code: sys_group = "Electrical"
        
        cursor.execute(insert_query, (
            str(uuid.uuid4()),
            sop_code,
            sop_name,
            sys_group,
            condition,
            action,
            priority,
            safety_critical
        ))
        
    conn.commit()
    print(f"Database initialized at {DB_PATH}. Inserted {len(all_scenarios)} Total SOPs.")
    
    # Query to verify
    print("\n--- Verifying Inserted Data ---\n")
    for row in cursor.execute("SELECT sop_code, priority_level, safety_critical FROM sop_catalog"):
        print(f"CODE: {row[0].ljust(25)} | PRIORITY: {row[1]} | SAFETY CRITICAL: {bool(row[2])}")
        
    conn.close()

if __name__ == "__main__":
    init_db()
