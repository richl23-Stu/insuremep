import os
import time
import requests
import json
from dotenv import load_dotenv

load_dotenv()
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
ACTOR_ID = "orgupdate/handshake-jobs-scraper"

def run_handshake_scraper():
    print("========== 🎓 Apify Cloud Scraper (Handshake Edition) ==========\n")
    if not APIFY_TOKEN:
        print("❌ ERROR: APIFY_API_TOKEN is not set in your .env file!")
        return

    print("🚀 Triggering cloud payload for Handshake University jobs...")
    
    actor_id_safe = ACTOR_ID.replace('/', '~')
    url = f"https://api.apify.com/v2/acts/{actor_id_safe}/runs?token={APIFY_TOKEN}"
    headers = {"Content-Type": "application/json"}
    
    # Handshake generic jobs pull
    run_input = {}
    
    try:
        response = requests.post(url, json=run_input, headers=headers)
        if response.status_code != 201:
            print(f"❌ Failed. Error: {response.text}")
            return
            
        run_data = response.json().get("data", {})
        run_id = run_data.get("id")
        dataset_id = run_data.get("defaultDatasetId")
        
        print(f"✅ Handshake Scraper successfully deployed! (Run ID: {run_id})")
        print(f"⏳ Waiting for extraction (This may take 1-3 minutes)...\n")
        
        status = "RUNNING"
        while status not in ["SUCCEEDED", "FAILED", "ABORTED"]:
            time.sleep(5)
            status_res = requests.get(f"https://api.apify.com/v2/actor-runs/{run_id}")
            if status_res.status_code == 200:
                current_status = status_res.json()["data"]["status"]
                if current_status != status:
                    print(f"  --> Apify Task Status Updated: {current_status}")
                    status = current_status
        
        print("\n📡 Fetching JSON dataset from Apify servers...")            
        if status == "SUCCEEDED":
            data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json"
            data_response = requests.get(data_url)
            scraped_jobs = data_response.json()
            
            # Convert to UI format
            standardized_jobs = []
            for job in scraped_jobs:
                standardized_jobs.append({
                    "company_name": job.get("companyName", job.get("company", "Unknown")),
                    "positionName": job.get("title", job.get("position", "Handshake Role")),
                    "location": job.get("location", "United States"),
                    "url": job.get("url", "https://app.joinhandshake.com/stu/jobs"),
                    "description": job.get("description", job.get("jobDescription", ""))
                })
                
            output_file = "handshake_jobs.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(standardized_jobs, f, indent=4, ensure_ascii=False)
                
            print(f"\n🎉 SUCCESS! Extracted {len(standardized_jobs)} Handshake jobs.")
            print(f"📂 Saved to '{output_file}'. The Streamlit Web UI has automatically recognized this new data!")
        else:
            print(f"\n❌ Scraper failed with status: {status}")
            
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_handshake_scraper()
