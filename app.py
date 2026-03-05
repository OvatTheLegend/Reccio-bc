from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import helper, parser, database
import random
import os
import config
import webbrowser
import threading
import time


app = Flask(__name__)
app.secret_key = 'moj_tajny_klucik_123'

#cesty z config suboru
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

#initialization of databse
database.init_database()


# ------------------------------------------------- ROUTES -------------------------------------------------------------
#aby ked je pouzivatel prihlaseny, bolo meno zobrazene v menu, nemuselo sa zakazdym posielat
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
                print("zapamatal som si")

            else:
                session.permanent = False
                print("odhlasim po zatvoreni")

            session['user_id'] = user_id
            session['username'] = username

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
            print("odhlasim po zatvoreni")

            session['user_id'] = user_id
            session['username'] = username

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
    last_receipts = helper.get_last_5_receipts(user_id)
    expensive_receipts = helper.get_top_5_expensive(user_id)

    return render_template('home.html', last_receipts = last_receipts, expensive_receipts = expensive_receipts, show_menu = True)

# MOJE BLOCKY
@app.route('/moje_blocky')
def moje_blocky():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    receipts = helper.get_all_receipts(user_id)
    return render_template('receipts.html', receipts = receipts, show_menu = True)

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

    return render_template('stats.html', show_menu = True)


#route for adding a new receipt into database: -> GET if default
#                                              -> POST if file was submitted
@app.route('/upload', methods=['GET','POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    #if pdf was submited
    if request.method == 'POST':
        #get file with request of file name
        file = request.files.get("receipt_file")

        if file and file.filename != "":

            user_id = session.get('user_id')
            
            #creating unique folder for specific user
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], f'user{user_id}')
            os.makedirs(user_folder, exist_ok=True)

            #saving file (FOR FUTURE ADD TIMESTAMP TO PREVENT SAME NAME FILE)
            temp_filename = f'temp_{file.filename}'
            file_path = os.path.join(user_folder, temp_filename)
            file.save(file_path)

            #extraction of text from pdf, parsing, 
            pdf_text = parser.extract_from_pdf(file_path)

            #receipt
            print("entering receipt section")
            parsed_receipt = parser.parse_receipt(pdf_text)
            if parsed_receipt:
                
                #items
                print("entering item section")
                parsed_items = parser.parse_items_universal(parsed_receipt["shop_name"], pdf_text)
                if parsed_items is not None:
                    #saving data to database
                    user_id = session.get('user_id')
                    receipt_id = helper.save_new_receipt(parsed_receipt, user_id, "manual")
                    if receipt_id is not None:
                        #rename the file_pre-saved
                        final_filename = f'r_{receipt_id}.pdf'
                        final_file_path = os.path.join(user_folder,final_filename)
                        os.rename(file_path, final_file_path)

                        #save items 
                        helper.save_new_items(parsed_items, receipt_id)

                        #save path to file
                        helper.save_file_path(receipt_id, final_file_path)

                        #vratime upozornenie
                        return jsonify({ "success": True, "message": "Bloček bol úspešne uložený" })
                    else: 
                        return jsonify({ "success": False, "message": "Bloček už existuje" })
                
                else:
                    #delete temporary file if not sucess
                    os.remove(file_path)
                    return jsonify({ "success": False, "message": "Nepodarilo sa uložiť položky bločku" })

            else:
                os.remove(file_path)
                return jsonify({ "success": False, "message": "Nepodarilo sa uložiť bloček" })

    return render_template('upload.html', show_menu = True)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html', show_menu = True)

# --------------------------------------------------------------------------------------------------------------

#automaticke otvorenie prehliadaca pri spusteni appky
def open_webbrowser():
    time.asleep(2)
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print("🌐 Appka beží na: http://localhost:5000")


    #otvori prehlaidac
    threading.Thread(target=open_webbrowser, daemon=True).start
    
    #spusti flask s debugom
    app.run(debug=True)