import imaplib
import email
import uuid
from helper import process_pdf_receipt
from email.header import decode_header
import os

def fetch_receipt_emails(email_user, email_password, filters):

    try:
        # pripojenie pre gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")

        #login 
        mail.login(email_user, email_password)

        #inbox
        mail.select("inbox")

        #vyhladavanie emailov v inboxe
        status, messages = mail.search(None, "ALL")

        #splitneme samostatne
        email_ids = messages[0].split()

        #ukladanie emailov po filty
        results = []
        
        for eid in email_ids[-20:]: #poslednych 2 emailov

            #nacitanie celeho obsahu spravy 
            status, msg_data = mail.fetch(eid, "(RFC822)") 
            
            #msg_data moze obsahovat viacero casti
            for response_part in msg_data: 

                #ak sprava ma nejaky obsah
                if isinstance(response_part, tuple):

                    #vytvorenie email objectu (subject | from | attachments | body)
                    msg = email.message_from_bytes(response_part[1])

                    subject, encoding = decode_header(msg["Subject"])[0]

                    #convert na obycajny text ak je v bytes
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")

                    #ziskanie hlavicky
                    from_email = msg.get("From")


                    # filtre, teda ak pouzivatel zadal filtre, skontroluje sa odosielatel, ak nepatri medzi filtre skip
                    if filters:
                        match = False
                        for f in filters:
                            if f.lower() in str(from_email).lower() or f.lower() in subject.lower():
                                match = True
                                break
                        if not match:
                            continue
                    
                    #ulozime odosielatela a predmet
                    results.append({
                        "subject": subject,
                        "from": from_email
                    })

        #logout po ukonceni
        mail.logout()
        return results

    except Exception as e:
        print("Email chyba:", e)
        return None

def import_receipts_from_email(user_email, user_email_password, filters, user_id, scan_limit):
    
    try:

        #ak nie su filtre tak nejdeme dalej
        if not filters:
            return {
                "success": False,
                "message": "Najprv si nastavte filtre emailov alebo obchodov v nastaveniach.",
                "results": []
            }

        #ssl pripojenie na gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
    
        #prihlasenie do emailu usera
        mail.login(user_email, user_email_password)

        #budeme prezeraz inbox
        mail.select("inbox")

        #pozrieme vsetky spravy v inboxe
        status, messages = mail.search(None, "ALL")

        #ak chyba vratime 
        if status != "OK":
            mail.logout()
            return {
                "success": False,
                "message": "Nepodarilo sa načítať emaily.",
                "results": []
            }
        
        email_ids = messages[0].split()

        #zoberieme podla filtru pocet emailov
        email_ids = email_ids[-scan_limit:]

        #ukladame vysledok importu kazdej prilohy
        results = []

        #ak neexeistuje folder tak vytvorime
        user_folder = os.path.join("uploads", f"user{user_id}")
        os.makedirs(user_folder, exist_ok=True)

        #iterujeme poslednych x mailov
        for eid in email_ids:

            #nacitanie celeho obsahu spravy 
            status, msg_data = mail.fetch(eid, "(RFC822)")

            if status != "OK":
                continue

            #msg_data moze mat viac casti preto ideme cez vsetky, moze obsahovat stringy aj tuple atd...
            for response_part in msg_data:
                
                #skutocne emialove data obsahuju iba tuple, takze ak neni tak skip
                if not isinstance(response_part, tuple):
                    continue

                #prekonvertujeme byty emailu na python object
                msg = email.message_from_bytes(response_part[1])

                subject_raw = msg["Subject"]
                if subject_raw:
                    subject, encoding = decode_header(subject_raw)[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                else:
                    subject = ""

                #nacitanie hlavicky
                from_email = msg.get("From")

                #filtre pouzivatela
                match = False

                print("FROM:", from_email)
                print("SUBJECT", subject)
                print("FILTERS:", filters)
                    
                #ak hlavicka alebo predmet obsahuje filter, tak breakneme a ideme dalej, inak iterujeme na dalsi email
                for f in filters:
                    if f.lower() in str(from_email) or f.lower() in subject.lower():
                        match = True
                        break

                    if not match:
                        continue
                    
                #prejdeme vsetky casty konkretneho emailu
                for part in msg.walk():

                    content_disposition = str(part.get("Content-Disposition") or "")
                    
                    #ak casti nemaju prilohu, tak ideme na dalsiu iteraciu
                    if "attachment" not in content_disposition:
                        continue

                    #ako ano, ziskame meno
                    filename = part.get_filename()
                    if not filename:
                        continue

                    #ak je encodovany, tak decodujeme
                    decoded_name, enc = decode_header(filename)[0]
                    if isinstance(decoded_name, bytes):
                        filename = decoded_name.decode(enc if enc else "utf-8", errors="ignore")
                    else:
                        filename = decoded_name

                    #ak neni pdf, tiez na dalsiu iteraciu
                    if not filename.lower().endswith(".pdf"):
                        continue
                    
                    #vytvorime temporary path, ak sa nepodari parser, ani AI, tak zmazeme
                    temp_name = f"temp_{uuid.uuid4()}.pdf"
                    temp_path = os.path.join(user_folder, temp_name)

                    #zapiseme binarny subor do preicinku
                    with open(temp_path, "wb") as f:
                        f.write(part.get_payload(decode=True))

                    print("TEMP SAVED:", temp_path)

                    #zavolame funkciu na parser
                    process_result = process_pdf_receipt(temp_path, user_id)
                    
                    #ak sa podarilo tak pridame do results
                    if process_result["success"]:
                        results.append({
                            "file": filename,
                            "status": "imported",
                            "parse_method": process_result.get("parse_method", "")
                        })

                    #ak zlyhalo
                    else:
                        # ak zlyhalo alebo je duplicate, temp subor moze stale existovat
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                        #ak duplicate vraime duplicate error status
                        if process_result["error"] == "duplicate":
                            results.append({
                                "file": filename,
                                "status": "duplicate"
                            })

                        #ak bola chyba niekde inde
                        elif process_result["error"] == "parse_failed":
                            results.append({
                                "file": filename,
                                "status": "failed"
                            })

                        else:
                            results.append({
                                "file": filename,
                                "status": "failed"
                            })

        mail.logout()

        #vratime results
        return {
            "success": True,
            "message": "Import emailov bol dokončený.",
            "results": results
        }

    except Exception as e:
        print("IMPORT EMAIL CHYBA:", e)
        return {
            "success": False,
            "message": "Nepodarilo sa spracovať emaily, skontrolujte internetové pripojenie.",
            "results": []
        }

