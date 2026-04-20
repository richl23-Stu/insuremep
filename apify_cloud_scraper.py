import os
import time
import requests
import json
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# The user needs to supply their Apify token in the .env file.
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# We choose a highly-rated, robust LinkedIn Scraper Actor currently available on Apify.
# This ID might be customized depending on the specific actor the user subscribes to.
ACTOR_ID = "curious_coder/linkedin-jobs-scraper" 

def run_apify_scraper():
    print("========== 🏢 Apify Cloud Scraper Interface ==========\n")
    if not APIFY_TOKEN:
        print("❌ ERROR: APIFY_API_TOKEN is not set in your .env file!")
        print("To fix this:")
        print("  1. Go to https://console.apify.com/account/integrations")
        print("  2. Copy your unique API Token.")
        print("  3. Add this line into your 'scratch/cactus/.env' file:")
        print("     APIFY_API_TOKEN=apify_api_XXXXXXXXXXXXXXX")
        print("\nExiting script.")
        return

    print("🚀 Connecting to Apify to deploy cloud scraper for LinkedIn Data Analyst roles...")
    
    # 1. Provide search parameters for the Apify Actor (curious_coder requires urls)
    run_input = {
        "urls": ["https://www.linkedin.com/jobs/search?keywords=Data%20Analyst&location=United%20States&f_TPR=r604800"]
    }
    
    actor_id_safe = ACTOR_ID.replace('/', '~')
    url = f"https://api.apify.com/v2/acts/{actor_id_safe}/runs?token={APIFY_TOKEN}"
    headers = {"Content-Type": "application/json"}
    
    try:
        # POST request to start the Actor run
        response = requests.post(url, json=run_input, headers=headers)
        if response.status_code != 201:
            print(f"❌ Failed to start run on Apify. Error: {response.text}")
            return
            
        run_data = response.json().get("data", {})
        run_id = run_data.get("id")
        dataset_id = run_data.get("defaultDatasetId")
        
        print(f"✅ Cloud Scraper successfully deployed! (Run ID: {run_id})")
        print(f"⏳ Waiting for the remote browser to extract jobs (This may take 1-2 minutes)...\n")
        
        # 2. Polling to wait for the run to complete
        status = "RUNNING"
        while status not in ["SUCCEEDED", "FAILED", "ABORTED"]:
            time.sleep(5)
            status_res = requests.get(f"https://api.apify.com/v2/actor-runs/{run_id}")
            if status_res.status_code == 200:
                current_status = status_res.json()["data"]["status"]
                if current_status != status:
                    print(f"  --> Apify Task Status Updated: {current_status}")
                    status = current_status
                else:
                    print(f"  ... still processing ...")
                    
        # 3. Retrieve the scraped dataset
        if status == "SUCCEEDED":
            print("\n📡 Scrape complete! Fetching dataset from cloud storage...")
            data_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?format=json"
            data_response = requests.get(data_url)
            scraped_jobs = data_response.json()
            
            # 4. Standardize the format to map directly into out sniper_web.py system
            standardized_jobs = []
            for job in scraped_jobs:
                standardized_jobs.append({
                    "company": job.get("companyName", job.get("company", "Unknown")),
                    "positionName": job.get("title", job.get("position", "Data Analyst")),
                    "location": job.get("location", "United States"),
                    "url": job.get("link", job.get("url", job.get("applyUrl", ""))),
                    "description": job.get("descriptionText", job.get("description", job.get("jobDescription", "")))
                })
                
            # Overwrite the target JSON file that the Streamlit UI reads from
            output_file = "apify_job_results_demo.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(standardized_jobs, f, indent=4, ensure_ascii=False)
                
            print(f"\n🎉 SUCCESS! Extracted {len(standardized_jobs)} authentic LinkedIn jobs.")
            print(f"📂 Jobs strictly saved to '{output_file}'.")
            print("🚀 The Streamlit Web UI has automatically recognized this new data. Refresh your browser!")
        else:
            print(f"\n❌ Apify cloud scraper failed with status: {status}")
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out. Apify is taking too long to respond.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
        
    print("\n========================================================")

if __name__ == "__main__":
    run_apify_scraper()
