#!/usr/bin/env python3
"""
Data Analyst Agent for NLQ to SQL

This module provides a data analyst agent that generates SQL queries from
natural language questions and refines them based on feedback.
"""

import logging
from typing import Dict, List, Any, Optional
from together import Together

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataAnalystAgent:
    """
    Agent responsible for generating SQL queries from natural language questions
    and refining them based on feedback.
    """
    
    def __init__(self, schema_rag, llm_client: Together):
        """
        Initialize the data analyst agent.
        
        Args:
            schema_rag: SchemaRAG instance for retrieving relevant schema
            llm_client: Together API client
        """
        self.schema_rag = schema_rag
        self.llm_client = llm_client
    
    def generate_sql(self, context: Dict[str, Any]) -> str:
        """
        Generate SQL based on question and previous feedback.
        
        Args:
            context: Dictionary containing question and optional feedback
            
        Returns:
            Generated SQL query or error message for nonsensical inputs
        """
        question = context["question"]
        feedback = context.get("feedback")
        iteration = context.get("iteration", 0)
        
        # Check for nonsensical input first
        if self._is_nonsensical_input(question):
            logger.warning(f"Rejected nonsensical input: '{question}'")
            return "ERROR: Your question appears to be nonsensical or too short. Please ask a clear, specific question about the database."
        
        # Simple check for vague questions
        is_vague = self._is_vague_question(question)
        
        # Get schema context
        relevant_chunks = self.schema_rag.retrieve_relevant_schema(question)
        schema_context = self.schema_rag.generate_schema_context(relevant_chunks)
        
        # Check if this is a complex query that needs decomposition
        is_complex = self._is_complex_query(question, schema_context)
        
        # Build prompt with feedback and vague question handling if needed
        prompt = self._build_prompt(question, schema_context, feedback, iteration, is_vague, is_complex)
        
        # Log the prompt for debugging
        logger.info(f"Prompt for iteration {iteration} (vague: {is_vague}, complex: {is_complex}):\n{prompt}")
        
        # Generate SQL
        response = self.llm_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {"role": "system", "content": "You are an expert SQL query generator with deep knowledge of database schema design. Always use the exact column names as provided in the schema. Pay special attention to table relationships and join conditions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500
        )
        
        sql_query = response.choices[0].message.content.strip()
        logger.info(f"Generated SQL for iteration {iteration} (raw):\n{sql_query}")
        
        # Clean up the SQL query
        sql_query = self._clean_sql_query(sql_query)
        logger.info(f"Cleaned SQL for iteration {iteration}:\n{sql_query}")
        
        return sql_query

    def _is_nonsensical_input(self, question: str) -> bool:
        """
        Check if a question is nonsensical using a validity scoring approach.
        
        Args:
            question: Natural language question
            
        Returns:
            True if the question is nonsensical, False otherwise
        """
        import re
        import os
        
        # Convert to lowercase for case-insensitive matching
        question_lower = question.lower().strip()
        
        # Initialize validity score
        validity_score = 0
        
        # Get database type from environment or default to retail
        db_type = os.environ.get("DB_TYPE", "retail")
        
        # --- POSITIVE SIGNALS (things that indicate a valid query) ---
        
        # 1. Contains database-specific entities
        entities = self._extract_entities(question_lower, db_type)
        if len(entities) > 0:
            validity_score += 3  # Strong signal of validity
            
        # 2. Contains common question words
        question_words = ['what', 'who', 'where', 'when', 'why', 'how', 'which', 'show', 'list', 'tell', 'find', 'get']
        has_question_words = any(word in question_lower for word in question_words)
        if has_question_words:
            validity_score += 2
            
        # 3. Contains query-specific patterns
        if self._has_query_patterns(question_lower):
            validity_score += 2
            
        # 4. Contains common English words (basic coherence)
        common_words = ['the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'from']
        has_common_words = any(word in question_lower for word in common_words)
        if has_common_words:
            validity_score += 1
            
        # 5. Has reasonable length (not too short)
        if len(question) > 15:
            validity_score += 1
            
        # --- NEGATIVE SIGNALS (things that indicate a nonsensical query) ---
        
        # 1. Very short with no meaningful content
        if len(question) < 10 and not (has_common_words or has_question_words):
            validity_score -= 2
            
        # 2. Repeating character patterns
        if re.search(r'(\w)\1{2,}', question_lower) or re.search(r'(\w{2,})\1+', question_lower):
            validity_score -= 3
            
        # 3. Random character sequences without spaces
        if len(question_lower) > 5 and ' ' not in question_lower and len(entities) == 0:
            validity_score -= 3
            
        # --- THRESHOLD DETERMINATION ---
        
        # Adjust threshold based on query length
        if len(question) < 15:
            # Short queries need stronger positive signals
            threshold = 3
        else:
            # Normal queries can have a lower threshold
            threshold = 2
            
        # Log the validity assessment
        logger.info(f"Query validity assessment: '{question}' - Score: {validity_score}, Threshold: {threshold}")
        logger.info(f"Validity factors: entities={len(entities)}, has_question_words={has_question_words}, " +
                   f"has_query_patterns={self._has_query_patterns(question_lower)}, has_common_words={has_common_words}")
        
        # Return True if the query is nonsensical (validity score below threshold)
        return validity_score < threshold
    
    def _has_query_patterns(self, question: str) -> bool:
        """
        Check if the question contains common query patterns.
        
        Args:
            question: Natural language question (lowercase)
            
        Returns:
            True if the question contains query patterns, False otherwise
        """
        import re
        
        # Common query patterns with regex
        patterns = [
            r'top \d+',  # "top 10", "top 25", etc.
            r'at least \d+',  # "at least 5000 votes"
            r'more than \d+',  # "more than 10 movies"
            r'less than \d+',  # "less than 90 minutes"
            r'between \d+ and \d+',  # "between 1990 and 2000"
            r'highest|lowest',  # "highest rating", "lowest budget"
            r'average|mean|median',  # "average rating"
            r'group by|grouped by',  # "grouped by genre"
            r'order by|sorted by',  # "ordered by year"
            r'most|least',  # "most popular", "least expensive"
            r'rated|rating|score',  # "rated R", "rating above 8"
            r'released|came out',  # "released in 1994"
            r'directed by|director',  # "directed by Spielberg"
            r'starring|actor|actress',  # "starring Tom Hanks"
            r'genre|category',  # "genre is action"
            r'budget|cost',  # "budget over $100 million"
            r'revenue|box office|gross',  # "revenue over $200 million"
            r'award|oscar|nomination',  # "won an Oscar"
            r'popular|successful',  # "most popular"
            r'recent|latest|newest',  # "most recent"
            r'old|oldest|earliest',  # "oldest movie"
            r'long|short|duration|runtime',  # "longest movie"
        ]
        
        # Check if any pattern matches
        for pattern in patterns:
            if re.search(pattern, question):
                return True
                
        # Check for specific database operations
        operations = [
            'count', 'sum', 'average', 'min', 'max', 'total',
            'list', 'show', 'find', 'display', 'return',
            'compare', 'rank', 'sort', 'order', 'filter',
            'group', 'categorize', 'classify', 'segment'
        ]
        
        for operation in operations:
            if operation in question.split():
                return True
                
        return False
    
    def _is_vague_question(self, question: str) -> bool:
        """
        Check if a question is vague or specific (but not nonsensical).
        
        Args:
            question: Natural language question
            
        Returns:
            True if the question is vague, False otherwise
        """
        import re
        
        # Convert to lowercase for case-insensitive matching
        question_lower = question.lower()
        
        # Check for very short questions (less than 15 characters)
        if len(question) < 15:
            return True
            
        # Very basic check for vague questions
        vague_indicators = [
            'what', 'show', 'list', 'tell', 'everything', 'all', 'data'
        ]
        
        # Check for vague indicators
        if any(indicator in question_lower for indicator in vague_indicators):
            # If it contains a vague indicator, check if it also contains a specific indicator
            specific_indicators = ['where', 'when', 'how many', 'which', 'who', 'top', 'most', 'least']
            if not any(indicator in question_lower for indicator in specific_indicators):
                return True
                
        return False
    
    def _clean_sql_query(self, sql_query: str) -> str:
        """
        Clean up the SQL query by removing markdown formatting and other artifacts.
        
        Args:
            sql_query: Raw SQL query from LLM
            
        Returns:
            Cleaned SQL query
        """
        # Remove markdown SQL code blocks (```sql ... ```)
        sql_query = sql_query.replace('```sql', '').replace('```', '')
        
        # Remove any leading/trailing backticks
        sql_query = sql_query.strip('`')
        
        # Remove any "SQL:" or "SQL Query:" prefixes
        sql_query = sql_query.replace('SQL:', '').replace('SQL Query:', '')
        
        # Strip extra whitespace
        sql_query = sql_query.strip()
        
        return sql_query
    
    def _build_prompt(self, question: str, schema_context: str, feedback: Optional[str] = None, 
                     iteration: int = 0, is_vague: bool = False, is_complex: bool = False) -> str:
        """
        Build prompt with schema context and feedback.
        
        Args:
            question: Natural language question
            schema_context: Database schema context
            feedback: Optional feedback from validation
            iteration: Current iteration number
            is_vague: Whether the question is vague
            is_complex: Whether the question is complex and needs decomposition
            
        Returns:
            Prompt for the LLM
        """
        import os
        
        # Get database type from environment or default to retail
        db_type = os.environ.get("DB_TYPE", "retail")
        
        prompt = f"""Given the following database schema and a natural language query, generate a valid SQL query.

**Schema**:
{schema_context}

**Instructions**:
- Use only the tables and columns from the schema above.
- Handle joins, aggregations, and conditions as needed.
- Return ONLY the SQL query, no explanations.
- Always use the exact column names as provided in the schema.
- Pay special attention to table relationships and join conditions.
- Avoid common column reference errors by double-checking column names.
- Ensure all columns referenced in SELECT, WHERE, GROUP BY, and JOIN clauses exist in the schema.
"""        

        # Add database-specific instructions
        if db_type == "bigquery_imdb":
            prompt += """
- This is a BigQuery database, so you MUST fully qualify table names with the project and dataset name 'bigquery-public-data.imdb'.
- For example, use '`bigquery-public-data.imdb.title_basics`' instead of just 'title_basics'.
- ALWAYS use backticks around the fully qualified table names: `bigquery-public-data.imdb.table_name`
- DO NOT use 'phonic-bivouac-272213' as the project ID - it must be 'bigquery-public-data'
- IMPORTANT: Column names in BigQuery IMDB use underscores, not camelCase. For example:
  * Use 'primary_name' (NOT 'primaryName')
  * Use 'title_type' (NOT 'titleType')
  * Use 'birth_year' (NOT 'birthYear')
  * Use 'primary_title' (NOT 'primaryTitle')
  * Use 'original_title' (NOT 'originalTitle')
  * Use 'is_adult' (NOT 'isAdult')
  * Use 'start_year' (NOT 'startYear')
  * Use 'end_year' (NOT 'endYear')
  * Use 'runtime_minutes' (NOT 'runtimeMinutes')
  * Use 'average_rating' (NOT 'averageRating')
  * Use 'num_votes' (NOT 'numVotes')

**IMDB Table Relationships**:
- The 'title_basics' table contains core information about movies and TV shows.
  * Use 'primary_title' for movie/show titles (NOT 'title' or 'name')
  * Use 'tconst' as the unique ID for movies/shows (NOT 'id' or 'movie_id')
- The 'name_basics' table contains information about people (actors, directors, etc.).
  * Use 'primary_name' for person names (NOT 'name')
  * Use 'nconst' as the unique ID for people (NOT 'id' or 'person_id')
- The 'title_ratings' table contains ratings information linked to titles via 'tconst'.
  * Use 'average_rating' for the rating value (NOT 'averageRating' or 'rating')
  * Use 'num_votes' for the vote count (NOT 'numVotes' or 'votes')
- The 'title_crew' table links directors and writers to titles via 'tconst'.
- The 'title_principals' table links cast and crew to titles via 'tconst' and to people via 'nconst'.
  * The 'category' column indicates the role (actor, actress, director, etc.)
- The 'title_episode' table contains TV episode information linked to series via 'parent_tconst'.
- The 'title_akas' table contains alternative titles linked to the main title via 'title_id'.

**Common Join Patterns**:
- To join movies with their ratings:
  `bigquery-public-data.imdb.title_basics` tb JOIN `bigquery-public-data.imdb.title_ratings` tr ON tb.tconst = tr.tconst
- To join movies with their cast:
  `bigquery-public-data.imdb.title_basics` tb JOIN `bigquery-public-data.imdb.title_principals` tp ON tb.tconst = tp.tconst
- To join cast with person details:
  `bigquery-public-data.imdb.title_principals` tp JOIN `bigquery-public-data.imdb.name_basics` nb ON tp.nconst = nb.nconst
- To join movies with their directors:
  `bigquery-public-data.imdb.title_basics` tb JOIN `bigquery-public-data.imdb.title_crew` tc ON tb.tconst = tc.tconst

- DO NOT include semicolons at the end of your SQL queries.
"""
        elif db_type == "retail":
            prompt += """
- The 'orders' table has 'status' column (not order_status) for order status values.
- The 'customers' table has 'customer_segment' column (not segment).
- The 'customers' table has 'state' column (not customer_state).
"""
        else:
            prompt += """
- The 'title_basics' table contains core information about movies and TV shows.
- The 'name_basics' table contains information about people (actors, directors, etc.).
- The 'title_ratings' table contains ratings information linked to titles via 'tconst'.
- The 'title_crew' table links directors and writers to titles via 'tconst'.
- The 'title_principals' table links cast and crew to titles via 'tconst' and to people via 'nconst'.
- The 'title_episode' table contains TV episode information linked to series via 'parentTconst'.
- The 'title_akas' table contains alternative titles linked to the main title via 'titleId'.
- When joining tables, remember that 'tconst' is the primary key for titles and 'nconst' is the primary key for people.
"""

        # Add query decomposition instructions for complex queries
        if is_complex:
            prompt += """
**Complex Query Decomposition**:
This is a complex query that requires multiple operations. Follow these steps:

1. First identify all entities and conditions in the query:
   - List all tables that will be needed
   - Identify all filtering conditions
   - Note any aggregations or calculations required
   - Determine the final sorting or limiting requirements

2. Break the problem into smaller sub-problems:
   - Start with the core entities and their relationships
   - Add filtering conditions one by one
   - Build up aggregations as needed
   - Apply final sorting and limiting

3. Solve each sub-problem with a Common Table Expression (CTE):
   - Use WITH clauses to create intermediate result sets
   - Name each CTE clearly based on its purpose
   - Keep each CTE focused on a single aspect of the problem

4. Combine the CTEs to form the final query:
   - Join the CTEs as needed in the final SELECT
   - Apply any final filtering, grouping, or sorting
   - Ensure the final query returns exactly what was asked for

Example structure for a complex query:
```
WITH filtered_movies AS (
  SELECT * FROM `bigquery-public-data.imdb.title_basics`
  WHERE condition1 AND condition2
),
director_movies AS (
  SELECT ... FROM filtered_movies
  JOIN ... ON ...
  WHERE ...
),
final_results AS (
  SELECT ... FROM director_movies
  GROUP BY ...
  HAVING ...
)
SELECT * FROM final_results
ORDER BY ... LIMIT ...
```
"""

        # Add special instructions for vague questions
        if is_vague:
            # Check if the question seems nonsensical
            common_words = ['the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'from']
            question_words = ['what', 'who', 'where', 'when', 'why', 'how', 'which', 'show', 'list', 'tell', 'find', 'get']
            
            has_common_words = any(word in question.lower() for word in common_words)
            has_question_words = any(word in question.lower() for word in question_words)
            
            if len(question) < 10 and not (has_common_words or has_question_words):
                prompt += """
**Handling Nonsensical Input**:
- The input appears to be nonsensical or random text.
- For such inputs, generate a simple exploratory query like 'SELECT * FROM products LIMIT 5'.
- Include a LIMIT clause to avoid returning too much data for random inputs.
"""
            else:
                prompt += """
**Handling Vague Questions**:
- This appears to be a vague or exploratory question.
- For vague questions, it's acceptable to generate a simple exploratory query.
- If the question is very general, you can return 'SELECT * FROM [most_relevant_table] LIMIT 10'.
- Do not apologize for the query being general if the question itself is general.
"""

        if feedback and iteration > 0:
            prompt += f"""
**Previous Attempt Issues (Iteration {iteration})**:
{feedback}

**How to Fix Common Column Reference Errors**:
- If you see "Missing or incorrect columns", double-check the column names in the schema.
- If you see "Column 'X' not found", make sure you're using the correct table prefix.
- For BigQuery IMDB, remember to use snake_case (primary_title) not camelCase (primaryTitle).
- For movie titles, use 'primary_title' in 'title_basics' table, not just 'title'.
- For person names, use 'primary_name' in 'name_basics' table, not just 'name'.
- For movie IDs, use 'tconst', not 'id' or 'movie_id'.
- For person IDs, use 'nconst', not 'id' or 'person_id'.

Please fix these issues in your SQL query.
"""

        prompt += f"""
**Query**: {question}

Generate only the SQL query without any explanation. The query should be valid SQLite syntax.
SQL Query:"""

        return prompt

    def _is_complex_query(self, question: str, schema_context: str) -> bool:
        """
        Determine if a question requires complex query decomposition.
        
        Args:
            question: Natural language question
            schema_context: Database schema context
            
        Returns:
            True if the question is complex, False otherwise
        """
        import re
        import os
        
        # Convert to lowercase for case-insensitive matching
        question_lower = question.lower().strip()
        
        # Get database type from environment or default to retail
        db_type = os.environ.get("DB_TYPE", "retail")
        
        # 1. Check for multiple entities requiring joins
        entities = self._extract_entities(question_lower, db_type)
        tables_needed = len(entities)
        
        # 2. Count filtering conditions (look for words that indicate conditions)
        condition_indicators = ['where', 'greater than', 'less than', 'equal to', 'more than', 
                               'at least', 'maximum', 'minimum', 'highest', 'lowest', 'top', 
                               'bottom', 'between', 'over', 'under', 'above', 'below']
        condition_count = sum(1 for indicator in condition_indicators if indicator in question_lower)
        
        # 3. Detect aggregations and grouping
        aggregation_keywords = ['average', 'avg', 'sum', 'count', 'total', 'mean', 'median', 
                               'maximum', 'minimum', 'max', 'min', 'group by', 'having']
        has_aggregation = any(keyword in question_lower for keyword in aggregation_keywords)
        
        # 4. Check for nested conditions
        nested_indicators = ['and', 'or', 'not', 'but', 'except', 'excluding', 'including', 
                            'with', 'without', 'who', 'that', 'which']
        nested_condition_count = sum(1 for indicator in nested_indicators if indicator in question_lower)
        
        # 5. Check for complex sorting or ranking
        ranking_indicators = ['order by', 'sort by', 'rank', 'top', 'best', 'worst', 'highest', 
                             'lowest', 'most', 'least', 'popular', 'rated', 'reviewed']
        has_ranking = any(indicator in question_lower for indicator in ranking_indicators)
        
        # Determine complexity based on heuristics
        is_complex = (
            (tables_needed >= 3) or  # Needs 3+ tables
            (condition_count >= 2) or  # Has 2+ filtering conditions
            (nested_condition_count >= 2) or  # Has 2+ nested conditions
            (has_aggregation and has_ranking) or  # Combines aggregation with ranking
            (len(question.split()) >= 15 and has_aggregation)  # Long question with aggregation
        )
        
        if is_complex:
            logger.info(f"Classified as COMPLEX query: '{question}'")
            logger.info(f"Complexity factors: tables={tables_needed}, conditions={condition_count}, " +
                       f"nested={nested_condition_count}, aggregation={has_aggregation}, ranking={has_ranking}")
        else:
            logger.info(f"Classified as SIMPLE query: '{question}'")
        
        return is_complex
    
    def _extract_entities(self, question: str, db_type: str) -> List[str]:
        """
        Extract database entities mentioned in the question.
        
        Args:
            question: Natural language question
            db_type: Type of database (retail, bigquery_imdb)
            
        Returns:
            List of entity names found in the question
        """
        entities = []
        
        if db_type == "bigquery_imdb":
            # IMDB database entities
            entity_mapping = {
                'movie': 'title_basics',
                'film': 'title_basics',
                'show': 'title_basics',
                'series': 'title_basics',
                'episode': 'title_episode',
                'actor': 'name_basics',
                'actress': 'name_basics',
                'director': 'name_basics',
                'writer': 'name_basics',
                'person': 'name_basics',
                'cast': 'title_principals',
                'crew': 'title_principals',
                'rating': 'title_ratings',
                'vote': 'title_ratings',
                'genre': 'title_basics',
                'title': 'title_basics',
                'name': 'name_basics',
                'aka': 'title_akas',
                'alternative': 'title_akas'
            }
        elif db_type == "retail":
            # Retail database entities
            entity_mapping = {
                'order': 'orders',
                'customer': 'customers',
                'product': 'products',
                'category': 'product_categories',
                'sale': 'orders',
                'purchase': 'orders',
                'return': 'returns',
                'inventory': 'inventory'
            }
        else:
            # Default mapping
            entity_mapping = {}
        
        # Check for entity mentions in the question
        for keyword, table in entity_mapping.items():
            if keyword in question:
                if table not in entities:
                    entities.append(table)
        
        return entities
