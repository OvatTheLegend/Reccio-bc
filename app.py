from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
from werkzeug.security import generate_password_hash
from services import ai_service, email_service
import helper, parser, database
import random
import os
import config
import webbrowser
import threading
import time
import re


app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

#flask key
app.config["SECRET_KEY"] = config.SECRET_KEY

#cesty z config suboru
app.config["UPLOAD_FOLDER"] = str(config.UPLOAD_FOLDER)

#initialization of databse
database.init_database()


# ------------------------------------------------- ROUTES -------------------------------------------------------------
#aby ked je pouzivatel prihlaseny, bolo meno zobrazene v menu, nemuselo sa zakazdym posielat
@app.errorhandler(413)
def too_large(e):
    return jsonify({
        "success": False,
        "message": "Súbor je príliš veľký (max 5 MB)"
    }), 413

@app.context_processor
def inject_user():
    return dict(
        logged_in = 'user_id' in session,
        username = session.get('username'))

# LOGIN
@app.route('/', methods=['GET','POST'])
def login():

    #ak je user prihlaseny:
    if 'user_id' in session:
        return redirect(url_for('home'))

    #defaultne zobrazenie stranky login
    if request.method == 'GET':
        return render_template('login.html', show_menu = False, login_type = 'signin', error_msg = None)

    #ak nastane odoslanie udajov
    if request.method == 'POST':
        #skontrolujem ci je to signin alebo registracia
        form_type = request.form.get('form_type')

        #ak prihlasovanie
        if form_type == 'signin':
            
            #ziskam udaje z formulara
            #zvalidujem

            username = request.form.get('username_signin')
            password = request.form.get('password_signin')
            remember_me = request.form.get('remember_me')
            is_valid, user_id, error_msg = helper.validate_signin(username,password)
            
            if not is_valid:
                return render_template('login.html', show_menu = False, login_type = 'signin', error_msg = error_msg)
            
            #vsetko prebehlo uspesne, dame usera do session, redirect na domovsku stranku
            #ak je zakliknute zostat prihlaseny
            if remember_me:
                session.permanent = True

            else:
                session.permanent = False

            session['user_id'] = user_id
            session['username'] = username

            flash("Boli ste úspešne prihlásený.", "success")

            return redirect(url_for('home'))
        
        #ak registracia
        if form_type == 'register':
            #ziskam udaje z formulara, overim
            username = request.form.get('username_register')
            password = request.form.get('password_register')
            password_repeat = request.form.get('password_repeat_register')

            is_valid, error_msg = helper.validate_register(username, password, password_repeat)
            
            if not is_valid:
                return render_template('login.html', show_menu=False, login_type = 'register',error_msg = error_msg)

            #zaregistrujeme pouzivatela, zistime ci sa podarilo
            success, user_id = helper.register_user(username,password)

            if not success:
                return render_template('login.html', show_menu=False, login_type = 'register',error_msg = 'Pri registrácii sa vyskytla chyba')

            #vsetko prebehlo uspesne, usera na session, redirect na domovsku stranku
            #po zatvoreni stranky odhlasi pouzivatela
            session.permanent = False

            session['user_id'] = user_id
            session['username'] = username

            flash("Boli ste úspešne zaregistrovaný.", "success")
            return redirect(url_for('home'))
    
    return render_template('login.html', show_menu = False, login_type = 'signin', error_msg = None)

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# DOMOV
@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    uncategorized_count = helper.get_uncategorized_count(user_id)

    dashboard_stats = helper.get_dashboard_per_month_stats(user_id)
    last_receipts = helper.get_last_5_receipts(user_id)
    expensive_receipts = helper.get_top_5_expensive(user_id)
    #graf

    expenses_chart = helper.get_daily_expenses_for_current_month(user_id)
    category_chart = helper.get_category_stat_for_current_month(user_id)


    return render_template('home.html',
        dashboard_stats = dashboard_stats,
        last_receipts = last_receipts,
        expensive_receipts = expensive_receipts,
        expenses_chart = expenses_chart,
        category_chart = category_chart,
        uncategorized_count = uncategorized_count,
        show_menu = True
        )

@app.route('/categorize_all_items', methods=['POST'])
def categorize_all_items():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Neprihlásený používateľ"}), 401

    user_id = session.get('user_id')

    uncategorized_items = helper.get_uncategorized_items(user_id)

    if not uncategorized_items:
        return jsonify({
        "success": True, 
        "updated_count": 0, 
        "message": "Všetky položky majú svoje kategórie." })

    groups = helper.split_into_groups(uncategorized_items, 40)

    updated_count = 0

    for group in groups:
        categorized_items = ai_service.categorize_items_ai(group)

        if isinstance(categorized_items, dict) and categorized_items.get("success") is False:
            return jsonify({
                "success": False,
                "message": categorized_items.get("message", "AI kategorizácia zlyhala.")
            })

        if categorized_items is None:
            return jsonify({
                "success": False,
                "message": "AI server nie je dostupný alebo nie je správne nakonfigurovaný."
            })
        
        for item in categorized_items:
            changed = helper.categorize_items(item["id"], item["category"])
            updated_count += changed
    
    return jsonify({
        "success": True, 
        "updated_count": updated_count, 
        "message": f"{updated_count} položkám boli priradené kategórie."})



# MOJE BLOCKY
@app.route('/receipts')
def receipts():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    #najprv ziskame filtre z url
    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from','').strip()
    date_to = request.args.get('date_to','').strip()

    #ak nieje zadany filter zobrazime vsetky
    if not search and not date_from and not date_to:
        receipts = helper.get_all_receipts(user_id)

    else:
        receipts = helper.get_filtered_receipts(user_id,search, date_from, date_to)

    return render_template(
    'receipts.html',
        receipts = receipts,
        show_menu = True,
        search = search,
        date_from = date_from,
        date_to = date_to,
    )
    
@app.route('/delete_receipt/<int:receipt_id>', methods=['DELETE'])
def delete_receipt(receipt_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    file_path = helper.get_file_path(receipt_id, user_id)

    deleted = helper.delete_receipt(receipt_id, user_id)

    #ak sa nevymazal, tak chyba
    if deleted == 0:
        return jsonify({"error" : "Neautorizované"}), 403
    #vraciame json object nie render (kvoli dynamickosti stranke -> bez zbytocneho reloadu)
    
    #odstraninie z disku
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    return jsonify({"success": True})

@app.route('/receipt_details/<int:receipt_id>')
def receipt_details(receipt_id):
    
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    
    #ziskame itemy

    items = helper.get_items(receipt_id, user_id)

    return jsonify(items)

@app.route('/receipt_file/<int:receipt_id>')
def receipt_origin(receipt_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))


    #ziskame user user_id so session a podla nej najdeme folder usera
    user_id = session.get('user_id')
    file_path = helper.get_file_path(receipt_id, user_id)

    if file_path is None or not os.path.exists(file_path):
        return "Súbor sa nenašiel", 404

    #ak vsetko v poriadku tak send file_path
    return send_file(file_path)

@app.route('/stats')
def stats():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    #ziskame datumy z filtrov, ak nie su bude default 6 mesiacov
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    if not date_from or not date_to:
        date_from, date_to = helper.get_default_stats_date_range()

    #pre 4 karticky
    summary_stats = helper.get_stats_summary_cards(user_id, date_from, date_to)

    #velky mesacny graf
    monthly_chart = helper.get_monthly_expenses(user_id, date_from, date_to)

    #graf kategorii
    category_chart = helper.get_category_monthly_expenses(user_id, date_from, date_to)

    #graf vydavkov na obchod
    shop_chart = helper.get_shop_monthly_expenses(user_id, date_from, date_to)
    return render_template('stats.html', 
        show_menu = True,
        date_from = date_from,
        date_to = date_to,
        summary_stats = summary_stats,
        monthly_chart=monthly_chart,
        category_chart=category_chart,
        shop_chart = shop_chart)

#default upload nacitanie stranky
@app.route('/upload', methods=['GET'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('upload.html', show_menu=True)

#pdf upload
@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    #get file with request of file name
    file = request.files.get("receipt_file_pdf")

    if not file or file.filename == "":
        return jsonify({"success": False, "message": "Vyberte súbor"})

    extension = file.filename.rsplit('.')[-1].lower()

    #povolene typy
    allowed = {
        'pdf'
    }

    if extension not in allowed:
        return jsonify({"success": False, "message": "Podporované formáty: pdf"})

    user_id = session.get('user_id')
    
    #creating unique folder for specific user
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], f'user{user_id}')
    os.makedirs(user_folder, exist_ok=True)

    
    temp_filename = f'temp_{file.filename}'
    file_path = os.path.join(user_folder, temp_filename)
    file.save(file_path)

    result = helper.process_pdf_receipt(file_path, user_id)

    if not result["success"]:

        if os.path.exists(file_path):
            os.remove(file_path)

        if result["error"] == "duplicate":
            return jsonify({"success": False, "message": "Bloček už existuje"})

        return jsonify({
            "success": False,
            "message": result.get("message", "Nepodarilo sa spracovať bloček")
        })

    return jsonify({ "success": True, "message": "Bloček bol úspešne uložený" })

#obrazok
@app.route('/upload_img', methods=['POST'])
def upload_img():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    #get file with request of file name
    file = request.files.get("receipt_file_img")

    if not file or file.filename == "":
        return jsonify({"success": False, "message": "Vyberte súbor"})

    #zistime typ suboru
    extension = file.filename.rsplit('.')[-1].lower()

    #povolene typy
    allowed = {
        'jpg','jpeg','png'
    }

    if extension not in allowed:
        return jsonify({"success": False, "message": "Podporované formáty: png, jpeg, jpg"})

    user_id = session.get('user_id')
    
    #creating unique folder for specific user
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], f'user{user_id}')
    os.makedirs(user_folder, exist_ok=True)

    #saving file (FOR FUTURE ADD TIMESTAMP TO PREVENT SAME NAME FILE)
    temp_filename = f'temp_{file.filename}'
    file_path = os.path.join(user_folder, temp_filename)
    file.save(file_path)


    #zavolanie parsera ai
    ai_result = ai_service.ai_parser_img(file_path)

    if not ai_result:
        os.remove(file_path)
        return jsonify({
            "success": False,
            "message": "Nepodarilo sa načítať bloček."
        })

    if isinstance(ai_result, dict) and ai_result.get("success") is False:
        os.remove(file_path)
        return jsonify({
            "success": False,
            "message": ai_result.get("message", "AI spracovanie zlyhalo.")
        })

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
    receipt_id = helper.save_receipt(parsed_receipt, parsed_items, user_id, "ai")

    #ak chyba pri ukladani
    if receipt_id is None:
        os.remove(file_path)
        return jsonify({"success": False, "message": "Skontrolujte či už bloček nie je pridaný"})

    save_attachments = helper.get_save_attachments_setting(user_id)

    if save_attachments:        
    #rename the file_pre-saved
        final_filename = f'r_{receipt_id}.{extension}'
        final_file_path = os.path.join(user_folder,final_filename)
        os.rename(file_path, final_file_path)

        #ulozime cestu k suboru pre zobrazovanie originalu
        helper.save_file_path(receipt_id, final_file_path)
    else:
        os.remove(file_path)

    return jsonify({ "success": True, "message": "Bloček bol úspešne uložený" })

#manualny upload
@app.route('/upload_manual', methods=['POST'])
def upload_manual():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    data = request.get_json()
    user_id = session.get('user_id')

    #naplnime blocek
    receipt = {
        "shop_name": data["shop_name"],
        "date": data["date"],
        "time": data["time"],
        "price": data["price"],
    }

    #teraz itemy
    items = data["items"]

    #ulozime blocek
    receipt_id = helper.save_receipt(receipt, items, user_id, "manual")

    #ak sa nepodari
    if receipt_id is None:
        return jsonify({"success": False, "message": "Skontrolujte či už bloček nie je pridaný"})
    
    return jsonify({"success": True, "message": "Bloček bol úspešne uložený"})
    
@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    settings_data = helper.get_user_settings(user_id)

    return render_template(
        "settings.html",
        show_menu=True,
        settings=settings_data
    )

@app.route('/settings/update-profile', methods=['POST'])
def update_profile():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Neprihlásený používateľ"}), 401
    
    user_id = session.get('user_id')

    #ziskame meno
    new_username = request.form.get('username', '').strip()

    #ak nie je zadane meno
    if not new_username:
        return jsonify({"success": False, "message": "Používateľské meno nemôže byť prázdne."}), 400

    
    if len(new_username) < 3:
        return jsonify({"success": False, "message": "Používateľské meno musí mať aspoň 3 znaky!"}), 400
    
    if len(new_username) > 25:
        return jsonify({"success": False, "message": "Používateľské meno je príliš dlhé (max 25 znakov)!"}), 400

    current_settings = helper.get_user_settings(user_id)
    current_username = current_settings["username"]

    if new_username != current_username and not helper.is_unique_username(new_username):
        return jsonify({"success": False, "message": "Používateľské meno už existuje."}), 400

    changed = helper.update_username(user_id, new_username)

    if not changed:
        return jsonify({"success": False, "message": "Používateľské meno sa nepodarilo zmeniť."}), 400

    session['username'] = new_username

    return jsonify({"success": True, "message": "Používateľské meno bolo aktualizované."})

#zmena hesla
@app.route('/settings/update-password', methods=['POST'])
def update_password():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Neprihlásený používateľ"}), 401

    user_id = session.get('user_id')
    new_password = request.form.get('new_password', '').strip()

    if not new_password:
        return jsonify({"success": False, "message": "Nové heslo nemôže byť prázdne."}), 400

    if len(new_password) < 5:
        return jsonify({"success": False, "message": "Heslo je príliš kratke (min 5 znakov)!"}), 400

    new_password_hashed = generate_password_hash(new_password)
    changed = helper.update_user_password(user_id, new_password_hashed)

    if not changed:
        return jsonify({"success": False, "message": "Heslo sa nepodarilo zmeniť."}), 400

    return jsonify({"success": True, "message": "Heslo bolo úspešne zmenené."})

#update pre email
@app.route('/settings/update-email', methods=['POST'])
def update_email_settings():

    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Neprihlásený používateľ"}), 401

    user_id = session.get('user_id')

    email_value = request.form.get('email', '').strip()

    #regex na validaciu gmailu
    gmail_pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'

    if not re.match(gmail_pattern, email_value) and email_value:
        return jsonify({
            "success": False,
            "message": "Povolené sú iba Gmail adresy (@gmail.com)"
        }), 400

    email_password = request.form.get('email_password', '').strip()
    email_password = email_password.replace(" ", "")

    email_filters = request.form.get('email_filters', '').strip()
    email_scan_limit = request.form.get('email_scan_limit', '').strip() or '20'

    if request.form.get("save_attachments") == "on":
        save_attachments = 1
    else:
        save_attachments = 0


    allowed_limits = {"20", "50", "100"}

    if email_scan_limit not in allowed_limits:
        return jsonify({
            "success": False,
            "message": "Neplatný limit emailov."
        }), 400

    changed = helper.update_email_settings(user_id, email_value, email_password, email_filters, int(email_scan_limit), save_attachments)

    if not changed:
        return jsonify({"success": False, "message": "Emailové nastavenia sa nepodarilo uložiť."}), 400

    return jsonify({"success": True, "message": "Emailové nastavenia boli uložené."})

@app.route('/import-email-receipts', methods=['POST'])
def import_email_receipts():

    #overime pirhlasenie

    if 'user_id' not in session:
        return jsonify({
            "success": False,
            "message": "Neprihlásený používateľ."
        }), 401

    user_id = session.get('user_id')
    settings = helper.get_user_settings(user_id)

    email_user = settings["email"]
    email_password = helper.get_decrypted_email_password(user_id)
    email_filters = settings["email_filters"]
    scan_limit = settings["email_scan_limit"]

    filters = [f.strip() for f in email_filters.splitlines() if f.strip()]

    #validacie
    if not email_user:
        return jsonify({
            "success": False,
            "message": "Najprv si nastavte Gmail adresu v nastaveniach."
        }), 400

    if not email_password:
        return jsonify({
            "success": False,
            "message": "Najprv si nastavte App Password v nastaveniach."
        }), 400

    if not filters:
        return jsonify({
            "success": False,
            "message": "Najprv si nastavte filtre emailov alebo obchodov v nastaveniach."
        }), 400

    result = email_service.import_receipts_from_email(
        email_user,
        email_password,
        filters,
        user_id,
        scan_limit
    )

    return jsonify(result)


# --------------------------------------------------------------------------------------------------------------

#automaticke otvorenie prehliadaca pri spusteni appky
def open_webbrowser():

    #po chvili sa otvori prehliaiacdac
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5000')



if __name__ == '__main__':


    #otvori prehlaidac
    threading.Thread(target=open_webbrowser, daemon=True).start()
    
    #spusti flask
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )

