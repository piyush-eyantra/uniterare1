import streamlit as st
import json
import requests
from datetime import datetime
import os
# import openai  # Removed OpenAI
from dotenv import load_dotenv

# --- Load API Key from .env ---
load_dotenv()
# openai.api_key = os.environ.get("OPENAI_API_KEY")  # Not needed for Ollama

# --- Streamlit Config ---
st.set_page_config(page_title="Rare Disease Intake", page_icon="🧬")
os.makedirs("patient_data", exist_ok=True)
st.title("Rare Disease Assistant")

# --- Session State ---
if "step" not in st.session_state: st.session_state.step = 0
if "responses" not in st.session_state: st.session_state.responses = {}
if "hpo_terms" not in st.session_state: st.session_state.hpo_terms = []

# --- Questions ---
questions = [
    {"key": "name", "text": "👤 What is your name?", "type": "text"},
    {"key": "age", "text": "1️⃣ What is your age?", "type": "number"},
    {"key": "gender", "text": "2️⃣ What is your gender?", "type": "text"},
    {"key": "symptoms", "text": "3️⃣ List your symptoms (comma-separated)", "type": "text"},
    {"key": "duration", "text": "4️⃣ How long have you had these symptoms?", "type": "text"},
    {"key": "family_history", "text": "5️⃣ Any family history of similar symptoms or rare diseases?", "type": "text"},
    {"key": "medications", "text": "6️⃣ Are you currently taking any medications? Please list them.", "type": "text"},
    {"key": "previous_diagnoses", "text": "7️⃣ Any previous diagnoses?", "type": "text"},
    {"key": "travel", "text": "8️⃣ Any recent travel? If yes, where?", "type": "text"},
    {"key": "allergies", "text": "9️⃣ Do you have any allergies?", "type": "text"},
    {"key": "other_conditions", "text": "🔟 Any other medical conditions?", "type": "text"},
]

# --- Step-by-Step Questions ---
if st.session_state.step < len(questions):
    q = questions[st.session_state.step]
    st.subheader(q["text"])

    def advance_step():
        answer = st.session_state.get(q["key"], "")
        if answer != "" and not (q["type"] == "number" and answer == 0):
            st.session_state.responses[q["key"]] = answer
            st.session_state.step += 1
        else:
            st.warning("Please provide an answer.")

    if q["type"] == "text":
        st.text_input("Answer:", key=q["key"], on_change=advance_step)
    elif q["type"] == "number":
        st.number_input("Answer:", min_value=0, step=1, key=q["key"], on_change=advance_step)

# --- After All Questions ---
elif st.session_state.step == len(questions):
    # st.success("✅ All responses collected")

    # Save user input to JSON file
    user_data = st.session_state.responses
    user_name = user_data.get("name", "user").replace(" ", "_")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = f"patient_data/{user_name}_{timestamp}.json"
    with open(file_name, "w") as f:
        json.dump(user_data, f, indent=2)
    st.success(f"✅ User input saved to {file_name}")

    # Step 2: Structured Ollama Response
    if st.button("🧬 Generate Structured Analysis (via Ollama)"):
        prompt = f"""
You are a medical assistant. Here is a patient's intake information:
{json.dumps(user_data, indent=2)}

1. Extract a JSON list of relevant HPO terms (label and id).
2. Suggest possible rare disease categories (as a JSON array).
3. For each suggested disease, provide a summary, typical symptoms, diagnostic approach, and possible next steps (as a JSON object).
4. Suggest next steps for the patient (as a JSON array).

Return a JSON object with keys: hpo_terms, disease_categories, disease_details, next_steps.
"""
        with st.spinner("Calling Ollama for structured analysis..."):
            ollama_url = "http://localhost:11434/api/generate"
            payload = {
                "model": "llama2",  # Change to your preferred Ollama model
                "prompt": prompt,
                "stream": False
            }
            try:
                response = requests.post(ollama_url, json=payload, timeout=120)
                response.raise_for_status()
                result = response.json()
                structured_json = result.get("response", "").strip()
                try:
                    structured_data = json.loads(structured_json)
                    st.success("✅ Structured response from Ollama:")
                    st.json(structured_data)
                except Exception as e:
                    st.error("❌ Failed to parse Ollama structured response.")
                    st.text(structured_json)
            except Exception as e:
                st.error(f"❌ Ollama API error: {e}")
