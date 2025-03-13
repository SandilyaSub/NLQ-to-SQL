#!/usr/bin/env python3
"""
Validation Agent for NLQ to SQL

This module provides a simplified validation agent that checks SQL queries for correctness
and provides feedback for refinement, focusing on syntax and column/table validation.
"""

import sqlite3
import re
import logging
from typing import Dict, List, Tuple, Any, Optional
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ValidationAgent:
    """
    Agent responsible for validating SQL queries and providing feedback
    for refinement.
    
    This simplified version focuses on three key validations:
    1. Syntax validation
    2. Column name validation
    3. Table column existence validation
    """
    
    def __init__(self, db_path: str, db_type: str = "retail"):
        """
        Initialize the validation agent.
        
        Args:
            db_path: Path to the SQLite database
            db_type: Type of database to use (retail, movie, or bigquery_imdb)
        """
        self.db_path = db_path
        self.db_type = db_type
        self.schema = {}
        self.table_relationships = {}
        
        # Load schema information based on database type
        if self.db_type == "bigquery_imdb":
            try:
                # Load schema from JSON file for BigQuery IMDB
                with open('imdb_bigquery_schema.json', 'r') as f:
                    schema_data = json.load(f)
                    self.schema = {}
                    for table_name, table_info in schema_data["tables"].items():
                        self.schema[table_name] = table_info["columns"]
                    self.table_relationships = {}
                    if "relationships" in schema_data:
                        for rel in schema_data["relationships"]:
                            table1 = rel["table1"]
                            if table1 not in self.table_relationships:
                                self.table_relationships[table1] = []
                            self.table_relationships[table1].append({
                                "table": rel["table2"],
                                "from_column": rel["column1"],
                                "to_column": rel["column2"]
                            })
                logger.info(f"Loaded BigQuery IMDB schema with {len(self.schema)} tables")
            except Exception as e:
                logger.error(f"Error loading BigQuery IMDB schema: {e}")
                # Initialize with empty schemas as fallback
                self.schema = {}
                self.table_relationships = {}
        else:
            # For SQLite databases (retail or movie)
            try:
                # Extract schema information from the database
                self._extract_schema_from_sqlite()
            except Exception as e:
                logger.error(f"Error extracting schema from SQLite: {e}")
                # Initialize with empty schemas as fallback
                self.schema = {}
                self.table_relationships = {}
    
    def _extract_schema_from_sqlite(self):
        """
        Extract schema information from the SQLite database.
        """
        with sqlite3.connect(self.db_path) as conn:
            self.schema = self._extract_schema(conn)
            self.table_relationships = self._extract_relationships(conn)
    
    def _extract_schema(self, conn) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract schema information from the database.
        
        Args:
            conn: SQLite connection
            
        Returns:
            Dictionary mapping table names to column information
        """
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall() if not table[0].startswith('sqlite_')]
        
        schema = {}
        for table in tables:
            # Get column information
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            schema[table] = [
                {
                    "name": col[1], 
                    "type": col[2],
                    "pk": col[5] == 1
                } for col in columns
            ]
        
        return schema
    
    def _extract_relationships(self, conn) -> Dict[str, List[Dict[str, str]]]:
        """
        Extract foreign key relationships from the database.
        For the movie database, define explicit relationships.
        
        Args:
            conn: SQLite connection
            
        Returns:
            Dictionary mapping table names to their relationships
        """
        # If it's the movie database, define explicit relationships
        if self.db_type == "movie":
            relationships = {
                "title_ratings": [
                    {"from_column": "tconst", "to_table": "title_basics", "to_column": "tconst"}
                ],
                "title_crew": [
                    {"from_column": "tconst", "to_table": "title_basics", "to_column": "tconst"}
                ],
                "title_episode": [
                    {"from_column": "tconst", "to_table": "title_basics", "to_column": "tconst"},
                    {"from_column": "parentTconst", "to_table": "title_basics", "to_column": "tconst"}
                ],
                "title_principals": [
                    {"from_column": "tconst", "to_table": "title_basics", "to_column": "tconst"},
                    {"from_column": "nconst", "to_table": "name_basics", "to_column": "nconst"}
                ],
                "title_akas": [
                    {"from_column": "titleId", "to_table": "title_basics", "to_column": "tconst"}
                ]
            }
            return relationships
        else:
            # For retail database, extract from SQLite
            cursor = conn.cursor()
            relationships = {}
            
            for table in self.schema.keys():
                cursor.execute(f"PRAGMA foreign_key_list({table})")
                foreign_keys = cursor.fetchall()
                
                if foreign_keys:
                    relationships[table] = []
                    for fk in foreign_keys:
                        relationships[table].append({
                            "from_column": fk[3],
                            "to_table": fk[2],
                            "to_column": fk[4]
                        })
            
            return relationships
    
    def is_sql(self, text: str) -> bool:
        """
        Check if the provided text is likely SQL rather than a natural language response.
        
        Args:
            text: Text to check
            
        Returns:
            True if the text appears to be SQL, False otherwise
        """
        # SQL keywords that indicate this is likely a SQL query
        sql_keywords = ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY", "ORDER BY", "HAVING", "LIMIT"]
        
        # Check if any SQL keywords are present
        text_upper = text.upper()
        if any(f" {keyword} " in f" {text_upper} " or text_upper.startswith(keyword) for keyword in sql_keywords):
            # Additional check: SQL typically has a structure with SELECT and FROM
            if "SELECT" in text_upper and "FROM" in text_upper:
                return True
        
        return False
    
    def validate(self, sql_query: str, question: str) -> Dict[str, Any]:
        """
        Validate a SQL query and return a confidence score with feedback.
        
        This simplified version focuses on three key validations:
        1. Syntax validation
        2. Column name validation
        3. Table column existence validation
        
        Args:
            sql_query: SQL query to validate
            question: Original natural language question
            
        Returns:
            Dictionary with validation results
        """
        feedback = []
        confidence = 100  # Start with perfect score and deduct
        
        # 1. Syntax check - most important to check first
        syntax_issues = self._check_syntax(sql_query)
        if syntax_issues:
            feedback.append(f"Syntax issues: {syntax_issues}")
            confidence -= 40  # Significant deduction for syntax errors
        
        # Only check columns if syntax is valid
        if not syntax_issues:
            # 2. Column and table existence check
            missing_columns, incorrect_tables = self._check_columns(sql_query)
            if missing_columns:
                feedback.append(f"Missing or incorrect columns: {', '.join(missing_columns)}")
                confidence -= min(30, len(missing_columns) * 10)  # Deduct up to 30 points
                
            if incorrect_tables:
                feedback.append(f"Missing or incorrect tables: {', '.join(incorrect_tables)}")
                confidence -= min(30, len(incorrect_tables) * 15)  # Deduct up to 30 points
        
        # Ensure confidence is between 0-100
        confidence = max(0, min(100, confidence))
        
        return {
            "confidence": confidence,
            "feedback": "; ".join(feedback) if feedback else "Query looks good",
            "issues_found": len(feedback) > 0
        }
    
    def _check_columns(self, sql_query: str) -> Tuple[List[str], List[str]]:
        """
        Check if all columns in the query exist in the schema.
        
        Args:
            sql_query: SQL query to check
            
        Returns:
            Tuple of (list of missing/incorrect columns, list of missing/incorrect tables)
        """
        # Extract column references from the query
        # This is a simplified approach and might miss some complex cases
        column_pattern = r'(?:SELECT|WHERE|ORDER BY|GROUP BY|HAVING|ON|AND|OR|,)\s+(?!COUNT|SUM|AVG|MIN|MAX)(?:\w+\.)?(\w+)'
        table_pattern = r'FROM\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?|JOIN\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        
        # Extract column references
        column_matches = re.finditer(column_pattern, sql_query, re.IGNORECASE)
        column_refs = []
        for match in column_matches:
            col = match.group(1)
            if col.lower() not in ('as', 'on', 'where', 'and', 'or', 'select', 'from', 'join', 'inner', 'left', 'right'):
                column_refs.append(col)
        
        # Extract table references
        table_matches = re.finditer(table_pattern, sql_query, re.IGNORECASE)
        table_refs = []
        for match in table_matches:
            if match.group(1):  # FROM clause
                table_refs.append(match.group(1))
            elif match.group(3):  # JOIN clause
                table_refs.append(match.group(3))
        
        # Check if tables exist
        incorrect_tables = []
        for table in table_refs:
            if table.lower() not in [t.lower() for t in self.schema.keys()]:
                incorrect_tables.append(table)
        
        # Check if columns exist in any table
        missing_columns = []
        for col in column_refs:
            # Skip special cases like * or functions
            if col == '*' or col.lower() in ('count', 'sum', 'avg', 'min', 'max'):
                continue
                
            # Check if column exists in any table
            found = False
            for table, columns in self.schema.items():
                if col.lower() in [c['name'].lower() for c in columns]:
                    found = True
                    break
            
            if not found:
                # For BigQuery IMDB, check if this might be a camelCase version of a valid column
                if self.db_type == "bigquery_imdb":
                    # Common camelCase to underscore mappings
                    camel_to_underscore = {
                        'primaryName': 'primary_name',
                        'titleType': 'title_type',
                        'birthYear': 'birth_year',
                        'deathYear': 'death_year',
                        'primaryTitle': 'primary_title',
                        'originalTitle': 'original_title',
                        'isAdult': 'is_adult',
                        'startYear': 'start_year',
                        'endYear': 'end_year',
                        'runtimeMinutes': 'runtime_minutes',
                        'primaryProfession': 'primary_profession',
                        'knownForTitles': 'known_for_titles'
                    }
                    
                    if col in camel_to_underscore:
                        underscore_col = camel_to_underscore[col]
                        # Check if the underscore version exists
                        for table, columns in self.schema.items():
                            if underscore_col.lower() in [c['name'].lower() for c in columns]:
                                missing_columns.append(f"{col} (should be {underscore_col})")
                                found = True  # Mark as found but still report the issue
                                break
                
                if not found:
                    missing_columns.append(col)
        
        return missing_columns, incorrect_tables
    
    def _check_joins(self, sql_query: str) -> Optional[str]:
        """
        Check if joins in the query are using correct relationships.
        
        Args:
            sql_query: SQL query to check
            
        Returns:
            String describing join issues or None if no issues found
        """
        # This is a simplified check and might miss some complex cases
        join_pattern = r'(\w+)\s+(?:INNER|LEFT|RIGHT|OUTER)?\s*JOIN\s+(\w+)\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
        
        join_matches = re.finditer(join_pattern, sql_query, re.IGNORECASE)
        
        for match in join_matches:
            table1, table2 = match.group(1), match.group(2)
            t1_alias, t2_alias = match.group(3), match.group(5)
            col1, col2 = match.group(4), match.group(6)
            
            # Skip if we can't determine the actual tables (due to aliases)
            if t1_alias != table1 and t2_alias != table2:
                continue
                
            # Check if this join matches a known relationship
            valid_join = False
            
            # Check relationships in both directions
            for src_table, relationships in self.table_relationships.items():
                if src_table.lower() not in (table1.lower(), table2.lower()):
                    continue
                    
                for rel in relationships:
                    # Check if this relationship matches our join
                    if (src_table.lower() == table1.lower() and 
                        rel['table'].lower() == table2.lower() and
                        rel['from_column'].lower() == col1.lower() and
                        rel['to_column'].lower() == col2.lower()):
                        valid_join = True
                        break
                    elif (src_table.lower() == table2.lower() and 
                          rel['table'].lower() == table1.lower() and
                          rel['from_column'].lower() == col2.lower() and
                          rel['to_column'].lower() == col1.lower()):
                        valid_join = True
                        break
            
            if not valid_join:
                return f"Join between {table1} and {table2} might not use the correct relationship"
        
        return None
    
    def _check_syntax(self, sql_query: str) -> Optional[str]:
        """
        Check if the SQL query has syntax errors.
        
        Args:
            sql_query: SQL query to check
            
        Returns:
            String describing syntax issues or None if no issues found
        """
        # Clean up the query - remove any trailing semicolons or whitespace
        test_query = sql_query.strip()
        if test_query.endswith(';'):
            test_query = test_query[:-1].strip()
        
        # Handle BigQuery IMDB database type
        if self.db_type == "bigquery_imdb":
            try:
                # Import BigQuery connector
                from bigquery_connector import check_sql_syntax, fix_unqualified_tables
                
                # First, try to fix unqualified table names
                fixed_query = fix_unqualified_tables(test_query)
                
                # Check if the query has syntax errors
                error = check_sql_syntax(fixed_query)
                
                if error:
                    # Provide more user-friendly error messages for common issues
                    if "Table not found" in error or "Not found" in error:
                        return "Table not found. Please check the table name and make sure it's qualified with 'imdb'."
                    elif "Unrecognized name" in error or "Column not found" in error:
                        return "Column not found. Please check the column name."
                    else:
                        return error
                return None
            except Exception as e:
                error_msg = str(e)
                # Provide more user-friendly error messages for common issues
                if "Table not found" in error_msg or "Not found" in error_msg:
                    return "Table not found. Please check the table name and make sure it's qualified with 'imdb'."
                elif "Unrecognized name" in error_msg or "Column not found" in error_msg:
                    return "Column not found. Please check the column name."
                else:
                    return error_msg
        # Handle SQLite database types
        else:
            try:
                # Use SQLite parser to check syntax with a new connection
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"EXPLAIN {test_query}")
                    cursor.fetchall()  # Consume the results
                return None
            except sqlite3.Error as e:
                error_msg = str(e)
                # Provide more user-friendly error messages for common issues
                if "no such table" in error_msg:
                    table_name = error_msg.split("no such table: ")[1].split()[0]
                    return f"Table '{table_name}' not found. Please check the table name."
                elif "no such column" in error_msg:
                    column_name = error_msg.split("no such column: ")[1].split()[0]
                    return f"Column '{column_name}' not found. Please check the column name."
                else:
                    return error_msg
    
    def _check_intent(self, sql_query: str, question: str) -> Optional[str]:
        """
        Check if the SQL query matches the intent of the question.
        
        Args:
            sql_query: SQL query to check
            question: Original natural language question
            
        Returns:
            String describing intent issues or None if no issues found
        """
        # This is a simplified check and might miss some complex cases
        
        # Check for aggregation
        aggregation_keywords = ['count', 'sum', 'avg', 'min', 'max', 'total']
        question_has_aggregation = any(keyword in question.lower() for keyword in aggregation_keywords)
        query_has_aggregation = any(keyword in sql_query.lower() for keyword in aggregation_keywords)
        
        if question_has_aggregation and not query_has_aggregation:
            return "Question asks for aggregation but query doesn't include it"
        
        # Check for ordering
        ordering_keywords = ['top', 'highest', 'lowest', 'most', 'least', 'best', 'worst', 'sort', 'order']
        question_has_ordering = any(keyword in question.lower() for keyword in ordering_keywords)
        query_has_ordering = 'order by' in sql_query.lower()
        
        if question_has_ordering and not query_has_ordering:
            return "Question implies ordering but query doesn't include ORDER BY"
        
        # Check for filtering
        filtering_keywords = ['where', 'filter', 'only', 'specific', 'particular']
        question_has_filtering = any(keyword in question.lower() for keyword in filtering_keywords)
        query_has_filtering = 'where' in sql_query.lower()
        
        if question_has_filtering and not query_has_filtering:
            return "Question implies filtering but query doesn't include WHERE clause"
        
        return None
    
    def _test_execution(self, sql_query: str) -> Optional[str]:
        """
        Test execute the SQL query with a LIMIT clause to check for execution issues.
        
        Args:
            sql_query: SQL query to check
            
        Returns:
            String describing execution issues or None if no issues found
        """
        # Clean up the query - remove any trailing semicolons or whitespace
        test_query = sql_query.strip()
        if test_query.endswith(';'):
            test_query = test_query[:-1].strip()
            
        # Don't add LIMIT for COUNT queries as it doesn't make sense
        is_count_query = re.search(r'\bSELECT\s+COUNT\s*\(', test_query, re.IGNORECASE) is not None
        
        if not is_count_query and 'limit' not in test_query.lower():
            # Check if there's already an ORDER BY clause
            if 'order by' in test_query.lower():
                test_query = re.sub(r'(ORDER BY\s+.+?)$', r'\1 LIMIT 1', test_query, flags=re.IGNORECASE)
            else:
                test_query += " LIMIT 1"
        
        try:
            # Use a new connection for thread safety
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(test_query)
                cursor.fetchall()  # Consume the results
            return None
        except sqlite3.Error as e:
            error_msg = str(e)
            # Check for specific error about multiple statements
            if "you can only execute one statement at a time" in error_msg.lower():
                # Look for multiple statements separated by semicolons
                statements = [s.strip() for s in sql_query.split(';') if s.strip()]
                if len(statements) > 1:
                    return "Multiple SQL statements detected. Please use only one statement."
                else:
                    # If we don't actually have multiple statements, this is likely a false positive
                    # due to some other syntax issue
                    return "Syntax error in the query. Please check the query structure."
            return error_msg
    
    def suggest_fixes(self, validation_result: Dict[str, Any], sql_query: str) -> str:
        """
        Suggest specific fixes based on validation results.
        
        Args:
            validation_result: Validation result dictionary
            sql_query: Original SQL query
            
        Returns:
            String with suggested fixes
        """
        feedback = validation_result.get("feedback", "")
        
        # If no issues, no fixes needed
        if feedback == "Query looks good":
            return feedback
            
        # Generate suggestions based on the feedback
        suggestions = []
        
        if "Missing or incorrect columns" in feedback:
            suggestions.append("Check column names and make sure they exist in the database schema.")
            
        if "Missing or incorrect tables" in feedback:
            suggestions.append("Check table names and make sure they exist in the database.")
            
        if "Syntax issues" in feedback:
            suggestions.append("Fix syntax errors in the query.")
        
        if not suggestions:
            return feedback
            
        return feedback + "\n\nSuggested fixes:\n- " + "\n- ".join(suggestions)
