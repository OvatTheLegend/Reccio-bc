import sqlite3
from datetime import datetime
import config

database = config.DATABASE_PATH

def init_database():
    #creating connection to database
    con = sqlite3.connect(database)
    con.execute("PRAGMA foreign_keys = ON")
    #for executing sql statements, we need database cursor
    cur = con.cursor()

    #user table
    cur.execute(""" CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hashed TEXT NOT NULL,
        email_address TEXT,
        email_app_password TEXT,
        email_filters TEXT,
        email_scan_limit INTEGER,
        save_attachments INTEGER DEFAULT 1
        )""")


    #craeting table for e-block
    cur.execute(""" CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        shop_name TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        datetime_iso TEXT NOT NULL,
        price REAL NOT NULL,
        parse_method TEXT,
        file_path TEXT,
        UNIQUE(user_id,shop_name,date,time,price),
        FOREIGN KEY (user_id) REFERENCES users(id)
        )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )""")

    #creating table for items from e-blocks
    cur.execute(""" CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        amount REAL NOT NULL,
        price REAL NOT NULL,
        category_id INTEGER,
        receipt_id INTEGER NOT NULL,
        FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(id)
        )""")

    
    #commiting changes
    con.commit()
    con.close()
    
    print("Database user,receipts,items created!")

def get_connection():
    return sqlite3.connect(database)

