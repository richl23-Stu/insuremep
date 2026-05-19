import os


import json


import numpy as np


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from google import genai
from google.genai import types

try:
    from rl_prototype_env import InsureMEPEnv, actions, action_names, get_q, update_q, SYSTEM_GROUPS
except ImportError:
    pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))




client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))





def analyze_image_with_gemini(image_path: str) -> dict:


    prompt = """


You are a critical infrastructure asset inspector AI. Analyze this equipment/asset photo and respond ONLY with a valid JSON object (no markdown, no explanation) in exactly this format:





AGENTIC GRID VISION: Mentally divide the image into a 2x2 grid (Top-Left, Top-Right, Bottom-Left, Bottom-Right). Scan each quadrant carefully to locate detailed inspection points, paying special attention to Control Valves (for Plumbing/HVAC) or emergency shutoffs.





{


  "asset_type": "<specific equipment type, e.g. Air Handling Unit, Electrical Panel. If blueprint, use 'Floor Plan / Blueprint'>",


  "control_valve_visible": <true or false, check grids to see if a valve/shutoff is clearly visible>,


  "valve_accessible": <true or false, is the valve unobstructed for emergency SOP?>,


  "system_group": "<one of: HVAC, Electrical, Electrical/Power, Fire/Life Safety, Plumbing, Controls/OT, Elevator, Environmental, Mechanical, Structural, Medical Gas, Food Service, Low Voltage, Security, Roofing, General>",


  "visual_leak_detected": <true or false>,


  "visual_corrosion_detected": <true or false>,


  "estimated_age_years": <integer estimate or null if unknown>,


  "risk_score": <integer 1-10>,


  "risk_tier": "<Low, Medium, or High>",


  "obligations_overdue_estimate": <integer 0-10, estimate based on visible condition>,


  "is_under_warranty": <true or false, estimate based on apparent age and condition>,


  "tags": ["<tag1>", "<tag2>", "<tag3>"],


  "confidence": <float 0.0-1.0>


}


"""


    import time


    


    with open(image_path, "rb") as f:


        image_bytes = f.read()





    max_retries = 3


    for attempt in range(max_retries):


        try:


            response = client.models.generate_content(


                model="gemini-2.5-flash",


                contents=[


                    types.Part.from_text(text=prompt),


                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),


                ]


            )


            break


        except Exception as e:


            if attempt == max_retries - 1:


                raise e


            if "503" in str(e) or "429" in str(e) or "UNAVAILABLE" in str(e) or "INTERNAL" in str(e):


                time.sleep(2)


            else:


                raise e





    raw = response.text.strip()


    if raw.startswith("```"):


        raw = raw.split("```")[1]


        if raw.startswith("json"):


            raw = raw[4:]


    raw = raw.strip()


    return json.loads(raw)





def main():


    print("--- 1. Training RL Agent (Fast Boot) ---")


    import random


    env = InsureMEPEnv()


    epsilon = 1.0


    for episode in range(5000):


        state = env.reset()


        done = False


        while not done:


            action = random.choice(actions) if random.random() < epsilon else np.argmax([get_q(state, a) for a in actions])


            next_state, reward, done, _ = env.step(action)


            update_q(state, action, reward, next_state)


            state = next_state


            if env.time_since_last_inspection > 60:


                done = True


        epsilon = max(0.05, epsilon * 0.9995)


    print("RL Agent training complete.\\n")





    test_image = "page_07_hvac_detail.png"


    print(f"--- 2. Analyzing Image: {test_image} ---")


    vision_result = analyze_image_with_gemini(test_image)


    print(json.dumps(vision_result, indent=2))


    


    print("\\n--- 3. Structuring RL State & Executing Decision Engine ---")


    sys_grp = vision_result.get("system_group", "General")


    risk_score = vision_result.get("risk_score", 5)


    obligations = vision_result.get("obligations_overdue_estimate", 0)


    leak = vision_result.get("visual_leak_detected", False)


    corrosion = vision_result.get("visual_corrosion_detected", False)


    warranty = vision_result.get("is_under_warranty", False)





    r_level = 0 if risk_score < 5 else (1 if risk_score < 8 else 2)


    oblig_bucket = 0 if obligations == 0 else (1 if obligations <= 3 else 2)


    valve_acc = vision_result.get("valve_accessible", False)


    


    state_vector = (


        sys_grp,


        r_level,


        0,    # time_since_last_inspection (fresh onboarding)


        1,    # time_since_last_maintenance


        1 if leak else 0,


        1 if corrosion else 0,


        1,    # compliance_flag


        oblig_bucket,


        1 if warranty else 0,


        1 if valve_acc else 0,


    )


    


    print(f"State Vector Built: {state_vector}")


    


    q_values = [get_q(state_vector, a) for a in actions]


    best_action_idx = int(np.argmax(q_values))


    recommended_action = action_names[best_action_idx]


    


    print("\\nQ-Values Breakdown:")


    for i, (name, q) in enumerate(zip(action_names, q_values)):


        is_best = ">" if i == best_action_idx else " "


        print(f"{is_best} {name:25s}: {q:+.3f}")


        


    print(f"\\n[FINAL RL RECOMMENDATION]: {recommended_action.upper()}")





if __name__ == '__main__':


    main()


