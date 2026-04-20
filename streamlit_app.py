import streamlit as st
import json
import tempfile
import os
from test_end_to_end import analyze_image_with_gemini

# Set page config for a wider layout
st.set_page_config(page_title="InsureMEP AI Vision", layout="centered", page_icon="🤖")

st.title("InsureMEP AI Asset Engine")
st.subheader("Agentic Grid Vision - Field Onboarding")
st.markdown("Upload photos of critical mechanical/electrical assets for automated AI feature extraction and risk assessment.")

st.divider()

uploaded_file = st.file_uploader("Upload Asset Image (JPG/PNG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Image Preview", width=500)
    
    if st.button("🚀 Analyze with Gemini Vision API", type="primary"):
        with st.spinner("Running Agentic Grid Scan (Locating control valves, assessing corrosion/leaks)..."):
            # Save uploaded file temporarily for the Gemini API call
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
                
            try:
                # Call our core Gemini ETL Module
                result = analyze_image_with_gemini(tmp_path)
                
                st.success("✅ Analysis Complete!")
                
                # Display metrics visually
                col1, col2, col3 = st.columns(3)
                col1.metric("Identified System", result.get("system_group", "N/A"))
                col2.metric("Overall Risk Score", f"{result.get('risk_score')}/10 ({result.get('risk_tier')})")
                col3.metric("Valve Accessible?", "Yes ✅" if result.get("valve_accessible") else "No ❌")
                
                st.markdown("### Detailed Output JSON schema:")
                st.json(result)
                
            except Exception as e:
                st.error(f"Error communicating with vision model: {e}")
            finally:
                os.remove(tmp_path)
