#!/usr/bin/env python3
"""
BigQuery Connector for NLQ to SQL

This module provides functions to connect to BigQuery and execute SQL queries.
It serves as a replacement for SQLite operations when using the BigQuery IMDB dataset.
"""

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
CREDENTIALS_PATH = "/Users/sandilya/CascadeProjects/nlq-to-sql/phonic-bivouac-272213-feb28388f88b.json"

def get_client():
    """Get a BigQuery client."""
    try:
        client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)
        return client
    except Exception as e:
        logger.error(f"Error connecting to BigQuery: {e}")
        raise

def execute_query(query, params=None):
    """Execute a SQL query on BigQuery."""
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
    """Get the schema of the BigQuery IMDB dataset."""
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

def check_sql_syntax(query):
    """
    Check if a SQL query has valid syntax for BigQuery without executing it.
    
    Args:
        query: The SQL query to check
        
    Returns:
        None if syntax is valid, error message string if invalid
    """
    try:
        client = get_client()
        
        # Create a dry run job configuration
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        
        # Start the query job but don't actually run it (dry run)
        query_job = client.query(query, job_config=job_config)
        
        # If we get here, the syntax is valid
        return None
    except Exception as e:
        error_msg = str(e)
        
        # Check for common BigQuery errors and provide more helpful messages
        if "Table name cannot be resolved" in error_msg or "Not found" in error_msg:
            # Check if the error is due to unqualified table names
            if "must be qualified with a dataset" in error_msg:
                table_name = error_msg.split("Table ")[1].split(" must")[0].strip('"')
                return f"Table '{table_name}' must be qualified with the dataset name 'imdb'. Use 'imdb.{table_name}' instead."
            return "Table not found. Please check the table name and make sure it's qualified with 'imdb'."
        elif "Unrecognized name" in error_msg or "Column not found" in error_msg:
            return "Column not found. Please check the column name."
        else:
            return error_msg

def fix_unqualified_tables(query):
    """
    Attempt to fix unqualified table names in a BigQuery SQL query.
    
    Args:
        query: The SQL query with potentially unqualified table names
        
    Returns:
        Updated query with qualified table names
    """
    import re
    
    # Common IMDB tables
    imdb_tables = [
        "title_basics", "name_basics", "title_ratings", "title_crew", 
        "title_principals", "title_episode", "title_akas"
    ]
    
    # First, check if the query already has the correct project ID
    if "bigquery-public-data.imdb" in query:
        # Just remove any semicolons at the end of the query
        query = re.sub(r';$', '', query)
        return query
    
    # Replace unqualified table names with qualified ones
    for table in imdb_tables:
        # Look for table names that are not already qualified with the public project ID
        pattern = r'(?<![.\w])' + table + r'(?![.\w])'
        query = re.sub(pattern, f'`bigquery-public-data.imdb.{table}`', query)
        
        # Also fix tables that are qualified with just 'imdb' but not the project ID
        pattern = r'imdb\.' + table
        query = re.sub(pattern, f'`bigquery-public-data.imdb.{table}`', query)
        
        # Fix tables that are qualified with the wrong project ID
        pattern = r'`phonic-bivouac-272213\.imdb\.' + table + r'`'
        query = re.sub(pattern, f'`bigquery-public-data.imdb.{table}`', query)
        
        # Also fix without backticks
        pattern = r'phonic-bivouac-272213\.imdb\.' + table
        query = re.sub(pattern, f'`bigquery-public-data.imdb.{table}`', query)
    
    # Remove any semicolons at the end of the query
    query = re.sub(r';$', '', query)
    
    return query
