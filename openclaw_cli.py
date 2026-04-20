import os
import sys
import time
import json
from google import genai
from dotenv import load_dotenv

# Optional color init for windows cmd
os.system('color') 

# ANSI Terminal Colors
C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_MAGENTA = '\033[95m'
C_WHITE = '\033[97m'
C_END = '\033[0m'
C_BOLD = '\033[1m'

LOGO = f"""
{C_CYAN}
  ██████╗  |██████╗|███████╗|███╗   ██╗|██████╗|██╗      |█████╗ |██╗    ██╗
 ██╔═══██╗ |██╔══██╗|██╔════╝|████╗  ██║|██╔════╝|██║     ██╔══██╗|██║    ██║
 ██║   ██║ |██████╔╝|█████╗  |██╔██╗ ██║|██║     |██║     ███████║|██║ █╗ ██║
 ██║   ██║ |██╔═══╝ |██╔══╝  |██║╚██╗██║|██║     |██║     ██╔══██║|██║███╗██║
 ╚██████╔╝ |██║     |███████╗|██║ ╚████║╚██████╗ |███████╗██║  ██║╚███╔███╔╝
  ╚═════╝  |╚═╝     |╚══════╝|╚═╝  ╚═══╝ ╚═════╝ |╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ 
                   {C_BOLD}-- AUTONOMOUS JOB APPLICATOR MODULE --{C_END}
"""

def type_text(text, delay=0.03):
    """Types out text character by character like a hacking terminal."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def fast_type(text, delay=0.01):
    type_text(text, delay)

def evaluate_job(job, resume, client):
    desc = job.get('description', '')
    sys_prompt = f"""You are OpenClaw, a highly intelligent career AI agent formatting an output block.
Analyze this job description against the candidate's resume.
Resume: {resume}
Job Describe: {desc}

You must return a JSON block with NO MARKDOWN ticks:
{{
  "match_score": 0-100,
  "reasoning": "A short, sharp 1 sentence explanation of why they fit or don't.",
  "cover_letter": "A highly tailored 2-paragraph cover letter using candidate's gaming and EDA background. Say NA if score is below 75"
}}"""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[sys_prompt]
        )
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        return None

def main():
    # Clear console cross-platform
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print(LOGO)
    
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        type_text(f"{C_RED}[FATAL ERROR] GEMINI_API_KEY not found in environment.{C_END}")
        return

    type_text(f"{C_YELLOW}[SYSTEM] Booting OpenClaw Neuro-Engine...{C_END}", 0.05)
    time.sleep(0.5)
    type_text(f"{C_YELLOW}[SYSTEM] Calibrating Gemini 2.0 Flash Vision-Language Model...{C_END}")
    time.sleep(1)
    type_text(f"{C_GREEN}[SUCCESS] Neural pathways established via Google Cloud.{C_END}")
    print()

    client = genai.Client(api_key=api_key)
    
    try:
        with open("apify_job_results_demo.json", "r", encoding="utf-8") as f:
            jobs = json.load(f)
    except Exception as e:
        type_text(f"{C_RED}[FATAL ERROR] Cannot read scraped job payload: {e}{C_END}")
        return
        
    resume_path = r"C:\Users\Administrator\.gemini\antigravity\brain\7dc1644f-9c40-4f9e-b478-bb5683107cc7\tailored_resume_gaming.md"
    try:
        with open(resume_path, "r", encoding="utf-8") as f:
            resume = f.read()
    except Exception as e:
        type_text(f"{C_RED}[FATAL ERROR] Tailored Resume payload missing: {e}{C_END}")
        return

    fast_type(f"> {C_WHITE}Loaded {len(jobs)} active job listings from scraper buffer.{C_END}")
    fast_type(f"> {C_WHITE}Loaded target candidate profile: Data Analyst (Gaming/Simulation).{C_END}")
    print()
    
    input(f"{C_MAGENTA}>> WAITING FOR USER INPUT: Press [ENTER] to execute Autonomous Deployment...{C_END}")
    
    print()
    for i in range(20):
        sys.stdout.write(f"\r{C_CYAN}[{'='*i}{' '*(20-i)}] INITIALIZING MATRIX...{C_END}")
        sys.stdout.flush()
        time.sleep(0.05)
    print("\n" + "="*60 + "\n")
    
    results = []
    
    for i, job in enumerate(jobs):
        company = job.get('company', 'Unknown')
        title = job.get('positionName', 'Role')
        
        print(f"{C_CYAN}[{i+1}/{len(jobs)}] Target Intercepted: {title} @ {company}{C_END}")
        sys.stdout.write(f"      {C_YELLOW}Evaluating match vector using Gemini 2.0... {C_END}")
        sys.stdout.flush()
        
        analysis = evaluate_job(job, resume, client)
        
        sys.stdout.write("\r" + " "*60 + "\r") # Erase evaluating line
        
        score = analysis.get('match_score', 0) if analysis else 0
        if score >= 75:
            print(f"      {C_GREEN}[HIGH MATCH DETECTED]{C_END} Alignment: {C_BOLD}{score}%{C_END}")
            fast_type(f"      [{C_MAGENTA}OpenClaw Logic{C_END}]: {analysis['reasoning']}")
            
            sys.stdout.write(f"      {C_YELLOW}Drafting tailored application package...{C_END}")
            time.sleep(1)
            sys.stdout.write("\r" + " "*50 + "\r")
            
            print(f"      {C_GREEN}[+] Payload Ready: COVER_LETTER_{company.upper().replace(' ', '_')}.TXT{C_END}")
            print("      " + "-" * 50)
            cover = analysis['cover_letter'].replace('\n', '\n      ')
            print(f"      {cover}")
            print("      " + "-" * 50 + "\n")
            results.append({"job": job, "analysis": analysis})
        else:
            print(f"      {C_RED}[ABORTED]{C_END} Score: {score}%. Failed minimum threshold.\n")
            time.sleep(0.5)
            
    print("="*60)
    fast_type(f"{C_GREEN}[TASK COMPLETED]{C_END} OpenClaw Autonomous Engine entering standby.", 0.02)
    fast_type(f">>> Outbound payloads: {len(results)} application(s) synced to 'ready_to_apply.json'. {C_END}")

if __name__ == "__main__":
    main()
