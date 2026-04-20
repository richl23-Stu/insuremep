import os
import time
from dotenv import load_dotenv
import google.generativeai as genai

# Load env variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ ERROR: GEMINI_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=api_key)

RESUME_CONTEXT = """
Candidate background: 
- Current MS Business Analytics student at UC Irvine, graduating mid-2026.
- Has STEM OPT (3 years available).
- Formerly Data Analytics Intern at Thermo Fisher: scraped competitor metrics, managed 400+ entries via ETL, helped feed GPT-4 unstructured text datasets.
- Formerly Data Analysis Intern at DECCO: built KPI dashboards, parsed 1000+ financial transaction entries finding 200+ anomalies.
- Skills: Python, SQL, Tableau, R, A/B Testing, ETL.
- Interested in Gaming, Fintech, and high-growth Startups.
"""

def fetch_startup_jobs():
    """
    Simulates scraping Wellfound/LinkedIn for recent 'Data Analyst' positions.
    In a real production environment, this would use Playwright to login and scrape.
    """
    print("🔍 Scanning Built In LA and Wellfound for recent DA positions...")
    time.sleep(1.5)
    
    mock_jobs = [
        {
            "company": "NextGen AI Health",
            "title": "Data Analyst (Remote/CA)",
            "description": "We are looking for a Data Analyst comfortable with ambiguous datasets at a rapid startup. You will own the primary data pipelines, build dashboards in Tableau, and help us optimize user retention. SQL and Python required.",
            "contact_person": "Jane Doe (Founder & CEO)",
            "contact_email": "jane@nextgenhealth.example.com"
        },
        {
            "company": "Rift Gaming Studios",
            "title": "Data & Growth Analyst",
            "description": "Rift is a stealth-mode Web3/gaming studio forming in Orange County. We need someone to map player telemetry, define KPIs, and work with our engineers to balance the game economy. Experience with Python scraping or game economies is a big plus.",
            "contact_person": "Alex Chen (Hiring Manager)",
            "contact_email": "alex@riftstudios.example.com"
        }
    ]
    return mock_jobs

def generate_cold_email(job):
    print(f"🤖 Generating targeted cold email for {job['company']}...")
    prompt = f"""
    You are an expert career coach helping a talented Data Analytics student write a cold email.
    
    Job Details:
    Company: {job['company']}
    Role: {job['title']}
    Job Description: {job['description']}
    Contact Person: {job['contact_person']}
    
    Candidate Background:
    {RESUME_CONTEXT}
    
    Task:
    Write a highly professional, concise, and compelling cold email from the Candidate to the Contact Person. 
    Do NOT mention 'sponsorship' or 'OPT' at this stage. Focus purely on VALUE ADD.
    Highlight specifically how the candidate's Thermo Fisher (ETL/GPT-4 data) or DECCO (KPIs/anomalies) experience directly maps to the job description problems.
    Make it feel personalized to the startup. Keep it under 150 words.
    """
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    return response.text

def main():
    print("========== 🎯 Startup Sniper System Initialized ==========\n")
    jobs = fetch_startup_jobs()
    
    os.makedirs("sniper_outputs", exist_ok=True)
    
    for i, job in enumerate(jobs):
        print(f"\n✅ Found Target: {job['title']} at {job['company']}")
        email_draft = generate_cold_email(job)
        
        output_file = f"sniper_outputs/Draft_{job['company'].replace(' ', '')}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Target: {job['company']} - {job['title']}\n")
            f.write(f"**Contact:** {job['contact_person']} ({job['contact_email']})\n\n")
            f.write("## Auto-Generated Cold Email Draft:\n\n")
            f.write(email_draft)
            
        print(f"📝 Draft saved to {output_file}")
        
    print("\n========================================================")
    print("✅ All targets processed. Please review the 'sniper_outputs' directory.")

if __name__ == "__main__":
    main()
