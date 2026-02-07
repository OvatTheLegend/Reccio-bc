from flask import Flask, render_template, request, redirect, url_for, session
import random, database, helper, os, parser


app = Flask(__name__)
app.secret_key = 'moj_tajny_klucik_123'

#if uploads folder does not exist, create one,
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
            is_valid, user_id, error_msg = helper.validate_signin(username,password)
            
            if not is_valid:
                return render_template('login.html', show_menu = False, login_type = 'signin', error_msg = error_msg)
            
            #vsetko prebehlo uspesne, dame usera do session, redirect na domovsku stranku
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
    user_id = session.get('user_id')
    last_receipts = helper.get_last_5_receipts(user_id)
    expensive_receipts = helper.get_top_5_expensive(user_id)

    return render_template('home.html', last_receipts = last_receipts, expensive_receipts = expensive_receipts, show_menu = True)

# MOJE BLOCKY
@app.route('/moje_blocky')
def moje_blocky():
    user_id = session.get('user_id')
    receipts = helper.get_all_receipts(user_id)
    return render_template('receipts.html', receipts = receipts, show_menu = True)

@app.route('/stats')
def stats():
    return render_template('stats.html', show_menu = True)


#route for adding a new receipt into database: -> GET if default
#                                              -> POST if pdf file was submitted
@app.route('/upload', methods=['GET','POST'])
def upload():

    message = ""
    #if pdf was submited
    if request.method == 'POST':
        #get file with request of file name
        file = request.files.get("receipt_file")

        if file and file.filename != "":

            #getting path of folder to save submitted file and saving it there
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
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
                if parsed_items:
                    #saving data to database
                    user_id = session.get('user_id')
                    receipt_id = helper.save_new_receipt(parsed_receipt, user_id, "manual")
                    if receipt_id is not None:
                        helper.save_new_items(parsed_items, receipt_id)
                        message = "Bloček bol úspešne uložený"
                    else: message = "Bloček už existuje"
                
                else:
                    message = "Nepodarilo sa uložiť položky bločku"

            else:
                message = "Nepodarilo sa uložiť bloček"

    return render_template('upload.html',  message = message, show_menu = True)

@app.route('/settings')
def settings():
    return render_template('settings.html', show_menu = True)

# --------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    print("Aplikacia beži:")
    app.run(debug=True)