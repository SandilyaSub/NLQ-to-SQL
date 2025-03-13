"""
SQL Query Validator
This module provides functions to validate and correct SQL queries.
"""

import logging
import re

logger = logging.getLogger(__name__)

def validate_sql_query(query):
    """Validate SQL query for common column name mistakes.
    
    Args:
        query (str): The SQL query to validate
        
    Returns:
        str: The corrected SQL query
    """
    logger.info("Validating SQL query for common column name mistakes")
    
    # Define common mistakes with word boundary patterns to prevent partial matches
    corrections = [
        # (pattern to match, replacement) - using word boundaries to prevent partial matches
        (r'\bo\.order_status\b', 'o.status'),  # orders table alias
        (r'\border_status\b', 'status'),      # without table alias
        (r'\bsegment\b', 'customer_segment'),  # but not customer_segment
        (r'\bcustomer_state\b', 'state')      # customer_state to state
    ]
    
    # Don't modify these correct column names
    protected_columns = [
        'customer_segment',
        'status',
        'state'
    ]
    
    # First check if the query contains any of the protected column names
    # and temporarily replace them to prevent incorrect modifications
    original_query = query
    placeholder_map = {}
    
    for i, col in enumerate(protected_columns):
        placeholder = f"__PROTECTED_COL_{i}__"
        if col in query:
            query = query.replace(col, placeholder)
            placeholder_map[placeholder] = col
    
    # Apply corrections using regex with word boundaries
    import re
    for pattern, replacement in corrections:
        query = re.sub(pattern, replacement, query)
    
    # Restore protected columns
    for placeholder, original in placeholder_map.items():
        query = query.replace(placeholder, original)
    
    # Log changes if any were made
    if original_query != query:
        logger.info("SQL query was corrected during validation")
        logger.info(f"Original: {original_query}")
        logger.info(f"Corrected: {query}")
    
    if original_query != query:
        logger.info("SQL query was corrected during validation")
        logger.info(f"Original: {original_query}")
        logger.info(f"Corrected: {query}")
    
    return query
