#!/usr/bin/env python3
"""
NLQ to SQL Converter using Together API
This script loads CSV files into SQL tables, extracts the schema,
and uses the Together API to convert natural language questions to SQL queries.
"""

import os
import json
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from together import Together
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Together API client
api_key = os.getenv("TOGETHER_API_KEY")
if not api_key:
    raise ValueError("TOGETHER_API_KEY not found in environment variables. Please add it to .env file.")

together_client = Together(api_key=api_key)

# Database setup
DB_PATH = "retail_db.sqlite"
CSV_DIR = "sample"

def create_database_from_csv():
    """Create a database from CSV files in the sample directory."""
    # Check if CSV directory exists
    if not os.path.exists(CSV_DIR):
        raise FileNotFoundError(f"CSV directory '{CSV_DIR}' not found. Please make sure it exists.")
    
    # Check if all required CSV files exist
    required_files = ["categories.csv", "products.csv", "customers.csv", "orders.csv", "order_items.csv"]
    for file in required_files:
        file_path = os.path.join(CSV_DIR, file)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Required CSV file '{file}' not found in '{CSV_DIR}' directory.")
    
    # Connect to SQLite database
    conn = sqlite3.connect(DB_PATH)
    
    # Load each CSV file into a corresponding table
    for file in required_files:
        table_name = file.split('.')[0]  # Remove .csv extension
        file_path = os.path.join(CSV_DIR, file)
        
        # Read CSV file
        df = pd.read_csv(file_path)
        
        # Write to SQLite database
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        print(f"Loaded {len(df)} rows from {file} into {table_name} table.")
    
    conn.close()
    print("Database created successfully from CSV files!")

def get_database_schema():
    """Get the schema of the 5 fundamental tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    schema = {}
    tables = ["categories", "products", "customers", "orders", "order_items"]
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        schema[table] = [{"name": col[1], "type": col[2]} for col in columns]
        
        # Get a sample of data for better context
        cursor.execute(f"SELECT * FROM {table} LIMIT 3")
        sample_data = cursor.fetchall()
        if sample_data:
            column_names = [description[0] for description in cursor.description]
            sample_rows = []
            for row in sample_data:
                sample_row = {}
                for i, value in enumerate(row):
                    sample_row[column_names[i]] = value
                sample_rows.append(sample_row)
            schema[f"{table}_sample"] = sample_rows
    
    conn.close()
    return schema

def generate_sql_query(question, schema):
    """Generate SQL query from natural language question using Together API."""
    # Prepare the schema as a string
    schema_str = json.dumps(schema, indent=2)
    
    # Prepare the prompt
    prompt = f"""You are an expert SQL query generator. Given a database schema and a natural language question, 
your task is to generate the correct SQL query that answers the question.

Database Schema:
{schema_str}

Important notes about the schema:
1. The 'order_items' table contains information about items in each order, including quantity and subtotal.
2. To calculate total sales, use the 'subtotal' column from 'order_items'.
3. For time-based queries, use the 'order_date' column from the 'orders' table.
4. When joining tables, make sure to use the correct foreign keys.
5. The schema includes sample data to help you understand the structure.

Question: {question}

Generate only the SQL query without any explanation. The query should be valid SQLite syntax.
SQL Query:"""
    
    # Call Together API
    response = together_client.chat.completions.create(
        model="mistralai/Mixtral-8x7B-Instruct-v0.1",
        messages=[
            {"role": "system", "content": "You are an expert SQL query generator."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=500
    )
    
    # Extract SQL query from response
    sql_query = response.choices[0].message.content.strip()
    
    # Clean up the SQL query (remove markdown formatting if present)
    if sql_query.startswith("```sql"):
        sql_query = sql_query.split("```sql")[1]
    elif sql_query.startswith("```"):
        sql_query = sql_query.split("```")[1]
    if sql_query.endswith("```"):
        sql_query = sql_query.split("```")[0]
    
    return sql_query.strip()

def execute_sql_query(query):
    """Execute SQL query and return results."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        return f"Error executing query: {str(e)}"

def main():
    # Create database from CSV files if it doesn't exist or if forced
    if not os.path.exists(DB_PATH):
        create_database_from_csv()
    
    # Get database schema
    schema = get_database_schema()
    
    # Natural language questions
    questions = [
        "How many customers do I have in total?",
        "What are total sales that happened last month?",
        "How many customers from Texas ordered totally?"
    ]
    
    # Process each question
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}: {question}")
        
        # Generate SQL query
        sql_query = generate_sql_query(question, schema)
        print(f"\nGenerated SQL Query:")
        print(sql_query)
        
        # Execute SQL query
        print("\nQuery Result:")
        result = execute_sql_query(sql_query)
        print(result)
        print("-" * 80)

if __name__ == "__main__":
    main()
