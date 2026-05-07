# 🌵 InsureMEP: AI-Driven Critical Infrastructure Maintenance

InsureMEP is an intelligent maintenance orchestration platform designed for complex building systems (HVAC, Plumbing, Electrical). It combines **Gemini Multimodal Vision** with **Reinforcement Learning (RL)** to automate asset onboarding, risk assessment, and SOP (Standard Operating Procedure) enforcement.

## 🚀 Features

- **Multimodal Intake**: Upload equipment photos to automatically detect asset type, corrosion, leaks, and accessibility using Gemini 2.5 Flash.
- **RL Decision Engine**: A Q-learning agent trained on historical SOP compliance and real-time visual risk factors to recommend optimal maintenance actions.
- **Spatial Integration**: Map maintenance tickets to specific building floors and rooms using interactive blueprint overlays.
- **Live Ticket Dashboard**: Real-time monitoring of maintenance requests, asset statuses, and completion rates.
- **AI Assistant**: A RAG-powered chatbot that helps field technicians query SOPs and manage tickets via natural language.

## 🛠️ Local Setup

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd cactus
   ```

2. **Set up Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**:
   ```bash
   streamlit run app.py
   ```

## 🌐 Deployment (Streamlit Cloud)

To deploy this app for public sharing:
1. Push this code to a **GitHub** repository.
2. Link the repository to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Add your `GEMINI_API_KEY` to the **Secrets** panel in the Streamlit Cloud dashboard.

## 🧰 Tech Stack

- **Frontend**: Streamlit
- **AI/ML**: Google Gemini (Vision & LLM), Q-Learning (Custom RL Implementation)
- **Database**: SQLite3
- **Language**: Python 3.12+

---
*Created for the Cactus x Google DeepMind Hackathon.*
