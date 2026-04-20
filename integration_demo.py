import sqlite3
import random
import numpy as np
from datetime import datetime
import json

# 1. We will import the exact Q-learning environment we built earlier
# To make this self-contained and fast for the demo, we will re-train it in < 0.1s
from rl_prototype_env import InsureMEPEnv, actions, action_names

print("[Phase 1/4] Training the RL Agent Policy...")
env = InsureMEPEnv()
Q = {}
def get_q(state, action): return Q.get((str(state), action), 0.0)
def update_q(state, action, reward, next_state):
    max_next = max([get_q(next_state, a) for a in actions])
    old_q = get_q(state, action)
    Q[(str(state), action)] = old_q + 0.1 * (reward + 0.9 * max_next - old_q)

epsilon = 1.0
epsilon_decay = 0.9995
for episode in range(10000):
    state = env.reset()
    done = False
    while not done:
        action = random.choice(actions) if random.random() < epsilon else np.argmax([get_q(state, a) for a in actions])
        next_state, reward, done, _ = env.step(action)
        update_q(state, action, reward, next_state)
        state = next_state
        if env.time_since_last_inspection > 60: done = True
    epsilon = max(0.05, epsilon * epsilon_decay)
print(f"-> RL Agent trained. Q-table holds {len(Q)} states.\n")

# 2. Setup SQLite Database using exactly the user's schema (modified lightly for SQLite compatibility)
print("[Phase 2/4] Setting up SQL Database & Ingesting Mock ETL Data...")
conn = sqlite3.connect(':memory:')  # In-memory database for demo
cursor = conn.cursor()

# Execute table creations similar to the .sql file
cursor.executescript("""
CREATE TABLE asset_instances (
    asset_instance_id TEXT PRIMARY KEY,
    system_group TEXT,
    asset_type_name TEXT,
    installation_date DATE,
    time_since_last_inspection INTEGER,
    time_since_last_maintenance INTEGER
);
CREATE TABLE asset_images (
    image_id TEXT PRIMARY KEY,
    asset_instance_id TEXT
);
CREATE TABLE asset_image_features (
    image_id TEXT,
    visual_leak_flag BOOLEAN,
    visual_corrosion_flag BOOLEAN,
    ocr_confidence_score FLOAT
);
CREATE TABLE risk_scores (
    asset_instance_id TEXT,
    risk_impact_score_pred INT,
    risk_tier_pred TEXT
);
""")

# 3. Simulate Data Intake (e.g. YOLO/VLM just processed a new image from the client)
asset_id = "550e8400-e29b-41d4-a716-446655440000"
image_id = "img_001_leak_detected"

# Insert the asset
cursor.execute("INSERT INTO asset_instances VALUES (?, ?, ?, ?, ?, ?)", 
               (asset_id, 'HVAC', 'AHU-Roof-1', '2019-01-01', 5, 12))
# Insert the image
cursor.execute("INSERT INTO asset_images VALUES (?, ?)", (image_id, asset_id))
# Insert the Computer Vision output (A leak was detected!)
cursor.execute("INSERT INTO asset_image_features VALUES (?, ?, ?, ?)", (image_id, True, False, 0.95))
# Insert the Risk engine output
cursor.execute("INSERT INTO risk_scores VALUES (?, ?, ?)", (asset_id, 8, 'High'))
conn.commit()

print("-> Mock Computer Vision Pipeline correctly inserted Leak & Risk Data into SQL.\n")

# 4. Integrate System: Fetch from SQL -> Pass to RL -> Output Chatbot String
print("[Phase 3/4] Structuring SQL output to RL State vector...")

# Complex query to join the features exactly as described in the PRD!
query = """
SELECT 
    a.system_group,
    r.risk_impact_score_pred,
    a.time_since_last_inspection,
    a.time_since_last_maintenance,
    f.visual_leak_flag,
    f.visual_corrosion_flag
FROM asset_instances a
JOIN risk_scores r ON a.asset_instance_id = r.asset_instance_id
JOIN asset_images i ON a.asset_instance_id = i.asset_instance_id
JOIN asset_image_features f ON i.image_id = f.image_id
WHERE a.asset_instance_id = ?
"""
cursor.execute(query, (asset_id,))
row = cursor.fetchone()

# Format specific to the RL algorithm state logic mapping
sys_grp = row[0]
risk_score_raw = row[1]
t_ins = row[2]
t_mnt = row[3]
leak = 1 if row[4] else 0
corr = 1 if row[5] else 0
compliance = 1  # Mock compliance standard

t_inspect_idx = 0 if t_ins < 3 else (1 if t_ins < 6 else 2)
t_maint_idx = 0 if t_mnt < 3 else (1 if t_mnt < 6 else 2)
risk_level_idx = 0 if risk_score_raw < 5 else (1 if risk_score_raw < 8 else 2)

rl_state = (sys_grp, risk_level_idx, t_inspect_idx, t_maint_idx, leak, corr, compliance)
print(f"-> Converted SQL row to RL State Vector: {rl_state}\n")

print("[Phase 4/4] Generating AI Chatbot Response...")
# Get best action out of RL model
q_values = [get_q(rl_state, a) for a in actions]
best_action_idx = np.argmax(q_values)
recommended_action = action_names[best_action_idx]

# Chatbot generation string
print("==================================================")
print("[INSURE MEP AI CAPSTONE AGENT: LIVE CHATBOT OUTPUT]")
print("==================================================")
print(f"[Asset Instance ID]: {asset_id}")
print(f"[Analysis]: A visual leak was detected by our semantic CV module. The Random Forest backend has assigned an impact score of {risk_score_raw} (Tier: {row[2]}).")
print(f"[RL Model Recommendation]: We strongly recommend **{recommended_action.upper()}**.")
print("==================================================")

conn.close()
