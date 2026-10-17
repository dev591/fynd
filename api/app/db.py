"""SQLite database with WAL mode and schema initialization."""

import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'app.db')

def init_db():
    """Initialize database schema."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    cursor = conn.cursor()
    
    # RFQs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rfqs (
            id TEXT PRIMARY KEY,
            buyer_id TEXT NOT NULL,
            item TEXT NOT NULL,
            quantity_needed INTEGER NOT NULL,
            need_by_days INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            decided_quote_id TEXT,
            FOREIGN KEY (buyer_id) REFERENCES supplier_profiles(id)
        )
    ''')
    
    # RFQ Invites (tokens per supplier, revocable)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rfq_invites (
            id TEXT PRIMARY KEY,
            rfq_id TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            revoked INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (rfq_id) REFERENCES rfqs(id),
            FOREIGN KEY (supplier_id) REFERENCES supplier_profiles(id)
        )
    ''')
    
    # Quotes (versioned: v1, v2, ...)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quotes (
            id TEXT PRIMARY KEY,
            rfq_id TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            price REAL NOT NULL,
            lead_days INTEGER NOT NULL,
            packing_json TEXT,
            notes TEXT,
            submitted_at INTEGER NOT NULL,
            rejected INTEGER DEFAULT 0,
            FOREIGN KEY (rfq_id) REFERENCES rfqs(id),
            FOREIGN KEY (supplier_id) REFERENCES supplier_profiles(id),
            UNIQUE(rfq_id, supplier_id, version)
        )
    ''')
    
    # Targets (negotiation targets)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS targets (
            id TEXT PRIMARY KEY,
            rfq_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_value REAL NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (rfq_id) REFERENCES rfqs(id)
        )
    ''')
    
    # Supplier Profiles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplier_profiles (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            company TEXT NOT NULL,
            state TEXT NOT NULL,
            business_type TEXT NOT NULL,
            categories TEXT NOT NULL,
            regions TEXT NOT NULL,
            default_lead_days INTEGER,
            gst_inclusive_default INTEGER DEFAULT 0,
            verification_json TEXT,
            created_at INTEGER NOT NULL
        )
    ''')
    
    # Products
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            supplier_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            photo_path TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES supplier_profiles(id)
        )
    ''')
    
    # Messages (RFQ + supplier thread)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            rfq_id TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (rfq_id) REFERENCES rfqs(id),
            FOREIGN KEY (supplier_id) REFERENCES supplier_profiles(id)
        )
    ''')
    
    conn.commit()
    conn.close()

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def dict_from_row(row):
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)

def now_unix():
    """Get current Unix timestamp."""
    return int(datetime.utcnow().timestamp())
