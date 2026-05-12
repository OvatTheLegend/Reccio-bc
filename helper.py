import sqlite3, re
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import config
import calendar
import parser
from services import ai_service
import pypdfium2 as pdfium
from cryptography.fernet import Fernet

database = config.DATABASE_PATH

cipher = Fernet(config.EMAIL_CREDENTIALS_KEY)

#---------------------------------------------------DATABASE INSERT SELECT SECTION---------------------------

def encrypt_value(value):
    if not value:
        return ""

    return cipher.encrypt(value.encode()).decode()


def decrypt_value(value):
    if not value:
        return ""

    try:
        return cipher.decrypt(value.encode()).decode()
    except Exception:
        return ""

def get_decrypted_email_password(user_id):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT email_app_password
        FROM users
        WHERE id = ?
    """, (user_id,))

    row = cur.fetchone()
    con.close()

    if not row or not row["email_app_password"]:
        return ""

    return decrypt_value(row["email_app_password"])

def process_pdf_receipt(file_path, user_id):
    image_path = None

    try:
        #extraction of text from pdf, parsing, 
        pdf_text = parser.extract_from_pdf(file_path)

        if not pdf_text or len(pdf_text.strip()) < 30:
            image_path = convert_pdf_first_page_to_image(file_path)
            ai_result = ai_service.ai_parser_img(image_path)

            if not ai_result:
                return {
                    "success": False,
                    "error": "parse_failed"
                }

            if isinstance(ai_result, dict) and ai_result.get("success") is False:
                return {
                    "success": False,
                    "error": ai_result.get("error", "ai_error"),
                    "message": ai_result.get("message", "AI spracovanie zlyhalo.")
                }

            parsed_ai = ai_result["data"]

            parsed_receipt = {
            "shop_name": parsed_ai["shop_name"],
            "date": parsed_ai["date"],
            "time": parsed_ai["time"],
            "price": parsed_ai["price"],
            }

            parsed_items = parsed_ai["items"]
            parse_method = "ai_pdf_image"

        else:
            parsed_receipt = parser.parse_receipt(pdf_text)

            #naprv vyparsuejeme blocek
            if parsed_receipt:
                parsed_items = parser.parse_items_universal(parsed_receipt["shop_name"], pdf_text)
            else:
                parsed_items = None
            
            parse_method = "parser"


            #manualny pareser zlyhal
            if not parsed_receipt or not parsed_items:
                #ak sa nepodari, skusime ai

                #zavolanie parsera ai
                ai_result = ai_service.ai_parser_text(pdf_text)

                if not ai_result:
                    return {
                        "success": False,
                        "error": "parse_failed"
                    }

                if isinstance(ai_result, dict) and ai_result.get("success") is False:
                    return {
                        "success": False,
                        "error": ai_result.get("error", "ai_error"),
                        "message": ai_result.get("message", "AI spracovanie zlyhalo.")
                    }

                parsed_ai = ai_result["data"]

                parsed_receipt = {
                    "shop_name":  parsed_ai["shop_name"],
                    "date":  parsed_ai["date"],
                    "time": parsed_ai["time"],
                    "price":  parsed_ai["price"],
                }

                parsed_items = parsed_ai["items"]
                parse_method = "ai"

        #ak vsetko v poriadku ulozime do db
        receipt_id = save_receipt(parsed_receipt, parsed_items, user_id, parse_method)

        #ak chyba pri ukladani
        if receipt_id is None:
            return {
                "success": False,
                "error": "duplicate"
            }
        
        save_attachments = get_save_attachments_setting(user_id)

        if save_attachments: 
            extension = file_path.rsplit('.')[-1].lower()
            user_folder = os.path.dirname(file_path)
                    
            #rename the file_pre-saved
            final_filename = f'r_{receipt_id}.{extension}'
            final_file_path = os.path.join(user_folder,final_filename)
            os.rename(file_path, final_file_path)

            #ulozime cestu k suboru pre zobrazovanie originalu
            save_file_path(receipt_id, final_file_path)

        else:
            os.remove(file_path)
            final_file_path = None
            
        return {
            "success": True,
            "receipt_id": receipt_id,
            "file_path": final_file_path,
            "parse_method": parse_method
        }

    except Exception as e:
        return {
            "success": False,
            "error": "exception"
        }
    
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
    
def convert_pdf_first_page_to_image(file_path):

    pdf = pdfium.PdfDocument(file_path)
    page = pdf[0]

    # scale na img x2
    pil_image = page.render(scale=2).to_pil()

    image_path = os.path.splitext(file_path)[0] + "_page1.png"
    pil_image.save(image_path)

    return image_path

    
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
        INSERT INTO receipts(shop_name, date, time, datetime_iso, price, user_id, parse_method)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, 
        (parsed_receipt["shop_name"], parsed_receipt["date"], parsed_receipt["time"],
          datetime_iso, parsed_receipt["price"], user_id, parse_method)
        )

        #zoberieme pridany blocek
        receipt_id = cur.lastrowid

        #teraz itemy
        for item in parsed_items:

            if parse_method == "ai":
                category_name = item.get("category")
                category_id = get_or_create_category_id_with_cursor(cur, category_name)
            else:
                category_id = get_category_for_item(item["item_name"], user_id)

            cur.execute(
            """
            INSERT INTO items(item_name, amount, price, category_id, receipt_id)
            VALUES (?, ?, ?, ?, ?)
            """, 
            (item["item_name"], item["amount"], item["price"], category_id, receipt_id))

        con.commit()
        return receipt_id

    except sqlite3.IntegrityError as e:
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

    if row:
        return row[0]
    else:
        return None

def get_or_create_category_id(category_name):
    if not category_name:
        return None

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO categories(name)
        VALUES (?)
    """, (category_name,))

    cur.execute("""
        SELECT id FROM categories
        WHERE name = ?
    """, (category_name,))

    row = cur.fetchone()
    con.commit()
    con.close()

    if row:
        return row[0]

    return None

def get_or_create_category_id_with_cursor(cur, category_name):
    if not category_name:
        return None

    cur.execute("""
        INSERT OR IGNORE INTO categories(name)
        VALUES (?)
    """, (category_name,))

    cur.execute("""
        SELECT id FROM categories
        WHERE name = ?
    """, (category_name,))

    row = cur.fetchone()

    if row:
        return row[0]

    return None

#pocet nekategorizovanych poloziek
def get_uncategorized_count(user_id):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT COUNT(*) as total
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        WHERE r.user_id = ?
        AND i.category_id IS NULL
    """, (user_id,))

    row = cur.fetchone()
    con.close()

    if row:
        return int(row["total"])

    return 0

#cvytiahneme vsetky nezaradene polozky
def get_uncategorized_items(user_id):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT i.id, i.item_name
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        WHERE r.user_id = ?
        AND i.category_id IS NULL
        ORDER BY i.id ASC
    """, (user_id,))

    items = cur.fetchall()
    con.close()

    return items

#zaradenie poloziek na konkretne kategorie
def categorize_items(item_id, category_name):

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO categories(name)
        VALUES (?)
    """, (category_name,))

    cur.execute("""
        SELECT id FROM categories
        WHERE name = ?
    """, (category_name,))

    row = cur.fetchone()
    category_id = row[0] if row else None

    cur.execute("""
        UPDATE items
        SET category_id = ?
        WHERE id = ?
    """, (category_id, item_id))

    con.commit()
    changed = cur.rowcount
    con.close()

    return changed

def get_category_for_item(item_name, user_id):

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""
        SELECT i.category_id
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        WHERE i.item_name = ?
        AND r.user_id = ?
        AND i.category_id IS NOT NULL
        LIMIT 1
    """, (item_name, user_id))

    result = cur.fetchone()
    con.close()

    if result:
        return result[0]  

    return None

#aby sme ai neposielali vela udajov naraz, rozdelime velke hodnoty na skupiny
def split_into_groups(items, group_size=50):
    
    groups = []

    for i in range(0, len(items), group_size):
        groups.append(items[i:i + group_size])

    #vratime list skupniek
    return groups


def get_all_receipts(user_id):
    
    con = sqlite3.connect(database)

    #aby sa sa vracal dict-like obejkt, kvoli prehladnosti v html
    con.row_factory = sqlite3.Row

    cur = con.cursor()

    cur.execute("""SELECT * FROM receipts
    WHERE user_id = ?
    ORDER BY datetime_iso DESC
    LIMIT 50""", (user_id,))
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
    ORDER BY datetime_iso DESC LIMIT 5""", (user_id,))
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
    ORDER BY CAST(REPLACE(price, ',', '.') AS REAL) DESC
    LIMIT 5""", (user_id,))
    receipts = cur.fetchall()
    con.close()

    return receipts


def get_current_month_range():
    # ziskame akutalny cas
    now = datetime.now()

    # zaciatgok mesiaca
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # zaciatok druheho
    #ak december tak dame na + rok a nastavime zaciatok
    if now.month == 12:
        next_month_start = now.replace(
            year=now.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
    #inak pokracujeme
    else:
        next_month_start = now.replace(
            month=now.month + 1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

    # voba vratime v datetimeiso formate na rychle porovnanvania
    return (
        month_start.strftime("%Y-%m-%d %H:%M:%S"),
        next_month_start.strftime("%Y-%m-%d %H:%M:%S")
    )

def get_default_stats_date_range():

    #
    today = datetime.now()

    #default je poslednych 6 mesiacov
    year = today.year
    month = today.month

    # - 5 mesiacov aby sme mali poslednych 5 + aktualny
    for _ in range(5):
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1

    # zaciatok obdobia = prvy den vypocitaneho mesiaca
    date_from = datetime(year, month, 1)

    # koniec obdobia = dnes
    date_to = today

    return (
        date_from.strftime("%Y-%m-%d"),
        date_to.strftime("%Y-%m-%d")
    )
def get_sum_amount_per_month(user_id):

    month_start, next_month_start = get_current_month_range()

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(price), 0) AS total_sum
        FROM receipts
        WHERE user_id = ?
        AND datetime_iso >= ?
        AND datetime_iso < ?
    """, (user_id, month_start, next_month_start))

    row = cur.fetchone()
    con.close()

    if row and row["total_sum"] is not None:
        return round(float(row["total_sum"]),2)

    #ak je none, vratime 0
    return 0.0

#ziskanie poctu nakupov za dany mesiac
def get_month_purchase_count(user_id):

    month_start, next_month_start = get_current_month_range()

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT COUNT(*) as purchase_count
        FROM receipts
        WHERE user_id = ?
        AND datetime_iso >= ?
        AND datetime_iso < ?
    """, (user_id, month_start, next_month_start))

    #ziskame a zavrieme
    row = cur.fetchone()
    con.close()

    if row:
        return int(row["purchase_count"])
    
    #inak 0
    return 0


#priemerny pocet nakupov za dany mesiac
def get_average_amount(user_id):
    #ziskame pocet nakupov a celkovz sunu za mesiac
    total_sum = get_sum_amount_per_month(user_id)
    pruchase_count = get_month_purchase_count(user_id)

    if (pruchase_count == 0):
        return 0.0


    return round(total_sum / pruchase_count, 2)


#najnavstevovanejsi obchod
def get_top_month_shop(user_id):

    month_start, next_month_start = get_current_month_range()

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT shop_name, COUNT(*) as shop_count
        FROM receipts
        WHERE user_id = ?
        AND datetime_iso >= ?
        AND datetime_iso < ?
        GROUP BY shop_name
        ORDER BY shop_count DESC, shop_name ASC
        LIMIT 1
    """, (user_id, month_start, next_month_start))

    #ziskame a zavrieme
    row = cur.fetchone()
    con.close()

    if row and row["shop_name"]:
        return row["shop_name"]

    return "-"

#vratime vsetko naraz
def get_dashboard_per_month_stats(user_id):
    return {
        "total_sum" : get_sum_amount_per_month(user_id),
        "purchase_count" : get_month_purchase_count(user_id),
        "average_amount" : get_average_amount(user_id),
        "top_shop" : get_top_month_shop(user_id)
    }

#funkcia na ziskanie udajov pre graf
def get_daily_expenses_for_current_month(user_id):

    month_start, next_month_start = get_current_month_range()

    #momentalny cas
    now = datetime.now()

    #rok a mesiac
    year = now.year
    month = now.month

    #musime ziszi kolko dni ma mesiac aktualny
    days_in_month = calendar.monthrange(year,month)[1]

    #spravime vynulovane pole 
    daily_totals = {}
    for day in range(1, days_in_month+1):
        daily_totals[day] = 0

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
    SELECT CAST(substr(datetime_iso,9,2) AS INTEGER) as day, SUM(price) as total
    FROM receipts
    WHERE user_id = ?
    AND datetime_iso >= ?
    AND datetime_iso <= ?
    GROUP BY day
    ORDER BY day ASC
    
    """, (user_id, month_start, next_month_start))

    rows = cur.fetchall()
    con.close()

    for row in rows:
        day = row["day"]
        total = row["total"]

        #kontrola ci neni none
        if day is not None and total is not None:
            daily_totals[int(day)] = round(float(total),2)
    
    #pripravime pre graf
    values = []
    labels = []
    for day in range(1,days_in_month+1):
        labels.append(str(day))
        values.append(daily_totals[day])

    return {
        "labels" : labels,
        "values" : values
    }

#hodnoty pre graf kategori
def get_category_stat_for_current_month(user_id):

    month_start, next_month_start = get_current_month_range()

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT COALESCE(c.name, 'Nezaradené') as category,
               COALESCE(SUM(i.price), 0) as total
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE r.user_id = ?
        AND r.datetime_iso >= ?
        AND r.datetime_iso < ?
        GROUP BY COALESCE(c.name, 'Nezaradené')
        ORDER BY total DESC
    """, (user_id, month_start, next_month_start))

    rows = cur.fetchall()
    con.close()
    
    values = []
    labels = []

    for row in rows:
        labels.append(row["category"])
        values.append(round(float(row["total"]), 2))

    return {
        "labels": labels,
        "values": values
    }

def get_stats_summary_cards(user_id, date_from, date_to):

    # prevedieme datumy na datetime_iso rozsah
    date_from_iso = date_from + " 00:00:00"
    date_to_iso = date_to + " 23:59:59"

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    #zobereieme celkovu sume v od do
    cur.execute("""
        SELECT COALESCE(SUM(price), 0) as total_sum
        FROM receipts
        WHERE user_id = ?
        AND datetime_iso >= ?
        AND datetime_iso <= ?
    """, (user_id, date_from_iso, date_to_iso))

    row = cur.fetchone()
    if row and row["total_sum"] is not None:
        total_sum = round(float(row["total_sum"]), 2)
    else:
        total_sum = 0.0
    

    #vyberieme pocet blockovv
    cur.execute("""
        SELECT COUNT(*) as receipt_count
        FROM receipts
        WHERE user_id = ?
        AND datetime_iso >= ?
        AND datetime_iso <= ?
    """, (user_id, date_from_iso, date_to_iso))

    row = cur.fetchone()
    if row:
        receipt_count = int(row["receipt_count"])
    else: 
        receipt_count = 0

    #najkupovanejsia kategoria
    #podla minutych Eur

    cur.execute("""
        SELECT COALESCE(c.name, 'Nezaradené') as category,
            SUM(i.price) as total_spent
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE r.user_id = ?
        AND r.datetime_iso >= ?
        AND r.datetime_iso <= ?
        GROUP BY COALESCE(c.name, 'Nezaradené')
        ORDER BY total_spent DESC, category ASC
        LIMIT 1
    """, (user_id, date_from_iso, date_to_iso))

    row = cur.fetchone()
    if row and row["category"]:
        top_category = row["category"]
    else:
        top_category = "-"

    # najkupovanejsia polozka podla SUM(amount)
    cur.execute("""
        SELECT i.item_name, SUM(COALESCE(i.amount,0)) as total_amount
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        WHERE r.user_id = ?
        AND r.datetime_iso >= ?
        AND r.datetime_iso <= ?
        GROUP BY i.item_name
        ORDER BY total_amount DESC, i.item_name ASC
        LIMIT 1
    """, (user_id, date_from_iso, date_to_iso))

    row = cur.fetchone()

    if row and row["item_name"]:
        top_item = row["item_name"]
        top_item_amount = round(float(row["total_amount"]), 2)
    else:
        top_item = "-"
        top_item_amount = 0

    con.close()

    return {
        "total_sum": total_sum,
        "receipt_count": receipt_count,
        "top_category": top_category,
        "top_item": top_item,
        "top_item_amount": top_item_amount
    }
    
def get_monthly_expenses(user_id, date_from, date_to):

    #dame rozsah
    date_from_iso = date_from + " 00:00:00"
    date_to_iso = date_to + " 23:59:59"

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT 
            strftime('%Y-%m', datetime_iso) as month,
            COALESCE(SUM(price), 0) as total
        FROM receipts
        WHERE user_id = ?
        AND datetime_iso >= ?
        AND datetime_iso <= ?
        GROUP BY month
        ORDER BY month ASC
    """, (user_id, date_from_iso, date_to_iso))

    rows = cur.fetchall()
    con.close()

    labels = []
    values = []

    for row in rows:
        labels.append(row["month"])
        values.append(round(float(row["total"]), 2))

    return {
        "labels": labels,
        "values": values
    }

def get_category_monthly_expenses(user_id, date_from, date_to):

    date_from_iso = date_from + " 00:00:00"
    date_to_iso = date_to + " 23:59:59"

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT COALESCE(c.name, 'Nezaradené') as category,
               COALESCE(SUM(i.price), 0) as total
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE r.user_id = ?
        AND r.datetime_iso >= ?
        AND r.datetime_iso <= ?
        GROUP BY COALESCE(c.name, 'Nezaradené')
        ORDER BY total DESC
    """, (user_id, date_from_iso, date_to_iso))

    rows = cur.fetchall()
    con.close()

    labels = []
    values = []

    for row in rows:
        labels.append(row["category"])
        values.append(round(float(row["total"]), 2))

    return {
        "labels": labels,
        "values": values
    }

def get_shop_monthly_expenses(user_id, date_from, date_to):

    #prevedieme
    date_from_iso = date_from + " 00:00:00"
    date_to_iso = date_to + " 23:59:59"

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT r.shop_name, COALESCE(SUM(r.price), 0) as total
        FROM receipts r
        WHERE r.user_id = ?
        AND r.datetime_iso >= ?
        AND r.datetime_iso <= ?
        GROUP BY r.shop_name
        ORDER BY total DESC
        LIMIT 6
    """, (user_id, date_from_iso, date_to_iso))

    rows = cur.fetchall()
    con.close()

    labels = []
    values = []

    for row in rows:
        labels.append(row["shop_name"])
        values.append(round(float(row["total"]), 2))

    return {
        "labels": labels,
        "values": values
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

def get_items(receipt_id, user_id):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT 
            i.item_name, 
            i.amount, 
            i.price, 
            COALESCE(c.name, 'Nezaradené') as category
        FROM items i
        JOIN receipts r ON i.receipt_id = r.id
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.receipt_id = ?
        AND r.user_id = ?
        ORDER BY i.id ASC
    """, (receipt_id, user_id))

    items = cur.fetchall()
    con.close()

    item_list = []
    for i in items:
        item = {
            "item_name": i["item_name"],
            "amount": i["amount"],
            "price": i["price"],
            "category": i["category"]
        }
        item_list.append(item)

    return item_list

#na filttovanie blockov
def get_filtered_receipts(user_id, search, date_from, date_to):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    #skladame query podla parametrovv
    query = """
        SELECT id, shop_name, date, time, price
        FROM receipts
        WHERE user_id = ?
        """
    
    #list kde budeme ukladat parametre a nakoniec executeneme poskaldanu query
    parameters = [user_id]

    #ak je nieco v search
    if search:
        query += " AND LOWER(shop_name) LIKE ?"
        parameters.append(f"%{search.lower()}%")

    #ak je zadany datum od
    if date_from:
        query += " AND datetime_iso >= ?"
        #aby sme mali v spravnom formate 
        parameters.append(date_from + " 00:00:00")

    #ak je datum do
    if date_to:
        query += " AND datetime_iso <= ?"
        parameters.append(date_to + " 23:59:59")

    #este zoradenie 
    query += " ORDER BY datetime_iso DESC"

    query += " LIMIT 50"

    #ziskame a zavrieme
    cur.execute(query,parameters)
    receipts = cur.fetchall()
    con.close()

    return receipts

def get_user_settings(user_id):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT username, email_address, email_filters, email_scan_limit, email_app_password, save_attachments
        FROM users
        WHERE id = ?
    """, (user_id,))

    row = cur.fetchone()
    con.close()

    if not row:
        return None


    return {
        "username": row["username"] if row["username"] else "",
        "email": row["email_address"] if row["email_address"] else "",
        "email_password": "Heslo je nastavené" if row["email_app_password"] else "Heslo ešte nie je správne nastavené",
        "email_filters": row["email_filters"] if row["email_filters"] else "",
        "email_scan_limit": row["email_scan_limit"] or 20,
        "save_attachments": bool(row["save_attachments"]) if row["save_attachments"] is not None else True
    }

#zmena mena 
def update_username(user_id, new_username):

    con = sqlite3.connect(database)
    cur = con.cursor()

    try:
        cur.execute("""
            UPDATE users
            SET username = ?
            WHERE id = ?
        """, (new_username, user_id))

        con.commit()
        changed = cur.rowcount
        con.close()

        return changed

    except sqlite3.IntegrityError:
        con.close()
        return 0

#zmena hesla
def update_user_password(user_id, password_hashed):

    con = sqlite3.connect(database)
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET password_hashed = ?
        WHERE id = ?
    """, (password_hashed, user_id))

    con.commit()
    changed = cur.rowcount
    con.close()

    return changed

#zmena nastavenia emailu
def update_email_settings(user_id, email, email_password, email_filters, email_scan_limit, save_attachments):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    #ak nie je zadane heslo, zoberie sa aktualne ulozene v db
    if not email_password:
        cur.execute("""
            SELECT email_app_password
            FROM users
            WHERE id = ?
        """, (user_id,))
        row = cur.fetchone()

        if row and row["email_app_password"]:
            encrypted_password = row["email_app_password"]
        else:
            encrypted_password = ""

    else:
        encrypted_password = encrypt_value(email_password)

    cur.execute("""
        UPDATE users
        SET email_address = ?, email_app_password = ?, email_filters = ?, email_scan_limit = ?, save_attachments = ?
        WHERE id = ?
    """, (email, encrypted_password, email_filters, email_scan_limit, save_attachments, user_id))

    con.commit()
    changed = cur.rowcount
    con.close()

    return changed

def get_save_attachments_setting(user_id):

    con = sqlite3.connect(database)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT save_attachments
        FROM users
        WHERE id = ?
    """, (user_id,))

    row = cur.fetchone()
    con.close()

    if not row:
        return True

    return bool(row["save_attachments"])
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
