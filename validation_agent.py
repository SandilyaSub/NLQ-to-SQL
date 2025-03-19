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
    
    This simplified version focuses on four key validations:
    1. Syntax validation
    2. Column name validation
    3. Table column existence validation
    4. CTE (Common Table Expression) validation
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
    
    def validate(self, sql_query: str, question: str = None) -> Dict[str, Any]:
        """
        Validate a SQL query against the schema.
        
        Args:
            sql_query: SQL query to validate
            question: Original natural language question (kept for backward compatibility)
            
        Returns:
            Dictionary with validation results
        """
        if not sql_query:
            return {
                "valid": False,
                "error": "Empty query",
                "severity": "error",
                "error_type": "syntax",
                "error_detail": "The query is empty"
            }
            
        # Extract CTEs from the query
        ctes = self._extract_ctes(sql_query)
        
        # Check for syntax errors
        syntax_error = self._check_syntax(sql_query)
        if syntax_error:
            return {
                "valid": False,
                "error": syntax_error,
                "severity": "error",
                "error_type": "syntax",
                "error_detail": "The query has syntax errors"
            }
            
        # Check for BigQuery-specific issues
        if self.db_type == "bigquery_imdb":
            bigquery_issues = self._check_bigquery_specific_issues(sql_query)
            if bigquery_issues:
                return {
                    "valid": False,
                    "error": bigquery_issues,
                    "severity": "warning",
                    "error_type": "bigquery_specific",
                    "error_detail": "The query has BigQuery-specific issues"
                }
            
        # Check for missing/incorrect columns and tables
        missing_columns, incorrect_tables, error_messages = self._check_columns(sql_query, ctes)
        
        # Classify errors by severity
        if incorrect_tables:
            # Missing tables is a critical error
            tables_str = ", ".join(incorrect_tables)
            return {
                "valid": False,
                "error": f"Tables not found: {tables_str}",
                "severity": "error",
                "error_type": "table_not_found",
                "error_detail": f"The following tables were not found in the schema: {tables_str}"
            }
        elif missing_columns:
            # Check if these are just CTE column issues
            cte_column_issues = [col for col in missing_columns if " in " in col and col.split(" in ")[1] in ctes]
            regular_column_issues = [col for col in missing_columns if " in " not in col or col.split(" in ")[1] not in ctes]
            
            # If we only have CTE column issues, it's a warning
            if cte_column_issues and not regular_column_issues:
                columns_str = ", ".join(cte_column_issues)
                return {
                    "valid": True,  # Still valid but with warnings
                    "warning": f"Potential CTE column issues: {columns_str}",
                    "severity": "warning",
                    "error_type": "cte_column_reference",
                    "error_detail": "The query references columns in CTEs that couldn't be validated. This might be due to limitations in the validation process."
                }
            # If we have regular column issues, it's an error
            elif regular_column_issues:
                columns_str = ", ".join(regular_column_issues)
                return {
                    "valid": False,
                    "error": f"Columns not found: {columns_str}",
                    "severity": "error",
                    "error_type": "column_not_found",
                    "error_detail": f"The following columns were not found in the schema: {columns_str}"
                }
            
        # If we get here, the query is valid
        return {
            "valid": True,
            "message": "Query is valid"
        }
    
    def _extract_ctes(self, sql_query: str) -> Dict[str, Dict]:
        """
        Extract Common Table Expressions (CTEs) from a SQL query.
        
        Args:
            sql_query: SQL query to analyze
            
        Returns:
            Dictionary mapping CTE names to their definitions
        """
        ctes = {}
        
        # Check if query has WITH clause
        if not re.search(r'\bWITH\b', sql_query, re.IGNORECASE):
            return ctes
        
        # Normalize the query to help with regex matching
        # Remove extra whitespace and newlines
        normalized_query = re.sub(r'\s+', ' ', sql_query).strip()
        
        # Extract the WITH clause - improved pattern that handles multiple CTEs
        # This pattern matches from WITH to the first SELECT that's not inside parentheses
        with_pattern = r'\bWITH\b\s+(.*?)(?=\bSELECT\b(?![^()]*\)))'
        with_match = re.search(with_pattern, normalized_query, re.IGNORECASE | re.DOTALL)
        
        if not with_match:
            # Try an alternative approach - find the main SELECT after all CTEs
            # First, find the position of WITH
            with_pos = re.search(r'\bWITH\b', normalized_query, re.IGNORECASE).start()
            
            # Track parentheses to find the end of all CTE definitions
            paren_count = 0
            in_cte_block = True
            cte_end_pos = with_pos + 4  # Start after "WITH"
            
            for i in range(with_pos + 4, len(normalized_query)):
                if normalized_query[i] == '(':
                    paren_count += 1
                elif normalized_query[i] == ')':
                    paren_count -= 1
                
                # If we're at balanced parentheses and find a SELECT not followed by another CTE definition
                if paren_count == 0 and re.match(r'\bSELECT\b', normalized_query[i:i+6], re.IGNORECASE):
                    if not re.search(r'\)\s*,\s*\w+\s+AS\s+\(', normalized_query[i:i+30], re.IGNORECASE):
                        cte_end_pos = i
                        break
            
            # Extract the WITH clause content
            with_clause = normalized_query[with_pos + 4:cte_end_pos].strip()
        else:
            with_clause = with_match.group(1)
        
        # Split the WITH clause into individual CTEs
        # Improved pattern that handles nested parentheses
        cte_pattern = r'([a-zA-Z0-9_]+)\s+AS\s+\(((?:[^()]|\([^()]*\)|\((?:[^()]*\))+\))*)\)'
        cte_matches = re.finditer(cte_pattern, with_clause, re.IGNORECASE | re.DOTALL)
        
        for match in cte_matches:
            cte_name = match.group(1)
            cte_definition = match.group(2).strip()
            
            # Extract columns from the CTE definition
            columns = self._extract_columns_from_cte(cte_definition)
            
            ctes[cte_name] = {
                "definition": cte_definition,
                "columns": columns
            }
        
        # If we didn't find any CTEs with the regex, try a more manual approach
        if not ctes:
            # Split by commas outside of parentheses
            parts = []
            current_part = ""
            paren_count = 0
            
            for char in with_clause:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                
                if char == ',' and paren_count == 0:
                    parts.append(current_part.strip())
                    current_part = ""
                else:
                    current_part += char
            
            if current_part.strip():
                parts.append(current_part.strip())
            
            # Process each part as a CTE
            for part in parts:
                match = re.match(r'([a-zA-Z0-9_]+)\s+AS\s+\((.*)', part, re.IGNORECASE | re.DOTALL)
                if match:
                    cte_name = match.group(1)
                    # Find the matching closing parenthesis
                    cte_def = match.group(2)
                    paren_count = 1  # We've already seen one opening parenthesis
                    
                    for i, char in enumerate(cte_def):
                        if char == '(':
                            paren_count += 1
                        elif char == ')':
                            paren_count -= 1
                            if paren_count == 0:
                                cte_definition = cte_def[:i].strip()
                                break
                    
                    # Extract columns
                    columns = self._extract_columns_from_cte(cte_definition)
                    
                    ctes[cte_name] = {
                        "definition": cte_definition,
                        "columns": columns
                    }
        
        return ctes
    
    def _extract_columns_from_cte(self, cte_definition: str) -> List[str]:
        """
        Extract column names from a CTE definition.
        
        Args:
            cte_definition: SQL for the CTE definition
            
        Returns:
            List of column names
        """
        columns = []
        
        # Normalize the definition to help with regex matching
        normalized_def = re.sub(r'\s+', ' ', cte_definition).strip()
        
        # Look for explicit column aliases in the SELECT clause
        select_pattern = r'\bSELECT\b\s+(.*?)(?:\bFROM\b)'
        select_match = re.search(select_pattern, normalized_def, re.IGNORECASE | re.DOTALL)
        
        if not select_match:
            # Try a more lenient approach for complex queries
            # Find the first FROM after SELECT
            select_pos = re.search(r'\bSELECT\b', normalized_def, re.IGNORECASE)
            if select_pos:
                select_pos = select_pos.start()
                from_pos = re.search(r'\bFROM\b', normalized_def[select_pos:], re.IGNORECASE)
                if from_pos:
                    from_pos = select_pos + from_pos.start()
                    select_clause = normalized_def[select_pos + 6:from_pos].strip()
                else:
                    # If FROM not found, try to extract columns anyway
                    select_clause = normalized_def[select_pos + 6:].strip()
            else:
                return columns
        else:
            select_clause = select_match.group(1)
        
        # Handle SELECT * case
        if select_clause.strip() == '*':
            # For SELECT *, we need to infer columns from the referenced tables
            # This is complex and would require analyzing the FROM clause of the CTE
            # For now, we'll just return a special marker
            return ['*']
        
        # Split by commas, but handle function calls and nested expressions
        in_function = 0
        in_parentheses = 0
        in_quotes = False
        quote_char = None
        current_column = ""
        
        for char in select_clause:
            if char in ('"', "'", '`') and (not quote_char or char == quote_char):
                in_quotes = not in_quotes
                if in_quotes:
                    quote_char = char
                else:
                    quote_char = None
                current_column += char
            elif in_quotes:
                current_column += char
            elif char == '(':
                in_parentheses += 1
                current_column += char
            elif char == ')':
                in_parentheses -= 1
                current_column += char
            elif char == ',' and in_parentheses == 0:
                # End of column expression
                columns.append(current_column.strip())
                current_column = ""
            else:
                current_column += char
        
        # Add the last column
        if current_column.strip():
            columns.append(current_column.strip())
        
        # Extract column aliases
        result_columns = []
        for col in columns:
            # Handle special case for BigQuery backtick identifiers
            if self.db_type == "bigquery_imdb" and '`' in col:
                # Extract the last backticked identifier if it's an alias
                backtick_parts = re.findall(r'`([^`]+)`', col)
                if backtick_parts:
                    # Check if the last part is likely an alias
                    if ' AS ' in col.upper():
                        result_columns.append(backtick_parts[-1])
                    else:
                        # Get the last part of the path (e.g., `project.dataset.table`.`column` -> column)
                        last_part = backtick_parts[-1].split('.')[-1]
                        result_columns.append(last_part)
                    continue
            
            # Look for AS alias (case insensitive)
            as_match = re.search(r'\bAS\b\s+([a-zA-Z0-9_]+|\`[^\`]+\`)', col, re.IGNORECASE)
            if as_match:
                alias = as_match.group(1)
                # Remove backticks if present
                alias = alias.strip('`')
                result_columns.append(alias)
                continue
                
            # Look for implicit alias (column_expression alias)
            implicit_match = re.search(r'([a-zA-Z0-9_]+|\`[^\`]+\`)$', col.strip())
            if implicit_match:
                alias = implicit_match.group(1)
                # Remove backticks if present
                alias = alias.strip('`')
                result_columns.append(alias)
                continue
                
            # For expressions without aliases, try to extract a meaningful name
            # Check for common aggregate functions
            agg_match = re.search(r'\b(COUNT|SUM|AVG|MIN|MAX|DISTINCT)\s*\(\s*(?:DISTINCT\s+)?([^\(\)]+)\)', col, re.IGNORECASE)
            if agg_match:
                func = agg_match.group(1).lower()
                col_name = agg_match.group(2).strip().split('.')[-1].strip('`" ')
                result_columns.append(f"{func}_{col_name}")
                continue
                
            # For other expressions without aliases, use a generic name
            # This is not ideal but better than nothing
            result_columns.append(col.strip())
        
        return result_columns
    
    def _validate_ctes(self, sql_query: str, ctes: Dict[str, Dict]) -> List[str]:
        """
        Validate CTE definitions and usage.
        
        Args:
            sql_query: SQL query to validate
            ctes: Dictionary of CTEs extracted from the query
            
        Returns:
            List of CTE validation issues
        """
        issues = []
        
        if not ctes:
            return issues
        
        # Check for recursive references (CTEs referencing themselves)
        for cte_name, cte_info in ctes.items():
            if re.search(r'\b' + re.escape(cte_name) + r'\b', cte_info["definition"], re.IGNORECASE):
                issues.append(f"CTE '{cte_name}' references itself, which may cause issues")
        
        # Check for forward references (CTEs referencing CTEs defined later)
        cte_names = list(ctes.keys())
        for i, cte_name in enumerate(cte_names):
            cte_info = ctes[cte_name]
            for later_cte in cte_names[i+1:]:
                if re.search(r'\b' + re.escape(later_cte) + r'\b', cte_info["definition"], re.IGNORECASE):
                    issues.append(f"CTE '{cte_name}' references '{later_cte}' which is defined later")
        
        # Check for unused CTEs
        main_query = sql_query
        with_match = re.search(r'\bWITH\b\s+(.*?)(?:\bSELECT\b)', sql_query, re.IGNORECASE | re.DOTALL)
        if with_match:
            # Get the part of the query after the WITH clause
            with_end_pos = with_match.end() - len("SELECT")
            main_query = sql_query[with_end_pos:]
        
        for cte_name in ctes:
            if not re.search(r'\b' + re.escape(cte_name) + r'\b', main_query, re.IGNORECASE):
                issues.append(f"CTE '{cte_name}' is defined but not used in the main query")
        
        return issues
    
    def _check_columns(self, sql_query: str, ctes: Dict[str, Dict] = None) -> Tuple[List[str], List[str], List[str]]:
        """
        Check if all columns in the query exist in the schema or CTEs.
        
        Args:
            sql_query: SQL query to check
            ctes: Dictionary of CTEs extracted from the query
            
        Returns:
            Tuple of (list of missing/incorrect columns, list of missing/incorrect tables, list of error messages)
        """
        if ctes is None:
            ctes = {}
            
        # Normalize the query to help with regex matching
        normalized_query = re.sub(r'\s+', ' ', sql_query).strip()
            
        # Extract table references and aliases with improved patterns for BigQuery
        # Handle backtick-quoted identifiers for BigQuery
        if self.db_type == "bigquery_imdb":
            # Pattern for BigQuery table references with backticks
            table_pattern = r'FROM\s+(?:`[^`]+`(?:\.[^`]+`)?|[a-zA-Z0-9_]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?|JOIN\s+(?:`[^`]+`(?:\.[^`]+`)?|[a-zA-Z0-9_]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?'
        else:
            # Standard pattern for SQLite
            table_pattern = r'FROM\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?|JOIN\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        
        # Extract table references and aliases
        table_matches = re.finditer(table_pattern, normalized_query, re.IGNORECASE)
        table_refs = []
        table_aliases = {}  # Map aliases to actual tables
        
        for match in table_matches:
            if self.db_type == "bigquery_imdb":
                # Extract table name and alias for BigQuery
                if match.group(0).startswith('FROM'):
                    # Extract the table name from backticks if present
                    table_part = re.search(r'FROM\s+(`[^`]+`(?:\.[^`]+`)?|[a-zA-Z0-9_]+)', match.group(0))
                    if table_part:
                        table = table_part.group(1).strip('`')
                        # For BigQuery, handle fully qualified names
                        if '.' in table:
                            # Extract just the table name from the fully qualified path
                            table = table.split('.')[-1]
                        alias = match.group(1) if match.group(1) else table
                        table_refs.append(table)
                        table_aliases[alias] = table
                else:  # JOIN clause
                    table_part = re.search(r'JOIN\s+(`[^`]+`(?:\.[^`]+`)?|[a-zA-Z0-9_]+)', match.group(0))
                    if table_part:
                        table = table_part.group(1).strip('`')
                        # For BigQuery, handle fully qualified names
                        if '.' in table:
                            # Extract just the table name from the fully qualified path
                            table = table.split('.')[-1]
                        alias = match.group(2) if match.group(2) else table
                        table_refs.append(table)
                        table_aliases[alias] = table
            else:
                # Standard SQLite extraction
                if match.group(1):  # FROM clause
                    table = match.group(1)
                    alias = match.group(2) if match.group(2) else table
                    table_refs.append(table)
                    table_aliases[alias] = table
                elif match.group(3):  # JOIN clause
                    table = match.group(3)
                    alias = match.group(4) if match.group(4) else table
                    table_refs.append(table)
                    table_aliases[alias] = table
        
        # Add CTE names as valid table references
        for cte_name in ctes:
            if cte_name not in table_refs:
                table_refs.append(cte_name)
                table_aliases[cte_name] = cte_name
        
        # Extract column references with improved patterns
        # Handle both standard and backtick-quoted column references
        if self.db_type == "bigquery_imdb":
            column_pattern = r'(?:SELECT|WHERE|ORDER BY|GROUP BY|HAVING|ON|AND|OR|,)\s+(?!COUNT|SUM|AVG|MIN|MAX|DISTINCT)(?:([a-zA-Z0-9_]+|`[^`]+`)\.)?([a-zA-Z0-9_]+|`[^`]+`)'
        else:
            column_pattern = r'(?:SELECT|WHERE|ORDER BY|GROUP BY|HAVING|ON|AND|OR|,)\s+(?!COUNT|SUM|AVG|MIN|MAX|DISTINCT)(?:(\w+)\.)?(\w+)'
        
        # Extract column references with table aliases
        column_matches = re.finditer(column_pattern, normalized_query, re.IGNORECASE)
        column_refs = []
        qualified_column_refs = []  # Store table.column pairs
        
        for match in column_matches:
            table_alias = match.group(1)
            col = match.group(2)
            
            # Clean up backticks for BigQuery
            if table_alias:
                table_alias = table_alias.strip('`')
            if col:
                col = col.strip('`')
            
            # Skip SQL keywords and special cases
            if col and col.lower() not in ('as', 'on', 'where', 'and', 'or', 'select', 'from', 'join', 'inner', 'left', 'right', 'full', 'outer', '*'):
                column_refs.append(col)
                if table_alias:
                    qualified_column_refs.append((table_alias, col))
        
        # Check if tables exist (either in schema or as CTEs)
        incorrect_tables = []
        for table in table_refs:
            # Skip checking CTEs - they are valid by definition
            if table in ctes:
                continue
                
            # For BigQuery, check if this is a fully qualified table
            if self.db_type == "bigquery_imdb" and '.' in table:
                # Extract just the table name
                simple_table = table.split('.')[-1]
                if simple_table.lower() not in [t.lower() for t in self.schema.keys()]:
                    incorrect_tables.append(table)
            elif table.lower() not in [t.lower() for t in self.schema.keys()]:
                incorrect_tables.append(table)
        
        # Check if columns exist in any table or CTE
        missing_columns = []
        error_messages = []
        
        # First check qualified column references (table.column)
        for table_alias, col in qualified_column_refs:
            if table_alias in table_aliases:
                actual_table = table_aliases[table_alias]
                
                # Check if this is a CTE
                if actual_table in ctes:
                    # Check if column exists in this CTE
                    cte_columns = ctes[actual_table]["columns"]
                    
                    # Handle the special case where CTE returns '*'
                    if '*' in cte_columns:
                        # We can't validate this precisely without analyzing the FROM clause of the CTE
                        continue
                        
                    if col.lower() not in [c.lower() for c in cte_columns]:
                        missing_columns.append(f"{col} in {actual_table}")
                        error_messages.append(f"Column {col} not found in CTE {actual_table}")
                # Check if this is a real table
                elif actual_table.lower() in [t.lower() for t in self.schema.keys()]:
                    # Get the actual table name with correct case
                    actual_table_name = next((t for t in self.schema.keys() if t.lower() == actual_table.lower()), actual_table)
                    
                    # Check if column exists in this table
                    table_schema = self.schema[actual_table_name]
                    if col.lower() not in [c['name'].lower() for c in table_schema]:
                        missing_columns.append(f"{col} in {actual_table}")
                        error_messages.append(f"Column {col} not found in table {actual_table}")
            else:
                # Table alias not found - this is likely a syntax error
                # We'll skip this as it will be caught by the syntax check
                pass
        
        # Then check unqualified column references
        for col in column_refs:
            # Skip special cases like * or functions
            if col == '*' or col.lower() in ('count', 'sum', 'avg', 'min', 'max', 'distinct'):
                continue
                
            # Check if column exists in any table or CTE
            found = False
            
            # First check in tables referenced in the query
            for table_alias, actual_table in table_aliases.items():
                # Check if this is a CTE
                if actual_table in ctes:
                    cte_columns = ctes[actual_table]["columns"]
                    # Handle the special case where CTE returns '*'
                    if '*' in cte_columns:
                        found = True
                        break
                    if col.lower() in [c.lower() for c in cte_columns]:
                        found = True
                        break
                # Check if this is a real table
                elif actual_table.lower() in [t.lower() for t in self.schema.keys()]:
                    # Get the actual table name with correct case
                    actual_table_name = next((t for t in self.schema.keys() if t.lower() == actual_table.lower()), actual_table)
                    table_schema = self.schema[actual_table_name]
                    if col.lower() in [c['name'].lower() for c in table_schema]:
                        found = True
                        break
            
            # If not found in referenced tables, check all tables (less reliable)
            if not found:
                for table, columns in self.schema.items():
                    if col.lower() in [c['name'].lower() for c in columns]:
                        found = True
                        break
            
            # For BigQuery IMDB, check for camelCase vs. snake_case issues
            if not found and self.db_type == "bigquery_imdb":
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
                    'knownForTitles': 'known_for_titles',
                    'averageRating': 'average_rating',
                    'numVotes': 'num_votes'
                }
                
                if col in camel_to_underscore:
                    underscore_col = camel_to_underscore[col]
                    # Check if the underscore version exists in any table
                    for table_alias, actual_table in table_aliases.items():
                        if actual_table.lower() in [t.lower() for t in self.schema.keys()]:
                            actual_table_name = next((t for t in self.schema.keys() if t.lower() == actual_table.lower()), actual_table)
                            table_schema = self.schema[actual_table_name]
                            if underscore_col.lower() in [c['name'].lower() for c in table_schema]:
                                missing_columns.append(f"{col} (should be {underscore_col})")
                                error_messages.append(f"Column {col} should be {underscore_col}")
                                found = True  # Mark as found but still report the issue
                                break
            
            if not found:
                missing_columns.append(col)
        
        return missing_columns, incorrect_tables, error_messages
    
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
        elif self.db_path is not None:
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
        else:
            # For testing or when no database is available, perform basic syntax check
            # Check for common syntax errors
            if "SELECT" not in test_query.upper():
                return "Missing SELECT statement"
            if "FROM" not in test_query.upper():
                return "Missing FROM clause"
            if test_query.upper().count("FROM") > test_query.upper().count("SELECT"):
                return "Mismatched FROM clauses"
            if test_query.count("(") != test_query.count(")"):
                return "Mismatched parentheses"
            
            # Check for other common SQL syntax errors
            common_errors = [
                (r'\bSELECT\s+,', "Invalid SELECT syntax with leading comma"),
                (r',\s*FROM\b', "Invalid comma before FROM clause"),
                (r'\bFROM\s+,', "Invalid FROM syntax with comma"),
                (r'\bWHERE\s+OR\b', "Invalid WHERE clause starting with OR"),
                (r'\bWHERE\s+AND\b', "Invalid WHERE clause starting with AND"),
                (r'\bGROUP BY\s+,', "Invalid GROUP BY syntax with leading comma"),
                (r'\bORDER BY\s+,', "Invalid ORDER BY syntax with leading comma")
            ]
            
            for pattern, error_msg in common_errors:
                if re.search(pattern, test_query, re.IGNORECASE):
                    return error_msg
            
            return None
    
    def _check_bigquery_specific_issues(self, sql_query: str) -> Optional[str]:
        """
        Check for BigQuery IMDB specific issues.
        
        Args:
            sql_query: SQL query to check
            
        Returns:
            String describing BigQuery specific issues or None if no issues found
        """
        issues = []
        
        # Check for unqualified table references (missing `bigquery-public-data.imdb.`)
        # Look for FROM or JOIN followed by a table name without backticks or proper qualification
        unqualified_tables = re.finditer(r'(?:FROM|JOIN)\s+(?!`bigquery-public-data\.imdb\.)([a-zA-Z0-9_]+)(?!\s*AS|\s*ON|\s*WHERE|\s*GROUP|\s*ORDER|\s*LIMIT)', sql_query, re.IGNORECASE)
        
        for match in unqualified_tables:
            table = match.group(1)
            # Check if this is a valid table name in our schema
            if table.lower() in [t.lower() for t in self.schema.keys()]:
                issues.append(f"Table '{table}' should be fully qualified as `bigquery-public-data.imdb.{table}`")
        
        # Check for missing backticks around table references
        missing_backticks = re.finditer(r'(?:FROM|JOIN)\s+bigquery-public-data\.imdb\.([a-zA-Z0-9_]+)(?!\s*`)', sql_query, re.IGNORECASE)
        
        for match in missing_backticks:
            table = match.group(1)
            issues.append(f"Table 'bigquery-public-data.imdb.{table}' should be enclosed in backticks: `bigquery-public-data.imdb.{table}`")
        
        # Check for camelCase column names instead of snake_case
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
            'knownForTitles': 'known_for_titles',
            'averageRating': 'average_rating',
            'numVotes': 'num_votes'
        }
        
        for camel, underscore in camel_to_underscore.items():
            if re.search(r'\b' + camel + r'\b', sql_query):
                issues.append(f"Column '{camel}' should be '{underscore}' (use snake_case instead of camelCase)")
        
        # Check for semicolons at the end of the query (not needed in BigQuery)
        if sql_query.strip().endswith(';'):
            issues.append("Semicolons at the end of queries are not needed in BigQuery")
        
        # Check for improper CTE syntax
        # BigQuery requires commas between CTEs
        cte_pattern = r'\bWITH\b\s+([a-zA-Z0-9_]+\s+AS\s+\([^)]+\))\s+([a-zA-Z0-9_]+\s+AS\s+\()'
        if re.search(cte_pattern, sql_query, re.IGNORECASE | re.DOTALL):
            issues.append("Missing comma between CTE definitions. Use: WITH cte1 AS (...), cte2 AS (...)")
        
        # Check for proper JOIN syntax
        join_without_on = re.search(r'\bJOIN\b\s+(`[^`]+`|[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)\s+(?!ON|USING)', sql_query, re.IGNORECASE)
        if join_without_on:
            issues.append(f"JOIN must be followed by ON or USING clause: {join_without_on.group(0)}")
        
        return "; ".join(issues) if issues else None
    
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
        
        # Extract specific error details
        error_details = validation_result.get("error_details", {})
        
        # Check for column reference errors - these are the most common issues
        if "Missing or incorrect columns" in feedback:
            missing_columns = error_details.get("missing_columns", [])
            for col in missing_columns:
                # Try to suggest correct column names
                if col == "title" or col == "name":
                    suggestions.append(f"Column '{col}' not found. Use 'primary_{col}' instead in the appropriate table.")
                elif col.endswith("Name") or col.endswith("Title") or col.endswith("Year"):
                    # Convert camelCase to snake_case for BigQuery IMDB
                    snake_case = ''.join(['_'+c.lower() if c.isupper() else c for c in col]).lstrip('_')
                    suggestions.append(f"Column '{col}' not found. BigQuery IMDB uses snake_case: use '{snake_case}' instead.")
                else:
                    suggestions.append(f"Check that column '{col}' exists in the referenced table.")
            
            # Add general column reference guidance
            suggestions.append("Common column mappings in BigQuery IMDB schema:")
            suggestions.append("- For movie titles, use 'primary_title' in 'title_basics' table")
            suggestions.append("- For person names, use 'primary_name' in 'name_basics' table")
            suggestions.append("- For movie IDs, use 'tconst' (not 'id' or 'movie_id')")
            suggestions.append("- For person IDs, use 'nconst' (not 'id' or 'person_id')")
            
        # Check for table reference errors
        if "Missing or incorrect tables" in feedback:
            missing_tables = error_details.get("missing_tables", [])
            for table in missing_tables:
                # Try to suggest correct table names
                if table.lower() == "movies":
                    suggestions.append(f"Table '{table}' not found. Use 'title_basics' instead.")
                elif table.lower() == "actors" or table.lower() == "people":
                    suggestions.append(f"Table '{table}' not found. Use 'name_basics' instead.")
                elif table.lower() == "ratings":
                    suggestions.append(f"Table '{table}' not found. Use 'title_ratings' instead.")
                else:
                    suggestions.append(f"Check that table '{table}' exists in the database.")
            
            # Add general table reference guidance
            suggestions.append("Make sure to use the correct BigQuery IMDB table names:")
            suggestions.append("- 'title_basics' for movie/TV show information")
            suggestions.append("- 'name_basics' for person information")
            suggestions.append("- 'title_principals' for cast and crew connections")
            suggestions.append("- 'title_ratings' for ratings information")
            suggestions.append("- 'title_crew' for director and writer information")
        
        # Check for syntax issues
        if "Syntax issues" in feedback:
            syntax_errors = error_details.get("syntax_errors", [])
            for error in syntax_errors:
                suggestions.append(f"Syntax error: {error}")
            
            # Add general syntax guidance for BigQuery
            if self.db_type == "bigquery_imdb":
                suggestions.append("For BigQuery IMDB, remember to:")
                suggestions.append("- Fully qualify table names with backticks: `bigquery-public-data.imdb.table_name`")
                suggestions.append("- Use proper JOIN syntax with ON clauses")
                suggestions.append("- Avoid using semicolons at the end of queries")
        
        # Extract and correct column reference errors from error messages
        if "error_messages" in error_details:
            for error_msg in error_details.get("error_messages", []):
                corrected_query = self._extract_and_correct_column_errors(error_msg, sql_query)
                if corrected_query != sql_query:
                    suggestions.append(f"Based on the error message, try this correction:")
                    suggestions.append(f"```sql\n{corrected_query}\n```")
        
        if not suggestions:
            return feedback
            
        return feedback + "\n\nSuggested fixes:\n- " + "\n- ".join(suggestions)
    
    def _extract_and_correct_column_errors(self, error_message: str, sql_query: str) -> str:
        """
        Extract column reference errors and apply corrections.
        
        Args:
            error_message: Error message from validation
            sql_query: Original SQL query
            
        Returns:
            Corrected SQL query or original if no corrections applied
        """
        # Common patterns for BigQuery error messages
        column_error_pattern = r"Name ([a-zA-Z0-9_]+) not found inside ([a-zA-Z0-9_]+)"
        matches = re.findall(column_error_pattern, error_message)
        
        if not matches:
            return sql_query
        
        corrected_query = sql_query
        
        # Common correction mappings for IMDB schema
        column_corrections = {
            # Format: (table, wrong_column): correct_column
            ("title_principals", "title"): "title_basics.primary_title",
            ("title_principals", "primary_title"): "title_basics.primary_title",
            ("title_principals", "name"): "name_basics.primary_name",
            ("title_principals", "primary_name"): "name_basics.primary_name",
            ("title_crew", "name"): "name_basics.primary_name",
            ("title_crew", "primary_name"): "name_basics.primary_name",
            ("title_basics", "name"): "primary_title",
            ("name_basics", "title"): "primary_name",
            # Add camelCase to snake_case mappings
            ("title_basics", "primaryTitle"): "primary_title",
            ("title_basics", "originalTitle"): "original_title",
            ("title_basics", "startYear"): "start_year",
            ("title_basics", "endYear"): "end_year",
            ("title_basics", "runtimeMinutes"): "runtime_minutes",
            ("name_basics", "primaryName"): "primary_name",
            ("name_basics", "birthYear"): "birth_year",
            ("name_basics", "deathYear"): "death_year",
            ("title_principals", "titleId"): "tconst",
            ("title_principals", "personId"): "nconst"
        }
        
        for wrong_column, table in matches:
            correction_key = (table, wrong_column)
            
            if correction_key in column_corrections:
                # Get the correct column reference
                correct_column = column_corrections[correction_key]
                
                # Create regex pattern to find the incorrect reference
                pattern = r'\b' + re.escape(table) + r'\.' + re.escape(wrong_column) + r'\b'
                
                # Apply correction
                corrected_query = re.sub(pattern, correct_column, corrected_query)
        
        return corrected_query
