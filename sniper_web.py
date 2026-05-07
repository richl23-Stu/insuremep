import streamlit as st
import os
import time
import requests
import re
import json
from dotenv import load_dotenv
import google.generativeai as genai

# Page config
st.set_page_config(page_title="Startup Sniper: Auto Cold Emailer", page_icon="🎯", layout="wide")

st.title("🎯 Startup Sniper Web UI (Multi-Platform Edition)")
st.markdown("Instantly write customized cold emails connecting your UC Irvine MSBA and data experience. Supports Live APIs and local JSON integrations for premium job boards!")

# Load env variables (fallback)
load_dotenv()
default_api_key = os.getenv("GEMINI_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key_input = st.text_input("Gemini API Key", value=default_api_key, type="password")
    if not api_key_input:
        st.warning("Please provide a valid Gemini API Key to proceed.")
        st.stop()
        
    st.divider()
    st.header("📡 Data Source")
    data_source_raw = st.radio("Choose your Job Feed:", [
        "🌐 RemoteOK (Live Tech Startups)", 
        "🎯 Otta (Tech/Startup - via JSON)",
        "🎓 Handshake (Campus - via JSON)",
        "📊 DataAnalyst.com (Vertical - via JSON)",
        "💼 LinkedIn/Indeed (via JSON Integration)"
    ])
    
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_real_jobs():
    """Fetches real highly-curated tech jobs using RemoteOK API"""
    url = "https://remoteok.com/api"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        jobs = []
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 1:
                data = data[1:]
                for j in data:
                    title = j.get("position", "Data Role")
                    location = j.get("location", "").lower()
                    
                    # Expanded target keywords for MSBA candidates
                    keywords = ["data", "analyst", "business", "product", "growth", "strategy", "intelligence", "analytics", "bi"]
                    
                    if any(k in title.lower() for k in keywords):
                        if "us" in location or "united states" in location or "worldwide" in location or "anywhere" in location or "america" in location:
                            # We can also capture the listed date to show they are from this month
                            date_posted = j.get("date", "")[:10] if j.get("date") else "Recent"
                            jobs.append({
                                "company_name": j.get("company", "Tech Startup") + f" [Posted: {date_posted}]",
                                "title": title,
                                "candidate_required_location": j.get("location", "Remote US"),
                                "description": j.get("description", ""),
                                "url": j.get("url", "")
                            })
            if jobs:
                # Return up to 60 jobs, which spans across the last 3-4 weeks on RemoteOK
                return jobs[:60] 
    except Exception as e:
        st.error(f"Failed to fetch from RemoteOK API: {e}")
    return []

def fetch_local_integration_data(source_name):
    """Fetches jobs from local JSON files, with realistic fallbacks if the file hasn't been created yet."""
    
    # Map selection to expected filenames
    file_map = {
        "LinkedIn": "apify_job_results_demo.json",
        "Otta": "otta_jobs.json",
        "Handshake": "handshake_jobs.json",
        "DataAnalyst.com": "dataanalyst_jobs.json"
    }
    
    target_file = ""
    for k, v in file_map.items():
        if k in source_name:
            target_file = v
            platform_id = k
            break
            
    # Try loading real JSON file
    if os.path.exists(target_file):
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [{
                    "company_name": j.get("company", f"{platform_id} Unknown"),
                    "title": j.get("positionName", "Data Analyst"),
                    "candidate_required_location": j.get("location", "United States"),
                    "description": j.get("description", ""),
                    "url": j.get("url", "https://linkedin.com")
                } for j in data]
        except: pass
        
    st.info(f"💡 No local `{target_file}` found. Loading realistic platform demonstration jobs for {platform_id}!")
    
    # Platform-specific Realistic Fallbacks
    if platform_id == "Otta":
        return [
            {"company_name": "Stripe (Demo)", "title": "Data Analyst, Growth", "candidate_required_location": "San Francisco / Remote", "url": "https://otta.com", "description": "Sponsorship Available. We are looking for an analyst to drive our product growth pipelines usings SQL and dbt."},
            {"company_name": "Brex (Demo)", "title": "Analytics Engineer", "candidate_required_location": "Remote US", "url": "https://otta.com", "description": "Help us build KPI dashboards. Python, big data experience required."}
        ]
    elif platform_id == "Handshake":
        return [
            {"company_name": "Disney (Campus Recruiting)", "title": "Entry-Level Data Analyst", "candidate_required_location": "Burbank, CA", "url": "https://joinhandshake.com", "description": "Exclusive entry-level role for Spring/Summer grads. Requires BI tool knowledge like Tableau."},
            {"company_name": "Edwards Lifesciences", "title": "Business Analyst (New Grad)", "candidate_required_location": "Irvine, CA", "url": "https://joinhandshake.com", "description": "Local campus hire. Will consider F1/OPT if eligible for 3 years. Help manage data pipelines for medical devices."}
        ]
    elif platform_id == "DataAnalyst.com":
        return [
            {"company_name": "Klaviyo (Demo)", "title": "Marketing Data Analyst", "candidate_required_location": "Remote", "url": "https://dataanalyst.com", "description": "Deep SQL and marketing funnel experience required."},
            {"company_name": "Discord (Demo)", "title": "Trust & Safety Analyst", "candidate_required_location": "Los Angeles, CA", "url": "https://dataanalyst.com", "description": "Analyze anomaly behavior and write python scripts to flag toxicity."}
        ]
    else: # LinkedIn
        return [
            {"company_name": "Riot Games (Demo)", "title": "Data Analyst, Player Dynamics", "candidate_required_location": "Los Angeles, CA", "url": "https://linkedin.com", "description": "Analyze player behavior and anti-toxicity metrics. Gaming analytics required."}
        ]

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).replace("&nbsp;", " ").replace("&amp;", "&").strip()

# Set up Gemini
genai.configure(api_key=api_key_input)

# Resume Context
RESUME_CONTEXT = """
Candidate background: 
- Current MS Business Analytics student at UC Irvine, graduating mid-2026.
- Has STEM OPT (3 years available).
- Formerly Data Analytics Intern at Thermo Fisher: scraped competitor metrics, managed 400+ entries via ETL, helped feed GPT-4 unstructured text datasets.
- Formerly Data Analysis Intern at DECCO: built KPI dashboards, parsed 1000+ financial transaction entries finding 200+ anomalies.
- Skills: Python, SQL, Tableau, R, A/B Testing, ETL.
- Interested in Gaming, Fintech, and high-growth Startups.
"""

st.divider()

# --- API FETCHING SECTION ---
with st.spinner(f"Loading {data_source_raw.split(' ')[0]}..."):
    if "RemoteOK" in data_source_raw:
        live_jobs = fetch_real_jobs()
    else:
        live_jobs = fetch_local_integration_data(data_source_raw)

selected_job = None
if live_jobs:
    st.subheader(f"1. Pick a Listing from {data_source_raw.split(' ')[1]}")
    
    location_filter = st.text_input("🌍 Filter by Region (e.g. 'California', 'Remote', 'NY'):", "")
    if location_filter:
        live_jobs = [j for j in live_jobs if location_filter.lower() in j.get('candidate_required_location', '').lower()]
        
    if not live_jobs:
        st.warning(f"No jobs match '{location_filter}'. Try a broader search like 'US', 'Remote', or clear the box.")
    else:
        job_options = { f"{j['company_name']} - {j['title']} ({j['candidate_required_location']})": j for j in live_jobs }
        selected_job_key = st.selectbox("Active Targets:", ["-- Select a Job --"] + list(job_options.keys()))
        
        if selected_job_key != "-- Select a Job --":
            selected_job = job_options[selected_job_key]

st.subheader("2. Job Details & Email Configuration")

# If user selected a job, show the hyperlink big and bold
if selected_job and selected_job.get("url"):
    st.success(f"🔗 **[Click Here to Apply & View Original Listing on {selected_job['company_name']}]({selected_job['url']})**")

col1, col2 = st.columns(2)

# Pre-fill if a real job is selected
prefill_company = selected_job['company_name'] if selected_job else "e.g. NextGen AI Health"
prefill_role = selected_job['title'] if selected_job else "e.g. Data Analyst"
prefill_desc = selected_job['description'] if selected_job else ""
if prefill_desc: prefill_desc = clean_html(prefill_desc) # Clean up HTML

with col1:
    company_name = st.text_input("Target Company", value=prefill_company)
with col2:
    role_title = st.text_input("Role Title", value=prefill_role)

contact_person = st.text_input("Contact Person (e.g., Hiring Manager / CEO)", "Hiring Team")

job_description = st.text_area("Job Description", value=prefill_desc, height=200, 
                               placeholder="Select a job above, or paste a custom JD here.")

st.divider()
output_type = st.radio("Output Format:", ["✉️ Cold Email (Short & Punchy)", "📄 Cover Letter (Formal & Detailed)"], horizontal=True)
button_text = f"🚀 Generate {output_type.split(' ')[1]} (Streaming)"

if st.button(button_text, type="primary"):
    if not company_name or not role_title or company_name.startswith("e.g."):
        st.error("Please fill in Company Name and Role Title.")
    else:
        st.info(f"Targeting: {role_title} at {company_name}")
        
        if "Cover Letter" in output_type:
            current_date = time.strftime("%B %d, %Y")
            prompt = f"""
            You are an expert career coach helping a talented Data Analytics student write a formal Cover Letter.
            
            Job Details:
            Company: {company_name}
            Role: {role_title}
            Job Description: {job_description}
            
            Candidate Background:
            {RESUME_CONTEXT}
            
            Task:
            Write a highly professional, compelling 3-paragraph Cover Letter from the Candidate.
            The cover letter MUST start precisely with the following header block:
            
            Zhengyi Lin
            Irvine, CA | (949) 304-4640 | richl23@uci.edu | http://linkedin.com/in/zhengyi-lin-28576936a
            
            {current_date}
            
            Hiring Team
            {company_name}
            
            Dear Hiring Manager,
            
            [Begin Content...]
            
            Do NOT mention 'sponsorship' or 'OPT' at this stage. Focus purely on VALUE ADD.
            Highlight specifically how the candidate's Thermo Fisher (ETL/GPT-4 data) or DECCO (KPIs/anomalies) experience directly maps to the actual requirements mentioned in the job description.
            Include the custom header, introduction, body highlighting exactly 2 relevant achievements, and a strong closing paragraph signing off as 'Sincerely, Zhengyi Lin'.
            Maximum 450 words. Make it sound enthusiastic but extremely professional.
            """
        else:
            prompt = f"""
            You are an expert career coach helping a talented Data Analytics student write a cold email.
            
            Job Details:
            Company: {company_name}
            Role: {role_title}
            Job Description: {job_description}
            Contact Person: {contact_person}
            
            Candidate Background:
            {RESUME_CONTEXT}
            
            Task:
            Write a highly professional, concise, and compelling cold email from the Candidate to the Contact Person. 
            Do NOT mention 'sponsorship' or 'OPT' at this stage. Focus purely on VALUE ADD.
            Highlight specifically how the candidate's Thermo Fisher (ETL/GPT-4 data) or DECCO (KPIs/anomalies) experience directly maps to the actual requirements mentioned in the job description.
            Make it feel personalized. Keep it under 150 words. Focus on the actual text in the JD.
            """
        
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt, stream=True)
            
            output_name = "Cover Letter" if "Cover Letter" in output_type else "Cold Email"
            st.markdown(f"### 🤖 Auto-Generated {output_name}:")
            
            message_placeholder = st.empty()
            full_response = ""
            
            for chunk in response:
                full_response += chunk.text
                message_placeholder.markdown(full_response + "▌")
                time.sleep(0.01)
                
            message_placeholder.markdown(full_response)
            st.success("Draft Generated Successfully! You can easily copy this and send it via LinkedIn or Email.")
            
            # --- Export to PDF Logic ---
            try:
                from markdown_pdf import MarkdownPdf, Section
                import tempfile
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    temp_path = tmp.name
                    
                pdf = MarkdownPdf(toc_level=0)
                # Automatically format the PDF title based on company and type
                doc_title = output_type.split(' ')[1]
                pdf_content = f"# {doc_title} - {company_name}\n\n{full_response}"
                
                pdf.add_section(Section(pdf_content))
                pdf.save(temp_path)
                
                with open(temp_path, "rb") as f:
                    pdf_bytes = f.read()
                os.remove(temp_path)
                
                export_name = f"{doc_title}_{company_name.replace(' ', '_')}.pdf"
                
                st.download_button(
                    label="📥 Export as PDF",
                    data=pdf_bytes,
                    file_name=export_name,
                    mime="application/pdf",
                    type="secondary"
                )
            except Exception as pdf_err:
                st.warning(f"Could not generate PDF: {pdf_err}")
                
        except Exception as e:
            st.error(f"An error occurred during Gemini generation: {e}")
