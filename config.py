#Konfiguracny subor pre aplikaciu
import os
import sys
import secrets
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("EMAIL_CREDENTIALS_KEY")

if not key:
    raise Exception("Missing EMAIL_CREDENTIALS_KEY in .env")

EMAIL_CREDENTIALS_KEY = key.encode()

#najdeme priecinok v ktorom sa nachadza 
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent


#nacitame env subor
load_dotenv(BASE_DIR / ".env")

#miesto ukladania suborov
def get_data_dir():

    #zistime ci ide o windows alebo linux
    #windows
    if os.name == 'nt':
        base_dir = Path(os.environ.get("LOCALAPPDATA", BASE_DIR)) / "Reccio"
    #linux
    else:
        base_dir = Path.home() / ".reccio"

    #ak existuje ok, ak nie vytvori
    base_dir.mkdir(parents=True, exist_ok=True)
    
    return base_dir

#ci je exe alebo py -> lebo py robim, najrpv -> potom az zabalim do exe
def get_path(relative_path:str) -> Path:
    try:
        #ak je exe, vytvara sa priecinok MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        #py
        base_path = BASE_DIR
    
    return base_path / relative_path

#tiskame secret key pre flask appku, ak nie je definovany, vygenerujeme a ulozime
def get_or_create_secret_key(secret_key_path: Path) -> str:

    #ziskame kluc
    secret_key = os.getenv("SECRET_KEY")

    if secret_key:
        return secret_key

    if secret_key_path.exists():
        return secret_key_path.read_text(encoding="utf-8").strip()

    #ak neexistuje tak vygenerujeme
    generated_secret_key = secrets.token_hex(32)

    #zapiseme 
    secret_key_path.write_text(generated_secret_key, encoding="utf-8")

    return generated_secret_key

def load_app_settings():
    if not APP_SETTINGS_PATH.exists():
        default_settings = {"ai_server_url": ""}
        APP_SETTINGS_PATH.write_text(
            json.dumps(default_settings, ensure_ascii=False, indent=4),
            encoding="utf-8"
        )
        return default_settings

    try:
        with open(APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return {
            "ai_server_url" : data.get("ai_server_url", "").strip()
        }
    
    except Exception as e:
        print("Chyba pri načítaní app_settings:", e)
        return{
            "ai_server_url" : ""
        }

#priecinok data_dir
DATA_DIR = get_data_dir()

#cesta k jsonu kde je nazov serveru
APP_SETTINGS_PATH = BASE_DIR / "app_settings.json"

APP_SETTINGS = load_app_settings()

#url servera
AI_SERVER_URL = APP_SETTINGS["ai_server_url"]

#databaza subor
DATABASE_PATH = DATA_DIR / "receipts.db"

#precinok pre uploady
UPLOAD_FOLDER = DATA_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

#secret_key cesta
SECRET_KEY_PATH = DATA_DIR / ".secret_key"

#secret key 
SECRET_KEY = get_or_create_secret_key(SECRET_KEY_PATH)

#openai key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# rezim appky defaultne production
FLASK_ENV = os.getenv("FLASK_ENV", "production").lower()

print(f"APP_SETTINGS:  {APP_SETTINGS_PATH}")
print(f"AI_SERVER_URL: {AI_SERVER_URL}")

# Debug info (zobrazí sa v konzole pri spustení)
print("=" * 60)
print("Reccio - konfiguracia")
print("=" * 60)
print(f"BASE_DIR:      {BASE_DIR}")
print(f"DATA_DIR:      {DATA_DIR}")
print(f"UPLOAD_FOLDER: {UPLOAD_FOLDER}")
print(f"DATABASE_PATH: {DATABASE_PATH}")
print(f"SECRET_FILE:   {SECRET_KEY_PATH}")
print(f"FLASK_ENV:     {FLASK_ENV}")
print("=" * 60)