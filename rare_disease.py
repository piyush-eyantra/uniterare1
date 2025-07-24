import os
import re
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import requests
import urllib.parse
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key)

db_config = {
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_NAME"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"),
    'port': os.getenv("DB_PORT")
}

def strip_think_block(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

def fetch_or_generate_description(disease_name):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id, description FROM diseases WHERE disease ILIKE %s;", (disease_name,))
        result = cursor.fetchone()

        if not result:
            return {"success": False,"message": "Disease not found in the database."}, 404

        disease_id, description = result

        if description and description.strip():
            return {"success": True,"message": "Description already in database.","disease": disease_name, "description": description}, 200
            # return {"description": description, "message": "Description already in database.", "success": True}, 200

        prompt = f"{disease_name}: give long description, symptoms, Clinical Significance, related disorders, treatment, and key aspects."

        completion = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=2048,
            top_p=0.95,
            stream=False,
        )

        raw_output = completion.choices[0].message.content.strip()
        final_content = strip_think_block(raw_output)

        cursor.execute("UPDATE diseases SET description = %s WHERE id = %s;", (final_content, disease_id))
        conn.commit()

        return {"success": True,"message": "Description fetched and stored successfully.","disease": disease_name, "description": final_content}, 200

    except Exception as e:
        return {"success": False,"message": "Something went wrong","error": str(e)}, 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_disease_suggestions(query):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT disease FROM diseases WHERE disease ILIKE %s LIMIT 10;",
            (f"%{query}%",)
        )
        suggestions = [row[0] for row in cursor.fetchall()]
        return {"suggestions": suggestions}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route("/api/disease-description", methods=["GET", "POST"])
def disease_description():
    if request.method == "GET":
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({"success": False, "message": "Query parameter 'q' is required"}), 400
        
        suggestions = get_disease_suggestions(query)
        return jsonify(suggestions)
    
    data = request.get_json()
    if not data or 'disease_name' not in data:
        return jsonify({"success": False, "message": "Missing 'disease_name' in request"}), 400

    disease_name = data['disease_name'].strip()
    if not disease_name:
        return jsonify({"success": False, "message": "Disease name cannot be empty"}), 400

    result, status_code = fetch_or_generate_description(disease_name)
    return jsonify(result), status_code

def get_drug_suggestions(query):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT drug_name FROM fda_drugs WHERE drug_name ILIKE %s LIMIT 10;",
            (f"%{query}%",)
        )
        suggestions = [row[0] for row in cursor.fetchall()]
        return {"suggestions": suggestions}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route("/api/drug-info", methods=["GET", "POST"])
def drug_info():
    if request.method == "GET":
        query = request.args.get('q', '').strip().upper()
        if not query:
            return jsonify({"success": False, "message": "Query parameter 'q' is required"}), 400
        
        suggestions = get_drug_suggestions(query)
        return jsonify(suggestions)
    
    data = request.get_json()
    if not data or 'drug_name' not in data:
        return jsonify({"success": False, "message": "Missing 'drug_name' in request"}), 400

    drug_name = data['drug_name'].strip().upper()
    if not drug_name:
        return jsonify({"success": False, "message": "Drug name cannot be empty"}), 400

    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT sponsor_name, disease_name
            FROM fda_drugs
            WHERE drug_name ILIKE %s;
        """, (f"%{drug_name}%",))
        rows = cursor.fetchall()

        if not rows:
            return jsonify({"success": False, "message": f"Drug '{drug_name}' not found in local database."}), 404

        manufacturers = sorted(set(row[0] for row in rows if row[0]))
        existing_disease = next((row[1] for row in rows if row[1]), None)

        if existing_disease:
            return jsonify({
                "success": True,
                "drug_name": drug_name,
                "manufacturers": manufacturers,
                "description": existing_disease
            }), 200

        # Query OpenFDA
        encoded_name = urllib.parse.quote(drug_name)
        url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:\"{encoded_name}\"&limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()

        if "results" not in data or not data["results"]:
            return jsonify({
                "success": True,
                "drug_name": drug_name,
                "manufacturers": manufacturers,
                "description": "No disease info found in OpenFDA."
            }), 200

        result = data["results"][0]

        def clean_section(field, label):
            val = result.get(field, [None])[0]
            if val:
                val_clean = val.strip().replace("\n", " ")
                return f"**{label}:**\n{val_clean}\n\n"
            return ""

        formatted = f"**{drug_name.title()}: A Comprehensive Overview**\n\n"
        formatted += clean_section("indications_and_usage", "Indications and Usage")
        formatted += clean_section("overdosage", "Overdosage")
        formatted += clean_section("drug_interactions", "Drug Interactions")
        formatted += clean_section("warnings_and_cautions", "Warnings and Cautions")
        formatted += clean_section("storage_and_handling", "Storage and Handling")
        formatted += clean_section("pregnancy", "Pregnancy")

        formatted = formatted.strip()
        if formatted:
            cursor.execute("""
                UPDATE fda_drugs
                SET disease_name = %s
                WHERE drug_name ILIKE %s;
            """, (formatted, f"%{drug_name}%"))
            conn.commit()

        return jsonify({
            "success": True,
            "drug_name": drug_name,
            "manufacturers": manufacturers,
            "description": formatted or "No description available."
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": "Server error", "error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def analyze_patient_data(patient_data):
    try:
        prompt = f"""
You are a medical assistant. Here is a patient's intake information:
{json.dumps(patient_data, indent=2)}

1. Structure the patient details as a JSON object under the key 'patient_details'.
2. Based on the provided information, search for rare diseases that match the patient's symptoms and history.
3. For the top 3 most likely rare diseases, provide the following for each (as an array under the key 'top_rare_diseases', each with a 'score' field indicating likelihood):
    - Disease_Name
    - Score (likelihood or relevance) (1-100)
    - Description
    - Disease_Overview
    - Symptoms (array of strings)
    - Clinical_Significance
    - Causes
    - Related_Disorders (Disorders with Similar Symptoms)(array of strings)
    - Diagnosis (array of strings)
    - Treatment (array of strings)
    - Clinical_Trials
    - Key_Aspects
4. Return a single JSON object with keys: patient_details, top_rare_diseases (array of objects as above).

Example output:
{{
  "patient_details": {{ ... }},
  "top_rare_diseases": [
    {{
      "disease_name": "...",
      "score": 92,
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
        completion = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            max_tokens=4096,
            top_p=1,
            stream=False,
        )
        
        content = completion.choices[0].message.content.strip()
        content = strip_think_block(content)
        
        # Try to extract JSON from the response
        try:
            # Try to find JSON in the response
            json_match = re.search(r'({.*})', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse AI response", "raw_response": content}
            
    except Exception as e:
        return {"error": str(e)}

@app.route("/api/diagnose", methods=["POST"])
def diagnose():
    try:
        patient_data = request.get_json()
        if not patient_data:
            return jsonify({"success": False, "message": "No patient data provided"}), 400
            
        try:
            os.makedirs("patient_data", exist_ok=True)
            user_name = patient_data.get("name", "user").replace(" ", "_")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f"patient_data/{user_name}_{timestamp}.json"
            with open(file_name, "w") as f:
                json.dump(patient_data, f, indent=2)
        except Exception as e:
            app.logger.error(f"Failed to save patient data: {str(e)}")
        
        diagnosis = analyze_patient_data(patient_data)
        
        if "error" in diagnosis:
            return jsonify({"success": False, "message": "Diagnosis failed", "error": diagnosis["error"]}), 500
            
        return jsonify({"success": True, "data": diagnosis})
        
    except Exception as e:
        return jsonify({"success": False, "message": "Server error", "error": str(e)}), 500

if __name__ == "__main__":
    os.makedirs("patient_data", exist_ok=True)
    app.run(debug=True)
