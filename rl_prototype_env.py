import random
import numpy as np

# ==========================================
# 16 Real-World Asset Trades (from CriticalAsset platform)
# ==========================================
SYSTEM_GROUPS = [
    "HVAC", "Electrical", "Electrical/Power", "Fire/Life Safety",
    "Plumbing", "Controls/OT", "Elevator", "Environmental",
    "Mechanical", "Structural", "Medical Gas", "Food Service",
    "Low Voltage", "Security", "Roofing", "General"
]

# Trade-specific risk multipliers (based on real asset counts from platform)
# Higher = more critical / faster degradation
TRADE_RISK_MULTIPLIER = {
    "HVAC": 1.3,
    "Electrical": 1.2,
    "Electrical/Power": 1.4,
    "Fire/Life Safety": 1.5,   # Safety-critical
    "Plumbing": 1.1,
    "Controls/OT": 1.3,
    "Elevator": 1.6,           # High liability
    "Environmental": 1.0,
    "Mechanical": 1.1,
    "Structural": 1.4,
    "Medical Gas": 1.8,        # Highest risk — life safety
    "Food Service": 1.0,
    "Low Voltage": 0.9,
    "Security": 0.8,
    "Roofing": 1.0,
    "General": 0.7,
}


class InsureMEPEnv:
    """
    Upgraded RL Environment for Critical Asset Maintenance.

    State Vector (7 → 10 features):
      (system_group, risk_level, t_inspect, t_maint,
       visual_leak, visual_corrosion, compliance_flag,
       obligations_overdue, is_under_warranty, valve_accessible)

    Actions:
      0: inspect
      1: schedule_maintenance
      2: urgent_repair
      3: defer
      4: no_action
    """

    def __init__(self):
        self.systems = SYSTEM_GROUPS
        self.reset()

    def reset(self):
        self.system_group = random.choice(self.systems)
        self.risk_score = random.randint(1, 4)
        self.time_since_last_inspection = 0
        self.time_since_last_maintenance = 0
        self.visual_leak = 0
        self.visual_corrosion = 0
        self.compliance_flag = 1
        # New state features
        self.obligations_overdue = random.randint(0, 5)       # real compliance backlog
        self.is_under_warranty = random.choice([True, False]) # 60% coverage on platform
        self.valve_accessible = random.choice([0, 1])         # SOP requirement
        self.is_failed = False
        return self._get_state()

    def _get_state(self):
        # Discretize time: 0-3m=0, 4-6m=1, >6m=2
        t_inspect = 0 if self.time_since_last_inspection < 3 else (1 if self.time_since_last_inspection < 6 else 2)
        t_maint = 0 if self.time_since_last_maintenance < 3 else (1 if self.time_since_last_maintenance < 6 else 2)

        # Discretize risk: Low(1-4)=0, Medium(5-7)=1, High(8-10)=2
        risk_level = 0 if self.risk_score < 5 else (1 if self.risk_score < 8 else 2)

        # Discretize obligations overdue: none=0, few(1-3)=1, many(4+)=2
        oblig_bucket = 0 if self.obligations_overdue == 0 else (1 if self.obligations_overdue <= 3 else 2)

        return (
            self.system_group,
            risk_level,
            t_inspect,
            t_maint,
            self.visual_leak,
            self.visual_corrosion,
            self.compliance_flag,
            oblig_bucket,
            1 if self.is_under_warranty else 0,
            self.valve_accessible
        )

    def step(self, action):
        reward = 0
        event = {
            "prevented_failure": False,
            "failure": False,
            "maintenance_success": False,
            "late_inspection": False,
        }

        # Trade-specific degradation multiplier
        mult = TRADE_RISK_MULTIPLIER.get(self.system_group, 1.0)

        # Advance time
        self.time_since_last_inspection += 1
        self.time_since_last_maintenance += 1

        # Natural degradation (trade-weighted)
        if random.random() < 0.2 * mult:
            self.risk_score = min(10, self.risk_score + 1)
        if self.risk_score >= 6 and random.random() < 0.3:
            self.visual_leak = 1
        if self.risk_score >= 7 and random.random() < 0.3:
            self.visual_corrosion = 1

        # Obligations accumulate over time
        if random.random() < 0.15:
            self.obligations_overdue = min(20, self.obligations_overdue + 1)

        # Execute Action
        if action == 0:  # Inspect
            self.time_since_last_inspection = 0
            if self.risk_score >= 8:
                event["late_inspection"] = True

        elif action == 1:  # Schedule Maintenance
            if self.risk_score >= 5:
                self.risk_score = max(1, self.risk_score - 3)
                self.visual_leak = 0
                self.visual_corrosion = 0
                self.time_since_last_maintenance = 0
                self.obligations_overdue = max(0, self.obligations_overdue - 2)
                event["maintenance_success"] = True
            else:
                reward -= 5  # Unnecessary maintenance

        elif action == 2:  # Urgent Repair
            if self.risk_score >= 8 or self.visual_leak == 1 or self.visual_corrosion == 1:
                # WARRANTY SHAPING: if under warranty, cost is near-zero → bigger reward
                repair_bonus = 8 if self.is_under_warranty else 10
                self.risk_score = 1
                self.visual_leak = 0
                self.visual_corrosion = 0
                self.time_since_last_maintenance = 0
                self.obligations_overdue = max(0, self.obligations_overdue - 3)
                event["prevented_failure"] = True
                reward += repair_bonus  # Warranty-aware bonus
            else:
                reward -= 5  # Unnecessary urgent repair

        elif action == 3 or action == 4:  # Defer / No Action
            self.risk_score = min(10, self.risk_score + 1)

        # Failure probability
        failure_prob = (self.risk_score / 10.0) * 0.5 * mult
        if self.visual_leak == 1:
            failure_prob += 0.2
        if self.visual_corrosion == 1:
            failure_prob += 0.2

        if random.random() < failure_prob and not event["prevented_failure"]:
            self.is_failed = True
            event["failure"] = True

        # Compute rewards
        if event["failure"]:
            reward -= 10
        elif event["prevented_failure"]:
            pass  # Already added warranty-aware bonus above
        elif event["maintenance_success"]:
            reward += 5

        if event["late_inspection"]:
            reward -= 3

        # COMPLIANCE PENALTY: overdue obligations reduce reward
        if self.obligations_overdue > 0:
            reward -= min(3, self.obligations_overdue * 0.5)

        # EMERGENCY SOP PENALTY: If life safety or plumbing has obscured valves
        if self.system_group in ["Plumbing", "Fire/Life Safety"] and self.valve_accessible == 0:
            reward -= 8 # severe penalty for violating SOP
            
        done = self.is_failed
        return self._get_state(), reward, done, event


# ==========================================
# Q-LEARNING AGENT
# ==========================================
actions = [0, 1, 2, 3, 4]
action_names = ["inspect", "schedule_maintenance", "urgent_repair", "defer", "no_action"]

Q = {}


def get_q(state, action):
    return Q.get((str(state), action), 0.0)


def update_q(state, action, reward, next_state):
    alpha = 0.1
    gamma = 0.9
    max_next = max([get_q(next_state, a) for a in actions])
    old_q = get_q(state, action)
    Q[(str(state), action)] = old_q + alpha * (reward + gamma * max_next - old_q)


# ==========================================
# TRAINING (runs when imported by app.py)
# ==========================================
if __name__ == "__main__":
    print("Starting RL Training (10,000 episodes, 16 trades, 9-feature state)...")
    env = InsureMEPEnv()
    epsilon = 1.0

    for episode in range(10000):
        state = env.reset()
        done = False
        while not done:
            if random.random() < epsilon:
                action = random.choice(actions)
            else:
                action = np.argmax([get_q(state, a) for a in actions])
            next_state, reward, done, _ = env.step(action)
            update_q(state, action, reward, next_state)
            state = next_state
            if env.time_since_last_inspection > 60:
                done = True
        epsilon = max(0.05, epsilon * 0.9995)

    print(f"Training Complete. Q-table size: {len(Q)}")

    # Test inference
    test_states = [
        ("HVAC", 0, 0, 0, 0, 0, 1, 0, 1, 1),
        ("Medical Gas", 2, 2, 2, 1, 1, 0, 2, 0, 1),
        ("Elevator", 1, 2, 1, 0, 0, 1, 1, 1, 1),
        ("Plumbing", 2, 1, 2, 1, 0, 0, 2, 0, 0), # Plumb test without valve
    ]

    print("\n--- INFERENCE ---")
    for ts in test_states:
        best = action_names[np.argmax([get_q(ts, a) for a in actions])]
        print(f"  {ts[0]:20s} risk={ts[1]} → {best}")
