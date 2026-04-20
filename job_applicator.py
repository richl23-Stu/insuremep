import os
import json
import glob
from google import genai
from dotenv import load_dotenv
load_dotenv()

def get_latest_job_file():
    files = glob.glob("apify_job_results_*.json")
    if not files:
        return None
    return max(files, key=os.path.getctime)

def load_resume():
    # Use the tailored gaming DA resume
    resume_path = r"C:\Users\Administrator\.gemini\antigravity\brain\7dc1644f-9c40-4f9e-b478-bb5683107cc7\tailored_resume_gaming.md"
    try:
        with open(resume_path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Resume not found."

def evaluate_and_draft(job, resume, client):
    company = job.get('company', 'Unknown Company')
    title = job.get('positionName', 'Data Analyst')
    desc = job.get('description', '')
    url = job.get('url', 'No URL')
    
    print(f"\nEvaluating: {title} @ {company}...")
    
    sys_prompt = f"""You are an expert career agent formatting an output block.
Analyze this job against the candidate's resume.
Resume: {resume}
Job Describe: {desc}

You must return a JSON block with NO MARKDOWN ticks:
{{
  "match_score": 0-100,
  "reasoning": "brief explanation",
  "cover_letter": "A highly tailored 2-paragraph cover letter using candidate's gaming and EDA background. Say NA if score is below 75"
}}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[sys_prompt]
        )
        # Parse the JSON
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        analysis = json.loads(clean_text)
        return analysis
    except Exception as e:
        print(f"Failed to analyze {company}: {e}")
        return None

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Missing GEMINI_API_KEY")
        return
        
    client = genai.Client(api_key=api_key)
    resume = load_resume()
    
    job_file = get_latest_job_file()
    if not job_file:
        print("No job scraping results found. Run scrape_deep2.py first.")
        return
        
    print(f"Loading jobs from {job_file}...")
    with open(job_file, "r", encoding="utf-8") as f:
        jobs = json.load(f)
        
    # Limit to top 5 jobs for demo
    jobs_to_process = jobs[:5]
    
    results = []
    
    for job in jobs_to_process:
        analysis = evaluate_and_draft(job, resume, client)
        if analysis and analysis.get('match_score', 0) >= 75:
            print(f"[HIGH MATCH] Score: {analysis['match_score']}%")
            print(f"Reason: {analysis['reasoning']}")
            print("--- Generated Cover Letter ---")
            print(analysis['cover_letter'])
            print("-" * 40)
            
            results.append({
                "job": job,
                "analysis": analysis
            })
        else:
            score = analysis.get('match_score', 0) if analysis else 0
            print(f"[Skipped] Score: {score}%. Only processing >= 75%")
            
    with open("ready_to_apply.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"\nSuccessfully generated {len(results)} application packages in ready_to_apply.json")

if __name__ == "__main__":
    main()
