#!/usr/bin/env python3
"""
NLQ to SQL Web Terminal
This script provides a web-based terminal interface for the NLQ to SQL converter.
"""

# For cloud deployment - create credentials file from environment variable
import os
import json

if os.environ.get('GOOGLE_CREDENTIALS_JSON'):
    # Create credentials file from environment variable
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    creds_path = '/tmp/google-credentials.json'
    with open(creds_path, 'w') as f:
        f.write(creds_json)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path

import os
import json
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from together import Together
from datetime import datetime, timedelta
import logging
import re
from rag_utils import SchemaRAG
from sql_validator import validate_sql_query
from recursive_validation_system import RecursiveValidationSystem
from query_feedback_db import init_db, save_query_feedback, update_user_feedback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Together API client
api_key = os.getenv("TOGETHER_API_KEY")
if not api_key:
    raise ValueError("TOGETHER_API_KEY not found in environment variables. Please add it to .env file.")

together_client = Together(api_key=api_key)

# Database setup
# Choose which database to use: "retail" or "movie"
DB_TYPE = os.environ.get("DB_TYPE", "bigquery_imdb")  # Options: retail, movie, bigquery_imdb

# Set environment variable for DB_TYPE so other modules can access it
os.environ["DB_TYPE"] = DB_TYPE

if DB_TYPE == "retail":
    DB_PATH = "retail_db.sqlite"
    CSV_DIR = "sample"
elif DB_TYPE == "bigquery_imdb":
    DB_PATH = None  # BigQuery doesn't use a local database file
    CSV_DIR = None
else:  # movie database
    DB_PATH = "MovieData.db"
    CSV_DIR = "sample/MovieData"

# Initialize Flask app
app = Flask(__name__)

# Initialize query history
query_history = []

# Initialize SchemaRAG system
schema_rag = SchemaRAG(together_client, DB_PATH, db_type=DB_TYPE)

# Initialize recursive validation system
validation_system = RecursiveValidationSystem(DB_PATH, schema_rag, together_client)

# Initialize query feedback database
init_db()

def get_database_schema():
    """Get the schema of the database tables with sample data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    schema = {}
    
    if DB_TYPE == "retail":
        tables = ["categories", "products", "customers", "orders", "order_items"]
    else:  # movie database
        tables = ["name_basics", "title_basics", "title_ratings", "title_crew", 
                 "title_episode", "title_principals", "title_akas"]
    
    for table in tables:
        # Get column information
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        schema[table] = [{"name": col[1], "type": col[2]} for col in columns]
        
        # Get a sample of data for better context
        cursor.execute(f"SELECT * FROM {table} LIMIT 2")
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
    """Generate SQL query from natural language question using Together API and RAG."""
    logger.info(f"Generating SQL query for question: {question}")
    
    # Current date for reference in time-based queries
    current_date = datetime.now().strftime("%Y-%m-%d")
    last_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
    last_month_end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Check if the question contains time-related terms
    time_related = any(term in question.lower() for term in ['month', 'year', 'date', 'day', 'week', 'time', 'recent', 'last', 'previous', 'ago'])
    
    # Use RAG to retrieve relevant schema context
    logger.info("Using RAG to retrieve relevant schema context")
    relevant_chunks = schema_rag.retrieve_relevant_schema(question)
    relevant_schema_context = schema_rag.generate_schema_context(relevant_chunks)
    
    logger.info(f"Retrieved relevant schema context with {len(relevant_chunks)} chunks")
    
    # Prepare the prompt with the relevant schema context
    if time_related:
        # Include date information for time-related queries
        prompt = f"""You are an expert SQL query writer. Given the following database schema and a natural language query, generate a valid SQL query.

**Schema**:
{relevant_schema_context}

**Instructions**:
- Use only the tables and columns from the schema.
- Handle joins, aggregations, and conditions as needed.
- Return only the SQL query, no explanations.
- Today's date is {current_date}.
- "Last month" refers to the period from {last_month_start} to {last_month_end}.
- The 'orders' table has 'order_date' column for time-based queries.
- The 'order_items' table has 'total' column which represents the total price for that item.
- The 'customers' table has 'state' column (not customer_state) which contains state codes like 'TX' for Texas.
- The 'customers' table has 'customer_segment' column (not segment) for customer segmentation.
- When joining tables, make sure to use the correct foreign keys.

**Query**: {question}

Generate only the SQL query without any explanation. The query should be valid SQLite syntax.
SQL Query:"""
    else:
        # Exclude date information for non-time-related queries
        prompt = f"""You are an expert SQL query writer. Given the following database schema and a natural language query, generate a valid SQL query.

**Schema**:
{relevant_schema_context}

**Instructions**:
- Use only the tables and columns from the schema.
- Handle joins, aggregations, and conditions as needed.
- Return only the SQL query, no explanations.
- The 'orders' table has 'order_date' column for time-based queries.
- The 'order_items' table has 'total' column which represents the total price for that item.
- The 'customers' table has 'state' column (not customer_state) which contains state codes like 'TX' for Texas.
- The 'customers' table has 'city' column for city-based queries.
- The 'customers' table has 'customer_segment' column (not segment) for customer segmentation.
- When joining tables, make sure to use the correct foreign keys.
- DO NOT add date constraints unless explicitly mentioned in the question.

**Query**: {question}

Generate only the SQL query without any explanation. The query should be valid SQLite syntax.
SQL Query:"""
    
    logger.info(f"Sending prompt to Together API: {question}")
    
    # Call Together API
    response = together_client.chat.completions.create(
        # Try Llama model which was working before
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        # Claude model - uncomment if you have access
        # model="anthropic/claude-3-opus-20240229",
        messages=[
            #{"role": "system", "content": "You are an expert SQL query generator. Always use the exact column names as provided in the schema. Never abbreviate or rename columns in your SQL queries unless explicitly using aliases. Pay special attention to compound column names like 'customer_segment' and use them exactly as specified."},
            {"role": "system", "content": "You are an expert SQL query generator with deep knowledge of database schema design. Always use the exact column names as provided in the schema. Pay special attention to table relationships and join conditions."},
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
    
    # Remove all common escape characters that might cause issues
    sql_query = sql_query.replace("\\_", "_")
    sql_query = sql_query.replace("\\'", "'")
    sql_query = sql_query.replace("\\\"", '"')
    sql_query = sql_query.replace("\\%", "%")
    sql_query = sql_query.replace("\\-", "-")
    sql_query = sql_query.replace("\\*", "*")
    
    # More comprehensive approach: remove backslash before any non-alphanumeric character
    sql_query = re.sub(r'\\([^a-zA-Z0-9])', r'\1', sql_query)
    
    # Validate column names
    sql_query = validate_sql_query(sql_query)
    
    logger.info(f"Generated SQL query: {sql_query}")
    return sql_query.strip()

def execute_sql_query(query):
    """Execute SQL query and return results."""
    # Handle BigQuery IMDB database type
    if DB_TYPE == "bigquery_imdb":
        try:
            # Import BigQuery connector
            from bigquery_connector import execute_query, fix_unqualified_tables
            
            # Fix unqualified table names in the query
            fixed_query = fix_unqualified_tables(query)
            
            logger.info(f"Executing BigQuery SQL query: {fixed_query}")
            
            # Execute the query using the BigQuery connector
            results = execute_query(fixed_query)
            
            # Convert results to the same format as SQLite
            if isinstance(results, pd.DataFrame):
                return results.to_dict(orient="records")
            return results
        except Exception as e:
            logger.error(f"Error executing BigQuery query: {str(e)}")
            return {"error": f"Error executing query: {str(e)}"}
    # Handle SQLite database types
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            logger.info(f"Executing SQLite query: {query}")
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df.to_dict(orient="records")
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            conn.close()
            return {"error": f"Error executing query: {str(e)}"}

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html', query_history=query_history)

@app.route('/api/query', methods=['POST'])
def process_query():
    """Process a natural language query and return the results."""
    data = request.json
    question = data.get('question', '')
    
    if not question:
        return jsonify({"error": "No question provided"}), 400
    
    # Add to query history
    query_history.append(question)
    if len(query_history) > 10:  # Keep only the last 10 queries
        query_history.pop(0)
    
    # Ensure SchemaRAG is initialized
    if not schema_rag.initialized:
        logger.info("Initializing SchemaRAG system")
        schema_rag.initialize()
    
    try:
        logger.info(f"Processing query: \"{question}\"")
        
        # Start timing for NLQ to SQL conversion
        nlq_start_time = datetime.now()
        
        # Process query using recursive validation system
        result = validation_system.process_query(question)
        
        # End timing for NLQ to SQL conversion
        nlq_end_time = datetime.now()
        nlq_to_sql_time = (nlq_end_time - nlq_start_time).total_seconds()
        
        # Start timing for SQL execution
        sql_start_time = datetime.now()
        
        # Assuming SQL execution happens in validation_system.process_query
        # End timing for SQL execution
        sql_end_time = datetime.now()
        sql_execution_time = (sql_end_time - sql_start_time).total_seconds()
        
        # Calculate total execution time
        total_execution_time_ms = (sql_end_time - nlq_start_time).total_seconds() * 1000
        
        # Extract data for feedback database
        if "error" not in result:
            # Save query feedback to database
            query_id = save_query_feedback(
                natural_language_query=question,
                generated_sql=result.get("sql_query", ""),
                validated=True,
                executed=True,
                nlq_to_sql_time_seconds=nlq_to_sql_time,
                sql_execution_time_seconds=sql_execution_time,
                total_execution_time_ms=total_execution_time_ms,
                result_count=len(result.get("results", [])),
                result_summary=json.dumps(result.get("results", [])[:5]),  # Store first 5 results as summary
                confidence_score=result.get("confidence", 0),
                interaction_logs=result.get("interaction_logs", []),
                validation_errors=None,
                execution_errors=None
            )
            
            # Add query ID to result for frontend reference
            result["query_id"] = query_id
        
        # Add query history to the result
        result["query_history"] = query_history
        
        # Return response
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({
            "error": str(e),
            "query_history": query_history
        })

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get the query history."""
    return jsonify({"query_history": query_history})

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback for a query."""
    data = request.json
    query_id = data.get('query_id')
    feedback = data.get('feedback')
    
    if not query_id or not feedback:
        return jsonify({"error": "Missing query_id or feedback"}), 400
    
    # Update feedback in database
    success = update_user_feedback(query_id, feedback)
    
    if success:
        return jsonify({"success": True, "message": "Feedback submitted successfully"})
    else:
        return jsonify({"success": False, "message": "Feedback already submitted or query not found"}), 400

if __name__ == '__main__':
    # Check if database exists, if not, warn the user (skip for BigQuery which doesn't use a local DB)
    if DB_TYPE != "bigquery_imdb" and DB_PATH is not None and not os.path.exists(DB_PATH):
        logger.warning(f"Database file {DB_PATH} does not exist. Please run process_csv_to_sql.py first.")
        print(f"WARNING: Database file {DB_PATH} does not exist. Please run process_csv_to_sql.py first.")
    else:
        # Initialize SchemaRAG system in the background
        logger.info("Initializing SchemaRAG system in the background")
        schema_rag.initialize()
        logger.info("SchemaRAG system initialized successfully")
    
    # Run the Flask app
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5724)))

# Initialize SchemaRAG system for Vercel deployment
# This code runs when the module is imported by Vercel
if DB_TYPE == "bigquery_imdb" and __name__ != '__main__':
    logger.info("Initializing SchemaRAG system for serverless deployment")
    schema_rag.initialize()
    logger.info("SchemaRAG system initialized successfully for serverless deployment")
