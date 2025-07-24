import psycopg2
from groq import Groq
import re
import os
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

conn = psycopg2.connect(**db_config)
cursor = conn.cursor()
cursor.execute("SELECT id, disease FROM diseases WHERE description IS NULL OR description = '';")
diseases = cursor.fetchall()

for disease_id, disease_name in diseases:
    prompt = f"{disease_name}: give long description, symptoms, Clinical Significance, related disorders, treatment, and key aspects."

    try:
        completion = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=2048,
            top_p=0.95,
            stream=False,
        )

        raw_output = completion.choices[0].message.content.strip()

        final_content = strip_think_block(raw_output)

        cursor.execute(
            "UPDATE diseases SET description = %s WHERE id = %s;",
            (final_content, disease_id)
        )
        conn.commit()

        print(f"Stored content for: {disease_name}")

    except Exception as e:
        print(f"Failed to process {disease_name}: {e}")

cursor.close()
conn.close()
print("All done.")
