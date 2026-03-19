import sqlite3

conn = sqlite3.connect("auction.db")
cur = conn.cursor()

# Users table
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

# Items table
cur.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    start_price INTEGER NOT NULL,
    highest_bid INTEGER NOT NULL,
    image TEXT,
    end_time TEXT,
    winner TEXT
)
""")

# Bids table
cur.execute("""
CREATE TABLE IF NOT EXISTS bids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    bidder TEXT,
    amount INTEGER,
    time TEXT,
    FOREIGN KEY(item_id) REFERENCES items(id)
)
""")

# Feedback table
cur.execute("""
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    rating INTEGER,
    review TEXT
)
""")

conn.commit()
conn.close()
print("Database and tables created successfully!")
