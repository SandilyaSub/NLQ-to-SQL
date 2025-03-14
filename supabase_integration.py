#!/usr/bin/env python3
"""
Supabase Integration for NLQ-to-SQL

This module handles all Supabase-related functionality for storing query feedback
and enhancing the RAG system with historical query data.
"""

import os
import uuid
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase client
def get_supabase_client():
    """Get or create a Supabase client."""
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            logger.warning("Supabase URL or key not found in environment variables")
            return None
            
        supabase_client = create_client(url, key)
        return supabase_client
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {str(e)}")
        return None

# Save query feedback to Supabase
def save_query_feedback(
    natural_language_query,
    generated_sql,
    validated=False,
    executed=False,
    nlq_to_sql_time_seconds=0.0,
    sql_execution_time_seconds=0.0,
    total_execution_time_ms=0.0,
    result_count=0,
    result_summary="[]",
    confidence_score=0.0,
    user_feedback=None,
    user_corrections=None,
    retrieved_schema_chunks=None,
    schema_relevance_scores=None,
    validation_errors=None,
    execution_errors=None,
    interaction_logs=None,
    embedding_vector=None,
    query_category=None,
    query_complexity=0.0,
    tables_referenced=None,
    similar_query_ids=None,
    refinement_count=0,
    refinement_history=None,
    ip_address=None,
    session_id=None
):
    """
    Save query feedback to Supabase.
    
    Returns the query ID if successful, None otherwise.
    """
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        if not supabase:
            logger.warning("Skipping query feedback save - Supabase client not available")
            return None
            
        # Prepare data
        query_id = str(uuid.uuid4())
        data = {
            "id": query_id,
            "timestamp": datetime.now().isoformat(),
            "ip_address": ip_address,
            "session_id": session_id,
            "natural_language_query": natural_language_query,
            "generated_sql": generated_sql,
            "validated": 1 if validated else 0,
            "executed": 1 if executed else 0,
            "nlq_to_sql_time_seconds": nlq_to_sql_time_seconds,
            "sql_execution_time_seconds": sql_execution_time_seconds,
            "total_execution_time_ms": total_execution_time_ms,
            "result_count": result_count,
            "result_summary": result_summary if isinstance(result_summary, str) else json.dumps(result_summary),
            "confidence_score": confidence_score,
            "user_feedback": user_feedback,
            "user_corrections": user_corrections,
            "retrieved_schema_chunks": retrieved_schema_chunks,
            "schema_relevance_scores": schema_relevance_scores,
            "validation_errors": validation_errors,
            "execution_errors": execution_errors,
            "interaction_logs": interaction_logs,
            "embedding_vector": embedding_vector,
            "query_category": query_category,
            "query_complexity": query_complexity,
            "tables_referenced": tables_referenced,
            "similar_query_ids": similar_query_ids,
            "refinement_count": refinement_count,
            "refinement_history": refinement_history
        }
        
        # Insert data
        result = supabase.table("query_feedback").insert(data).execute()
        logger.info(f"Saved query feedback with ID: {query_id}")
        return query_id
        
    except Exception as e:
        logger.error(f"Error saving query feedback to Supabase: {str(e)}")
        return None

# Get successful queries with positive feedback
def get_successful_queries_with_feedback(limit=100):
    """
    Get successful queries with positive feedback for RAG enhancement.
    
    Returns a list of query feedback records.
    """
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        if not supabase:
            logger.warning("Cannot get successful queries - Supabase client not available")
            return []
            
        # Query for successful queries with positive feedback
        result = supabase.table("query_feedback") \
            .select("*") \
            .eq("validated", 1) \
            .eq("executed", 1) \
            .is_("validation_errors", "null") \
            .is_("execution_errors", "null") \
            .order("confidence_score", desc=True) \
            .limit(limit) \
            .execute()
            
        return result.data
        
    except Exception as e:
        logger.error(f"Error getting successful queries from Supabase: {str(e)}")
        return []

# Find similar queries based on embedding vector
def find_similar_queries(query_embedding, limit=5):
    """
    Find similar queries based on embedding vector.
    
    Returns a list of similar query feedback records.
    """
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        if not supabase:
            logger.warning("Cannot find similar queries - Supabase client not available")
            return []
            
        # This would require pgvector extension in Supabase
        # For now, we'll just return an empty list
        logger.warning("Finding similar queries via vector similarity not implemented yet")
        return []
        
    except Exception as e:
        logger.error(f"Error finding similar queries in Supabase: {str(e)}")
        return []

# Enhance RAG with feedback data
def enhance_rag_with_feedback(schema_rag):
    """
    Enhance RAG with query feedback data.
    
    Returns True if successful, False otherwise.
    """
    try:
        # Get successful queries with positive feedback
        successful_queries = get_successful_queries_with_feedback()
        
        if not successful_queries:
            logger.info("No successful queries found for RAG enhancement")
            return False
            
        logger.info(f"Enhancing RAG with {len(successful_queries)} successful queries")
        
        for query in successful_queries:
            # Extract the tables that were actually used in successful queries
            tables_used = json.loads(query.get('tables_referenced', '[]')) if query.get('tables_referenced') else []
            
            # Add exemplar queries with their schema chunks
            if query.get('user_feedback') == 'positive':
                retrieved_chunks = json.loads(query.get('retrieved_schema_chunks', '[]')) if query.get('retrieved_schema_chunks') else []
                
                # This would call a method on your SchemaRAG class
                # Implement this method in your SchemaRAG class
                if hasattr(schema_rag, 'add_exemplar_query'):
                    schema_rag.add_exemplar_query(
                        query_text=query.get('natural_language_query', ''),
                        relevant_chunks=retrieved_chunks,
                        sql_result=query.get('generated_sql', '')
                    )
        
        return True
        
    except Exception as e:
        logger.error(f"Error enhancing RAG with feedback: {str(e)}")
        return False

# Schedule periodic RAG updates
def schedule_rag_updates(schema_rag):
    """
    Schedule periodic RAG updates based on new feedback.
    
    This function should be called during application initialization.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        
        def update_job():
            """Background job to update RAG with new feedback."""
            logger.info("Running scheduled RAG update job")
            enhance_rag_with_feedback(schema_rag)
            
        # Schedule the update job to run every hour
        scheduler = BackgroundScheduler()
        scheduler.add_job(update_job, 'interval', hours=1)
        scheduler.start()
        
        logger.info("Scheduled RAG updates every hour")
        return True
        
    except Exception as e:
        logger.error(f"Error scheduling RAG updates: {str(e)}")
        return False
