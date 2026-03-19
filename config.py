#Konfiguracny subor pre aplikaciu
import os
import sys
import secrets
from pathlib import Path
from dotenv import load_dotenv

#najdeme priecinok v ktorom sa nachadza 
BASE_DIR = Path(__file__).resolve().parent

#nacitame env subor
load_dotenv(BASE_DIR / ".env")

#miesto ukladania suborov
def get_data_dir():

    #zistime ci ide o windows alebo linux
    #windows
    if os.name == 'nt':
        base_dir = Path(os.environ.get("LOCALAPPDATA", BASE_DIR)) / "ComfyeBlok"
    #linux
    else:
        base_dir = Path.home() / ".comfyeblok"

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
    secret_key_path.write(generated_secret_key, encoding="utf-8")

    return generated_secret_key


#priecinok data_dir
DATA_DIR = get_data_dir()

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

#debugovanie len v development
DEBUG = FLASK_ENV == "development"

# Debug info (zobrazí sa v konzole pri spustení)
print("=" * 60)
print("ComfyeBlok - konfiguracia")
print("=" * 60)
print(f"BASE_DIR:      {BASE_DIR}")
print(f"DATA_DIR:      {DATA_DIR}")
print(f"UPLOAD_FOLDER: {UPLOAD_FOLDER}")
print(f"DATABASE_PATH: {DATABASE_PATH}")
print(f"SECRET_FILE:   {SECRET_KEY_PATH}")
print(f"FLASK_ENV:     {FLASK_ENV}")
print(f"DEBUG:         {DEBUG}")
print("=" * 60)