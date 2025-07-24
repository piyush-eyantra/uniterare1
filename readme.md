# Rare Disease Database Application

## Prerequisites

- Python 3.7+
- PostgreSQL database
- Groq API key (for AI-powered features)

## Installation

Install the required packages:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root directory with the following variables:

```env
# Database Configuration
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key

# Multi-threaded Loading Configuration
max_workers=5
```

## Database Setup

1. Create a new PostgreSQL database
2. Run the database initialization script:
   ```bash
   python3 dbscript.py
   ```
   This will create the necessary tables and load initial data.

3. Run the FDA drugs database initialization script:
   ```bash
   python3 dbscript_FDA_drugs.py
   ```
   This will create the necessary tables and load initial data.

## Loading Disease Data

### Option 1: Single-threaded Loading
For smaller datasets or testing:
```bash
python3 single_data_loader.py
```

### Option 2: Multi-threaded Loading
For faster loading of large datasets:
```bash
python3 multi_thread_loader.py
```

## Running the Application

Start the Flask backend:
```bash
python3 rare_disease.py
```

## Project Structure

- `rare_disease.py` - Main Flask application
- `dbscript.py` - Database initialization script
- `dbscript_FDA_drugs.py` - Database initialization script for FDA drugs
- `single_data_loader.py` - Single-threaded data loader
- `multi_thread_loader.py` - Multi-threaded data loader
- `nord_rare_disease_database_export.csv` - Sample disease data
- `requirements.txt` - Project dependencies

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| DB_NAME | PostgreSQL database name | Yes |
| DB_USER | Database username | Yes |
| DB_PASSWORD | Database password | Yes |
| DB_HOST | Database host | Yes |
| DB_PORT | Database port | Yes |
| GROQ_API_KEY | Groq API key for AI features | Yes |
| max_workers | Number of threads for multi-threaded loading | Yes |

