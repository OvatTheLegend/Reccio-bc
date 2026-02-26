#Konfiguracny subor pre aplikaciu
import os
import sys

def get_data_dir():

    #zistime ci ide o windows alebo linux
    #windows
    if os.name == 'nt':
        base_dir = os.path.join(os.environ['LOCALAPPDATA'], 'ComfyeBlok')
    #linux
    else:
        base_dir = os.path.join(os.path.expanduser('~'), '.comfyeblok')

    #ak existuje ok, ak nie vytvori
    os.makedirs(base_dir, exist_ok=True)
    
    return base_dir

#ci je exe alebo py -> lebo py robim, najrpv -> potom az zabalim do exe
def get_path(relative_path):
    try:
        #ak je exe, vytvara sa priecinok MEIPASS
        base_path = sys.MEIPASS
    except:
        #py
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

#priecinok data_dir
DATA_DIR = get_data_dir()

#databaza subor
DATABASE_PATH = os.path.join(DATA_DIR, 'receipts.db')

#precinok pre uploady
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')

#secret_key
SECRET_KEY_PATH = os.path.join(DATA_DIR,'.seckret.key')

# Debug info (zobrazí sa v konzole pri spustení)
print("=" * 60)
print("📂 ComfyeBlok - Konfigurácia ciest")
print("=" * 60)
print(f"App data dir:  {DATA_DIR}")
print(f"Upload folder: {UPLOAD_FOLDER}")
print(f"Database:      {DATABASE_PATH}")
print(f"Secret key:    {SECRET_KEY_PATH}")
print("=" * 60)
