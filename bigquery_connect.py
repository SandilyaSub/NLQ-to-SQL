#!/usr/bin/env python3
"""
BigQuery IMDB Explorer

This script connects to Google BigQuery's public IMDB dataset and allows you to:
1. List available tables in the dataset
2. View table schemas
3. Run sample queries against the dataset

No data is uploaded or modified - this is read-only access to public data.
"""
# Add near the top of bigquery_connect.py
from dotenv import load_dotenv
load_dotenv()  # This loads the variables from .env

import os
from google.cloud import bigquery
client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH, location="US")
from google.api_core.exceptions import GoogleAPIError
import pandas as pd
from tabulate import tabulate
import json

# Configuration
PROJECT_ID = "bigquery-public-data"  # This is Google's project ID for public datasets
DATASET_ID = "imdb"  # The IMDB dataset ID

class BigQueryIMDBExplorer:
    def __init__(self):
        """Initialize the BigQuery client."""
        try:
            # Get credentials path from environment variable
            credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            print(f"Using credentials from: {credentials_path}")
            
            # Check if file exists
            if not os.path.exists(credentials_path):
                print(f"Warning: Credentials file not found at {credentials_path}")
                # Use environment variable as fallback
                credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', "/tmp/google-credentials.json")
                print(f"Using fallback path: {credentials_path}")
            
            # Create client with explicit credentials path
            self.client = bigquery.Client.from_service_account_json(credentials_path)
            print("Successfully connected to BigQuery!")
        except Exception as e:
            print(f"Error connecting to BigQuery: {e}")
            print("\nTo authenticate with Google Cloud:")
            print("1. Create a Google Cloud project: https://console.cloud.google.com/")
            print("2. Enable the BigQuery API")
            print("3. Create a service account and download the JSON key file")
            print("4. Set the GOOGLE_APPLICATION_CREDENTIALS environment variable:")
            print("   export GOOGLE_APPLICATION_CREDENTIALS=\"/path/to/your-key-file.json\"")
            exit(1)
    
    def list_tables(self):
        """List all tables in the IMDB dataset."""
        dataset_ref = self.client.dataset(DATASET_ID, project=PROJECT_ID)
        
        try:
            tables = list(self.client.list_tables(dataset_ref))
            
            if not tables:
                print("No tables found in the dataset.")
                return []
            
            print(f"\nTables in {PROJECT_ID}.{DATASET_ID}:")
            table_list = []
            for table in tables:
                table_list.append(table.table_id)
                print(f"- {table.table_id}")
            
            return table_list
        except GoogleAPIError as e:
            print(f"Error listing tables: {e}")
            return []
    
    def get_table_schema(self, table_id):
        """Get and display the schema of a specific table."""
        table_ref = self.client.dataset(DATASET_ID, project=PROJECT_ID).table(table_id)
        
        try:
            table = self.client.get_table(table_ref)
            
            print(f"\nSchema for {PROJECT_ID}.{DATASET_ID}.{table_id}:")
            schema_data = []
            for field in table.schema:
                schema_data.append([field.name, field.field_type, field.description])
            
            print(tabulate(schema_data, headers=["Column", "Type", "Description"], tablefmt="grid"))
            return table.schema
        except GoogleAPIError as e:
            print(f"Error getting table schema: {e}")
            return None
    
    def run_sample_query(self, table_id, limit=5):
        """Run a simple sample query on a table."""
        query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.{table_id}`
        LIMIT {limit}
        """
        
        try:
            print(f"\nRunning sample query on {table_id}:")
            print(query)
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            # Convert to pandas DataFrame for nice display
            df = results.to_dataframe()
            if not df.empty:
                print("\nResults:")
                print(tabulate(df, headers="keys", tablefmt="grid", showindex=False))
            else:
                print("No results returned.")
            
            return df
        except Exception as e:
            print(f"Error running query: {e}")
            return None
    
    def get_table_relationships(self):
        """
        Identify potential relationships between tables based on column names.
        This is a heuristic approach since BigQuery doesn't store foreign key relationships.
        """
        dataset_ref = self.client.dataset(DATASET_ID, project=PROJECT_ID)
        tables = list(self.client.list_tables(dataset_ref))
        
        # Collect all table schemas
        table_schemas = {}
        for table in tables:
            table_ref = dataset_ref.table(table.table_id)
            table_obj = self.client.get_table(table_ref)
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
        
        if relationships:
            print("\nPotential table relationships:")
            for rel in relationships:
                print(f"- {rel['table1']}.{rel['column1']} → {rel['table2']}.{rel['column2']}")
        else:
            print("\nNo obvious relationships found between tables.")
        
        return relationships
    
    def export_schema_to_json(self, output_file="imdb_schema.json"):
        """Export the complete schema information to a JSON file."""
        dataset_ref = self.client.dataset(DATASET_ID, project=PROJECT_ID)
        tables = list(self.client.list_tables(dataset_ref))
        
        schema_data = {}
        
        for table in tables:
            table_ref = dataset_ref.table(table.table_id)
            table_obj = self.client.get_table(table_ref)
            
            schema_data[table.table_id] = {
                "columns": [
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "description": field.description or ""
                    }
                    for field in table_obj.schema
                ]
            }
        
        with open(output_file, 'w') as f:
            json.dump(schema_data, f, indent=2)
        
        print(f"\nSchema exported to {output_file}")
        return schema_data

def main():
    explorer = BigQueryIMDBExplorer()
    
    while True:
        print("\n" + "="*50)
        print("BigQuery IMDB Explorer")
        print("="*50)
        print("1. List all tables")
        print("2. View table schema")
        print("3. Run sample query")
        print("4. Identify table relationships")
        print("5. Export schema to JSON")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            explorer.list_tables()
        
        elif choice == '2':
            tables = explorer.list_tables()
            if tables:
                table_id = input("\nEnter table name: ")
                if table_id in tables:
                    explorer.get_table_schema(table_id)
                else:
                    print(f"Table '{table_id}' not found.")
        
        elif choice == '3':
            tables = explorer.list_tables()
            if tables:
                table_id = input("\nEnter table name: ")
                if table_id in tables:
                    limit = input("Enter number of rows to display (default 5): ")
                    limit = int(limit) if limit.isdigit() else 5
                    explorer.run_sample_query(table_id, limit)
                else:
                    print(f"Table '{table_id}' not found.")
        
        elif choice == '4':
            explorer.get_table_relationships()
        
        elif choice == '5':
            output_file = input("\nEnter output filename (default: imdb_schema.json): ")
            output_file = output_file if output_file else "imdb_schema.json"
            explorer.export_schema_to_json(output_file)
        
        elif choice == '6':
            print("\nExiting. Goodbye!")
            break
        
        else:
            print("\nInvalid choice. Please try again.")

if __name__ == "__main__":
    main()
