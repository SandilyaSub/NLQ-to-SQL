"""
RAG Utilities for NLQ to SQL Converter

This module provides utilities for implementing a Retrieval-Augmented Generation (RAG)
approach to optimize the NLQ to SQL conversion process.
"""

import json
import numpy as np
import sqlite3
import logging
from typing import List, Dict, Any, Tuple
from together import Together

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SchemaRAG:
    """
    Implements a Retrieval-Augmented Generation system for database schema information.
    """
    
    def __init__(self, together_client: Together, db_path=None, embedding_model: str = "togethercomputer/m2-bert-80M-8k-retrieval", db_type: str = "retail"):
        """
        Initialize the SchemaRAG system.
        
        Args:
            together_client: Initialized Together API client
            db_path: Path to the SQLite database (can be None for BigQuery)
            embedding_model: Name of the embedding model to use
            db_type: Type of database (retail, movie, or bigquery_imdb)
        """
        self.together_client = together_client
        self.db_path = db_path
        self.embedding_model = embedding_model
        self.db_type = db_type
        self.schema_chunks = []
        self.chunk_embeddings = []
        self.table_relationships = {}
        self.initialized = False
        
    def initialize(self):
        """
        Initialize the RAG system by extracting schema and creating embeddings.
        """
        if self.initialized:
            return
            
        logger.info("Initializing SchemaRAG system...")
        
        # Extract schema from database
        schema = self._extract_schema()
        
        # Create schema chunks and embeddings
        self._create_schema_embeddings(schema)
        
        # Extract table relationships
        self._extract_table_relationships(schema)
        
        self.initialized = True
        logger.info(f"SchemaRAG initialized with {len(self.schema_chunks)} schema chunks")
        
    def _extract_schema(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract schema information from the database.
        
        Returns:
            Dictionary mapping table names to column information
        """
        schema = {}
        
        # Handle BigQuery IMDB database type
        if self.db_type == "bigquery_imdb":
            logger.info("Using BigQuery IMDB schema")
            try:
                # Load the schema from the JSON file
                with open("imdb_bigquery_schema.json", 'r') as f:
                    schema_data = json.load(f)
                
                # Create schema dictionary from JSON file
                for table_name, table_info in schema_data["tables"].items():
                    schema[table_name] = table_info["columns"]
                
                # Create chunks for each table
                for table_name, table_info in schema_data["tables"].items():
                    # Table-level chunk
                    table_description = table_info.get("description", f"Table {table_name}")
                    columns_text = ", ".join([f"{col['name']} ({col['type']}): {col['description']}" 
                                            for col in table_info["columns"]])
                    
                    table_chunk = f"Table: {table_name}\nDescription: {table_description}\nColumns: {columns_text}"
                    self.schema_chunks.append({
                        "content": table_chunk,
                        "type": "table",
                        "table": table_name
                    })
                    
                    # Column-level chunks
                    for column in table_info["columns"]:
                        column_chunk = f"Table: {table_name}, Column: {column['name']}\nType: {column['type']}\nDescription: {column['description']}"
                        self.schema_chunks.append({
                            "content": column_chunk,
                            "type": "column",
                            "table": table_name,
                            "column": column['name']
                        })
                
                # Add relationships chunk
                if "relationships" in schema_data and schema_data["relationships"]:
                    relationships_text = "\n".join([
                        f"{rel['table1']}.{rel['column1']} → {rel['table2']}.{rel['column2']}"
                        for rel in schema_data["relationships"]
                    ])
                    self.schema_chunks.append({
                        "content": f"Table Relationships:\n{relationships_text}",
                        "type": "relationships"
                    })
                
                # Add overall database chunk
                tables_summary = ", ".join(schema_data["tables"].keys())
                self.schema_chunks.append({
                    "content": f"Database: IMDB BigQuery\nTables: {tables_summary}\nThis is the Internet Movie Database (IMDB) containing information about movies, TV shows, actors, directors, and other related data.",
                    "type": "database"
                })
                
                logger.info(f"Created {len(self.schema_chunks)} schema chunks for BigQuery IMDB")
                
                return schema
            except Exception as e:
                logger.error(f"Error loading BigQuery IMDB schema: {e}")
                raise
        
        # Handle retail database type
        elif self.db_type == "retail":
            tables = ["categories", "products", "customers", "orders", "order_items"]
            
            # Connect to SQLite database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Detailed schema information with descriptions
            detailed_schema = {
            "categories": [
                {"name": "category_id", "type": "INTEGER", "description": "A unique identifier for each product category. Primary key for the categories table."},
                {"name": "category_name", "type": "TEXT", "description": "The name of the category (e.g., 'Electronics', 'Clothing')."},
                {"name": "description", "type": "TEXT", "description": "A brief explanation of what the category includes or represents."},
                {"name": "parent_category_id", "type": "REAL", "description": "The ID of the parent category if this is a subcategory (e.g., 'Laptops' under 'Electronics'). Can be null if it's a top-level category."}
            ],
            "products": [
                {"name": "product_id", "type": "INTEGER", "description": "A unique identifier for each product. Primary key for the products table."},
                {"name": "product_name", "type": "TEXT", "description": "The name of the product (e.g., 'Wireless Mouse', 'T-shirt')."},
                {"name": "category_id", "type": "INTEGER", "description": "The ID of the category this product belongs to, linking to the categories table."},
                {"name": "price", "type": "REAL", "description": "The selling price of the product in the local currency (e.g., 29.99)."},
                {"name": "cost", "type": "REAL", "description": "The cost to the business to acquire or produce the product (e.g., 15.50)."},
                {"name": "stock_quantity", "type": "INTEGER", "description": "The number of units currently available in inventory."},
                {"name": "description", "type": "TEXT", "description": "A detailed description of the product (e.g., features, materials, or usage)."},
                {"name": "weight_kg", "type": "REAL", "description": "The weight of the product in kilograms (e.g., 0.25 for a lightweight item)."},
                {"name": "dimensions_cm", "type": "TEXT", "description": "The dimensions of the product in centimeters, typically in 'L x W x H' format (e.g., '10 x 5 x 2')."},
                {"name": "is_active", "type": "INTEGER", "description": "A flag indicating if the product is currently available for sale (1 = active, 0 = inactive)."}
            ],
            "customers": [
                {"name": "customer_id", "type": "INTEGER", "description": "A unique identifier for each customer. Primary key for the customers table."},
                {"name": "first_name", "type": "TEXT", "description": "The customer's first name (e.g., 'John')."},
                {"name": "last_name", "type": "TEXT", "description": "The customer's last name (e.g., 'Smith')."},
                {"name": "email", "type": "TEXT", "description": "The customer's email address (e.g., 'john.smith@example.com')."},
                {"name": "phone", "type": "TEXT", "description": "The customer's phone number (e.g., '+1-555-123-4567')."},
                {"name": "address", "type": "TEXT", "description": "The street address of the customer (e.g., '123 Main St')."},
                {"name": "city", "type": "TEXT", "description": "The city where the customer resides (e.g., 'New York')."},
                {"name": "state", "type": "TEXT", "description": "The state or region of the customer's address (e.g., 'NY')."},
                {"name": "zip_code", "type": "INTEGER", "description": "The postal code for the customer's address (e.g., 10001)."},
                {"name": "registration_date", "type": "TEXT", "description": "The date the customer registered, stored as text (e.g., '2023-01-15')."},
                {"name": "customer_segment", "type": "TEXT", "description": "A classification of the customer (e.g., 'VIP', 'Regular', 'New')."}
            ],
            "orders": [
                {"name": "order_id", "type": "INTEGER", "description": "A unique identifier for each order. Primary key for the orders table."},
                {"name": "customer_id", "type": "INTEGER", "description": "The ID of the customer who placed the order, linking to the customers table."},
                {"name": "order_date", "type": "TEXT", "description": "The date and time the order was placed, stored as text (e.g., '2023-03-08 14:30:00')."},
                {"name": "status", "type": "TEXT", "description": "The current status of the order (e.g., 'Pending', 'Shipped', 'Delivered', 'Cancelled')."},
                {"name": "payment_method", "type": "TEXT", "description": "The method used to pay for the order (e.g., 'Credit Card', 'PayPal', 'Cash on Delivery')."},
                {"name": "shipping_address", "type": "TEXT", "description": "The street address where the order will be shipped (e.g., '456 Oak St')."},
                {"name": "shipping_city", "type": "TEXT", "description": "The city for the shipping address (e.g., 'Boston')."},
                {"name": "shipping_state", "type": "TEXT", "description": "The state or region for the shipping address (e.g., 'MA')."},
                {"name": "shipping_zip", "type": "INTEGER", "description": "The postal code for the shipping address (e.g., 02108)."},
                {"name": "shipping_cost", "type": "REAL", "description": "The cost of shipping the order in the local currency (e.g., 5.99)."}
            ],
            "order_items": [
                {"name": "order_item_id", "type": "INTEGER", "description": "A unique identifier for each item within an order. Primary key for the order_items table."},
                {"name": "order_id", "type": "INTEGER", "description": "The ID of the order this item belongs to, linking to the orders table."},
                {"name": "product_id", "type": "INTEGER", "description": "The ID of the product being ordered, linking to the products table."},
                {"name": "quantity", "type": "INTEGER", "description": "The number of units of this product in the order (e.g., 2 for two items)."},
                {"name": "price", "type": "REAL", "description": "The price per unit of the product at the time of the order (e.g., 19.99)."},
                {"name": "discount", "type": "REAL", "description": "The discount applied to this item, if any, in the local currency (e.g., 2.00). Can be null."},
                {"name": "total", "type": "REAL", "description": "The total cost for this item after applying quantity and discount (e.g., 37.98)."}
            ]
        }
        elif self.db_type == "movie":
            tables = ["name_basics", "title_basics", "title_ratings", "title_crew", 
                     "title_episode", "title_principals", "title_akas"]
            
            # Detailed schema information for movie database
            detailed_schema = {
                "name_basics": [
                    {"name": "nconst", "type": "TEXT", "description": "Alphanumeric unique identifier for each person. Primary key for the name_basics table."},
                    {"name": "primaryName", "type": "TEXT", "description": "Name by which the person is most often credited in films and TV shows."},
                    {"name": "birthYear", "type": "INTEGER", "description": "Year of birth in YYYY format."},
                    {"name": "deathYear", "type": "INTEGER", "description": "Year of death in YYYY format if applicable, NULL if still alive."},
                    {"name": "primaryProfession", "type": "TEXT", "description": "The top-3 professions of the person as a comma-separated list (e.g., 'actor,director,producer')."},
                    {"name": "knownForTitles", "type": "TEXT", "description": "Titles the person is known for as a comma-separated list of tconst identifiers."}
                ],
                "title_basics": [
                    {"name": "tconst", "type": "TEXT", "description": "Alphanumeric unique identifier of the title. Primary key for the title_basics table."},
                    {"name": "titleType", "type": "TEXT", "description": "The type/format of the title (e.g. movie, short, tvseries, tvepisode, video, etc)."},
                    {"name": "primaryTitle", "type": "TEXT", "description": "The more popular title / the title used by the filmmakers on promotional materials at the point of release."},
                    {"name": "originalTitle", "type": "TEXT", "description": "Original title, in the original language."},
                    {"name": "isAdult", "type": "INTEGER", "description": "Boolean flag: 0 for non-adult title; 1 for adult title."},
                    {"name": "startYear", "type": "INTEGER", "description": "Represents the release year of a title. In the case of TV Series, it is the series start year."},
                    {"name": "endYear", "type": "INTEGER", "description": "TV Series end year. NULL for all other title types."},
                    {"name": "runtimeMinutes", "type": "INTEGER", "description": "Primary runtime of the title, in minutes."},
                    {"name": "genres", "type": "TEXT", "description": "Includes up to three genres associated with the title as a comma-separated list."}
                ],
                "title_ratings": [
                    {"name": "tconst", "type": "TEXT", "description": "Alphanumeric unique identifier of the title, foreign key to title_basics."},
                    {"name": "averageRating", "type": "REAL", "description": "Weighted average of all the individual user ratings."},
                    {"name": "numVotes", "type": "INTEGER", "description": "Number of votes the title has received."}
                ],
                "title_crew": [
                    {"name": "tconst", "type": "TEXT", "description": "Alphanumeric unique identifier of the title, foreign key to title_basics."},
                    {"name": "directors", "type": "TEXT", "description": "Director(s) of the given title as a comma-separated list of nconst identifiers."},
                    {"name": "writers", "type": "TEXT", "description": "Writer(s) of the given title as a comma-separated list of nconst identifiers."}
                ],
                "title_episode": [
                    {"name": "tconst", "type": "TEXT", "description": "Alphanumeric identifier of episode, foreign key to title_basics."},
                    {"name": "parentTconst", "type": "TEXT", "description": "Alphanumeric identifier of the parent TV Series, foreign key to title_basics."},
                    {"name": "seasonNumber", "type": "INTEGER", "description": "Season number the episode belongs to."},
                    {"name": "episodeNumber", "type": "INTEGER", "description": "Episode number of the tconst in the TV series."}
                ],
                "title_principals": [
                    {"name": "tconst", "type": "TEXT", "description": "Alphanumeric unique identifier of the title, foreign key to title_basics."},
                    {"name": "ordering", "type": "INTEGER", "description": "A number to uniquely identify rows for a given titleId."},
                    {"name": "nconst", "type": "TEXT", "description": "Alphanumeric unique identifier of the name/person, foreign key to name_basics."},
                    {"name": "category", "type": "TEXT", "description": "The category of job that person was in (e.g., actor, director)."},
                    {"name": "job", "type": "TEXT", "description": "The specific job title if applicable, NULL otherwise."},
                    {"name": "characters", "type": "TEXT", "description": "The name of the character played if applicable, NULL otherwise."}
                ],
                "title_akas": [
                    {"name": "titleId", "type": "TEXT", "description": "Alphanumeric unique identifier of the title, foreign key to title_basics."},
                    {"name": "ordering", "type": "INTEGER", "description": "A number to uniquely identify rows for a given titleId."},
                    {"name": "title", "type": "TEXT", "description": "The localized title."},
                    {"name": "region", "type": "TEXT", "description": "The region for this version of the title."},
                    {"name": "language", "type": "TEXT", "description": "The language of the title."},
                    {"name": "types", "type": "TEXT", "description": "Enumerated set of attributes for this alternative title as a comma-separated list."},
                    {"name": "attributes", "type": "TEXT", "description": "Additional terms to describe this alternative title, not enumerated."},
                    {"name": "isOriginalTitle", "type": "INTEGER", "description": "Boolean flag: 0 for not original title; 1 for original title."}
                ]
            }
        
        for table in tables:
            # Use the detailed schema information instead of querying the database
            if table in detailed_schema:
                schema[table] = detailed_schema[table]
            else:
                # Fallback to database query if table not in detailed schema
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                schema[table] = [{"name": col[1], "type": col[2]} for col in columns]
                
                # Try to get sample data for better descriptions
                try:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 5")
                    sample_data = cursor.fetchall()
                    if sample_data:
                        # Add sample values to the schema
                        for i, col in enumerate(schema[table]):
                            sample_values = [row[i] for row in sample_data if row[i] is not None]
                            if sample_values:
                                col["sample"] = sample_values[:3]  # Include up to 3 sample values
                except Exception as e:
                    logger.warning(f"Error getting sample data for {table}: {e}")
        
        conn.close()
        return schema
        
    def _create_schema_embeddings(self, schema: Dict[str, List[Dict[str, Any]]]):
        """
        Create embeddings for schema chunks.
        
        Args:
            schema: Dictionary mapping table names to column information
        """
        # Create chunks at different granularities
        
        # 1. Table-level chunks
        for table_name, columns in schema.items():
            if not table_name.endswith("_sample"):
                # Create a chunk for the table with its columns
                column_descriptions = []
                for col in columns:
                    # Add detailed column description with emphasis on exact column name
                    description = col.get('description', '')
                    col_desc = f"{col['name']} ({col['type']}) - {description} The exact column name is '{col['name']}'"
                    column_descriptions.append(col_desc)
                
                chunk_text = f"Table: {table_name}\nColumns:\n- " + "\n- ".join(column_descriptions)
                
                # Add sample data if available
                sample_key = f"{table_name}_sample"
                if sample_key in schema:
                    sample_str = json.dumps(schema[sample_key][:2], indent=2)
                    chunk_text += f"\nSample data: {sample_str}"
                
                self.schema_chunks.append({
                    "type": "table",
                    "table": table_name,
                    "text": chunk_text,
                    "columns": columns
                })
        
        # 2. Column-level chunks for more specific retrieval
        for table_name, columns in schema.items():
            if not table_name.endswith("_sample"):
                for column in columns:
                    # Enhanced column description with emphasis on exact column name and usage
                    description = column.get('description', '')
                    chunk_text = f"Column: {column['name']} in table {table_name}\nType: {column['type']}\n"
                    chunk_text += f"Description: {description}\n"
                    chunk_text += f"IMPORTANT: The exact column name is '{column['name']}'. When referencing this column in SQL, use {table_name}.{column['name']} or alias.{column['name']}.\n"
                    
                    # Add sample values if available
                    sample_key = f"{table_name}_sample"
                    if sample_key in schema:
                        sample_values = [str(row.get(column['name'], '')) for row in schema[sample_key][:2]]
                        chunk_text += f"Sample values: {', '.join(sample_values)}\n"
                        
                    # Add usage examples
                    chunk_text += f"Example SQL usage:\n"
                    chunk_text += f"- SELECT {column['name']} FROM {table_name}\n"
                    chunk_text += f"- SELECT t.{column['name']} FROM {table_name} t\n"
                    
                    self.schema_chunks.append({
                        "type": "column",
                        "table": table_name,
                        "column": column['name'],
                        "text": chunk_text
                    })
        
        # 3. Create a chunk for the overall database schema
        all_tables = [table for table in schema.keys() if not table.endswith("_sample")]
        overall_schema_text = f"Database contains tables: {', '.join(all_tables)}"
        self.schema_chunks.append({
            "type": "database",
            "text": overall_schema_text
        })
        
        # Generate embeddings for all chunks
        logger.info(f"Generating embeddings for {len(self.schema_chunks)} schema chunks...")
        
        chunk_texts = []
        for chunk in self.schema_chunks:
            if "content" in chunk:
                chunk_texts.append(chunk["content"])
            elif "text" in chunk:
                chunk_texts.append(chunk["text"])
            else:
                logger.warning(f"Schema chunk missing both 'content' and 'text' keys: {chunk}")
                chunk_texts.append("")  # Add empty string as fallback
        
        # Generate embeddings in batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[i:i+batch_size]
            try:
                response = self.together_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                batch_embeddings = [data.embedding for data in response.data]
                self.chunk_embeddings.extend(batch_embeddings)
                logger.info(f"Generated embeddings for chunks {i} to {i+len(batch)-1}")
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i}: {str(e)}")
                # Add empty embeddings as placeholders
                self.chunk_embeddings.extend([[0] * 768] * len(batch))
    
    def _extract_table_relationships(self, schema: Dict[str, List[Dict[str, Any]]]):
        """
        Extract relationships between tables based on common column names.
        
        Args:
            schema: Dictionary mapping table names to column information
        """
        if self.db_type == "retail":
            # Simple heuristic for retail database: Look for columns that could be foreign keys
            for table1, columns1 in schema.items():
                if table1.endswith("_sample"):
                    continue
                    
                self.table_relationships[table1] = []
                
                for table2, columns2 in schema.items():
                    if table2.endswith("_sample") or table1 == table2:
                        continue
                    
                    # Check for potential foreign key relationships
                    for col1 in columns1:
                        if not isinstance(col1, dict):
                            continue
                            
                        col1_name = col1.get('name', '')
                        
                        # Check if this column might be a foreign key to table2
                        if col1_name == f"{table2[:-1]}_id" or col1_name == f"{table2}_id":
                            self.table_relationships[table1].append({
                                "related_table": table2,
                                "from_column": col1_name,
                                "to_column": "id" if "id" in [col['name'] for col in columns2 if isinstance(col, dict)] else f"{table2[:-1]}_id"
                            })
        elif self.db_type == "movie":
            # Define explicit relationships for movie database
            self.table_relationships = {
                "title_ratings": [{
                    "related_table": "title_basics",
                    "from_column": "tconst",
                    "to_column": "tconst"
                }],
                "title_crew": [{
                    "related_table": "title_basics",
                    "from_column": "tconst",
                    "to_column": "tconst"
                }],
                "title_episode": [{
                    "related_table": "title_basics",
                    "from_column": "tconst",
                    "to_column": "tconst"
                }, {
                    "related_table": "title_basics",
                    "from_column": "parentTconst",
                    "to_column": "tconst"
                }],
                "title_principals": [{
                    "related_table": "title_basics",
                    "from_column": "tconst",
                    "to_column": "tconst"
                }, {
                    "related_table": "name_basics",
                    "from_column": "nconst",
                    "to_column": "nconst"
                }],
                "title_akas": [{
                    "related_table": "title_basics",
                    "from_column": "titleId",
                    "to_column": "tconst"
                }]
            }
    
    def get_embeddings(self, text: str) -> List[float]:
        """
        Get embeddings for a text using the Together API.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = self.together_client.embeddings.create(
                model=self.embedding_model,
                input=[text]
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embeddings: {str(e)}")
            return [0] * 768  # Return zero vector as fallback
    
    def retrieve_relevant_schema(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant schema chunks for a query.
        
        Args:
            query: Natural language query
            top_k: Number of top chunks to retrieve
            
        Returns:
            List of relevant schema chunks
        """
        if not self.initialized:
            self.initialize()
            
        logger.info(f"Retrieving relevant schema for query: {query}")
        
        # Get query embedding
        query_embedding = self.get_embeddings(query)
        
        # Calculate similarity scores
        similarities = []
        for embedding in self.chunk_embeddings:
            # Cosine similarity
            dot_product = np.dot(query_embedding, embedding)
            norm_product = np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
            similarity = dot_product / norm_product if norm_product != 0 else 0
            similarities.append(similarity)
        
        # Get top-k most relevant chunks
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        relevant_chunks = [self.schema_chunks[i] for i in top_indices]
        
        # Log the retrieved chunks
        logger.info(f"Retrieved {len(relevant_chunks)} relevant schema chunks")
        for i, chunk in enumerate(relevant_chunks):
            logger.info(f"Chunk {i+1}: {chunk.get('type', 'unknown')} - {chunk.get('table', '')} {chunk.get('column', '')}")
        
        return relevant_chunks
    
    def generate_schema_context(self, relevant_chunks: List[Dict[str, Any]]) -> str:
        """
        Generate schema context from relevant chunks for inclusion in the prompt.
        
        Args:
            relevant_chunks: List of relevant schema chunks
            
        Returns:
            Schema context as a string
        """
        # Extract unique tables from the chunks
        tables = set()
        columns = {}
        
        for chunk in relevant_chunks:
            if chunk.get("type") == "table":
                tables.add(chunk.get("table"))
                if "columns" in chunk:
                    columns[chunk.get("table")] = chunk.get("columns")
            elif chunk.get("type") == "column":
                tables.add(chunk.get("table"))
        
        # Add related tables based on relationships
        related_tables = set()
        for table in tables:
            if table in self.table_relationships:
                for relation in self.table_relationships[table]:
                    related_tables.add(relation["related_table"])
        
        # Combine all tables
        all_tables = tables.union(related_tables)
        
        # Generate context
        context = "Database Schema:\n"
        
        for table in all_tables:
            context += f"Table: {table}\n"
            if table in columns:
                context += "Columns:\n"
                for column in columns[table]:
                    description = column.get('description', '')
                    # Include the detailed description if available
                    if description:
                        context += f"  - {column['name']} ({column['type']}): {description}\n"
                    else:
                        context += f"  - {column['name']} ({column['type']})\n"
            context += "\n"
        
        # Add relationship information
        context += "Table Relationships:\n"
        for table in all_tables:
            if table in self.table_relationships:
                for relation in self.table_relationships[table]:
                    context += f"  - {table}.{relation['from_column']} references {relation['related_table']}.{relation['to_column']}\n"
        
        # Add special notes about commonly confused columns
        context += "\nSpecial Notes:\n"
        context += "  - The orders table has a 'status' column (NOT 'order_status') for order status values.\n"
        context += "  - The customers table has a 'customer_segment' column (NOT just 'segment').\n"
        context += "  - The customers table has a 'state' column (NOT 'customer_state').\n"
        
        return context
