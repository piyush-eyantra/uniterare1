import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_PATH = os.path.join(BASE_DIR, "Products.txt")
APPLICATIONS_PATH = os.path.join(BASE_DIR, "Applications.txt")
CLEAN_PRODUCTS = os.path.join(BASE_DIR, "Products_cleaned.txt")
CLEAN_APPLICATIONS = os.path.join(BASE_DIR, "Applications_cleaned.txt")
BAD_ROWS_LOG = os.path.join(BASE_DIR, "bad_rows.log")

def clean_file(input_path, output_path, expected_cols):
    with open(input_path, 'r', encoding='utf-8') as fin, \
         open(output_path, 'w', encoding='utf-8') as fout, \
         open(BAD_ROWS_LOG, 'a', encoding='utf-8') as blog:

        header = fin.readline().replace('\r', '').strip().split('\t')

        # Normalize headers to match database schema
        if input_path == PRODUCTS_PATH:
            fout.write('\t'.join(['applno', 'productno', 'form', 'strength', 'referencedrug', 'drugname', 'activeingredient', 'referencestandard']) + '\n')
        elif input_path == APPLICATIONS_PATH:
            fout.write('\t'.join(['applno', 'appltype', 'applpublicnotes', 'sponsorname']) + '\n')
        else:
            fout.write('\t'.join(header[:expected_cols]) + '\n')

        for i, line in enumerate(fin):
            fields = line.replace('\r', '').strip().split('\t')

            if len(fields) < expected_cols:
                blog.write(f"[{input_path}] Line {i+2}: {len(fields)} columns — skipped\n{line}\n")
                continue

            # Strip all fields before writing
            clean_fields = [f.strip() for f in fields[:expected_cols]]
            fout.write('\t'.join(clean_fields) + '\n')

# Clean the files
clean_file(PRODUCTS_PATH, CLEAN_PRODUCTS, 8)
clean_file(APPLICATIONS_PATH, CLEAN_APPLICATIONS, 4)

# Connect to PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT")
)
cursor = conn.cursor()

# Drop and recreate products table
cursor.execute("DROP TABLE IF EXISTS products;")
cursor.execute("""
CREATE TABLE products (
    applno CHAR(6),
    productno CHAR(6),
    form VARCHAR(255),
    strength VARCHAR(240),
    referencedrug TEXT,
    drugname VARCHAR(125),
    activeingredient TEXT,
    referencestandard TEXT
);
""")

# Drop and recreate applications table
cursor.execute("DROP TABLE IF EXISTS applications;")
cursor.execute("""
CREATE TABLE applications (
    applno CHAR(6),
    appltype CHAR(5),
    applpublicnotes TEXT,
    sponsorname VARCHAR(500)
);
""")
conn.commit()

# Load cleaned data into products
with open(CLEAN_PRODUCTS, "r", encoding='utf-8') as f:
    cursor.copy_expert("""
        COPY products FROM STDIN WITH (FORMAT csv, DELIMITER E'\t', HEADER TRUE)
    """, f)

# Load cleaned data into applications
with open(CLEAN_APPLICATIONS, "r", encoding='utf-8') as f:
    cursor.copy_expert("""
        COPY applications FROM STDIN WITH (FORMAT csv, DELIMITER E'\t', HEADER TRUE)
    """, f)

conn.commit()

# Create final combined table
cursor.execute("DROP TABLE IF EXISTS fda_drugs;")
cursor.execute("""
CREATE TABLE fda_drugs (
    id CHAR(6),
    drug_name VARCHAR(125),
    sponsor_name VARCHAR(500),
    PRIMARY KEY (id, drug_name)
);
""")

# Populate fda_drugs
cursor.execute("""
INSERT INTO fda_drugs (id, drug_name, sponsor_name)
SELECT DISTINCT p.applno, p.drugname, a.sponsorname
FROM products p
JOIN applications a ON p.applno = a.applno
WHERE p.drugname IS NOT NULL AND p.drugname <> ''
  AND a.sponsorname IS NOT NULL AND a.sponsorname <> '';
""")
conn.commit()

# Verify final row count
cursor.execute("SELECT COUNT(*) FROM fda_drugs;")
count = cursor.fetchone()[0]
print(f"✅ Successfully loaded {count} records into fda_drugs.")

# Clean up
cursor.close()
conn.close()
