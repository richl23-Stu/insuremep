import sqlite3
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'insuremep_sops.db')

class InsureMEP_RL_Env:
    def __init__(self):
        self.state_map = self._load_states_from_db()
        self.num_states = len(self.state_map)
        
        # Action space mapping
        self.action_space = [
            "ignore",                  
            "inspect",                 
            "maintenance",             
            "urgent repair",           
            "urgent if near electrical"
        ]
        self.num_actions = len(self.action_space)

    def _load_states_from_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sop_code, recommended_action, priority_level, safety_critical FROM sop_catalog")
        data = cursor.fetchall()
        conn.close()
        return data

    def step(self, state_idx, action_idx):
        state_code, gt_action, priority, safety = self.state_map[state_idx]
        chosen_action = self.action_space[action_idx]
        
        reward = 0
        done = True # Single step episode
        
        # Reward logic matrix
        if chosen_action in gt_action:
            reward = 10 * priority  # Scaled positive reward for correct SOP
        else:
            if safety:
                reward = -50  # Fatal penalty for ignoring critical asset
            else:
                reward = -5   # Minor penalty for wrong general SOP
                
        return state_idx, reward, done

def train_q_learning(episodes=5000):
    env = InsureMEP_RL_Env()
    
    # Q-Learning Hyperparameters
    alpha = 0.1      # Learning rate (how quickly it adopts new information)
    gamma = 0.0      # Discount factor (0 because this is a single-step bandit-like state right now)
    epsilon = 1.0    # Exploration rate (starts 100% random)
    min_epsilon = 0.01
    decay_rate = 0.005
    
    # Initialize Q-Table with Zeroes
    q_table = np.zeros((env.num_states, env.num_actions))
    
    print(f"Starting Q-Learning Training over {episodes} episodes...")
    for episode in range(episodes):
        state = np.random.randint(0, env.num_states)
        
        # Epsilon-greedy action selection
        if np.random.uniform(0, 1) < epsilon:
            action = np.random.randint(0, env.num_actions) # Explore
        else:
            action = np.argmax(q_table[state]) # Exploit
            
        _, reward, done = env.step(state, action)
        
        # Bellman Equation Update
        old_value = q_table[state, action]
        next_max = 0 # No future state in our simple architecture
        new_value = (1 - alpha) * old_value + alpha * (reward + gamma * next_max)
        
        q_table[state, action] = new_value
        
        # Decay Epsilon
        epsilon = max(min_epsilon, epsilon * (1 - decay_rate))
        
    print("\nTraining Complete!")
    print("---------------------------------------------------------")
    print("Evaluating Learned Policy vs Ground Truth SOPs:\n")
    
    for s in range(env.num_states):
        best_action_idx = np.argmax(q_table[s])
        best_action = env.action_space[best_action_idx]
        state_code, gt_action, priority, safety = env.state_map[s]
        
        icon = "[MATCH]" if best_action in gt_action else "[MISS]"
        critical_tag = " [SAFETY CRITICAL]" if safety else ""
        print(f"Fault State: {state_code}{critical_tag}")
        print(f"  -> AI Learned Action: '{best_action}' {icon}")
        print(f"  -> Q-Table Values: {np.round(q_table[s], 2)}\n")

    return q_table, env

if __name__ == "__main__":
    train_q_learning()
