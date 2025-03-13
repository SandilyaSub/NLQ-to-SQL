#!/usr/bin/env python3
"""
NLQ to SQL Converter using Together API
This script converts natural language questions to SQL queries for a retail database.
"""

import os
import json
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from together import Together
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize Together API client
api_key = os.getenv("TOGETHER_API_KEY")
if not api_key:
    raise ValueError("TOGETHER_API_KEY not found in environment variables. Please add it to .env file.")

together_client = Together(api_key=api_key)

# Database setup
DB_PATH = "retail_db.sqlite"

# Create sample database with tables if it doesn't exist
def create_sample_database():
    """Create a sample retail database with the 5 fundamental tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        category_id INTEGER PRIMARY KEY,
        category_name TEXT NOT NULL,
        category_description TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        product_description TEXT,
        product_price REAL NOT NULL,
        product_image TEXT,
        category_id INTEGER,
        FOREIGN KEY (category_id) REFERENCES categories (category_id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY,
        customer_fname TEXT NOT NULL,
        customer_lname TEXT NOT NULL,
        customer_email TEXT UNIQUE NOT NULL,
        customer_password TEXT NOT NULL,
        customer_street TEXT,
        customer_city TEXT,
        customer_state TEXT,
        customer_zipcode TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY,
        order_date TIMESTAMP NOT NULL,
        order_status TEXT NOT NULL,
        customer_id INTEGER,
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        order_item_id INTEGER PRIMARY KEY,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
        FOREIGN KEY (product_id) REFERENCES products (product_id)
    )
    ''')
    
    # Insert sample data
    # Categories
    categories = [
        (1, "Electronics", "Electronic items and gadgets"),
        (2, "Clothing", "Apparel and fashion items"),
        (3, "Home & Kitchen", "Home appliances and kitchen items"),
        (4, "Books", "Books and educational materials"),
        (5, "Sports", "Sports equipment and fitness gear")
    ]
    cursor.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?, ?)", categories)
    
    # Products
    products = [
        (1, "Smartphone", "Latest smartphone with advanced features", 699.99, "smartphone.jpg", 1),
        (2, "Laptop", "High-performance laptop for professionals", 1299.99, "laptop.jpg", 1),
        (3, "T-shirt", "Cotton t-shirt, comfortable fit", 19.99, "tshirt.jpg", 2),
        (4, "Jeans", "Denim jeans, slim fit", 49.99, "jeans.jpg", 2),
        (5, "Coffee Maker", "Automatic coffee maker with timer", 89.99, "coffeemaker.jpg", 3),
        (6, "Blender", "High-speed blender for smoothies", 79.99, "blender.jpg", 3),
        (7, "Novel", "Bestselling fiction novel", 14.99, "novel.jpg", 4),
        (8, "Textbook", "College textbook on computer science", 99.99, "textbook.jpg", 4),
        (9, "Yoga Mat", "Non-slip yoga mat", 29.99, "yogamat.jpg", 5),
        (10, "Dumbbells", "Set of adjustable dumbbells", 149.99, "dumbbells.jpg", 5)
    ]
    cursor.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?, ?, ?)", products)
    
    # Customers
    customers = [
        (1, "John", "Doe", "john.doe@email.com", "password123", "123 Main St", "Austin", "Texas", "78701"),
        (2, "Jane", "Smith", "jane.smith@email.com", "password456", "456 Elm St", "Dallas", "Texas", "75201"),
        (3, "Bob", "Johnson", "bob.johnson@email.com", "password789", "789 Oak St", "Houston", "Texas", "77002"),
        (4, "Alice", "Williams", "alice.williams@email.com", "passwordabc", "101 Pine St", "New York", "New York", "10001"),
        (5, "Charlie", "Brown", "charlie.brown@email.com", "passworddef", "202 Maple St", "Los Angeles", "California", "90001")
    ]
    cursor.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", customers)
    
    # Calculate dates for orders
    today = datetime.now()
    last_month = today - timedelta(days=30)
    two_months_ago = today - timedelta(days=60)
    
    # Orders
    orders = [
        (1, today.strftime("%Y-%m-%d %H:%M:%S"), "Completed", 1),
        (2, last_month.strftime("%Y-%m-%d %H:%M:%S"), "Completed", 2),
        (3, last_month.strftime("%Y-%m-%d %H:%M:%S"), "Completed", 3),
        (4, two_months_ago.strftime("%Y-%m-%d %H:%M:%S"), "Completed", 4),
        (5, two_months_ago.strftime("%Y-%m-%d %H:%M:%S"), "Completed", 5),
        (6, last_month.strftime("%Y-%m-%d %H:%M:%S"), "Completed", 1),
        (7, last_month.strftime("%Y-%m-%d %H:%M:%S"), "Completed", 2)
    ]
    cursor.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?)", orders)
    
    # Order Items
    order_items = [
        (1, 1, 1, 1, 699.99),
        (2, 1, 3, 2, 39.98),
        (3, 2, 2, 1, 1299.99),
        (4, 3, 5, 1, 89.99),
        (5, 3, 7, 3, 44.97),
        (6, 4, 9, 1, 29.99),
        (7, 5, 10, 1, 149.99),
        (8, 6, 4, 2, 99.98),
        (9, 7, 6, 1, 79.99)
    ]
    cursor.executemany("INSERT OR IGNORE INTO order_items VALUES (?, ?, ?, ?, ?)", order_items)
    
    conn.commit()
    conn.close()
    print("Sample database created successfully!")

def get_database_schema():
    """Get the schema of the 5 fundamental tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    schema = {}
    tables = ["categories", "products", "customers", "orders", "order_items"]
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        schema[table] = [{"name": col[1], "type": col[2]} for col in columns]
    
    conn.close()
    return schema

def generate_sql_query(question, schema):
    """Generate SQL query from natural language question using Together API."""
    # Prepare the schema as a string
    schema_str = json.dumps(schema, indent=2)
    
    # Prepare the prompt
    prompt = f"""You are an expert SQL query generator. Given a database schema and a natural language question, 
your task is to generate the correct SQL query that answers the question.

Database Schema:
{schema_str}

Important notes about the schema:
1. The 'order_items' table contains 'subtotal' which represents the total price for that item (quantity * price).
2. To calculate total sales, use the 'subtotal' column from 'order_items'.
3. For time-based queries, use the 'order_date' column from the 'orders' table.
4. When joining tables, make sure to use the correct foreign keys.

Question: {question}

Generate only the SQL query without any explanation. The query should be valid SQLite syntax.
SQL Query:"""
    
    # Call Together API
    response = together_client.chat.completions.create(
        model="mistralai/Mixtral-8x7B-Instruct-v0.1",
        messages=[
            {"role": "system", "content": "You are an expert SQL query generator."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=500
    )
    
    # Extract SQL query from response
    sql_query = response.choices[0].message.content.strip()
    
    # Clean up the SQL query (remove markdown formatting if present)
    if sql_query.startswith("```sql"):
        sql_query = sql_query.split("```sql")[1]
    if sql_query.startswith("```"):
        sql_query = sql_query.split("```")[1]
    if sql_query.endswith("```"):
        sql_query = sql_query.split("```")[0]
    
    return sql_query.strip()

def execute_sql_query(query):
    """Execute SQL query and return results."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        return f"Error executing query: {str(e)}"

def main():
    # Create sample database if it doesn't exist
    if not os.path.exists(DB_PATH):
        create_sample_database()
    
    # Get database schema
    schema = get_database_schema()
    
    # Natural language questions
    questions = [
        "How many customers do I have in total?",
        "What are total sales that happened last month?",
        "How many customers from Texas ordered totally?"
    ]
    
    # Process each question
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}: {question}")
        
        # Generate SQL query
        sql_query = generate_sql_query(question, schema)
        print(f"\nGenerated SQL Query:")
        print(sql_query)
        
        # Execute SQL query
        print("\nQuery Result:")
        result = execute_sql_query(sql_query)
        print(result)
        print("-" * 80)

if __name__ == "__main__":
    main()
