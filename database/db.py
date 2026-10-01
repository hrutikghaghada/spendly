import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = "spendly.db"

def get_db():
    """
    Returns a SQLite connection with row_factory and foreign keys enabled.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """
    Creates the users and expenses tables.
    """
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()

def seed_db():
    """
    Inserts sample data for development if the database is empty.
    """
    with get_db() as conn:
        # Check if users table already contains data
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if user:
            return

        # Insert demo user
        demo_password_hash = generate_password_hash("demo123")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", demo_password_hash)
        )
        user_id = cursor.lastrowid

        # Sample expenses
        sample_expenses = [
            (user_id, 12.50, "Food", "2026-09-01", "Lunch at Cafe"),
            (user_id, 45.00, "Transport", "2026-09-02", "Weekly Fuel"),
            (user_id, 120.00, "Bills", "2026-09-03", "Internet Bill"),
            (user_id, 30.00, "Health", "2026-09-05", "Pharmacy"),
            (user_id, 15.00, "Entertainment", "2026-09-07", "Movie Ticket"),
            (user_id, 60.00, "Shopping", "2026-09-10", "New Shirt"),
            (user_id, 10.00, "Other", "2026-09-12", "Parking Fee"),
            (user_id, 25.00, "Food", "2026-09-15", "Dinner with Friends"),
        ]

        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            sample_expenses
        )
        conn.commit()

def create_user(name, email, password):
    """
    Hashes the password and inserts a new user into the database.
    Returns the new user's ID.
    """
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )
        conn.commit()
        return cursor.lastrowid

def get_user_by_email(email):
    """
    Fetches a user record by email. Returns the row if found, otherwise None.
    """
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
