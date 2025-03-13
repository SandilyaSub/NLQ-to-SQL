#!/usr/bin/env python3
"""
Export BigQuery IMDB Schema

This script connects to Google BigQuery, extracts the schema of the IMDB dataset,
and exports it in a format compatible with the SchemaRAG system.
"""

from dotenv import load_dotenv
import os
import json
from google.cloud import bigquery
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = "bigquery-public-data"
DATASET_ID = "imdb"
OUTPUT_FILE = "imdb_bigquery_schema.json"
CREDENTIALS_PATH = "/Users/sandilya/CascadeProjects/nlq-to-sql/phonic-bivouac-272213-feb28388f88b.json"

def get_table_relationships():
    """
    Identify potential relationships between tables based on column names.
    This is a heuristic approach since BigQuery doesn't store foreign key relationships.
    """
    client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)
    
    dataset_ref = client.dataset(DATASET_ID, project=PROJECT_ID)
    tables = list(client.list_tables(dataset_ref))
    
    # Collect all table schemas
    table_schemas = {}
    for table in tables:
        table_ref = dataset_ref.table(table.table_id)
        table_obj = client.get_table(table_ref)
        table_schemas[table.table_id] = {field.name: field.field_type for field in table_obj.schema}
    
    # Find potential relationships
    relationships = []
    
    for table1 in table_schemas:
        for col1 in table_schemas[table1]:
            for table2 in table_schemas:
                if table1 != table2:
                    for col2 in table_schemas[table2]:
                        # Check for exact column name matches
                        if col1 == col2:
                            relationships.append({
                                "table1": table1,
                                "column1": col1,
                                "table2": table2,
                                "column2": col2
                            })
                        # Check for primary key pattern (id in one table, table_id in another)
                        elif col1 == "id" and col2 == f"{table1}_id":
                            relationships.append({
                                "table1": table1,
                                "column1": col1,
                                "table2": table2,
                                "column2": col2
                            })
                        # Check for IMDB specific patterns (tconst, nconst)
                        elif col1 == "tconst" and col2 == "tconst":
                            relationships.append({
                                "table1": table1,
                                "column1": col1,
                                "table2": table2,
                                "column2": col2
                            })
                        elif col1 == "nconst" and col2 == "nconst":
                            relationships.append({
                                "table1": table1,
                                "column1": col1,
                                "table2": table2,
                                "column2": col2
                            })
    
    return relationships

def export_schema():
    """Export the complete schema information to a JSON file."""
    try:
        client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)
        
        dataset_ref = client.dataset(DATASET_ID, project=PROJECT_ID)
        tables = list(client.list_tables(dataset_ref))
        
        schema_data = {
            "database_type": "bigquery_imdb",
            "tables": {},
            "relationships": get_table_relationships()
        }
        
        for table in tables:
            logger.info(f"Processing table: {table.table_id}")
            table_ref = dataset_ref.table(table.table_id)
            table_obj = client.get_table(table_ref)
            
            # Get sample data
            query = f"""
            SELECT *
            FROM `{PROJECT_ID}.{DATASET_ID}.{table.table_id}`
            LIMIT 3
            """
            sample_data = list(client.query(query).result())
            
            schema_data["tables"][table.table_id] = {
                "columns": [
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "description": field.description or f"Column {field.name} in table {table.table_id}"
                    }
                    for field in table_obj.schema
                ],
                "sample_data": [dict(row) for row in sample_data] if sample_data else []
            }
        
        # Add table descriptions
        table_descriptions = {
            "title_basics": "Contains basic information for titles",
            "title_ratings": "Contains ratings information for titles",
            "title_akas": "Contains alternative titles for titles",
            "title_crew": "Contains director and writer information for titles",
            "title_episode": "Contains episode information for TV series",
            "title_principals": "Contains principal cast/crew for titles",
            "name_basics": "Contains information about people (directors, writers, actors, etc.)",
            "title_region_restrictions": "Contains region restriction information for titles"
        }
        
        for table_id, description in table_descriptions.items():
            if table_id in schema_data["tables"]:
                schema_data["tables"][table_id]["description"] = description
        
        # Write to file
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(schema_data, f, indent=2, default=str)
        
        logger.info(f"Schema exported to {OUTPUT_FILE}")
        return schema_data
    
    except Exception as e:
        logger.error(f"Error exporting schema: {e}")
        raise

if __name__ == "__main__":
    export_schema()
