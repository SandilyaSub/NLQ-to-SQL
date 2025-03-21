#!/usr/bin/env python3
"""
Validation System for NLQ to SQL

This module provides a system that coordinates between the Data Analyst Agent
and Validation Agent to validate and refine SQL queries.
"""

import logging
import sqlite3
import json
import os
from typing import Dict, List, Any, Optional, Tuple
from data_analyst_agent import DataAnalystAgent
from validation_agent import ValidationAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RecursiveValidationSystem:
    """
    A system that recursively validates and refines SQL queries.
    
    This simplified version uses a deterministic approach with a single validation cycle:
    1. Generate initial SQL query
    2. Validate the query
    3. If validation fails, refine the query
    4. Return the final query and validation results
    """
    
    def __init__(self, db_path, schema_rag, llm_client):
        """
        Initialize the recursive validation system.
        
        Args:
            db_path: Path to the SQLite database
            schema_rag: SchemaRAG instance
            llm_client: Together API client
        """
        self.db_path = db_path
        # Don't maintain a persistent connection to avoid thread safety issues
        self.data_analyst = DataAnalystAgent(schema_rag, llm_client)
        
        # Get the database type from environment variables
        db_type = os.getenv("DB_TYPE", "retail")
        
        # Initialize the validator with the correct database type
        self.validator = ValidationAgent(db_path, db_type=db_type)
        
        self.max_iterations = 2  # Limit to just one refinement attempt
        self.confidence_threshold = 80  # Lower threshold for acceptance
    
    #def process_query(self, question: str, question_type: str) -> Dict[str, Any]:
    def process_query(self, question: str) -> Dict[str, Any]:

        """
        Process a natural language question and generate a SQL query with validation.
        
        This simplified version uses a deterministic approach with a single validation cycle:
        1. Generate initial SQL query
        2. Validate the query for syntax and column/table existence
        3. If issues found, attempt one refinement with feedback
        4. Return the best query
        
        Args:
            question: Natural language question
            
        Returns:
            Dictionary with query results or error information
        """
        logger.info(f"Processing query: {question}")
        
        # Track iterations and best query
        iterations = 0
        best_query = None
        best_confidence = 0
        validation_history = []
        interaction_logs = []  # Track detailed interaction logs
        
        # Initial context
        context = {"question": question, "feedback": None, "iteration": iterations}
        
        while iterations < self.max_iterations:
            # Log the start of this iteration
            iteration_log = f"Iteration {iterations + 1}: Data Analyst Agent generating SQL..."
            interaction_logs.append(iteration_log)
            logger.info(iteration_log)
            
            try:
                # Generate SQL query
                sql_query = self.data_analyst.generate_sql(context)
                
                # Log the generated SQL
                sql_log = f"Iteration {iterations + 1}: Data Analyst Agent generated SQL: {sql_query}"
                interaction_logs.append(sql_log)
                logger.info(sql_log)
                
                # Check if the response is an error message from the DataAnalystAgent
                if sql_query.startswith("ERROR:"):
                    error_log = f"Data Analyst Agent rejected the input: {sql_query}"
                    interaction_logs.append(error_log)
                    logger.warning(error_log)
                    return {
                        "error": "Could not generate SQL from your question",
                        "message": sql_query.replace("ERROR: ", ""),
                        "suggestion": "Please provide a clear, specific question about the database.",
                        "interaction_logs": interaction_logs,
                        "sql_query": ""  # Include empty SQL for consistency
                    }
                
                # Check if response is actually SQL
                if not self.validator.is_sql(sql_query):
                    error_log = f"Generated response is not SQL: {sql_query}"
                    interaction_logs.append(error_log)
                    logger.warning(error_log)
                    return {
                        "error": "Could not generate SQL from your question",
                        "message": sql_query,
                        "suggestion": "Please provide more specific details about what you're looking for in the database.",
                        "interaction_logs": interaction_logs,
                        "sql_query": sql_query  # Include the non-SQL response
                    }
                
                # Log validation start
                validation_start_log = f"Validation Agent validating SQL..."
                interaction_logs.append(validation_start_log)
                logger.info(validation_start_log)
                
                # Validate query - focusing only on syntax and column/table existence
                validation_result = self.validator.validate(sql_query, question)
                confidence = validation_result["confidence"]
                
                # Extract error details for better logging
                error_details = validation_result.get("error_details", {})
                fatal_errors = error_details.get("fatal_errors", [])
                warnings = error_details.get("warnings", [])
                style_issues = error_details.get("style_issues", [])
                
                # Log validation result with error categories
                validation_log = f"Validation Agent feedback (confidence: {confidence}%):"
                interaction_logs.append(validation_log)
                
                # Add categorized errors to logs
                if fatal_errors:
                    fatal_log = "FATAL ERRORS (will prevent execution):"
                    interaction_logs.append(fatal_log)
                    for error in fatal_errors:
                        interaction_logs.append(f"- {error}")
                
                if warnings:
                    warning_log = "WARNINGS (may affect results):"
                    interaction_logs.append(warning_log)
                    for warning in warnings:
                        interaction_logs.append(f"- {warning}")
                
                if style_issues:
                    style_log = "STYLE ISSUES (won't affect execution):"
                    interaction_logs.append(style_log)
                    for issue in style_issues:
                        interaction_logs.append(f"- {issue}")
                
                if not fatal_errors and not warnings and not style_issues:
                    interaction_logs.append("Query looks good!")
                
                logger.info(f"Validation result: confidence={confidence}, feedback={validation_result['feedback']}")
                
                # Save validation history
                validation_history.append({
                    "iteration": iterations,
                    "sql_query": sql_query,
                    "confidence": confidence,
                    "feedback": validation_result["feedback"],
                    "fatal_errors": fatal_errors,
                    "warnings": warnings,
                    "style_issues": style_issues
                })
                
                # Track best query
                if confidence > best_confidence:
                    best_query = sql_query
                    best_confidence = confidence
                
                # Check if good enough - now considering both confidence and absence of fatal errors
                if (confidence >= self.confidence_threshold and not fatal_errors) or validation_result["feedback"] == "Query looks good":
                    success_log = f"Query achieved confidence threshold ({confidence}% >= {self.confidence_threshold}%) with no fatal errors. Stopping iterations."
                    interaction_logs.append(success_log)
                    logger.info(success_log)
                    break
                    
                # Prepare for next iteration - only one refinement attempt
                iterations += 1
                if iterations < self.max_iterations:
                    # Get detailed feedback with suggestions
                    detailed_feedback = self.validator.suggest_fixes(validation_result, sql_query)
                    
                    # Log detailed feedback
                    feedback_log = f"Validation Agent provided feedback for refinement: {detailed_feedback}"
                    interaction_logs.append(feedback_log)
                    logger.info(feedback_log)
                    
                    # Add feedback for refinement
                    context = {
                        "question": question,
                        "feedback": detailed_feedback,
                        "iteration": iterations,
                        "fatal_errors": fatal_errors,  # Include categorized errors in context
                        "warnings": warnings,
                        "style_issues": style_issues
                    }
                else:
                    max_iter_log = f"Reached maximum iterations ({self.max_iterations}). Using best query with confidence {best_confidence}%."
                    interaction_logs.append(max_iter_log)
                    logger.info(max_iter_log)
                    
            except Exception as e:
                # Log the exception in the interaction logs
                error_message = f"Error during iteration {iterations + 1}: {str(e)}"
                interaction_logs.append(error_message)
                logger.error(error_message)
                
                # Return error with interaction logs
                return {
                    "error": f"An error occurred: {str(e)}",
                    "sql_query": sql_query if 'sql_query' in locals() else "",
                    "confidence": 0,
                    "interaction_logs": interaction_logs
                }
        
        # Execute best query
        if best_query:
            try:
                # Get the database type
                db_type = os.getenv("DB_TYPE", "retail")
                
                # Handle BigQuery IMDB database type
                if db_type == "bigquery_imdb":
                    try:
                        # Import BigQuery connector
                        from bigquery_connector import execute_query, fix_unqualified_tables
                        
                        # Fix unqualified table names in the query
                        fixed_query = fix_unqualified_tables(best_query)
                        
                        # Log the execution attempt
                        execution_log = f"Executing BigQuery SQL query: {fixed_query}"
                        interaction_logs.append(execution_log)
                        logger.info(execution_log)
                        
                        # Execute the query using the BigQuery connector
                        results = execute_query(fixed_query)
                        
                        # Log the execution success
                        success_log = f"Query executed successfully. Retrieved {len(results) if results else 0} results."
                        interaction_logs.append(success_log)
                        
                        # If results is a list of dictionaries
                        if isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict):
                            # Extract column names from the first result
                            column_names = list(results[0].keys())
                            return {
                                "question": question,
                                "sql_query": best_query,
                                "results": results,
                                "column_names": column_names,
                                "confidence": best_confidence,
                                "validation_history": validation_history,
                                "interaction_logs": interaction_logs
                            }
                        else:
                            # Empty results or unexpected format
                            return {
                                "question": question,
                                "sql_query": best_query,
                                "results": [],
                                "column_names": [],
                                "confidence": best_confidence,
                                "validation_history": validation_history,
                                "interaction_logs": interaction_logs
                            }
                    except Exception as e:
                        # Log the execution error
                        error_log = f"Error executing BigQuery SQL: {str(e)}"
                        interaction_logs.append(error_log)
                        logger.error(error_log)
                        
                        # Return error with interaction logs
                        return {
                            "error": f"Error executing SQL query: {str(e)}",
                            "sql_query": best_query,
                            "confidence": best_confidence,
                            "validation_history": validation_history,
                            "interaction_logs": interaction_logs
                        }
                else:
                    # SQLite execution
                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        
                        # Log the execution attempt
                        execution_log = f"Executing SQLite query: {best_query}"
                        interaction_logs.append(execution_log)
                        logger.info(execution_log)
                        
                        cursor.execute(best_query)
                        results = [dict(row) for row in cursor.fetchall()]
                        
                        # Log the execution success
                        success_log = f"Query executed successfully. Retrieved {len(results)} results."
                        interaction_logs.append(success_log)
                        
                        column_names = [description[0] for description in cursor.description] if cursor.description else []
                        
                        return {
                            "question": question,
                            "sql_query": best_query,
                            "results": results,
                            "column_names": column_names,
                            "confidence": best_confidence,
                            "validation_history": validation_history,
                            "interaction_logs": interaction_logs
                        }
            except Exception as e:
                # Log the execution error
                error_log = f"Error executing SQL: {str(e)}"
                interaction_logs.append(error_log)
                logger.error(error_log)
                
                # Return error with interaction logs
                return {
                    "error": f"Error executing SQL query: {str(e)}",
                    "sql_query": best_query,
                    "confidence": best_confidence,
                    "validation_history": validation_history,
                    "interaction_logs": interaction_logs
                }
        else:
            # No valid query was generated
            no_query_log = "No valid SQL query could be generated."
            interaction_logs.append(no_query_log)
            logger.warning(no_query_log)
            
            return {
                "error": "Could not generate a valid SQL query for your question.",
                "suggestion": "Please try rephrasing your question to be more specific about what you're looking for in the database.",
                "interaction_logs": interaction_logs
            }
    
    def _execute_sql_query(self, sql_query: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Execute a SQL query and return the results.
        
        Args:
            sql_query: SQL query to execute
            
        Returns:
            Tuple of (results as list of dictionaries, column names)
        """
        # Get the database type
        db_type = os.getenv("DB_TYPE", "retail")
        
        # Handle BigQuery IMDB database type
        if db_type == "bigquery_imdb":
            try:
                # Import BigQuery connector
                from bigquery_connector import execute_query, fix_unqualified_tables
                
                # Fix unqualified table names in the query
                fixed_query = fix_unqualified_tables(sql_query)
                
                logger.info(f"Executing BigQuery SQL query: {fixed_query}")
                
                # Execute the query using the BigQuery connector
                results = execute_query(fixed_query)
                
                # If results is a list of dictionaries
                if isinstance(results, list) and len(results) > 0 and isinstance(results[0], dict):
                    # Extract column names from the first result
                    column_names = list(results[0].keys())
                    return results, column_names
                # If results is a dictionary with an error key
                elif isinstance(results, dict) and "error" in results:
                    raise Exception(results["error"])
                # Empty results case - return empty list and empty column names
                elif isinstance(results, list) and len(results) == 0:
                    logger.info("Query executed successfully but returned no results")
                    return [], []
                # Default case
                else:
                    return [], []
            except Exception as e:
                logger.error(f"Error executing BigQuery query: {str(e)}")
                raise
        # Handle SQLite database types
        else:
            # Create a new connection for thread safety
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql_query)
                
                # Get column names
                column_names = [description[0] for description in cursor.description]
                
                # Fetch all results
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                results = []
                for row in rows:
                    result = {}
                    for i, column in enumerate(column_names):
                        result[column] = row[i]
                    results.append(result)
                
                return results, column_names
