import streamlit as st
import tempfile
import os
import numpy as np
from test_end_to_end import analyze_image_with_gemini
from rl_sop_integration import train_q_learning
from google import genai
from google.genai import types
from ticket_manager import search_sops, create_ticket, get_open_tickets, update_ticket_status
import sqlite3

def get_sop_details(sop_code):
    try:
        conn = sqlite3.connect('insuremep_sops.db')
        c = conn.cursor()
        c.execute("SELECT sop_name, condition_type FROM sop_catalog WHERE sop_code=?", (sop_code,))
        row = c.fetchone()
        conn.close()
        return row if row else ("Unknown SOP", "No condition specified")
    except Exception:
        return ("Unknown SOP", "N/A")

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
    # Dynamically trains on the latest SOP DB (incorporating the new downloaded HTML files!)
    q_table, env = train_q_learning(episodes=5000)
    return q_table, env

q_table, rl_env = load_rl_model()

# Must be the first Streamlit command
st.set_page_config(layout="wide", page_title="InsureMEP RL Decision Engine", page_icon="⚙️")

# Header with Logo
lcol, rcol = st.columns([1, 8], vertical_alignment="center")
with lcol:
    try:
        st.image("assets/logo.png", use_container_width=True)
    except:
        pass
with rcol:
    st.title("InsureMEP Workbench")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Multimodal Onboarding Intake")
    st.info("Upload an equipment photo. Gemini Vision AI will automatically detect asset type, leaks, corrosion, and risk level.")
    
    floor_plans = {
        "Floor 1 (Ground)": "assets/IMG_4999.JPG",
        "Floor 2": "assets/IMG_5001.JPG",
        "Floor 3": "assets/IMG_5002.JPG",
        "Floor 4": "assets/IMG_5003.JPG",
        "Floor 5 (Roof)": "assets/IMG_5004.JPG"
    }
    
    ROOM_DATA = {
        "Floor 1 (Ground)": ["1000A", "1000B", "1100A", "1100B", "1100C", "1120", "1128A", "1128B", "1200", "AHU-1", "AHU-2", "AHU-3", "AHU-4", "FCU-1", "FCU-2", "FCU-4", "Starbucks", "Other"],
        "Floor 2": ["2011", "2015", "2100", "FCU-3", "FCU-2", "2125", "2904", "2200", "2300", "2900", "2311", "2321", "2409", "2516", "2511", "2512", "2400B", "2325", "2400A", "2500", "2508", "2504", "2502", "Other"],
        "Floor 3": ["3100", "3107", "3205", "3207", "3211", "3215", "3216", "3226", "3229", "3232", "3235", "3300", "3309", "3310A", "3310B", "3310C", "3310D", "3317", "3321", "3401", "3402", "3410", "3901", "3902", "Other"],
        "Floor 4": ["4101", "4107", "4111", "4200", "4202", "4208", "4212", "4214", "4300", "4303", "4311", "4317", "4401", "4410", "4502", "4504", "4508", "4514", "4530", "4540", "4562", "4600", "4601", "4606", "4612", "4617", "4618", "4900", "4902", "Other"],
        "Floor 5 (Roof)": ["5110", "5200A", "5200B", "5301", "5302", "5305", "5310", "5311", "5400", "5402", "5408", "5420", "5500", "5502", "5508", "5516", "5524", "5600", "5601", "5603", "5604", "5607", "5608", "5900A", "5900B", "Other"]
    }
    
    c1, c2 = st.columns(2)
    with c1:
        selected_floor = st.selectbox("🏗️ Select Building Floor", list(floor_plans.keys()))
    with c2:
        locations = ROOM_DATA.get(selected_floor, ["Unknown"])
        selected_loc = st.selectbox("📍 Select Asset Room/Location", locations)
    
    with st.expander(f"🗺️ View {selected_floor} Blueprint", expanded=True):
        st.image(floor_plans[selected_floor], use_container_width=True)
        
    uploaded_file = st.file_uploader("Upload Asset Photo (JPG/PNG)", type=["png", "jpg", "jpeg"])
    
    if uploaded_file is not None:
        st.image(uploaded_file, caption=f"{uploaded_file.name} (Uploaded)", use_container_width=True)

with col2:
    st.subheader("2. Database & RL Decision Engine")
    
    if uploaded_file is not None:
        with st.spinner("Analyzing via Gemini Vision API & Running RL Policy..."):
            try:
                # Call gemini with caching so chatting doesn't trigger a rerun and change risk scores!
                data = get_cached_vision_data(uploaded_file.getvalue())
                
                # Logic to map Gemini visual features -> RL State Space (from DB)
                leak = data.get('visual_leak_detected')
                corr = data.get('visual_corrosion_detected')
                valve = data.get('valve_accessible')
                sys_grp = data.get('system_group', 'General')
                obligations = data.get('obligations_overdue_estimate', 0)
                
                target_code = "HVAC_ROUTINE"
                if sys_grp == "Plumbing":
                    if leak and not valve: target_code = "PLUMBING_MAJOR_LEAK"
                    elif obligations > 0: target_code = "PLUMBING_OBLIGATION_OVERDUE"
                    elif corr: target_code = "PLUMBING_CORROSION"
                    elif leak: target_code = "PLUMBING_MINOR_LEAK"
                    else: target_code = "PLUMBING_ROUTINE"
                elif "Elect" in sys_grp or sys_grp == "Low Voltage":
                    if leak: target_code = "ELEC_WATER_EXPOSURE"
                    elif corr: target_code = "ELEC_CORRODED_PANEL"
                    else: target_code = "ELEC_ROUTINE"
                else: # Default HVAC and others
                    if leak and not valve: target_code = "HVAC_LEAK_CONDENSATE"
                    elif leak: target_code = "HVAC_REF_LEAK"
                    elif corr: target_code = "HVAC_OVERHEAT" 
                    else: target_code = "HVAC_ROUTINE"
                    
                # Inference via Q-table learned policy mapping
                state_idx = 0
                for i, row in enumerate(rl_env.state_map):
                    if row[0] == target_code:
                        state_idx = i
                        break
                state_code = rl_env.state_map[state_idx][0]
                best_action_idx = np.argmax(q_table[state_idx])
                best_action = rl_env.action_space[best_action_idx].upper()
                q_vals = q_table[state_idx]
                
                # Fetch readable SOP details from database
                sop_name, condition_type = get_sop_details(state_code)
                
                # Render the right panel dynamically
                st.info(f"🤖 Gemini Observations: {data.get('observations', 'N/A')}")
                
                with st.expander("Show Raw SQL ETL Output"):
                    st.json(data)
                
                # Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Risk Score", f"{data.get('risk_score', 0)}/10", f"{data.get('risk_tier', 'Low')} Tier", delta_color="inverse")
                m2.metric("Mapped RL State", state_code)
                m3.metric("Valve Accessible", "Yes" if valve else "No")
                
                # Detailed findings
                st.markdown("### 💀 RL Decision Engine Output")
                
                leak_status = "✔️ No Leak" if not leak else "⚠️ Leak Detected"
                corr_status = "✔️ No Corrosion" if not corr else "⚠️ Corrosion Detected"
                
                st.info(f"""
**Asset Category:** {state_code} | **Type:** {data.get('asset_type', 'Unknown')} | **Trade:** {data.get('system_group', 'General')}

📋 **Triggered Standard Operating Procedure (SOP):**
* **SOP Protocol:** {sop_name}
* **Detected Condition:** {condition_type}

**Gemini Vision Findings:**
* {leak_status}
* {corr_status}
* Risk 🟢 {data.get('risk_score')}/10 ({data.get('risk_tier')})
* ✔️ Valve Accessible: {'True' if valve else 'False'}

🧠 **RL Model Recommendation (trained on NEW SOP rules):**

# 🔍 {best_action}
                """)
                
                if st.button("🎟️ 1-Click Create Ticket based on RL Action", type="primary"):
                    desc = f"Visual Findings: {data.get('observations', 'N/A')}. RL Action: {best_action}."
                    asset = data.get('asset_type', 'Unknown_Asset')
                    full_location = f"{selected_floor} - {selected_loc}"
                    res = create_ticket(asset_id=asset, description=desc, sop_code=state_code, location=full_location)
                    st.success(res)
                
                with st.expander("Q-Values Breakdown"):
                    st.markdown(f"""
                    - **State Mapping:** Indexed to `{state_code}`
                    - **Action `IGNORE`:** {q_vals[0]:.4f}
                    - **Action `INSPECT`:** {q_vals[1]:.4f}
                    - **Action `MAINTENANCE`:** {q_vals[2]:.4f}
                    - **Action `URGENT REPAIR`:** {q_vals[3]:.4f}
                    - **Action `URGENT IF NEAR ELEC`:** {q_vals[4]:.4f}
                    """)
            except Exception as e:
                st.error(f"Error processing image: {e}")
    else:
        st.info("Waiting for photo upload...")

# --- LIVE TICKETS DASHBOARD ---
st.divider()
st.subheader("📊 Live Tickets Dashboard")
st.markdown("Monitor real-time maintenance requests and statuses.")

try:
    conn = sqlite3.connect('insuremep_sops.db')
    cursor = conn.cursor()
    # Check if notes column exists
    cursor.execute("PRAGMA table_info(tickets)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "location" in columns and "notes" in columns:
        cursor.execute("SELECT ticket_id, asset_id, description, sop_code, location, status, notes, created_at FROM tickets ORDER BY created_at DESC LIMIT 10")
        cols = ["Ticket ID", "Asset", "Description", "SOP Code", "Location", "Status", "Notes", "Created At"]
    elif "notes" in columns:
        cursor.execute("SELECT ticket_id, asset_id, description, sop_code, status, notes, created_at FROM tickets ORDER BY created_at DESC LIMIT 10")
        cols = ["Ticket ID", "Asset", "Description", "SOP Code", "Status", "Notes", "Created At"]
    else:
        cursor.execute("SELECT ticket_id, asset_id, description, sop_code, status, created_at FROM tickets ORDER BY created_at DESC LIMIT 10")
        cols = ["Ticket ID", "Asset", "Description", "SOP Code", "Status", "Created At"]
        
    rows = cursor.fetchall()
    if rows:
        data_list = [dict(zip(cols, r)) for r in rows]
        st.dataframe(data_list, use_container_width=True)
        
        # Simple button to close tickets
        open_tickets = [r for r in rows if r[4] == 'OPEN']
        if open_tickets:
            st.markdown("**Quick Close Ticket:**")
            c1, c2 = st.columns([3, 1])
            with c1:
                selected_ticket = st.selectbox("Select an OPEN ticket to close:", [f"{t[0]} - {t[1]}" for t in open_tickets], label_visibility="collapsed")
            with c2:
                if st.button("✅ Mark as Closed", use_container_width=True):
                    t_id = selected_ticket.split(" - ")[0]
                    res = update_ticket_status(t_id, "CLOSED", "Closed via Quick Button")
                    st.success(res)
                    st.rerun()
    else:
        st.info("No tickets found in the system.")
    conn.close()
except Exception as e:
    st.warning(f"Dashboard unavailable. Please initialize the database. {e}")

# --- INTERACTIVE CHATBOT ---
st.divider()
st.subheader("💬 Interactive Maintenance Assistant")
st.markdown("Ask the AI about the visual findings, RL decisions, or request SOP generation.")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am your InsureMEP AI Agent. Upload a photo above to begin bounding box analysis, or ask me any questions about building maintenance protocols."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Type your question here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Consulting Maintenance AI..."):
            try:
                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                
                # Context building from previous state
                sys_context = "No asset analyzed yet."
                if uploaded_file is not None and 'data' in locals() and 'best_action' in locals():
                    sys_context = f"Asset Type: {data.get('asset_type')}, Risk Level: {data.get('risk_score')}/10, Overdue Obligations: {obligations}. The underlying AI RL Engine recommendation was {best_action} because the SOP database matched condition: '{condition_type}'."

                system_prompt = f"You are the InsureMEP critical infrastructure AI assistant. You answer technical engineering questions concisely based ONLY on the following current asset context: {sys_context}. If a user requests a ticket or reports an issue, you MUST use the `search_sops` tool to find the correct SOP, then use the `create_ticket` tool. If a user tells you they have completed or fixed a ticket, you MUST use `update_ticket_status` to close it (and you can use `get_open_tickets` if you need to find the ID)."
                
                # Reconstruct history to support multi-turn chat and tools
                history = []
                for m in st.session_state.messages:
                    if m["content"].startswith("Hello! I am"): continue
                    role = 'user' if m["role"] == 'user' else 'model'
                    history.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
                    
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[search_sops, create_ticket, get_open_tickets, update_ticket_status],
                    temperature=0.2
                )
                
                chat = client.chats.create(model="gemini-2.5-flash", config=config, history=history)
                api_response = chat.send_message(prompt)
                response_text = api_response.text
            except Exception as e:
                response_text = f"Warning: Connection to Gemini Assistant failed. ({e})"
                
        st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

