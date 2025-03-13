#!/usr/bin/env python3
"""
Import IMDb TSV files into a SQLite database.
This script creates a MovieData.db file with tables corresponding to the IMDb dataset.
"""

import os
import sqlite3
import csv
import sys
import time
from pathlib import Path

# Increase CSV field size limit to handle large fields
csv.field_size_limit(sys.maxsize)

# Configure paths
DATA_DIR = Path('/Users/sandilya/CascadeProjects/nlq-to-sql/sample/MovieData')
DB_PATH = Path('/Users/sandilya/CascadeProjects/nlq-to-sql/MovieData.db')

# Define table schemas based on IMDb dataset structure
TABLE_SCHEMAS = {
    'name_basics': '''
        CREATE TABLE IF NOT EXISTS name_basics (
            nconst TEXT PRIMARY KEY,
            primaryName TEXT,
            birthYear INTEGER,
            deathYear INTEGER,
            primaryProfession TEXT,
            knownForTitles TEXT
        )
    ''',
    
    'title_basics': '''
        CREATE TABLE IF NOT EXISTS title_basics (
            tconst TEXT PRIMARY KEY,
            titleType TEXT,
            primaryTitle TEXT,
            originalTitle TEXT,
            isAdult INTEGER,
            startYear INTEGER,
            endYear INTEGER,
            runtimeMinutes INTEGER,
            genres TEXT
        )
    ''',
    
    'title_ratings': '''
        CREATE TABLE IF NOT EXISTS title_ratings (
            tconst TEXT PRIMARY KEY,
            averageRating REAL,
            numVotes INTEGER,
            FOREIGN KEY (tconst) REFERENCES title_basics(tconst)
        )
    ''',
    
    'title_crew': '''
        CREATE TABLE IF NOT EXISTS title_crew (
            tconst TEXT PRIMARY KEY,
            directors TEXT,
            writers TEXT,
            FOREIGN KEY (tconst) REFERENCES title_basics(tconst)
        )
    ''',
    
    'title_episode': '''
        CREATE TABLE IF NOT EXISTS title_episode (
            tconst TEXT PRIMARY KEY,
            parentTconst TEXT,
            seasonNumber INTEGER,
            episodeNumber INTEGER,
            FOREIGN KEY (tconst) REFERENCES title_basics(tconst),
            FOREIGN KEY (parentTconst) REFERENCES title_basics(tconst)
        )
    ''',
    
    'title_principals': '''
        CREATE TABLE IF NOT EXISTS title_principals (
            tconst TEXT,
            ordering INTEGER,
            nconst TEXT,
            category TEXT,
            job TEXT,
            characters TEXT,
            PRIMARY KEY (tconst, ordering),
            FOREIGN KEY (tconst) REFERENCES title_basics(tconst),
            FOREIGN KEY (nconst) REFERENCES name_basics(nconst)
        )
    ''',
    
    'title_akas': '''
        CREATE TABLE IF NOT EXISTS title_akas (
            titleId TEXT,
            ordering INTEGER,
            title TEXT,
            region TEXT,
            language TEXT,
            types TEXT,
            attributes TEXT,
            isOriginalTitle INTEGER,
            PRIMARY KEY (titleId, ordering),
            FOREIGN KEY (titleId) REFERENCES title_basics(tconst)
        )
    '''
}

# Map file names to table names
FILE_TO_TABLE = {
    'name.basics.tsv': 'name_basics',
    'title.basics.tsv': 'title_basics',
    'title.ratings.tsv': 'title_ratings',
    'title.crew.tsv': 'title_crew',
    'title.episode.tsv': 'title_episode',
    'title.principals.tsv': 'title_principals',
    'title.akas.tsv': 'title_akas'
}

def create_database():
    """Create the database and tables."""
    print(f"Creating database at {DB_PATH}...")
    
    # Remove existing database if it exists
    if DB_PATH.exists():
        os.remove(DB_PATH)
    
    # Create database and tables
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Create tables
    for table_name, schema in TABLE_SCHEMAS.items():
        print(f"Creating table: {table_name}")
        cursor.execute(schema)
    
    conn.commit()
    conn.close()
    print("Database and tables created successfully.")

def import_data(limit_rows=None):
    """Import data from TSV files into the database.
    
    Args:
        limit_rows: Optional limit on number of rows to import per file (for testing)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Process each TSV file
    for file_name, table_name in FILE_TO_TABLE.items():
        file_path = DATA_DIR / file_name
        
        if not file_path.exists():
            print(f"Warning: File {file_path} not found. Skipping.")
            continue
        
        print(f"Importing {file_path} into {table_name}...")
        start_time = time.time()
        
        # Get column names from the first row
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            file_columns = next(reader)
        
        # Get table columns from the database schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        table_columns = [row[1] for row in cursor.fetchall()]
        
        # Map file columns to table columns
        column_indices = []
        columns_to_insert = []
        
        for col in table_columns:
            if col in file_columns:
                column_indices.append(file_columns.index(col))
                columns_to_insert.append(col)
            else:
                print(f"  Warning: Column '{col}' not found in file {file_name}")
        
        # Create placeholders for INSERT statement
        placeholders = ', '.join(['?' for _ in columns_to_insert])
        insert_query = f"INSERT OR IGNORE INTO {table_name} ({', '.join(columns_to_insert)}) VALUES ({placeholders})"
        
        # Import data in batches
        batch_size = 10000
        batch_data = []
        row_count = 0
        error_count = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader)  # Skip header
            
            for row in reader:
                try:
                    # Skip rows that don't have enough columns
                    if len(row) < max(column_indices) + 1:
                        error_count += 1
                        if error_count <= 5:  # Only show first few errors
                            print(f"  Warning: Row {row_count+1} has {len(row)} columns, expected at least {max(column_indices) + 1}. Skipping.")
                        continue
                    
                    # Extract only the columns we need and replace "\\N" with None
                    processed_row = [None if row[i] == "\\N" else row[i] for i in column_indices]
                    batch_data.append(processed_row)
                    row_count += 1
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:  # Only show first few errors
                        print(f"  Error processing row {row_count+1}: {e}. Skipping.")
                
                # Insert batch when it reaches the batch size
                if len(batch_data) >= batch_size:
                    cursor.executemany(insert_query, batch_data)
                    conn.commit()
                    batch_data = []
                    print(f"  Imported {row_count} rows...")
                
                # Stop if we've reached the limit
                if limit_rows and row_count >= limit_rows:
                    break
        
        # Insert any remaining rows
        if batch_data:
            cursor.executemany(insert_query, batch_data)
            conn.commit()
        
        elapsed_time = time.time() - start_time
        print(f"Completed importing {row_count} rows into {table_name} in {elapsed_time:.2f} seconds")
    
    # Create indexes for better performance
    print("Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_basics_year ON title_basics(startYear)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_ratings_rating ON title_ratings(averageRating)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_principals_nconst ON title_principals(nconst)")
    conn.commit()
    
    conn.close()
    print("Data import completed successfully.")

def create_sample_views():
    """Create some useful views for common queries."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # View for movies with ratings
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS movie_ratings AS
    SELECT 
        b.tconst, 
        b.primaryTitle, 
        b.originalTitle,
        b.startYear, 
        b.genres, 
        r.averageRating, 
        r.numVotes
    FROM 
        title_basics b
    JOIN 
        title_ratings r ON b.tconst = r.tconst
    WHERE 
        b.titleType = 'movie'
    ''')
    
    # View for directors and their movies
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS director_movies AS
    SELECT 
        n.nconst,
        n.primaryName AS director,
        b.tconst,
        b.primaryTitle,
        b.startYear,
        r.averageRating
    FROM 
        name_basics n
    JOIN 
        title_principals p ON n.nconst = p.nconst
    JOIN 
        title_basics b ON p.tconst = b.tconst
    LEFT JOIN 
        title_ratings r ON b.tconst = r.tconst
    WHERE 
        p.category = 'director'
    ''')
    
    conn.commit()
    conn.close()
    print("Sample views created successfully.")

def main():
    """Main function to import IMDb data."""
    # Check if data directory exists
    if not DATA_DIR.exists():
        print(f"Error: Data directory {DATA_DIR} does not exist.")
        sys.exit(1)
    
    # Create database and tables
    create_database()
    
    # Import data (with optional row limit for testing)
    # Uncomment the line below to limit rows for testing
    # import_data(limit_rows=1000)
    import_data()
    
    # Create sample views
    create_sample_views()
    
    print(f"Database created at: {DB_PATH}")
    print("You can now use this database with the NLQ-to-SQL system.")

if __name__ == "__main__":
    main()
