import sqlite3
from datetime import datetime

database = 'receipts.db'

def init_database():
    #creating connection to database
    con = sqlite3.connect(database)

    #for executing sql statements, we need database cursor
    cur = con.cursor()

    #user table
    cur.execute(""" CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hashed TEXT NOT NULL,
        email_addres TEXT,
        email_2fa_password TEXT
        )""")


    #craeting table for e-block
    cur.execute(""" CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        shop_name TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        datetime_iso TEXT NOT NULL,
        prize REAL NOT NULL,
        parse_method TEXT,
        UNIQUE(user_id,shop_name,date,time,prize),
        FOREIGN KEY (user_id) REFERENCES users(id)
        )""")


    #creating table for items from e-blocks
    cur.execute(""" CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        amount REAL NOT NULL,
        prize REAL NOT NULL,
        category TEXT NOT NULL,
        receipt_id INTEGER NOT NULL,
        FOREIGN KEY (receipt_id) REFERENCES receipts(id)
        )""")

    #commiting changes
    con.commit()
    con.close
    
    print("Database user,receipts,items created!")

def get_connection():
    return sqlite3.connect(database)

