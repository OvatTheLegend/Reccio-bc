from flask import Flask, render_template, request
import random, database, helper, os, parser


app = Flask(__name__)

#if uploads folder does not exist, create one,
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#initialization of databse
database.init_database()


# ------------------------------------------------- ROUTES -------------------------------------------------------------

# DOMOV
@app.route('/')
def index():
    last_receipts = helper.get_last_5_receipts()
    expensive_receipts = helper.get_top_5_expensive()

    return render_template('index.html', last_receipts = last_receipts, expensive_receipts = expensive_receipts)

# MOJE BLOCKY
@app.route('/moje_blocky')
def moje_blocky():
    receipts = helper.get_all_receipts()
    return render_template('receipts.html', receipts = receipts)

@app.route('/stats')
def stats():
    return render_template('stats.html')


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
                    receipt_id = helper.save_new_receipt(parsed_receipt)
                    if receipt_id is not None:
                        helper.save_new_items(parsed_items, receipt_id)
                        message = "Bloček bol úspešne uložený"
                    else: message = "Bloček už existuje"
                
                else:
                    message = "Nepodarilo sa uložiť položky bločku"

            else:
                message = "Nepodarilo sa uložiť bloček"

    return render_template('upload.html',  message = message)

@app.route('/settings')
def settings():
    return render_template('settings.html')

# --------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    print("Aplikacia beži:")
    app.run(debug=True)