import requests
import json
import time
import sys
from io import BytesIO
from app import analyze_image_with_gemini

sys.stdout.reconfigure(encoding='utf-8')

# MOCK PAYLOAD: The exact JSON you just intercepted from uci.criticalasset.tech
RAW_API_RESPONSE = """
[
    {
        "id": "e831b9fd-f7fa-49b8-83eb-c9d401a25f5c",
        "file_name": "73d7f436-651c-48d7-999e-cd163198ff46_Conf__1_fire_sprinkler_1772136093472.jpg",
        "location_path": [
            "University of California, Irvine",
            "SB1",
            "Ground Floor",
            "Conf. 1"
        ],
        "asset_name": "fire sprinkler",
        "asset_category": "FLS",
        "url": "https://zmdibgmloboukgkwsgre.supabase.co/storage/v1/object/public/photos/73d7f436-651c-48d7-999e-cd163198ff46/73d7f436-651c-48d7-999e-cd163198ff46_Conf__1_fire_sprinkler_1772136093472.jpg"
    },
    {
        "id": "2f2c1da0-549a-465b-a95c-b726aaf65a13",
        "file_name": "e0564dce-d212-457d-ba40-620cc2babd43_Lobby_Main_Transformer_1772137827847.jpg",
        "location_path": [
            "University of California, Irvine",
            "SB1",
            "Ground Floor",
            "Lobby"
        ],
        "asset_name": "Main Transformer",
        "asset_category": "MEP",
        "url": "https://zmdibgmloboukgkwsgre.supabase.co/storage/v1/object/public/photos/e0564dce-d212-457d-ba40-620cc2babd43/e0564dce-d212-457d-ba40-620cc2babd43_Lobby_Main_Transformer_1772137827847.jpg"
    }
]
"""

def sync_critical_assets():
    print("🚀 [1/3] Intercepting data from CriticalAsset Tech API...")
    assets = json.loads(RAW_API_RESPONSE)
    print(f"📦 Found {len(assets)} assets waiting for Agentic Vision Validation.\\n")

    for asset in assets:
        print(f"==================================================")
        print(f"🔍 Analyzing Asset ID: {asset['id']}")
        print(f"📍 Location Hierarchy: {' > '.join(asset['location_path'])}")
        print(f"🏷️ Declared Name: {asset.get('asset_name', 'Unknown')} ({asset.get('asset_category', 'Unknown')})")
        print(f"📥 Downloading image from Supabase Storage...")
        
        try:
            # Download the image from the URL into memory
            response = requests.get(asset["url"], timeout=10)
            img_file = BytesIO(response.content)
            img_file.name = "downloaded.jpg" # Dummy name for PIL/Gemini
            
            print(f"🤖 Passing to Gemini 2.0 Agentic Grid Engine for Deep Validation...")
            vision_result = analyze_image_with_gemini(img_file)
            
            # Simulated Data Push to Backend
            patch_payload = {
                "asset_id": asset["id"],
                "ai_verified_type": vision_result.get("asset_type"),
                "detected_defects": {
                    "leak": vision_result.get("visual_leak_detected"),
                    "corrosion": vision_result.get("visual_corrosion_detected")
                },
                "sop_validation": {
                    "control_valve_visible": vision_result.get("control_valve_visible", False),
                    "valve_accessible": vision_result.get("valve_accessible", False)
                },
                "ai_risk_score": vision_result.get("risk_score", 0)
            }
            
            print(f"✅ AI Analysis Complete!")
            print(f"📤 Preparing Database PATCH request to update CriticalAsset Backend:")
            print(json.dumps(patch_payload, indent=2))
            
        except Exception as e:
            print(f"❌ Error processing asset: {e}")
            
        print(f"==================================================\\n")
        time.sleep(1) # Rate limiting

if __name__ == "__main__":
    sync_critical_assets()
