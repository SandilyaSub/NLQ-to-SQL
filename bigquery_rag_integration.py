#!/usr/bin/env python3
"""
BigQuery IMDB RAG Integration

This script integrates the BigQuery IMDB schema with the existing RAG system.
It loads the exported schema JSON file and updates the SchemaRAG class to handle
BigQuery IMDB queries.
"""

import os
import json
import logging
from dotenv import load_dotenv
from together import Together
from rag_utils import SchemaRAG

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
SCHEMA_FILE = "imdb_bigquery_schema.json"
DB_TYPE = "bigquery_imdb"

def load_schema():
    """Load the exported schema from the JSON file."""
    try:
        with open(SCHEMA_FILE, 'r') as f:
            schema_data = json.load(f)
        logger.info(f"Loaded schema from {SCHEMA_FILE}")
        return schema_data
    except Exception as e:
        logger.error(f"Error loading schema: {e}")
        raise

def update_rag_utils():
    """Update the rag_utils.py file to handle BigQuery IMDB schema."""
    try:
        # Read the current rag_utils.py file
        with open("rag_utils.py", 'r') as f:
            content = f.read()
        
        # Check if BigQuery IMDB is already supported
        if "bigquery_imdb" in content:
            logger.info("BigQuery IMDB already supported in rag_utils.py")
            return
        
        # Find the section where DB_TYPE is handled
        db_type_section = content.find("if self.db_type == \"retail\":")
        if db_type_section == -1:
            logger.error("Could not find DB_TYPE section in rag_utils.py")
            return
        
        # Find the end of the if-elif section
        elif_section = content.find("elif self.db_type == \"movie\":", db_type_section)
        if elif_section == -1:
            logger.error("Could not find movie DB_TYPE section in rag_utils.py")
            return
        
        # Find the end of the movie section
        end_section = content.find("else:", elif_section)
        if end_section == -1:
            # If there's no else section, find the next line after the movie section
            lines = content[elif_section:].split('\n')
            indentation = 0
            for i, line in enumerate(lines):
                if i == 0:  # First line is the elif statement
                    indentation = len(line) - len(line.lstrip())
                    continue
                if line.strip() and len(line) - len(line.lstrip()) <= indentation:
                    end_section = elif_section + sum(len(l) + 1 for l in lines[:i])
                    break
        
        # If we still couldn't find the end, use a reasonable position
        if end_section == -1:
            logger.warning("Could not find the end of the movie section, using approximate position")
            end_section = elif_section + 500  # Approximate length of the movie section
        
        # Create the BigQuery IMDB section
        bigquery_imdb_section = """
        elif self.db_type == "bigquery_imdb":
            logger.info("Using BigQuery IMDB schema")
            # Load the schema from the JSON file
            try:
                with open("imdb_bigquery_schema.json", 'r') as f:
                    schema_data = json.load(f)
                
                # Create chunks for each table
                for table_name, table_info in schema_data["tables"].items():
                    # Table-level chunk
                    table_description = table_info.get("description", f"Table {table_name}")
                    columns_text = ", ".join([f"{col['name']} ({col['type']}): {col['description']}" 
                                            for col in table_info["columns"]])
                    
                    table_chunk = f"Table: {table_name}\\nDescription: {table_description}\\nColumns: {columns_text}"
                    self.schema_chunks.append({
                        "content": table_chunk,
                        "type": "table",
                        "table": table_name
                    })
                    
                    # Column-level chunks
                    for column in table_info["columns"]:
                        column_chunk = f"Table: {table_name}, Column: {column['name']}\\nType: {column['type']}\\nDescription: {column['description']}"
                        self.schema_chunks.append({
                            "content": column_chunk,
                            "type": "column",
                            "table": table_name,
                            "column": column['name']
                        })
                
                # Add relationships chunk
                if "relationships" in schema_data and schema_data["relationships"]:
                    relationships_text = "\\n".join([
                        f"{rel['table1']}.{rel['column1']} → {rel['table2']}.{rel['column2']}"
                        for rel in schema_data["relationships"]
                    ])
                    self.schema_chunks.append({
                        "content": f"Table Relationships:\\n{relationships_text}",
                        "type": "relationships"
                    })
                
                # Add overall database chunk
                tables_summary = ", ".join(schema_data["tables"].keys())
                self.schema_chunks.append({
                    "content": f"Database: IMDB BigQuery\\nTables: {tables_summary}\\nThis is the Internet Movie Database (IMDB) containing information about movies, TV shows, actors, directors, and other related data.",
                    "type": "database"
                })
                
                logger.info(f"Created {len(self.schema_chunks)} schema chunks for BigQuery IMDB")
            except Exception as e:
                logger.error(f"Error loading BigQuery IMDB schema: {e}")
                raise
        """
        
        # Insert the BigQuery IMDB section before the else section
        new_content = content[:end_section] + bigquery_imdb_section + content[end_section:]
        
        # Write the updated content back to the file
        with open("rag_utils.py", 'w') as f:
            f.write(new_content)
        
        logger.info("Updated rag_utils.py to support BigQuery IMDB")
    except Exception as e:
        logger.error(f"Error updating rag_utils.py: {e}")
        raise

def update_app_py():
    """Update app.py to support BigQuery IMDB."""
    try:
        # Read the current app.py file
        with open("app.py", 'r') as f:
            content = f.read()
        
        # Check if BigQuery IMDB is already supported
        if "bigquery_imdb" in content:
            logger.info("BigQuery IMDB already supported in app.py")
            return
        
        # Find the DB_TYPE definition
        db_type_line = content.find("DB_TYPE = os.environ.get(\"DB_TYPE\", \"retail\")")
        if db_type_line == -1:
            db_type_line = content.find("DB_TYPE = ")
        
        if db_type_line == -1:
            logger.error("Could not find DB_TYPE definition in app.py")
            return
        
        # Find the end of the line
        end_line = content.find("\n", db_type_line)
        
        # Replace the DB_TYPE definition
        new_db_type_line = "DB_TYPE = os.environ.get(\"DB_TYPE\", \"bigquery_imdb\")  # Options: retail, movie, bigquery_imdb"
        new_content = content[:db_type_line] + new_db_type_line + content[end_line:]
        
        # Find the database path definition
        db_path_line = content.find("DB_PATH = ")
        if db_path_line == -1:
            logger.error("Could not find DB_PATH definition in app.py")
            return
        
        # Find the end of the if-elif section for DB_PATH
        end_db_path = content.find("else:", db_path_line)
        if end_db_path == -1:
            logger.error("Could not find the end of DB_PATH section in app.py")
            return
        
        # Find the end of the line after else:
        end_else_line = content.find("\n", end_db_path)
        end_else_line = content.find("\n", end_else_line + 1)  # Get the next line
        
        # Add BigQuery IMDB case
        bigquery_imdb_case = """    elif DB_TYPE == "bigquery_imdb":
        DB_PATH = None  # BigQuery doesn't use a local database file
"""
        
        # Insert the BigQuery IMDB case before the else section
        new_content = new_content[:end_db_path] + bigquery_imdb_case + new_content[end_db_path:]
        
        # Write the updated content back to the file
        with open("app.py", 'w') as f:
            f.write(new_content)
        
        logger.info("Updated app.py to support BigQuery IMDB")
    except Exception as e:
        logger.error(f"Error updating app.py: {e}")
        raise

def create_bigquery_connector():
    """Create a BigQuery connector module to handle database operations."""
    try:
        # Create the bigquery_connector.py file
        with open("bigquery_connector.py", 'w') as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
BigQuery Connector for NLQ to SQL

This module provides functions to connect to BigQuery and execute SQL queries.
It serves as a replacement for SQLite operations when using the BigQuery IMDB dataset.
\"\"\"

import os
import json
import logging
from google.cloud import bigquery
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = "bigquery-public-data"
DATASET_ID = "imdb"
CREDENTIALS_PATH = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', "/tmp/google-credentials.json")

def get_client():
    \"\"\"Get a BigQuery client.\"\"\"
    try:
        client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)
        return client
    except Exception as e:
        logger.error(f"Error connecting to BigQuery: {e}")
        raise

def execute_query(query, params=None):
    \"\"\"Execute a SQL query on BigQuery.\"\"\"
    try:
        client = get_client()
        
        # Add LIMIT clause if not present to prevent large result sets
        if "LIMIT" not in query.upper():
            query += " LIMIT 1000"
        
        logger.info(f"Executing BigQuery SQL: {query}")
        query_job = client.query(query)
        results = query_job.result()
        
        # Convert to list of dictionaries
        rows = []
        for row in results:
            rows.append(dict(row.items()))
        
        return rows
    except Exception as e:
        logger.error(f"Error executing BigQuery SQL: {e}")
        return {"error": str(e)}

def get_schema():
    \"\"\"Get the schema of the BigQuery IMDB dataset.\"\"\"
    try:
        # Load from the cached schema file for better performance
        with open("imdb_bigquery_schema.json", 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading schema from file, fetching from BigQuery: {e}")
        
        # If file doesn't exist, fetch from BigQuery
        client = get_client()
        dataset_ref = client.dataset(DATASET_ID, project=PROJECT_ID)
        tables = list(client.list_tables(dataset_ref))
        
        schema = {
            "database_type": "bigquery_imdb",
            "tables": {}
        }
        
        for table in tables:
            table_ref = dataset_ref.table(table.table_id)
            table_obj = client.get_table(table_ref)
            
            schema["tables"][table.table_id] = {
                "columns": [
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "description": field.description or f"Column {field.name} in table {table.table_id}"
                    }
                    for field in table_obj.schema
                ]
            }
        
        return schema
""")
        
        logger.info("Created bigquery_connector.py")
    except Exception as e:
        logger.error(f"Error creating bigquery_connector.py: {e}")
        raise

def update_requirements():
    """Update requirements.txt to include BigQuery dependencies."""
    try:
        # Read the current requirements.txt file
        with open("requirements.txt", 'r') as f:
            content = f.read()
        
        # Check if BigQuery is already in requirements
        if "google-cloud-bigquery" in content:
            logger.info("google-cloud-bigquery already in requirements.txt")
            return
        
        # Add BigQuery dependencies
        new_content = content + "\ngoogle-cloud-bigquery>=3.0.0\n"
        
        # Write the updated content back to the file
        with open("requirements.txt", 'w') as f:
            f.write(new_content)
        
        logger.info("Updated requirements.txt to include BigQuery dependencies")
    except Exception as e:
        logger.error(f"Error updating requirements.txt: {e}")
        raise

def main():
    """Main function to integrate BigQuery IMDB with the RAG system."""
    try:
        # Load the schema
        schema_data = load_schema()
        logger.info(f"Loaded schema with {len(schema_data['tables'])} tables")
        
        # Update rag_utils.py
        update_rag_utils()
        
        # Update app.py
        update_app_py()
        
        # Create BigQuery connector
        create_bigquery_connector()
        
        # Update requirements.txt
        update_requirements()
        
        logger.info("Successfully integrated BigQuery IMDB with the RAG system")
        logger.info("To use the BigQuery IMDB dataset, set DB_TYPE='bigquery_imdb' in your .env file")
    except Exception as e:
        logger.error(f"Error integrating BigQuery IMDB: {e}")
        raise

if __name__ == "__main__":
    main()
