#!/usr/bin/env python3
"""
Recursive Validation System for NLQ to SQL

This module provides a system that coordinates between the Data Analyst Agent
and Validation Agent to recursively refine SQL queries.
"""

import logging
import sqlite3
import json
from typing import Dict, List, Any, Optional, Tuple
from data_analyst_agent import DataAnalystAgent
from validation_agent import ValidationAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RecursiveValidationSystem:
    """
    System that coordinates between the Data Analyst Agent and Validation Agent
    to recursively refine SQL queries.
    """
    
    def __init__(self, db_path: str, schema_rag, llm_client):
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
        self.validator = ValidationAgent(db_path)
        self.max_iterations = 3
        self.confidence_threshold = 90
    
    def process_query(self, question: str) -> Dict[str, Any]:
        """
        Process a natural language question and generate a SQL query with validation.
        
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
            
            # Generate SQL query
            sql_query = self.data_analyst.generate_sql(context)
            
            # Log the generated SQL
            sql_log = f"Iteration {iterations + 1}: Data Analyst Agent generated SQL: {sql_query}"
            interaction_logs.append(sql_log)
            logger.info(sql_log)
            
            # Check if response is actually SQL
            if not self.validator.is_sql(sql_query):
                error_log = f"Iteration {iterations + 1}: Generated response is not SQL: {sql_query}"
                interaction_logs.append(error_log)
                logger.warning(error_log)
                return {
                    "error": "Could not generate SQL from your question",
                    "message": sql_query,
                    "suggestion": "Please provide more specific details about what you're looking for in the database.",
                    "interaction_logs": interaction_logs
                }
            
            # Log validation start
            validation_start_log = f"Iteration {iterations + 1}: Validation Agent validating SQL..."
            interaction_logs.append(validation_start_log)
            logger.info(validation_start_log)
            
            # Validate query
            validation_result = self.validator.validate(sql_query, question)
            confidence = validation_result["confidence"]
            
            # Log validation result
            validation_log = f"Iteration {iterations + 1}: Validation Agent feedback (confidence: {confidence}%): {validation_result['feedback']}"
            interaction_logs.append(validation_log)
            logger.info(f"Validation result for iteration {iterations}: confidence={confidence}, feedback={validation_result['feedback']}")
            
            # Save validation history
            validation_history.append({
                "iteration": iterations,
                "sql_query": sql_query,
                "confidence": confidence,
                "feedback": validation_result["feedback"]
            })
            
            # Track best query
            if confidence > best_confidence:
                best_query = sql_query
                best_confidence = confidence
            
            # Check if good enough
            if confidence >= self.confidence_threshold:
                logger.info(f"Query achieved confidence threshold ({confidence}%). Stopping iterations.")
                break
                
            # Prepare for next iteration
            iterations += 1
            if iterations < self.max_iterations:
                # Get detailed feedback with suggestions
                detailed_feedback = self.validator.suggest_fixes(validation_result, sql_query)
                
                # Log detailed feedback
                feedback_log = f"Iteration {iterations}: Validation Agent provided detailed feedback for next iteration: {detailed_feedback}"
                interaction_logs.append(feedback_log)
                logger.info(feedback_log)
                
                # Add feedback for next iteration
                context = {
                    "question": question,
                    "feedback": detailed_feedback,
                    "iteration": iterations
                }
            else:
                max_iter_log = f"Reached maximum iterations ({self.max_iterations}). Using best query with confidence {best_confidence}%."
                interaction_logs.append(max_iter_log)
                logger.info(max_iter_log)
        
        # Execute best query
        if best_query:
            try:
                results, column_names = self._execute_sql_query(best_query)
                
                success_log = f"Successfully executed query with confidence {best_confidence}%"
                interaction_logs.append(success_log)
                logger.info(success_log)
                
                return {
                    "question": question,
                    "sql_query": best_query,
                    "confidence": best_confidence,
                    "results": results,
                    "column_names": column_names,
                    "iterations": iterations,
                    "validation_history": validation_history,
                    "interaction_logs": interaction_logs
                }
            except Exception as e:
                logger.error(f"Error executing query: {str(e)}")
                error_log = f"Error executing query: {str(e)}"
                interaction_logs.append(error_log)
                logger.error(error_log)
                
                return {
                    "error": f"Error executing query: {str(e)}",
                    "sql_query": best_query,
                    "confidence": best_confidence,
                    "suggestion": "The query syntax looks valid but there was an execution error",
                    "validation_history": validation_history,
                    "interaction_logs": interaction_logs
                }
        else:
            logger.error("Could not generate a valid SQL query")
            error_log = "Could not generate a valid SQL query"
            interaction_logs.append(error_log)
            logger.error(error_log)
            
            return {
                "error": "Could not generate a valid SQL query",
                "message": "The system could not translate your question to SQL",
                "validation_history": validation_history,
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
