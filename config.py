#Konfiguracny subor pre aplikaciu
import os
import sys
import secrets
from pathlib import Path
from cryptography.fernet import Fernet

#najdeme priecinok v ktorom sa nachadza appka
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

#miesto ukladania suborov
def get_data_dir():
    if os.name == 'nt':
        base_dir = Path(os.environ.get("LOCALAPPDATA", BASE_DIR)) / "Reccio"
    else:
        base_dir = Path.home() / ".reccio"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

#ci je exe alebo py
def get_path(relative_path:str) -> Path:
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = BASE_DIR
    return base_path / relative_path

#generovanie klucov pri prvom spusteni
def get_or_create_env_keys(env_path: Path):
    existing = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

    changed = False

    if "SECRET_KEY" not in existing or not existing["SECRET_KEY"]:
        existing["SECRET_KEY"] = secrets.token_hex(32)
        changed = True

    if "EMAIL_CREDENTIALS_KEY" not in existing or not existing["EMAIL_CREDENTIALS_KEY"]:
        existing["EMAIL_CREDENTIALS_KEY"] = Fernet.generate_key().decode()
        changed = True

    if changed:
        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

    return existing["SECRET_KEY"], existing["EMAIL_CREDENTIALS_KEY"]


MAX_CONTENT_LENGTH = 5 * 1024 * 1024

DATA_DIR = get_data_dir()

ENV_PATH = Path(os.environ.get("RECCIO_ENV_PATH", BASE_DIR / ".env"))
SECRET_KEY, email_key = get_or_create_env_keys(ENV_PATH)
EMAIL_CREDENTIALS_KEY = email_key.encode()

AI_SERVER_URL = "https://reccio-ai-backend.onrender.com"

DATABASE_PATH = DATA_DIR / "receipts.db"

UPLOAD_FOLDER = DATA_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

FLASK_ENV = os.getenv("FLASK_ENV", "production").lower()
