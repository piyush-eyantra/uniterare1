import streamlit as st
import json
import requests
from datetime import datetime
import os
from groq import Groq
from dotenv import load_dotenv
import re

def extract_json(text):
    # Find the first {...} block in the text
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        return match.group(1)
    return text  # fallback

def strip_think_block(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

# --- Load API Key from .env ---
load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY_Deepseek")

# --- Streamlit Config ---
st.set_page_config(page_title="UniteRare", page_icon="🧬")
os.makedirs("patient_data", exist_ok=True)
st.title("🩺 Get Diagnosed")

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

    # # If this is the last question, show the analysis button
    # if st.session_state.step == len(questions) - 1:
    #     if st.button("Find Possible Conditions"):
    #         st.session_state.responses[q["key"]] = st.session_state.get(q["key"], "")
    #         st.session_state.step += 1
    #         st.session_state.run_analysis = True
else:
    # Save user input to JSON file
    user_data = st.session_state.responses
    user_name = user_data.get("name", "user").replace(" ", "_")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = f"patient_data/{user_name}_{timestamp}.json"
    with open(file_name, "w") as f:
        json.dump(user_data, f, indent=2)
    # st.success(f"✅ User input saved to {file_name}")

    # Show patient details filled by user
    st.subheader("Patient Details (as entered)")
    # st.json(user_data)
    for key, value in user_data.items():
        if isinstance(value, list):
            st.markdown(f"**{key.replace('_', ' ').capitalize()}:** {', '.join(str(v) for v in value)}")
        else:
            st.markdown(f"**{key.replace('_', ' ').capitalize()}:** {value}")

    # Step 2: Structured Groq Llama-4 Response
    run_analysis = st.session_state.pop("run_analysis", False)
    if run_analysis or st.button("Find Possible Conditions"):
        prompt = f"""
You are a medical assistant. Here is a patient's intake information:
{json.dumps(user_data, indent=2)}

1. Structure the patient details as a JSON object under the key 'patient_details'.
2. Based on the provided information, search for rare diseases that match the patient's symptoms and history.
3. For the top 5 most likely rare diseases, provide the following for each (as an array under the key 'top_rare_diseases', each with a 'score' field indicating likelihood):
    - Disease Name
    - Score (likelihood or relevance)
    - Description
    - Disease Overview
    - Signs & Symptoms
    - Clinical Significance
    - Causes
    - Related Disorders (Disorders with Similar Symptoms)
    - Diagnosis
    - Standard Therapies or Treatment
    - Clinical Trials and Studies in detail if any
    - Key Aspects
4. Return a single JSON object with keys: patient_details, top_rare_diseases (array of objects as above).

Example output:
{{
  "patient_details": {{ ... }},
  "top_rare_diseases": [
    {{
      "disease_name": "...",
      "score": 0.92,
      "description": "...",
      "overview": "...",
      "signs_symptoms": ["...", "..."],
      "clinical_significance": "...",
      "causes": "...",
      "related_disorders": ["...", "..."],
      "diagnosis": "...",
      "treatment": "...",
      "clinical_trials": ["...", "..."],
      "key_aspects": ["...", "..."]
    }},
    ...
  ]
}}
IMPORTANT: Do NOT include any reasoning, explanation, <think> tags, or any text before or after the JSON. ONLY return the JSON object as the output.
"""
        with st.spinner("Rare Disease analysis..."):
            try:
                client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else Groq()
                completion = client.chat.completions.create(
                    model="deepseek-r1-distill-llama-70b",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=1,
                    max_completion_tokens=4096,
                    top_p=1,
                    stream=False,
                    stop=None,
                )
                # If not streaming, get the full response
                if hasattr(completion, 'choices'):
                    content = completion.choices[0].message.content
                else:
                    # fallback for other return types
                    content = "".join(chunk.choices[0].delta.content or "" for chunk in completion)
                structured_json = content.strip()
                # Remove any <think>...</think> blocks if present
                structured_json = strip_think_block(structured_json)
                json_str = extract_json(structured_json)
                try:
                    structured_data = json.loads(json_str)
                    #st.success("✅ Structured response from Groq Llama-4:")
                    #st.json(structured_data)
                    # Save Groq response to JSON file
                    groq_file_name = f"patient_data/{user_name}_{timestamp}_groq_response.json"
                    with open(groq_file_name, "w") as f:
                        json.dump(structured_data, f, indent=2)
                    # st.info(f"Groq response saved to {groq_file_name}")

                    # Visualize in a more structured way
                    if "patient_details" in structured_data:
                        pass

                    if "top_rare_diseases" in structured_data:
                        st.subheader("Top Rare Diseases")
                        for disease in structured_data["top_rare_diseases"]:
                            with st.expander(f"{disease.get('disease_name', 'Unknown Disease')} (Score: {disease.get('score', 'N/A')})"):
                                st.markdown(f"**Description:** {disease.get('description', 'N/A')}")
                                st.markdown(f"**Overview:** {disease.get('overview', 'N/A')}")
                                st.markdown(f"**Signs & Symptoms:** {', '.join(disease.get('signs_symptoms', [])) if disease.get('signs_symptoms') else 'N/A'}")
                                st.markdown(f"**Clinical Significance:** {disease.get('clinical_significance', 'N/A')}")
                                st.markdown(f"**Causes:** {disease.get('causes', 'N/A')}")
                                st.markdown(f"**Related Disorders:** {', '.join(disease.get('related_disorders', [])) if disease.get('related_disorders') else 'N/A'}")
                                st.markdown(f"**Diagnosis:** {disease.get('diagnosis', 'N/A')}")
                                st.markdown(f"**Standard Therapies or Treatment:** {disease.get('treatment', 'N/A')}")
                                st.markdown(f"**Clinical Trials and Studies (in detail if any):** {', '.join(disease.get('clinical_trials', [])) if disease.get('clinical_trials') else 'N/A'}")
                                st.markdown(f"**Key Aspects:** {', '.join(disease.get('key_aspects', [])) if disease.get('key_aspects') else 'N/A'}")
                except Exception as e:
                    st.error("❌ Still failed to parse JSON.")
                    st.text(structured_json)
            except Exception as e:
                st.error(f"❌ Groq API error: {e}")
