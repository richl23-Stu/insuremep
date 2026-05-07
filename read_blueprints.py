import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def analyze_blueprints():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    images = ["IMG_4999.JPG", "IMG_5001.JPG", "IMG_5002.JPG", "IMG_5003.JPG", "IMG_5004.JPG"]
    base_path = r"c:\Users\Administrator\.gemini\antigravity\scratch\9-20260421T084832Z-3-001"
    
    # find images
    image_paths = []
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file in images:
                image_paths.append(os.path.join(root, file))
                
    for path in image_paths:
        try:
            sample_file = client.files.upload(file=path)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    "Analyze this architectural floor plan. Extract all the room numbers visible on this blueprint (e.g., 1128, 1152, etc.). Output ONLY a comma-separated list of room numbers/names. No other text.",
                    sample_file
                ]
            )
            print(f"--- {os.path.basename(path)} ---")
            print(response.text.strip())
        except Exception as e:
            print(f"Error on {path}: {e}")

if __name__ == "__main__":
    analyze_blueprints()
