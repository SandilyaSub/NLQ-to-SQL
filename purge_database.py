#!/usr/bin/env python3
"""
Purge Database Script
This script drops all tables in the SQLite database and removes the database file.
"""

import os
import sqlite3

# Database path
DB_PATH = "retail_db.sqlite"

def purge_database():
    """Drop all tables in the database and remove the database file."""
    if os.path.exists(DB_PATH):
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Drop each table
        for table in tables:
            table_name = table[0]
            print(f"Dropping table: {table_name}")
            cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        # Remove the database file
        os.remove(DB_PATH)
        print(f"Removed database file: {DB_PATH}")
    else:
        print(f"Database file {DB_PATH} does not exist.")

if __name__ == "__main__":
    purge_database()
    print("Database purge completed successfully.")
