import sqlite3

database = 'receipts.db'

#function for saving new recepit into databse, data of type dictionary
def save_new_receipt(data_dict):

    #connection to database and getting cursor for making sql statements 
    con = sqlite3.connect(database)
    cur = con.cursor()

    try:
        cur.execute(
            """
            INSERT INTO receipts(shop_name, date, time, prize)
            VALUES (?, ?, ?, ?)
            """, (data_dict["shop_name"],data_dict["date"],data_dict["time"],data_dict["prize"])
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

def get_all_receipts():

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""SELECT * FROM receipts""")
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





