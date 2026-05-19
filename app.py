import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import os
import sys
import tempfile
import numpy as np

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from test_end_to_end import analyze_image_with_gemini
from rl_sop_integration import train_q_learning
from google import genai
from google.genai import types
from ticket_manager import search_sops, create_ticket, get_open_tickets, update_ticket_status, clear_all_tickets

# Configure page
st.set_page_config(
    layout="wide",
    page_title="InsureMEP Unified Workbench",
    page_icon="🏗️",
)

# ── Global CSS Overrides ─────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Bolder, larger tab labels to clearly distinguish each workflow */
  .stTabs [data-baseweb="tab"] > div {
    font-size: 15px !important;
    font-weight: 700 !important;
    letter-spacing: 0.3px !important;
    padding: 8px 18px !important;
  }
  .stTabs [aria-selected="true"] > div {
    color: #1d4ed8 !important;
  }
  /* Align Task Inspection Board subheader with the global location bar above */
  .task-board-header {
    padding-left: 6px;
    border-left: 4px solid #2563eb;
    margin-bottom: 12px;
  }
</style>
""", unsafe_allow_html=True)

# ── Floor plan and room data ─────────────────────────────────────────────────
FLOOR_PLANS = {
    "Floor 1 (Ground)": os.path.join(BASE_DIR, "assets/IMG_4999.JPG"),
    "Floor 2":          os.path.join(BASE_DIR, "assets/IMG_5001.JPG"),
    "Floor 3":          os.path.join(BASE_DIR, "assets/IMG_5002.JPG"),
    "Floor 4":          os.path.join(BASE_DIR, "assets/IMG_5003.JPG"),
    "Floor 5 (Roof)":   os.path.join(BASE_DIR, "assets/IMG_5004.JPG"),
}

ROOM_DATA = {
    "Floor 1 (Ground)": [
        "1000A","1000B","1100A","1100B","1100C","1120","1128A","1128B","1200",
        "AHU-1","AHU-2","AHU-3","AHU-4","FCU-1","FCU-2","FCU-4","Starbucks","Other",
    ],
    "Floor 2": [
        "2011","2015","2100","FCU-3","FCU-2","2125","2904","2200","2300","2900",
        "2311","2321","2409","2516","2511","2512","2400B","2325","2400A","2500",
        "2508","2504","2502","Other",
    ],
    "Floor 3": [
        "3100","3107","3205","3207","3211","3215","3216","3226","3229","3232",
        "3235","3300","3309","3310A","3310B","3310C","3310D","3317","3321",
        "3401","3402","3410","3901","3902","Other",
    ],
    "Floor 4": [
        "4101","4107","4111","4200","4202","4208","4212","4214","4300","4303",
        "4311","4317","4401","4410","4502","4504","4508","4514","4530","4540",
        "4562","4600","4601","4606","4612","4617","4618","4900","4902","Other",
    ],
    "Floor 5 (Roof)": [
        "5110","5200A","5200B","5301","5302","5305","5310","5311","5400","5402",
        "5408","5420","5500","5502","5508","5516","5524","5600","5601","5603",
        "5604","5607","5608","5900A","5900B","Other",
    ],
}

DB_PATH = os.path.join(BASE_DIR, "insuremep_sops.db")

# ── Helpers ──────────────────────────────────────────────────────────────────
def get_sop_details(sop_code):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT sop_name, condition_type, priority_level, recommended_action FROM sop_catalog WHERE sop_code=?",
            (sop_code,),
        )
        row = c.fetchone()
        conn.close()
        return row if row else ("Unknown SOP", "No condition specified", 1, "inspect")
    except Exception:
        return ("Unknown SOP", "N/A", 1, "inspect")

@st.cache_data(show_spinner=False)
def get_cached_vision_data(image_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        return analyze_image_with_gemini(tmp_path)
    finally:
        os.remove(tmp_path)

@st.cache_resource
def load_rl_model():
    orig_dir = os.getcwd()
    os.chdir(BASE_DIR)
    q_table, env = train_q_learning(episodes=5000)
    os.chdir(orig_dir)
    return q_table, env

def init_asset_catalog():
    """Create asset_catalog table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_catalog (
            asset_id        TEXT PRIMARY KEY,
            asset_name      TEXT NOT NULL,
            system_group    TEXT,
            location        TEXT,
            floor           TEXT,
            room            TEXT,
            risk_score      INTEGER DEFAULT 0,
            risk_tier       TEXT DEFAULT 'Low',
            sop_code        TEXT,
            tags            TEXT,
            estimated_age   INTEGER,
            leak_detected   BOOLEAN DEFAULT 0,
            corrosion_found BOOLEAN DEFAULT 0,
            valve_accessible BOOLEAN DEFAULT 0,
            onboarded_by    TEXT DEFAULT 'Unassigned',
            onboarded_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes           TEXT
        )
    """)
    conn.commit()
    conn.close()

init_asset_catalog()

def save_asset_to_registry(asset_name, system_group, location, floor, room,
                            risk_score, risk_tier, sop_code, tags, estimated_age,
                            leak_detected, corrosion_found, valve_accessible,
                            onboarded_by, notes=""):
    """Insert or update an asset record in asset_catalog."""
    import uuid as _uuid
    asset_id = f"AST-{_uuid.uuid4().hex[:8].upper()}"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO asset_catalog
            (asset_id, asset_name, system_group, location, floor, room,
             risk_score, risk_tier, sop_code, tags, estimated_age,
             leak_detected, corrosion_found, valve_accessible,
             onboarded_by, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (asset_id, asset_name, system_group, location, floor, room,
               risk_score, risk_tier, sop_code, tags, estimated_age,
               int(leak_detected), int(corrosion_found), int(valve_accessible),
               onboarded_by, notes))
        conn.commit()
        conn.close()
        return asset_id
    except Exception as e:
        return f"ERROR: {e}"

def render_mermaid(mermaid_code: str, height: int = 380):
    escaped = html.escape(mermaid_code)
    html_code = f"""
    <html>
    <head>
      <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
          startOnLoad: true,
          theme: 'default',
          securityLevel: 'loose',
          flowchart: {{
            useMaxWidth: false,
            htmlLabels: true,
            curve: 'basis'
          }}
        }});
      </script>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          background: transparent;
        }}

        /* ── Normal card wrapper ─────────────────────────────── */
        .card {{
          position: relative;
          background: #ffffff;
          border-radius: 12px;
          border: 2px solid #e2e8f0;
          box-shadow: 0 4px 20px -2px rgba(0,0,0,0.07);
          overflow: auto;
          padding: 20px 20px 16px;
        }}
        .card .diagram-scroll {{
          overflow-x: auto;
        }}
        .mermaid svg {{
          font-size: 15px !important;
          min-width: 700px !important;
          height: auto !important;
        }}
        .node label {{
          font-family: inherit !important;
          line-height: 1.4 !important;
        }}
        .edgeLabel {{
          font-size: 13px !important;
          font-weight: 600 !important;
          color: #374151 !important;
          background-color: #fff !important;
          padding: 3px 6px !important;
          border-radius: 4px !important;
          border: 1px solid #e5e7eb !important;
        }}

        /* ── Fullscreen button (top-right of card) ───────────── */
        .fs-open-btn {{
          position: absolute;
          top: 10px;
          right: 12px;
          background: #1e293b;
          color: #fff;
          border: none;
          border-radius: 8px;
          padding: 6px 14px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
          transition: background 0.15s, transform 0.1s;
          z-index: 10;
          letter-spacing: 0.3px;
        }}
        .fs-open-btn:hover {{ background: #334155; transform: scale(1.04); }}
        .fs-open-btn:active {{ transform: scale(0.97); }}

        /* ── Fullscreen Overlay ──────────────────────────────── */
        #fs-overlay {{
          display: none;
          position: fixed;
          inset: 0;
          z-index: 99999;
          background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f172a 100%);
          flex-direction: column;
        }}
        #fs-overlay.active {{
          display: flex;
        }}

        /* Top control bar */
        .fs-bar {{
          flex-shrink: 0;
          height: 56px;
          background: rgba(255,255,255,0.06);
          border-bottom: 1px solid rgba(255,255,255,0.1);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 24px;
          backdrop-filter: blur(8px);
        }}
        .fs-title {{
          color: #f1f5f9;
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 0.3px;
          display: flex;
          align-items: center;
          gap: 8px;
        }}
        .fs-title-badge {{
          background: rgba(99,102,241,0.25);
          color: #a5b4fc;
          border: 1px solid rgba(99,102,241,0.4);
          border-radius: 6px;
          padding: 2px 8px;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }}
        .fs-controls {{
          display: flex;
          align-items: center;
          gap: 10px;
        }}
        .fs-ctrl-btn {{
          background: rgba(255,255,255,0.1);
          color: #f1f5f9;
          border: 1px solid rgba(255,255,255,0.15);
          border-radius: 8px;
          padding: 6px 14px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s, transform 0.1s;
          display: flex;
          align-items: center;
          gap: 5px;
        }}
        .fs-ctrl-btn:hover {{ background: rgba(255,255,255,0.2); transform: scale(1.04); }}
        .fs-ctrl-btn:active {{ transform: scale(0.97); }}
        .fs-close-btn {{
          background: rgba(239,68,68,0.15);
          border-color: rgba(239,68,68,0.3);
          color: #fca5a5;
        }}
        .fs-close-btn:hover {{ background: rgba(239,68,68,0.3); }}

        /* Diagram canvas in fullscreen */
        .fs-canvas {{
          flex: 1;
          overflow: auto;
          display: flex;
          align-items: flex-start;
          justify-content: center;
          padding: 32px;
        }}
        .fs-diagram-card {{
          background: #ffffff;
          border-radius: 16px;
          box-shadow: 0 25px 60px rgba(0,0,0,0.5);
          padding: 32px 40px;
          transform-origin: top center;
          transition: transform 0.2s ease;
        }}
        #fs-overlay .mermaid svg {{
          min-width: unset !important;
          max-width: 90vw !important;
          height: auto !important;
          font-size: 16px !important;
        }}

        /* Hint bar */
        .fs-hint {{
          flex-shrink: 0;
          text-align: center;
          padding: 8px;
          color: rgba(148,163,184,0.7);
          font-size: 12px;
        }}

        /* Interactive badge */
        .interact-badge {{
          display: inline-flex;
          align-items: center;
          gap: 5px;
          background: #f0f9ff;
          color: #0369a1;
          border: 1px solid #bae6fd;
          border-radius: 20px;
          padding: 3px 10px;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.3px;
          margin-bottom: 10px;
          user-select: none;
        }}
      </style>
    </head>
    <body>

      <!-- Normal card view -->
      <div class="card">
        <div class="diagram-scroll">
          <div class="mermaid" id="diagram-normal">
{escaped}
          </div>
        </div>
        <div style="display:flex; align-items:center; justify-content:center; gap:12px; margin-top: 12px; padding-top: 10px; border-top: 1px solid #f1f5f9;">
          <div class="interact-badge">🖱️ Interactive &nbsp;·&nbsp; Scroll to explore</div>
          <button class="fs-open-btn" onclick="openFullscreen()">
            ⛶ Full Screen
          </button>
        </div>
      </div>

      <!-- Fullscreen Overlay -->
      <div id="fs-overlay">
        <div class="fs-bar">
          <div class="fs-title">
            🗺️ Diagram Viewer
            <span class="fs-title-badge">Fullscreen</span>
          </div>
          <div class="fs-controls">
            <button class="fs-ctrl-btn" onclick="adjustZoom(-0.1)">－ Zoom Out</button>
            <button class="fs-ctrl-btn" onclick="adjustZoom(0.1)">＋ Zoom In</button>
            <button class="fs-ctrl-btn" onclick="resetZoom()">↺ Reset</button>
            <button class="fs-ctrl-btn fs-close-btn" onclick="closeFullscreen()">✕ Close</button>
          </div>
        </div>
        <div class="fs-canvas" id="fs-canvas">
          <div class="fs-diagram-card" id="fs-diagram-card">
            <div class="mermaid" id="diagram-fs"></div>
          </div>
        </div>
        <div class="fs-hint">Press <kbd style="background:#334155;color:#94a3b8;border-radius:4px;padding:1px 6px;font-size:11px;">ESC</kbd> or click Close to exit fullscreen</div>
      </div>

      <script>
        let currentZoom = 1.0;

        function openFullscreen() {{
          const srcSvg = document.querySelector('#diagram-normal svg');
          const fsCard = document.getElementById('diagram-fs');
          if (srcSvg) {{
            fsCard.innerHTML = '';
            fsCard.appendChild(srcSvg.cloneNode(true));
            // Make SVG responsive
            const svgEl = fsCard.querySelector('svg');
            if (svgEl) {{
              svgEl.style.maxWidth = '85vw';
              svgEl.style.height = 'auto';
              svgEl.style.display = 'block';
            }}
          }}
          currentZoom = 1.0;
          document.getElementById('fs-diagram-card').style.transform = 'scale(1)';
          document.getElementById('fs-overlay').classList.add('active');
          document.body.style.overflow = 'hidden';
        }}

        function closeFullscreen() {{
          document.getElementById('fs-overlay').classList.remove('active');
          document.body.style.overflow = '';
        }}

        function adjustZoom(delta) {{
          currentZoom = Math.max(0.3, Math.min(3.0, currentZoom + delta));
          document.getElementById('fs-diagram-card').style.transform = `scale(${{currentZoom}})`;
        }}

        function resetZoom() {{
          currentZoom = 1.0;
          document.getElementById('fs-diagram-card').style.transform = 'scale(1)';
        }}

        document.addEventListener('keydown', (e) => {{
          if (e.key === 'Escape' && document.getElementById('fs-overlay').classList.contains('active')) {{
            closeFullscreen();
          }}
        }});
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=height, scrolling=True)

import re
import html

def clean_id(s: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '_', s)

def risk_class(score: int) -> str:
    if score >= 8:
        return "critical"
    elif score >= 5:
        return "warning"
    else:
        return "normal"

def build_asset_mermaid(asset_context: dict) -> str:
    building_id = clean_id(asset_context["building"])
    floor_id = clean_id(asset_context["floor"])
    zone_id = clean_id(asset_context["zone"])
    room_id = clean_id(asset_context["room"])

    asset = asset_context["input_asset"]
    main_id = clean_id(asset["asset_id"])

    lines = ["flowchart LR"]

    # Location hierarchy with styled HTML labels
    lines.append(f'{building_id}["<div style=\'padding: 8px; font-weight: bold; font-size: 14px; text-align: center;\'>🏫 Building:<br/>{asset_context["building"]}</div>"]')
    lines.append(f'{floor_id}["<div style=\'padding: 8px; font-weight: bold; font-size: 14px; text-align: center;\'>🏗️ Floor:<br/>{asset_context["floor"]}</div>"]')
    lines.append(f'{zone_id}["<div style=\'padding: 8px; font-weight: bold; font-size: 14px; text-align: center;\'>Zone:<br/>{asset_context["zone"]}</div>"]')
    lines.append(f'{room_id}["<div style=\'padding: 8px; font-weight: bold; font-size: 14px; text-align: center;\'>📍 Room:<br/>{asset_context["room"]}</div>"]')

    lines.append(f"{building_id} --> {floor_id}")
    lines.append(f"{floor_id} --> {zone_id}")
    lines.append(f"{zone_id} --> {room_id}")

    # Main asset
    cond_preview = html.escape(asset['condition'])
    if len(cond_preview) > 40:
        cond_preview = cond_preview[:37] + "..."
        
    main_label = (
        f"<div style=\'padding: 10px; text-align: left; font-family: sans-serif; line-height: 1.4; width: 280px; white-space: normal; word-break: break-word;\'>"
        f"<strong style=\'font-size: 16px; color: #b91c1c; display: block; border-bottom: 2px solid #fca5a5; padding-bottom: 4px; margin-bottom: 6px;\'>🚨 {html.escape(asset['asset_name'])}</strong>"
        f"<span style=\'font-size: 13px; color: #4b5563;\'>Type:</span> <strong style=\'font-size: 13px; color: #1f2937;\'>{html.escape(asset['asset_type'])}</strong><br/>"
        f"<span style=\'font-size: 13px; color: #4b5563;\'>Risk:</span> <strong style=\'font-size: 13px; color: #dc2626;\'>{asset['risk_score']}/10</strong><br/>"
        f"<span style=\'font-size: 13px; color: #4b5563;\'>SOP:</span> <code style=\'font-size: 12px; background: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b;\'>{html.escape(asset['sop_code'])}</code><br/>"
        f"<span style=\'font-size: 13px; color: #4b5563;\'>Condition:</span> <span style=\'font-size: 12px; font-style: italic; color: #4b5563;\'>{cond_preview}</span>"
        f"</div>"
    )
    lines.append(f'{main_id}["{main_label}"]')
    lines.append(f"{room_id} --> {main_id}")

    # Linked assets
    for linked in asset_context["linked_assets"]:
        linked_id = clean_id(linked["asset_id"])
        
        status_color = "#dc2626" if linked["risk_score"] >= 8 else ("#d97706" if linked["risk_score"] >= 5 else "#16a34a")
        
        status_preview = html.escape(linked["status"])
        if len(status_preview) > 40:
            status_preview = status_preview[:37] + "..."
            
        label = (
            f"<div style=\'padding: 10px; text-align: left; font-family: sans-serif; line-height: 1.4; width: 240px; white-space: normal; word-break: break-word;\'>"
            f"<strong style=\'font-size: 15px; color: {status_color}; display: block; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; margin-bottom: 6px;\'>{html.escape(linked['asset_name'])}</strong>"
            f"<span style=\'font-size: 12px; color: #4b5563;\'>Type:</span> <strong style=\'font-size: 12px; color: #1f2937;\'>{html.escape(linked['asset_type'])}</strong><br/>"
            f"<span style=\'font-size: 12px; color: #4b5563;\'>Risk:</span> <strong style=\'font-size: 12px; color: {status_color};\'>{linked['risk_score']}/10</strong><br/>"
            f"<span style=\'font-size: 12px; color: #4b5563;\'>Status:</span> <span style=\'font-size: 11px; font-weight: 500; color: #4b5563;\'>{status_preview}</span>"
            f"</div>"
        )
        relationship = linked["relationship"]

        lines.append(f'{linked_id}["{label}"]')
        lines.append(f'{main_id} -- "{relationship}" --> {linked_id}')

        cls = risk_class(linked["risk_score"])
        lines.append(f"class {linked_id} {cls};")

    # Classes
    lines.append("classDef location fill:#e8f1ff,stroke:#2563eb,stroke-width:2px,color:#111827;")
    lines.append("classDef main fill:#fff1f2,stroke:#dc2626,stroke-width:4px,color:#111827;")
    lines.append("classDef critical fill:#fee2e2,stroke:#dc2626,stroke-width:3px,color:#111827;")
    lines.append("classDef warning fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#111827;")
    lines.append("classDef normal fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#111827;")

    lines.append(f"class {building_id},{floor_id},{zone_id},{room_id} location;")
    lines.append(f"class {main_id} main;")

    return "\n".join(lines)

def get_asset_context_by_ticket_data(active_t: dict) -> dict:
    loc_parts = active_t['location'].split(" - ")
    floor_str = loc_parts[0] if len(loc_parts) > 0 else "Floor 1 (Ground)"
    room_str = loc_parts[1] if len(loc_parts) > 1 else "1000A"
    
    # Map zone name
    if "5" in floor_str:
        zone_str = "Roof Plant HVAC Deck"
    elif "1" in floor_str:
        zone_str = "Mechanical / Utility Area"
    else:
        zone_str = "Central Distribution Duct Zone"
        
    # Map trade group
    sop_code = active_t.get('sop_code', '').lower()
    if 'hvac' in sop_code or 'temp' in sop_code:
        asset_type = 'HVAC'
        linked_assets = [
            {
                "asset_id": "AST_CONDENSER_LOOP",
                "asset_name": "Refrigerant Condenser Loop",
                "asset_type": "HVAC",
                "relationship": "connected_to",
                "risk_score": 8,
                "status": "Pressure Normal"
            },
            {
                "asset_id": "AST_VAV_BOX",
                "asset_name": "VAV damper controller",
                "asset_type": "HVAC",
                "relationship": "controlled_by",
                "risk_score": 6,
                "status": "Online"
            }
        ]
    elif 'plumb' in sop_code or 'leak' in sop_code:
        asset_type = 'Plumbing'
        linked_assets = [
            {
                "asset_id": "AST_SHUTOFF_VALVE",
                "asset_name": "Main Water Shutoff Valve",
                "asset_type": "Plumbing",
                "relationship": "controlled_by",
                "risk_score": 7,
                "status": "Valve Accessible: Yes"
            },
            {
                "asset_id": "AST_DRAIN_TRAP",
                "asset_name": "Emergency Floor Drain Trap",
                "asset_type": "Plumbing",
                "relationship": "downstream_of",
                "risk_score": 4,
                "status": "Clear flow"
            }
        ]
    else:
        asset_type = 'Electrical'
        linked_assets = [
            {
                "asset_id": "AST_MAIN_BREAKER",
                "asset_name": "SB1 Main Distribution Breaker",
                "asset_type": "Electrical",
                "relationship": "powered_by",
                "risk_score": 9,
                "status": "Load capacity: 85%"
            },
            {
                "asset_id": "AST_SUB_PANEL",
                "asset_name": "Room distribution panel board",
                "asset_type": "Electrical",
                "relationship": "feeds",
                "risk_score": 5,
                "status": "Breaker 14 Normal"
            }
        ]
        
    return {
        "building": "SB1 - Science Library",
        "floor": floor_str,
        "zone": zone_str,
        "room": room_str,
        "input_asset": {
            "asset_id": active_t['asset_id'],
            "asset_name": active_t['asset_id'],
            "asset_type": asset_type,
            "risk_score": active_t['priority_level'] * 3 if active_t['priority_level'] else 6,
            "sop_code": active_t['sop_code'],
            "condition": active_t['description'],
            "status": "Open Ticket" if active_t['status'] == "OPEN" else "Closed Ticket"
        },
        "linked_assets": linked_assets
    }

def should_show_mermaid(user_prompt: str) -> bool:
    trigger_phrases = [
        "show map",
        "show diagram",
        "where is",
        "locate asset",
        "asset relationship",
        "linked assets",
        "dependency map",
        "show dependencies",
        "show blueprint map",
        "where is this asset",
    ]
    prompt = user_prompt.lower()
    return any(phrase in prompt for phrase in trigger_phrases)

# Train RL engine
q_table, rl_env = load_rl_model()

# ── Header ──────────────────────────────────────────────────────────────────
try:
    col_logo, col_title = st.columns([1, 9], vertical_alignment="center")
    with col_logo:
        st.image(os.path.join(BASE_DIR, "assets/logo.png"), use_container_width=True)
    with col_title:
        st.title("InsureMEP Workbench")
        st.caption("AI-Driven Critical Infrastructure Maintenance · UCI Capstone Project")
except Exception:
    st.title("🏗️ InsureMEP Workbench")
    st.caption("AI-Driven Critical Infrastructure Maintenance · UCI Capstone Project")

st.divider()

# ── Global Location Context Bar ──────────────────────────────────────────────
st.subheader("🌐 Global Location Filter")
lc1, lc2, lc3 = st.columns(3)
with lc1:
    selected_building = st.selectbox("🏫 Building", ["SB1 - Science Library"])
with lc2:
    selected_floor = st.selectbox("🏗️ Floor", list(ROOM_DATA.keys()))
with lc3:
    selected_room = st.selectbox(
        "📍 Room / Location", ROOM_DATA.get(selected_floor, ["Other"])
    )

st.divider()

# ── Sidebar: Context-Aware AI Co-pilot ──────────────────────────────────────
with st.sidebar:
    st.header("💬 AI Co-pilot")
    st.caption("Ask about the active asset, RL decisions, or SOP guidelines.")

    if "global_messages" not in st.session_state:
        st.session_state.global_messages = []

    # Display message history
    for msg in st.session_state.global_messages[-8:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "mermaid_code" in msg:
                render_mermaid(msg["mermaid_code"], height=320)

    if chat_prompt := st.chat_input("Ask the AI Co-pilot...", key="global_chat"):
        st.session_state.global_messages.append({"role": "user", "content": chat_prompt})
        
        # Build prompt context
        ctx = "No active asset analysed yet."
        if "last_analysis_ctx" in st.session_state:
            ctx = st.session_state["last_analysis_ctx"]
            
        triggered_mermaid_code = None
        active_t = None
        if should_show_mermaid(chat_prompt):
            selected_id = st.session_state.get("selected_ticket_id")
            if selected_id:
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT t.ticket_id, t.asset_id, t.description, t.sop_code, t.location, t.assign_id, t.status, t.notes, t.created_at,
                               s.sop_name, s.priority_level, s.safety_critical
                        FROM tickets t
                        LEFT JOIN sop_catalog s ON t.sop_code = s.sop_code
                        WHERE t.ticket_id = ?
                    """, (selected_id,))
                    r = cursor.fetchone()
                    conn.close()
                    if r:
                        active_t = {
                            "ticket_id": r[0],
                            "asset_id": r[1],
                            "description": r[2],
                            "sop_code": r[3],
                            "location": r[4],
                            "assign_id": r[5],
                            "status": r[6],
                            "notes": r[7],
                            "created_at": r[8],
                            "sop_name": r[9] or "Unknown SOP",
                            "priority_level": r[10] or 1,
                            "safety_critical": r[11] or 0
                        }
                except Exception:
                    pass
            
            if not active_t:
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT t.ticket_id, t.asset_id, t.description, t.sop_code, t.location, t.assign_id, t.status, t.notes, t.created_at,
                               s.sop_name, s.priority_level, s.safety_critical
                        FROM tickets t
                        LEFT JOIN sop_catalog s ON t.sop_code = s.sop_code
                        WHERE t.status = 'OPEN'
                        LIMIT 1
                    """)
                    r = cursor.fetchone()
                    conn.close()
                    if r:
                        active_t = {
                            "ticket_id": r[0],
                            "asset_id": r[1],
                            "description": r[2],
                            "sop_code": r[3],
                            "location": r[4],
                            "assign_id": r[5],
                            "status": r[6],
                            "notes": r[7],
                            "created_at": r[8],
                            "sop_name": r[9] or "Unknown SOP",
                            "priority_level": r[10] or 1,
                            "safety_critical": r[11] or 0
                        }
                except Exception:
                    pass
            
            if active_t:
                asset_context = get_asset_context_by_ticket_data(active_t)
                triggered_mermaid_code = build_asset_mermaid(asset_context)

        try:
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            config = types.GenerateContentConfig(
                system_instruction=(
                    "You are InsureMEP's intelligent site co-pilot. "
                    f"Current global location context: {selected_building} - {selected_floor} - {selected_room}. "
                    f"Active Asset diagnostics context: {ctx}. "
                    "Provide extremely clear, concise, actionable maintenance advice."
                ),
                tools=[search_sops, create_ticket, get_open_tickets, update_ticket_status],
                temperature=0.2,
            )
            chat = client.chats.create(model="gemini-2.5-flash", config=config)
            response = chat.send_message(chat_prompt)
            reply = response.text
            if triggered_mermaid_code:
                reply += f"\n\n🗺️ **Digital Twin: I have located asset '{active_t['asset_id']}' and rendered its dependency map below!**"
        except Exception as e:
            reply = f"⚠️ Connection error: {e}"
            
        assistant_msg = {"role": "assistant", "content": reply}
        if triggered_mermaid_code:
            assistant_msg["mermaid_code"] = triggered_mermaid_code
            
        st.session_state.global_messages.append(assistant_msg)
        st.rerun()

# ── Interactive Tabs ─────────────────────────────────────────────────────────
tab_onboarding, tab_maintenance, tab_blueprints, tab_registry = st.tabs([
    "📸 Onboarding Asset",
    "📋 Current Maintenance",
    "🗺️ Floor Plans",
    "📦 Asset Registry",
])

# ── Tab 1: Onboarding Asset ──────────────────────────────────────────────────
with tab_onboarding:
    st.header("📸 New Asset Onboarding")
    st.caption("Upload equipment photos to parse asset details, estimate risk, and generate compliance SOP tasks.")
    
    col_ob1, col_ob2 = st.columns([1, 1], gap="large")
    
    with col_ob1:
        st.subheader("1. Asset Intake")
        onboard_status = st.radio(
            "Are you onboarding a new asset?",
            ["Yes, Onboard New Asset", "No, Inspect Existing Asset"],
            horizontal=True,
            key="ob_status_radio"
        )
        
        st.info(f"📍 Location Assigned: **{selected_building}** · **{selected_floor}** · **Room {selected_room}**")
        
        uploaded_file = st.file_uploader(
            "📷 Upload Equipment Photo (JPG/PNG)", type=["png", "jpg", "jpeg"], key="ob_uploader"
        )
        if uploaded_file:
            st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)
            
    with col_ob2:
        st.subheader("2. Asset Diagnostics & Decision Engine")
        
        if uploaded_file:
            with st.spinner("🔍 Running Gemini Vision & Q-Learning Agent..."):
                try:
                    data = get_cached_vision_data(uploaded_file.getvalue())
                    
                    leak = data.get("visual_leak_detected", False)
                    corr = data.get("visual_corrosion_detected", False)
                    valve = data.get("valve_accessible", False)
                    sys_grp = data.get("system_group", "General")
                    obligations = data.get("obligations_overdue_estimate", 0)
                    
                    # Map findings to RL state code
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
                        
                    state_idx = 0
                    for i, row in enumerate(rl_env.state_map):
                        if row[0] == target_code:
                            state_idx = i
                            break
                            
                    state_code = rl_env.state_map[state_idx][0]
                    best_action_idx = np.argmax(q_table[state_idx])
                    best_action = rl_env.action_space[best_action_idx].upper()
                    q_vals = q_table[state_idx]
                    sop_name, condition_type, priority, recommended_action = get_sop_details(state_code)
                    
                    tags = data.get("tags", [])
                    tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
                    
                    # Store diagnostics in session state
                    st.session_state["last_analysis_ctx"] = (
                        f"Asset: {data.get('asset_type')}, System: {sys_grp}, "
                        f"Risk: {data.get('risk_score')}/10, RL Action: {best_action}, "
                        f"SOP: {sop_name}, Condition: {condition_type}"
                    )
                    
                    # ── Structured Asset Diagnostics Card (Sketch 3) ──
                    with st.container(border=True):
                        st.markdown(f"### 📋 Asset Diagnostics")
                        st.markdown(f"**🏷️ AI Tags:** `{tags_str}`")
                        st.divider()
                        
                        ad_c1, ad_c2 = st.columns(2)
                        with ad_c1:
                            st.markdown(f"**📦 Asset Name:** {data.get('asset_type', 'Unknown Equipment')}")
                            st.markdown(f"**🛠️ System Group:** {sys_grp}")
                            st.markdown(f"**⏳ Estimated Age:** {data.get('estimated_age_years', 'N/A')} Years")
                        with ad_c2:
                            st.markdown(f"**⚠️ Risk Score:** `{data.get('risk_score', 5)}/10` ({data.get('risk_tier', 'Low')})")
                            st.markdown(f"**💧 Leak Detected:** {'🚨 Yes' if leak else '✔️ None'}")
                            st.markdown(f"**⚡ Valve Accessible:** {'✅ Yes' if valve else '❌ No'}")
                            st.markdown(f"**⚙️ Corrosion Found:** {'🚨 Yes' if corr else '✔️ None'}")
                        
                        st.divider()
                        st.markdown(f"### 📋 Triggered SOP Guidelines")
                        st.markdown(f"**📖 SOP:** `{state_code}` — {sop_name}")
                        st.info(f"**🔍 Condition Details:** {condition_type}")
                        st.warning(f"**🎯 RL Recommended Action:** **{best_action}** (SOP Action: {recommended_action.upper()})")
                        
                    # ── Save to Asset Registry + Create Ticket ──
                    st.divider()
                    st.markdown("### 🎟️ Actions")
                    act_c1, act_c2 = st.columns(2)
                    
                    with act_c1:
                        st.markdown("**Save to Asset Registry**")
                        ob_operator = st.text_input("👤 Operator / Assign ID:", value="Unassigned", key="ob_assign_id")
                        ob_notes = st.text_area("📝 Notes (optional):", value="", height=68, key="ob_notes_input")
                        if st.button("💾 Save to Asset Registry", type="primary", key="btn_save_registry", use_container_width=True):
                            saved_id = save_asset_to_registry(
                                asset_name=data.get("asset_type", "Unknown_Asset"),
                                system_group=sys_grp,
                                location=f"{selected_floor} - {selected_room}",
                                floor=selected_floor,
                                room=selected_room,
                                risk_score=data.get("risk_score", 0),
                                risk_tier=data.get("risk_tier", "Low"),
                                sop_code=state_code,
                                tags=tags_str,
                                estimated_age=data.get("estimated_age_years") or 0,
                                leak_detected=leak,
                                corrosion_found=corr,
                                valve_accessible=valve,
                                onboarded_by=ob_operator,
                                notes=ob_notes,
                            )
                            if saved_id.startswith("AST-"):
                                st.success(f"✅ Asset saved! Registry ID: **{saved_id}**")
                                st.info("Switch to the **📦 Asset Registry** tab to see all records.")
                            else:
                                st.error(saved_id)
                    
                    with act_c2:
                        st.markdown("**Create Maintenance Ticket**")
                        ticket_assign = st.text_input("👤 Ticket Assign ID:", value="Unassigned", key="ob_ticket_assign_id")
                        st.write("")
                        st.write("")
                        if st.button("🎟️ Create Onboarding Ticket", type="secondary", key="btn_create_ob_ticket", use_container_width=True):
                            desc = f"Tags: {tags_str}. RL Action: {best_action}. Description: Onboarded visual inspection."
                            asset = data.get("asset_type", "Unknown_Asset")
                            full_location = f"{selected_floor} - {selected_room}"
                            res = create_ticket(
                                asset_id=asset,
                                description=desc,
                                sop_code=state_code,
                                location=full_location,
                                assign_id=ticket_assign,
                            )
                            st.success(res)
                        
                except Exception as e:
                    st.error(f"Error parsing image: {e}")
        else:
            st.info("⬅️ Upload an equipment photo on the left to trigger the Gemini & RL diagnostics engine.")

    # Mermaid diagram checkpoint
    if uploaded_file and "last_analysis_ctx" in st.session_state:
        st.divider()
        st.subheader("🔀 System Relationship Checklist")
        st.caption("Review the dynamic Mermaid flowchart generated by Gemini based on the asset inspection.")
        
        if st.button("🔄 Generate System Relationship Flowchart", type="secondary", key="btn_gen_ob_mermaid"):
            with st.spinner("Generating flowchart..."):
                try:
                    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                    ctx = st.session_state.get("last_analysis_ctx", "")
                    mermaid_prompt = (
                        f"Based on this asset analysis: {ctx}\n\n"
                        "Generate a Mermaid flowchart diagram showing:\n"
                        "1. The asset and its system group\n"
                        "2. Detected conditions (leak, corrosion, etc.)\n"
                        "3. The triggered SOP\n"
                        "4. The RL-recommended maintenance action and next steps\n\n"
                        "Output ONLY valid Mermaid code. No markdown fences, no explanation. Start with: flowchart TD"
                    )
                    response = client.models.generate_content(
                        model="gemini-2.5-flash", contents=mermaid_prompt
                    )
                    mermaid_code = response.text.strip()
                    if mermaid_code.startswith("```"):
                        mermaid_code = mermaid_code.split("```")[1]
                        if mermaid_code.startswith("mermaid"):
                            mermaid_code = mermaid_code[7:]
                    st.session_state["last_mermaid"] = mermaid_code.strip()
                except Exception as e:
                    st.error(f"Diagram generation failed: {e}")
                    
        if "last_mermaid" in st.session_state:
            diagram_col, code_col = st.columns([2, 1])
            with diagram_col:
                render_mermaid(st.session_state["last_mermaid"])
            with code_col:
                st.code(st.session_state["last_mermaid"], language="")
                st.caption("✅ **Human Verification Checkpoint** - Discrepancies can be logged in the Co-pilot chat.")

# ── Tab 2: Current Maintenance ───────────────────────────────────────────────
with tab_maintenance:
    st.header("📋 Maintenance Workbench")
    st.caption("Review active building tickets, organize daily operational schedules, and verify task closures.")
    
    # Fetch active tickets from SQLite DB (unfiltered base list for assistant stats)
    all_tickets = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query_str = """
            SELECT t.ticket_id, t.asset_id, t.description, t.sop_code, t.location, t.assign_id, t.status, t.notes, t.created_at,
                   s.sop_name, s.priority_level, s.safety_critical
            FROM tickets t
            LEFT JOIN sop_catalog s ON t.sop_code = s.sop_code
            ORDER BY s.priority_level DESC, t.created_at DESC
        """
        cursor.execute(query_str)
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            all_tickets.append({
                "ticket_id": r[0],
                "asset_id": r[1],
                "description": r[2],
                "sop_code": r[3],
                "location": r[4],
                "assign_id": r[5],
                "status": r[6],
                "notes": r[7],
                "created_at": r[8],
                "sop_name": r[9] or "Unknown SOP",
                "priority_level": r[10] or 1,
                "safety_critical": r[11] or 0
            })
    except Exception as e:
        st.warning(f"Database read failed: {e}")

    open_tickets = [t for t in all_tickets if t["status"] == "OPEN"]
    critical_tickets = [t for t in open_tickets if t["priority_level"] >= 3 or t["safety_critical"] == 1]
    unassigned_tickets = [t for t in open_tickets if t["assign_id"].lower() == "unassigned"]

    # ── 💡 What's On Today? — Daily Maintenance Helper Panel (Sketch 1 & 2) ──
    with st.container(border=True):
        st.markdown("### 💡 What's On Today? — Daily Maintenance Helper")
        if open_tickets:
            # Dynamic Greeting & AI-driven Guidance
            if critical_tickets:
                top_priority = critical_tickets[0]
                st.error(
                    f"🔴 **Action Required:** You have **{len(open_tickets)} open tasks** today. "
                    f"**{len(critical_tickets)} are Safety-Critical!**"
                )
                st.markdown(
                    f"👉 **Highest Priority Action:** Inspect **{top_priority['asset_id']}** at **{top_priority['location']}** immediately "
                    f"(Triggered SOP: `{top_priority['sop_code']}`)."
                )
            else:
                st.info(
                    f"🟡 **Routine Tasks:** You have **{len(open_tickets)} active tasks** today. "
                    f"No safety-critical issues detected."
                )
                st.markdown(
                    f"👉 **Next Step:** Review the unassigned tasks below and allocate operators to begin work."
                )
                
            if unassigned_tickets:
                st.warning(f"👤 **{len(unassigned_tickets)} tasks are currently Unassigned.** Allocate operators to avoid SLA delays.")
                
            # Quick Shortcut Buttons inside the Assistant Widget
            st.caption("⚡ **Helper Quick Actions:**")
            hk1, hk2 = st.columns(2)
            with hk1:
                if st.button("🚨 Put Tasks in Critical Order", use_container_width=True, key="helper_btn_crit"):
                    st.session_state["ctrl_sort_crit"] = True
                    st.rerun()
            with hk2:
                if st.button(f"📍 Focus on Current Room ({selected_room})", use_container_width=True, key="helper_btn_loc"):
                    st.session_state["ctrl_filt_loc"] = True
                    st.rerun()
        else:
            st.success("✨ **All Systems Operational:** No open tickets logged today! Excellent work.")
            st.markdown("👉 **Next Step:** Head over to **📸 Onboarding Asset** to register new equipment or run a visual health check.")

    st.divider()

    # Criticality and Location Sorting Controls
    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        sort_critical = st.checkbox("🚨 Sort by Criticality (Critical Order)", value=False, key="ctrl_sort_crit")
    with col_ctrl2:
        filter_by_loc = st.checkbox(f"📍 Filter by Current Room Location ({selected_room})", value=False, key="ctrl_filt_loc")

    st.divider()

    col_m1, col_m2 = st.columns([2, 3], gap="large")

    # Apply interactive filters to the tickets list displayed in the master column
    filtered_tickets = list(all_tickets)
    
    if filter_by_loc:
        loc_str = f"{selected_floor} - {selected_room}"
        filtered_tickets = [t for t in filtered_tickets if t["location"] == loc_str]
        
    if sort_critical:
        # Already ordered by priority in DB query, but let's enforce it
        filtered_tickets.sort(key=lambda x: (x["priority_level"], x["created_at"]), reverse=True)
    else:
        # Standard chronological order
        filtered_tickets.sort(key=lambda x: x["created_at"], reverse=True)

    # Left Column: Today's Works (Master List)
    with col_m1:
        st.subheader("📋 Today's Works")
        
        if filtered_tickets:
            for t in filtered_tickets:
                status_icon = "🟢" if t["status"] == "CLOSED" else "🔴"
                crit_badge = "🚨 High" if t["priority_level"] >= 3 else ("⚠️ Med" if t["priority_level"] == 2 else "⚙️ Routine")
                
                # Dynamic card-like list
                card_title = f"{status_icon} **{t['ticket_id']}** — {t['asset_id']}"
                card_desc = f"📍 {t['location']} | {crit_badge}"
                
                with st.container(border=True):
                    st.markdown(card_title)
                    st.caption(card_desc)
                    if st.button(f"Open Details →", key=f"t_btn_{t['ticket_id']}", use_container_width=True):
                        st.session_state["selected_ticket_id"] = t["ticket_id"]
                        st.rerun()
        else:
            st.info("No tasks logged for this filter setting.")

    # Right Column: Detail & Operations
    with col_m2:
        st.markdown('<div class="task-board-header"><h3 style="margin:0; padding: 6px 0;">🔍 Task Inspection Board</h3></div>', unsafe_allow_html=True)
        
        selected_id = st.session_state.get("selected_ticket_id")
        active_t = next((t for t in all_tickets if t["ticket_id"] == selected_id), None) if selected_id else None
        
        if active_t:
            with st.container(border=True):
                st.markdown(f"## 🎫 Ticket Details: {active_t['ticket_id']}")
                st.divider()
                
                det1, det2 = st.columns(2)
                with det1:
                    st.markdown(f"**📦 Asset Name:** {active_t['asset_id']}")
                    st.markdown(f"**📌 Status:** `{active_t['status']}`")
                    st.markdown(f"**📍 Location:** {active_t['location']}")
                with det2:
                    st.markdown(f"**📖 Linked SOP:** `{active_t['sop_code']}`")
                    st.markdown(f"**👤 Assigned Operator:** `{active_t['assign_id']}`")
                    st.markdown(f"**📅 Logged Date:** {active_t['created_at']}")
                
                st.divider()
                st.markdown(f"**📝 Description:**  \n{active_t['description']}")
                if active_t['notes']:
                    st.info(f"**🗒️ Closure Notes:** {active_t['notes']}")
                
                # Operations
                st.divider()
                st.markdown("### ⚙️ Operator Operations")
                
                # 1. Update assignment
                new_assign = st.text_input("Update Operator Assignment:", value=active_t['assign_id'], key="update_assign_input")
                if st.button("Update Operator", type="secondary", key="btn_update_operator"):
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute("UPDATE tickets SET assign_id = ? WHERE ticket_id = ?", (new_assign, active_t['ticket_id']))
                        conn.commit()
                        conn.close()
                        st.success(f"Assigned Operator updated to {new_assign}!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Failed to update assignment: {ex}")
                
                # 2. Close ticket
                if active_t['status'] == "OPEN":
                    st.divider()
                    close_note = st.text_input("Task Resolution Note:", value="Maintenance verified complete.", key="close_note_input")
                    if st.button("✅ Verify & Close Ticket", type="primary", use_container_width=True, key="btn_close_ticket"):
                        res = update_ticket_status(active_t['ticket_id'], "CLOSED", close_note)
                        st.success(res)
                        st.rerun()

                # 3. 🗺️ Digital Twin Dependency Map (Notebook Inspiration)
                st.divider()
                st.markdown("### 🗺️ Digital Twin Dependency Map")
                st.caption("Live asset localization and upstream/downstream facility dependency map.")
                
                try:
                    asset_context = get_asset_context_by_ticket_data(active_t)
                    m_dependency_code = build_asset_mermaid(asset_context)
                    render_mermaid(m_dependency_code, height=450)
                    
                    with st.expander("🛠️ View Dependency Map Source Code"):
                        st.code(m_dependency_code, language="mermaid")
                except Exception as map_err:
                    st.warning(f"Could not load dependency map: {map_err}")
                        
                # 4. Dynamic Mermaid for active ticket SOP flowchart
                st.divider()
                st.markdown("### 🔀 System Operations Flowchart")
                st.caption("Generate a visual operations flowchart for the linked Standard Operating Procedure.")
                
                if st.button("🔄 Generate Action Flowchart", type="secondary", key="btn_gen_t_mermaid"):
                    with st.spinner("Generating flowchart..."):
                        try:
                            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                            prompt_t = (
                                f"SOP Code: {active_t['sop_code']}\n"
                                f"SOP Name: {active_t['sop_name']}\n"
                                f"Asset: {active_t['asset_id']}\n"
                                f"Description: {active_t['description']}\n\n"
                                "Generate a Mermaid flowchart diagram mapping the troubleshooting flow for this SOP.\n"
                                "CRITICAL RULES:\n"
                                "1. Output ONLY valid Mermaid code, starting with 'flowchart TD'.\n"
                                "2. Do NOT wrap in markdown code fences (no ``` or ```mermaid).\n"
                                "3. Node labels must NOT contain parentheses () or special chars – use square brackets [] for all nodes.\n"
                                "4. Keep labels short (under 40 characters each).\n"
                                "5. Use --> for edges and -- label --> for labelled edges."
                            )
                            response = client.models.generate_content(
                                model="gemini-2.5-flash", contents=prompt_t
                            )
                            m_code = response.text.strip()
                            
                            # Robust fence stripper
                            import re as _re
                            m_code = _re.sub(r'^```(?:mermaid)?\s*', '', m_code, flags=_re.IGNORECASE)
                            m_code = _re.sub(r'\s*```\s*$', '', m_code)
                            m_code = m_code.strip()
                            
                            st.session_state[f"mermaid_t_{active_t['ticket_id']}"] = m_code
                        except Exception as e:
                            st.error(f"Flowchart generation failed: {e}")
                            
                active_mermaid = st.session_state.get(f"mermaid_t_{active_t['ticket_id']}")
                if active_mermaid:
                    render_mermaid(active_mermaid, height=400)
        else:
            st.info("👈 Select a ticket card from 'Today's Works' on the left to view detailed operations, check SOP guidelines, and complete resolutions.")

# ── Tab 3: Floor Plans ───────────────────────────────────────────────────────
with tab_blueprints:
    st.header("🗺️ Digital Twin Blueprint Reader")
    st.caption("Explore interactive building floor plans matching the active global location selector.")
    
    st.markdown(f"#### 🗺️ Current Location: **{selected_floor}** — Room **{selected_room}**")
    
    blueprint_path = FLOOR_PLANS.get(selected_floor)
    if blueprint_path and os.path.exists(blueprint_path):
        st.image(
            blueprint_path,
            use_container_width=True,
            caption=f"SB1 Science Library · {selected_floor} Blueprint View (Highlight Room: {selected_room})",
        )
    else:
        st.warning(
            f"Blueprint image for {selected_floor} not found in resources."
        )
        
    st.divider()
    with st.expander("ℹ️ About SB1 Floor Plans", expanded=True):
        st.markdown(
            """
Currently, only **architectural floor plans** are loaded as base templates. 
The UCI facilities contact is actively preparing the digital twin layer containing:
- Plumbing pipe networks and main valves
- Electrical panels, busways, and load loops
- HVAC duct runs and damper control valves
            """
        )

# ── Tab 4: Asset Registry ────────────────────────────────────────────────────
with tab_registry:
    st.header("📦 Asset Registry")
    st.caption("A persistent record of all assets onboarded by your team. Filter, search, and track status across the facility.")

    # ── Load all assets from DB ──
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT asset_id, asset_name, system_group, floor, room,
                   risk_score, risk_tier, sop_code, tags,
                   leak_detected, corrosion_found,
                   onboarded_by, onboarded_at, notes
            FROM asset_catalog
            ORDER BY onboarded_at DESC
        """)
        registry_rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        registry_rows = []
        st.error(f"Failed to load Asset Registry: {e}")

    # ── Summary stats bar ──
    total_assets = len(registry_rows)
    high_risk     = sum(1 for r in registry_rows if r[5] >= 7)
    leak_count    = sum(1 for r in registry_rows if r[9])
    corr_count    = sum(1 for r in registry_rows if r[10])

    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("🏷️ Total Assets", total_assets)
    sm2.metric("🚨 High Risk (7+)", high_risk, delta=None)
    sm3.metric("💧 Leak Detected", leak_count)
    sm4.metric("⚙️ Corrosion Found", corr_count)

    st.divider()

    if not registry_rows:
        st.info("📭 No assets have been saved to the registry yet. Head to **📸 Onboarding Asset** and click **💾 Save to Asset Registry** after running diagnostics.")
    else:
        # ── Filters ──
        with st.expander("🔍 Filter Assets", expanded=True):
            fc1, fc2, fc3 = st.columns(3)
            all_systems = sorted(set(r[2] for r in registry_rows if r[2]))
            all_floors  = sorted(set(r[3] for r in registry_rows if r[3]))
            all_tiers   = sorted(set(r[6] for r in registry_rows if r[6]))

            filt_sys  = fc1.multiselect("System Group",  all_systems, default=all_systems, key="reg_filt_sys")
            filt_floor = fc2.multiselect("Floor",        all_floors,  default=all_floors,  key="reg_filt_floor")
            filt_tier  = fc3.multiselect("Risk Tier",    all_tiers,   default=all_tiers,   key="reg_filt_tier")
            search_kw  = st.text_input("🔎 Search by asset name, operator, or tags:", key="reg_search")

        filtered = [
            r for r in registry_rows
            if (not filt_sys   or r[2] in filt_sys)
            and (not filt_floor or r[3] in filt_floor)
            and (not filt_tier  or r[6] in filt_tier)
            and (not search_kw  or search_kw.lower() in (str(r[1])+str(r[8])+str(r[11])).lower())
        ]

        st.caption(f"Showing **{len(filtered)}** of **{total_assets}** registered assets")
        st.divider()

        # ── Asset Cards ──
        for r in filtered:
            (
                asset_id, asset_name, system_group, floor, room,
                risk_score, risk_tier, sop_code, tags,
                leak_detected, corrosion_found,
                onboarded_by, onboarded_at, notes
            ) = r

            risk_color = (
                "#fee2e2" if risk_score >= 7
                else "#fef3c7" if risk_score >= 4
                else "#dcfce7"
            )
            risk_badge = (
                "🔴 High" if risk_score >= 7
                else "🟡 Medium" if risk_score >= 4
                else "🟢 Low"
            )

            with st.container(border=True):
                card_top, card_actions = st.columns([4, 1])
                with card_top:
                    st.markdown(
                        f"""<div style='display:flex; align-items:center; gap:12px;'>
                            <div style='background:{risk_color}; border-radius:10px; padding:8px 16px;
                                        font-weight:700; font-size:15px; border:1.5px solid #e5e7eb;'>
                                📦 {asset_name}
                            </div>
                            <span style='color:#64748b; font-size:13px;'>ID: <code>{asset_id}</code></span>
                            <span style='color:#64748b; font-size:13px;'>|</span>
                            <span style='font-size:13px; font-weight:600;'>{risk_badge} Risk ({risk_score}/10)</span>
                        </div>""",
                        unsafe_allow_html=True
                    )
                    st.markdown("")
                    info_c1, info_c2, info_c3 = st.columns(3)
                    info_c1.markdown(f"**🛠️ System:** {system_group or 'N/A'}")
                    info_c1.markdown(f"**📍 Location:** {floor} · Room {room}")
                    info_c2.markdown(f"**📖 SOP:** `{sop_code or 'N/A'}`")
                    info_c2.markdown(f"**👤 Onboarded by:** {onboarded_by or 'Unassigned'}")
                    info_c3.markdown(f"**💧 Leak:** {'🚨 Yes' if leak_detected else '✔️ No'}  |  **⚙️ Corrosion:** {'🚨 Yes' if corrosion_found else '✔️ No'}")
                    info_c3.markdown(f"**🏷️ Tags:** {tags or '—'}")
                    if notes:
                        st.caption(f"📝 Notes: {notes}")
                    st.caption(f"🕐 Onboarded at: {onboarded_at}")

                with card_actions:
                    if st.button("🗑️ Remove", key=f"reg_del_{asset_id}", type="secondary", use_container_width=True):
                        try:
                            conn = sqlite3.connect(DB_PATH)
                            conn.execute("DELETE FROM asset_catalog WHERE asset_id = ?", (asset_id,))
                            conn.commit()
                            conn.close()
                            st.success(f"Asset {asset_id} removed.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Delete failed: {ex}")

    st.divider()
    with st.expander("🔧 Registry Maintenance"):
        if st.button("🗑️ Clear Entire Asset Registry", type="secondary"):
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("DELETE FROM asset_catalog")
                conn.commit()
                conn.close()
                st.success("Asset Registry cleared.")
                st.rerun()
            except Exception as ex:
                st.error(f"Failed: {ex}")

# ── System Maintenance and Factory Reset ──────────────────────────────────────
st.divider()
with st.expander("🛠️ Advanced Developer Panel"):
    st.warning("⚠️ Critical developer actions — proceed with caution.")
    if st.button("🗑️ Clear All Operational Tickets (System Reset)", type="secondary"):
        res = clear_all_tickets()
        st.success(res)
        st.rerun()

st.divider()
st.caption(
    "InsureMEP Unified Workbench · Powered by Gemini 2.5 Flash + Q-Learning RL Engine"
)
