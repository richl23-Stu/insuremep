import streamlit as st
import tempfile
import os
import numpy as np
from test_end_to_end import analyze_image_with_gemini
from rl_sop_integration import train_q_learning
from google import genai
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
# st.set_page_config is already set correctly... wait! I need to replace from the top!
st.set_page_config(layout="wide", page_title="InsureMEP RL Decision Engine", page_icon="⚙️")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Multimodal Onboarding Intake")
    st.info("Upload an equipment photo. Gemini Vision AI will automatically detect asset type, leaks, corrosion, and risk level.")
    
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

                system_prompt = f"You are the InsureMEP critical infrastructure AI assistant. You answer technical engineering questions concisely based ONLY on the following current asset context: {sys_context}."
                
                api_response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[system_prompt, f"User Query: {prompt}"]
                )
                response_text = api_response.text
            except Exception as e:
                response_text = f"Warning: Connection to Gemini Assistant failed. ({e})"
                
        st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

