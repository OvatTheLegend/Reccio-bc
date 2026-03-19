import sqlite3, re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import config

database = config.DATABASE_PATH


#---------------------------------------------------DATABASE INSERT SELECT SECTION---------------------------
def save_file_path(receipt_id, file_path):

    con = sqlite3.connect(database)
    cur = con.cursor()


    try:
        cur.execute(
        """
           UPDATE receipts SET file_path = ?
           WHERE id = ?
        """,(file_path, receipt_id))

        con.commit()
    
    except sqlite3.IntegrityError:
        return None

    finally:
        con.close()

def save_receipt(parsed_receipt, parsed_items, user_id, parse_method):

    #pripojim k databaze so zapnutymi cudzimi klucami
    con = sqlite3.connect(database)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    #datum
    date = parsed_receipt["date"]
    #cas
    time = parsed_receipt["time"][:5]
    #dam na datetime
    dt = datetime.strptime(f"{date} {time}", "%d.%m.%Y %H:%M")
    #prehodim kvoli filtrovaniu
    datetime_iso = dt.strftime("%Y-%m-%d %H:%M:%S")


    try:
        #najrpv blocek
        cur.execute(
        """
        INSERT INTO receipts(shop_name, date, time, datetime_iso, prize, user_id, parse_method)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, 
        (parsed_receipt["shop_name"], parsed_receipt["date"], parsed_receipt["time"],
          datetime_iso, parsed_receipt["prize"], user_id, parse_method)
        )

        #zoberieme pridany blocek
        receipt_id = cur.lastrowid

        #teraz itemy
        for item in parsed_items:

            #spracovanie kategorie
            category = item["category"] if parse_method == "ai" else "nezaradené"

            cur.execute(
            """
            INSERT INTO items(item_name, amount, prize, category, receipt_id)
            VALUES (?, ?, ?, ?, ?)
            """, 
            (item["item_name"], item["amount"], item["prize"], category, receipt_id))

        con.commit()
        return receipt_id

    except sqlite3.IntegrityError:
        con.rollback()
        return None

    except Exception as e:
        con.rollback()
        return None

    finally:
        con.close()

def get_file_path(receipt_id, user_id):

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""SELECT file_path FROM receipts
    WHERE id = ?
    AND user_id = ?
    """, (receipt_id, user_id))

    row = cur.fetchone()
    con.close()

    print(f"get_file_path: receipt_id={receipt_id}, user_id={user_id}, row={row}") 
    if row:
        return row[0]
    else:
        return None

def get_all_receipts(user_id):

    con = sqlite3.connect(database)

    #aby sa sa vracal dict-like obejkt, kvoli prehladnosti v html
    con.row_factory = sqlite3.Row

    cur = con.cursor()

    cur.execute("""SELECT * FROM receipts
    WHERE user_id = ?
    ORDER BY datetime_iso DESC""", (user_id,))
    receipts = cur.fetchall()
    con.close()

    return receipts

#vrati 5 najnovsich
def get_last_5_receipts(user_id):

    con = sqlite3.connect(database)

    #aby sa sa vracal dict-like obejkt, kvoli prehladnosti v html
    con.row_factory = sqlite3.Row

    cur = con.cursor()

    cur.execute("""SELECT * FROM receipts
    WHERE user_id = ?
    ORDER BY prize DESC LIMIT 5""", (user_id,))
    receipts = cur.fetchall()
    con.close()

    return receipts

#vrati 5 najdrahsich blockov
def get_top_5_expensive(user_id):

    con = sqlite3.connect(database)

    #aby sa sa vracal dict-like obejkt, kvoli prehladnosti v html
    con.row_factory = sqlite3.Row

    cur = con.cursor()

    cur.execute("""SELECT * FROM receipts
    WHERE user_id = ?
    ORDER BY datetime_iso DESC LIMIT 5""", (user_id,))
    receipts = cur.fetchall()
    con.close()

    return receipts

#vrati sucasny mesiac a rok
def get_current_month_and_year():

    #aktualny
    now = datetime.now()
    month = f"{now.month:02d}"
    year = f"{now.year}"

    return month, year

def get_sum_amount_per_month(user_id):

    current_month, current_year = get_current_month_and_year()

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(prize), 0) AS total_sum
        FROM receipts
        WHERE user_id = ?
        AND substr(date, 4, 2) = ?
        AND substr(date, 7, 4) = ?
    """, (user_id, current_month, current_year))

    row = cur.fetchone()
    con.close()

    if row and row["total_sum"] is not None:
        return round(float(row["total_sum"]),2)

    #ak je none, vratime 0
    return 0.0



def get_dashboard_per_month_stats(user_id):
    return {
        "total_sum" : get_sum_amount_per_month(user_id)
    }
def delete_receipt(receipt_id, user_id):

    con = sqlite3.connect(database)
    #zapnut foreign_keys, pretoze mama CASCADE, defaultne su vypnute
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    cur.execute("""DELETE FROM receipts where id = ? AND user_id = ?
    """, (receipt_id, user_id,))

    #aby sme vedeli ci sme vymazali blocek
    deleted = cur.rowcount

    con.commit()
    con.close()

    return deleted

def get_receipt_details(receipt_id, user_id):
    
    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""SELECT item_name, amount, category, prize FROM items
    WHERE 
    ORDER BY datetime_iso DESC LIMIT 5""", (receipt_id, user_id))

    receipts = cur.fetchall()
    con.close()

def get_items(receipt_id, user_id):

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""
    SELECT i.item_name, i.amount, i.prize, i.category
    FROM items i
    JOIN receipts r ON i.receipt_id = r.id
    WHERE i.receipt_id = ?
    AND r.user_id = ?""", (receipt_id, user_id))

    items = cur.fetchall()
    con.close()

    #naplnime itemy
    item_list = []
    for i in items:
        item = {
            "item_name": i[0],
            "amount": i[1],
            "prize": i[2],
            "category": i[3]
        }

        item_list.append(item)

    #a vratime
    return item_list
#-----------------------------------------------------------------------------------------------

#---------------------------------------------------LOGIN/REGISTRATION SECTION---------------------------
def register_user(username, password):

    #registracia noveho pouzivatela

    con = sqlite3.connect(database)
    cur = con.cursor()

    password_hashed = generate_password_hash(password)

    try:
        cur.execute(
            """
            INSERT INTO users(username, password_hashed)
            VALUES (?,?)
            """, (username, password_hashed)
            )
        con.commit()

        user_id = cur.lastrowid
        con.close()
        return True, user_id

    except sqlite3.IntegrityError:
        con.close()
        return False, None

def validate_register(username, password, password_repeat):
    #overenie ci nie su prazdne polia
    if not username or not password or not password_repeat:
        return False, 'Všetky polia musia byť vyplnené!'
    
    #USERNAME KONTROLA
    if not is_unique_username(username):
        return False, 'Toto používateľské meno už existuje!'

    if len(username) < 3:
        return False, 'Používateľské meno musí mať aspoň 3 znaky!'
    
    if len(username) > 25:
        return False, 'Používateľské meno je príliš dlhé (max 25 znakov)!'

    #MOZNO KONTROLA ZNAKOV....

    #HESLO KONTROLA
    if len(password) < 5:
        return False, 'Heslo je príliš kratke (min 5 znakov)!'

    if password != password_repeat:
        return False, 'Heslá sa nezhodujú!'

    return True, None
    
def is_unique_username(username):
    #zistenie ci meno je jedinecne v ramci databazy

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""SELECT id FROM users
    WHERE username = ?""", (username,))

    unique_username = cur.fetchone()
    con.close()

    if unique_username is None:
        return True
    
    else: 
        return False

def validate_signin(username,password):

    #overenie ci nie su prazdne polia
    if not username or not password:
        return False, None, 'Všetky polia musia byť vyplnené!'

    #ziskame heshovane heslo usera, v pripade ak user existuje
    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""SELECT id, password_hashed from users
    WHERE username = ?""", (username,))
    
    user = cur.fetchone()
    con.close()

    #ak user neexistuje
    if not user:
        return False, None, 'Používateľské meno alebo heslo je nesprávne'

    #inak
    user_id = user['id']
    password_hashed = user['password_hashed']

    #skontrolujem heslo
    if check_password_hash(password_hashed, password):
        return True, user_id, None

    return False, None, 'Používateľské meno alebo heslo je nesprávne'
