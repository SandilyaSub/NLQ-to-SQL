#!/usr/bin/env python3
"""
Test script for BigQuery IMDB integration
"""

import os
import logging
from together import Together
from rag_utils import SchemaRAG
from data_analyst_agent import DataAnalystAgent
from validation_agent import ValidationAgent
from bigquery_connector import execute_query, fix_unqualified_tables

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set environment variables
os.environ["DB_TYPE"] = "bigquery_imdb"

def test_query(question):
    """Test a natural language query end-to-end"""
    
    # Initialize components
    together_client = Together()
    schema_rag = SchemaRAG(together_client=together_client, db_type="bigquery_imdb")
    data_analyst = DataAnalystAgent(schema_rag, together_client)
    validation_agent = ValidationAgent(db_type="bigquery_imdb")
    
    # Step 1: Generate SQL query
    logger.info(f"Generating SQL for question: {question}")
    sql_query = data_analyst.generate_sql({"question": question})
    logger.info(f"Generated SQL: {sql_query}")
    
    # Step 2: Validate the SQL query
    logger.info("Validating SQL query...")
    validation_result = validation_agent.validate_sql(sql_query)
    logger.info(f"Validation result: {validation_result}")
    
    # Step 3: Execute the query if validation passed
    if validation_result["confidence"] >= 80:
        logger.info("Executing SQL query...")
        # Fix unqualified table names if any
        fixed_query = fix_unqualified_tables(sql_query)
        results = execute_query(fixed_query)
        logger.info(f"Query results: {results[:5] if isinstance(results, list) else results}")
        return results
    else:
        logger.error(f"Validation failed: {validation_result['feedback']}")
        return {"error": validation_result["feedback"]}

if __name__ == "__main__":
    # Test with a simple question
    results = test_query("how many actors are there?")
    print("\nFinal results:", results[:5] if isinstance(results, list) and len(results) > 5 else results)
