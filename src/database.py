import sqlite3
import os
import logging
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="marketplace_scraper.db"):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.initialize()
        
    def initialize(self):
        """Create the database and tables if they don't exist."""
        db_exists = os.path.exists(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        if not db_exists:
            self.create_tables()
            logging.info(f"Database created at {self.db_path}")
        
    def create_tables(self):
        """Create the necessary tables for tracking listings and searches."""
        self.cursor.execute('''
        CREATE TABLE listings (
            id TEXT PRIMARY KEY,
            title TEXT,
            price REAL,
            url TEXT,
            location TEXT,
            discovered_at TIMESTAMP
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP,
            search_terms TEXT,
            items_found INTEGER,
            new_items INTEGER,
            status TEXT
        )
        ''')
        
        self.conn.commit()
        
    def item_exists(self, item_id):
        """Check if an item already exists in the database."""
        self.cursor.execute("SELECT id FROM listings WHERE id = ?", (item_id,))
        return self.cursor.fetchone() is not None
        
    def add_item(self, item_id, title, price, url, location):
        """Add a new item to the database."""
        try:
            self.cursor.execute(
                "INSERT INTO listings VALUES (?, ?, ?, ?, ?, ?)",
                (item_id, title, price, url, location, datetime.now())
            )
            self.conn.commit()
            logging.info(f"Added new item to database: {title} (${price})")
            return True
        except sqlite3.Error as e:
            logging.error(f"Database error when adding item: {e}")
            return False
            
    def log_search(self, search_terms, items_found, new_items, status="completed"):
        """Log a search attempt to the database."""
        try:
            self.cursor.execute(
                "INSERT INTO searches (timestamp, search_terms, items_found, new_items, status) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(), search_terms, items_found, new_items, status)
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Database error when logging search: {e}")
            return False
    
    def get_recent_searches(self, limit=5):
        """Get recent search logs."""
        self.cursor.execute(
            "SELECT timestamp, search_terms, items_found, new_items, status FROM searches ORDER BY timestamp DESC LIMIT ?", 
            (limit,)
        )
        return self.cursor.fetchall()
        
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()