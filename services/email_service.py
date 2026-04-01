import imaplib
import email
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