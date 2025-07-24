import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from pathlib import Path

class DiseaseDataImporter:
    def __init__(self, db_config):

        self.db_config = db_config
        self.connection = None
    
    def connect_to_database(self):
        try:
            self.connection = psycopg2.connect(**self.db_config)
            print("Successfully connected to PostgreSQL database")
            return True
        except psycopg2.Error as e:
            print(f"Error connecting to database: {e}")
            return False
    
    def create_table_if_not_exists(self):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS diseases (
            id SERIAL PRIMARY KEY,
            disease VARCHAR(255) NOT NULL,
            description TEXT
        );
        """
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(create_table_query)
                self.connection.commit()
                print("Table 'diseases' created or already exists")
                return True
        except psycopg2.Error as e:
            print(f"Error creating table: {e}")
            return False
    
    def read_excel_file(self, file_path):
        try:
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            if 'Disease Name' not in df.columns:
                print("Error: 'Disease Name' column not found in the file")
                print(f"Available columns: {list(df.columns)}")
                return None
            
            disease_names = df['Disease Name'].dropna().drop_duplicates().tolist()
            
            disease_names = [name.strip() for name in disease_names if str(name).strip()]
            
            print(f"Found {len(disease_names)} unique disease names")
            return disease_names
            
        except Exception as e:
            print(f"Error reading file: {e}")
            return None
    
    def insert_diseases(self, disease_names):
        if not disease_names:
            print("No disease names to insert")
            return False
        
        insert_query = """
        INSERT INTO diseases (disease, description) 
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING;
        """
        
        try:
            with self.connection.cursor() as cursor:
                for disease_name in disease_names:
                    cursor.execute(insert_query, (disease_name, ''))
                
                self.connection.commit()
                print(f"Successfully inserted {len(disease_names)} disease names")
                return True
                
        except psycopg2.Error as e:
            print(f"Error inserting data: {e}")
            self.connection.rollback()
            return False
    
    def close_connection(self):
        if self.connection:
            self.connection.close()
            print("Database connection closed")
    
    def process_excel_file(self, excel_file_path):
        if not Path(excel_file_path).exists():
            print(f"Error: File '{excel_file_path}' not found")
            return False
        
        if not self.connect_to_database():
            return False

        if not self.create_table_if_not_exists():
            self.close_connection()
            return False
        
        disease_names = self.read_excel_file(excel_file_path)
        if disease_names is None:
            self.close_connection()
            return False
        
        success = self.insert_diseases(disease_names)
        
        self.close_connection()
        
        return success

def main():
    db_config = {
        'host': 'localhost',
        'database': 'rare_diseases',
        'user': 'my_user',
        'password': 'my_secure_password',
        'port': 5432
    }
    
    excel_file_path = 'nord_rare_disease_database_export.csv'
    
    importer = DiseaseDataImporter(db_config)
    
    if importer.process_excel_file(excel_file_path):
        print("Data import completed successfully!")
    else:
        print("Data import failed!")

if __name__ == "__main__":
    main()


def simple_excel_to_postgres(file_path, db_config):
    try:
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        if 'Disease Name' not in df.columns:
            print("Error: 'Disease Name' column not found")
            return False
        
        diseases = df['Disease Name'].dropna().drop_duplicates().tolist()
        
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diseases (
                id SERIAL PRIMARY KEY,
                disease VARCHAR(255) NOT NULL,
                description TEXT
            );
        """)
        
        for disease in diseases:
            cursor.execute(
                "INSERT INTO diseases (disease, description) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (disease.strip(), '')
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Successfully imported {len(diseases)} diseases")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False