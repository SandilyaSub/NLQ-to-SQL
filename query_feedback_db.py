import sqlite3
import json
import uuid
import datetime
import os
from flask import request

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'query_feedback.db')

def init_db():
    """Initialize the database with the query feedback table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the query feedback table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS query_feedback (
        id TEXT PRIMARY KEY,
        timestamp TEXT,
        ip_address TEXT,
        session_id TEXT,
        natural_language_query TEXT,
        generated_sql TEXT,
        validated INTEGER,
        executed INTEGER,
        nlq_to_sql_time_seconds REAL,
        sql_execution_time_seconds REAL,
        total_execution_time_ms REAL,
        result_count INTEGER,
        result_summary TEXT,
        confidence_score REAL,
        user_feedback TEXT,
        user_corrections TEXT,
        retrieved_schema_chunks TEXT,
        schema_relevance_scores TEXT,
        validation_errors TEXT,
        execution_errors TEXT,
        interaction_logs TEXT,
        embedding_vector TEXT,
        query_category TEXT,
        query_complexity REAL,
        tables_referenced TEXT,
        similar_query_ids TEXT,
        refinement_count INTEGER,
        refinement_history TEXT
    )
    ''')
    
    conn.commit()
    conn.close()
    
    print("Query feedback database initialized.")

def get_client_ip():
    """Get the client IP address from the request"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    else:
        return request.environ.get('REMOTE_ADDR', 'unknown')

def save_query_feedback(
    natural_language_query,
    generated_sql,
    validated,
    executed,
    nlq_to_sql_time_seconds,
    sql_execution_time_seconds,
    total_execution_time_ms,
    result_count,
    result_summary,
    confidence_score,
    interaction_logs,
    retrieved_schema_chunks=None,
    schema_relevance_scores=None,
    validation_errors=None,
    execution_errors=None,
    embedding_vector=None,
    query_category=None,
    query_complexity=None,
    tables_referenced=None,
    similar_query_ids=None,
    refinement_count=0,
    refinement_history=None,
    session_id=None
):
    """Save query feedback to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Generate a unique ID for this query
    query_id = str(uuid.uuid4())
    
    # Get current timestamp
    timestamp = datetime.datetime.now().isoformat()
    
    # Get client IP address
    ip_address = get_client_ip()
    
    # Convert lists/dicts to JSON strings
    if isinstance(result_summary, (dict, list)):
        result_summary = json.dumps(result_summary)
    
    if isinstance(interaction_logs, (dict, list)):
        interaction_logs = json.dumps(interaction_logs)
    
    if isinstance(retrieved_schema_chunks, (dict, list)):
        retrieved_schema_chunks = json.dumps(retrieved_schema_chunks)
    
    if isinstance(schema_relevance_scores, (dict, list)):
        schema_relevance_scores = json.dumps(schema_relevance_scores)
    
    if isinstance(validation_errors, (dict, list)):
        validation_errors = json.dumps(validation_errors)
    
    if isinstance(execution_errors, (dict, list)):
        execution_errors = json.dumps(execution_errors)
    
    if isinstance(tables_referenced, (dict, list)):
        tables_referenced = json.dumps(tables_referenced)
    
    if isinstance(similar_query_ids, (dict, list)):
        similar_query_ids = json.dumps(similar_query_ids)
    
    if isinstance(refinement_history, (dict, list)):
        refinement_history = json.dumps(refinement_history)
    
    # Insert the query feedback into the database
    cursor.execute('''
    INSERT INTO query_feedback (
        id, timestamp, ip_address, session_id, natural_language_query, generated_sql,
        validated, executed, nlq_to_sql_time_seconds, sql_execution_time_seconds,
        total_execution_time_ms, result_count, result_summary, confidence_score,
        user_feedback, user_corrections, retrieved_schema_chunks, schema_relevance_scores,
        validation_errors, execution_errors, interaction_logs, embedding_vector,
        query_category, query_complexity, tables_referenced, similar_query_ids,
        refinement_count, refinement_history
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        query_id, timestamp, ip_address, session_id, natural_language_query, generated_sql,
        1 if validated else 0, 1 if executed else 0, nlq_to_sql_time_seconds, sql_execution_time_seconds,
        total_execution_time_ms, result_count, result_summary, confidence_score,
        None, None, retrieved_schema_chunks, schema_relevance_scores,
        validation_errors, execution_errors, interaction_logs, embedding_vector,
        query_category, query_complexity, tables_referenced, similar_query_ids,
        refinement_count, refinement_history
    ))
    
    conn.commit()
    query_record_id = cursor.lastrowid
    conn.close()
    
    return query_id

def update_user_feedback(query_id, feedback):
    """Update the user feedback for a query"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user has already provided feedback
    cursor.execute("SELECT user_feedback FROM query_feedback WHERE id = ?", (query_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        # User has already provided feedback
        conn.close()
        return False
    
    # Update the user feedback
    cursor.execute("UPDATE query_feedback SET user_feedback = ? WHERE id = ?", (feedback, query_id))
    conn.commit()
    
    rows_affected = cursor.rowcount
    conn.close()
    
    return rows_affected > 0

def update_user_corrections(query_id, corrections):
    """Update the user corrections for a query"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update the user corrections
    cursor.execute("UPDATE query_feedback SET user_corrections = ? WHERE id = ?", (corrections, query_id))
    conn.commit()
    
    rows_affected = cursor.rowcount
    conn.close()
    
    return rows_affected > 0

def get_query_feedback(query_id):
    """Get the query feedback for a specific query"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM query_feedback WHERE id = ?", (query_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        return dict(result)
    else:
        return None

def get_all_query_feedback():
    """Get all query feedback records"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM query_feedback ORDER BY timestamp DESC")
    results = cursor.fetchall()
    
    conn.close()
    
    return [dict(row) for row in results]
