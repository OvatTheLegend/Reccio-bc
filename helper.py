import sqlite3
from datetime import datetime

database = 'receipts.db'

#function for saving new recepit into databse, data of type dictionary
def save_new_receipt(data_dict):

    #connection to database and getting cursor for making sql statements 
    con = sqlite3.connect(database)
    cur = con.cursor()

    #need to switch from sk format to iso due to filetring later
    date = data_dict["date"]
    time = data_dict["time"]
    #ignore seconds
    time = time[:5]

    dt = datetime.strptime(f"{date} {time}", "%d.%m.%Y %H:%M")
    datetime_iso = dt.strftime("%Y-%m-%d %H:%M:%S")

    try:
        cur.execute(
            """
            INSERT INTO receipts(shop_name, date, time, datetime_iso, prize)
            VALUES (?, ?, ?, ?, ?)
            """, (data_dict["shop_name"],data_dict["date"],data_dict["time"], datetime_iso, data_dict["prize"])
            )

        #getting last added row to table
        receipt_id = cur.lastrowid

        con.commit()
        con.close()

        return receipt_id

    except sqlite3.IntegrityError:
        return None

    finally:
        con.close()


#function for saving new items into database
def save_new_items(data_list_dict, receipt_id):

    con = sqlite3.connect(database)
    cur = con.cursor()


    for data_item in data_list_dict:
        cur.execute(
        """
        INSERT INTO items(item_name, amount, prize, category, receipt_id)
        VALUES (?,?,?,?,?)
        """, (data_item["item_name"],data_item["amount"],
            data_item["prize"], "UNKNOWN", receipt_id)
        )


    con.commit()
    con.close()

    return

def get_receipts():

    con = sqlite3.connect(database)

    #aby sa sa vracal dict-like obejkt, kvoli prehladnosti v html
    con.row_factory = sqlite3.Row

    cur = con.cursor()

    cur.execute("""SELECT * FROM receipts
    ORDER BY datetime_iso DESC LIMIT 20""")
    receipts = cur.fetchall()
    con.close()

    return receipts

#testing function
def delete_receipt():
    
    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("DELETE FROM receipts WHERE id = (SELECT MAX(id) from receipts)")

    con.commit()
    con.close()





