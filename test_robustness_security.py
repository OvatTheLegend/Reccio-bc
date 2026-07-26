import atexit
import io
import os
import shutil
import sqlite3
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
_TEST_DATA_ROOT = ROOT / "testing_runtime_robustness" / f"run_{os.getpid()}"
_TEST_DATA_ROOT.mkdir(parents=True, exist_ok=True)
atexit.register(lambda: shutil.rmtree(_TEST_DATA_ROOT, ignore_errors=True))

os.environ["LOCALAPPDATA"] = str(_TEST_DATA_ROOT)
os.environ["FLASK_ENV"] = "testing"
os.environ["RECCIO_ENV_PATH"] = str(_TEST_DATA_ROOT / ".env")

import app as flask_app_module
import config
import database
import helper


TESTING_DIR = ROOT / "TESTING"
THESIS_PDF = TESTING_DIR / "thesis.pdf"


class RobustnessAndSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = flask_app_module.app
        self.app.config.update(TESTING=True)

        if Path(config.DATABASE_PATH).exists():
            Path(config.DATABASE_PATH).unlink()

        Path(config.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
        for child in Path(config.UPLOAD_FOLDER).iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

        database.init_database()
        self.client = self.app.test_client()

    def register(self, username="tester", password="secret1"):
        return self.client.post(
            "/",
            data={
                "form_type": "register",
                "username_register": username,
                "password_register": password,
                "password_repeat_register": password,
            },
            follow_redirects=False,
        )

    def login_user(self):
        self.register()

    def manual_payload(self, **overrides):
        payload = {
            "shop_name": "Manual Shop",
            "date": "12.05.2026",
            "time": "09:30",
            "price": 12.34,
            "items": [{"item_name": "Chlieb", "amount": 1, "price": 2.5}],
        }
        payload.update(overrides)
        return payload

    def db_rows(self, query, params=()):
        con = sqlite3.connect(config.DATABASE_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(query, params).fetchall()
        con.close()
        return rows

    def table_exists(self, table_name):
        rows = self.db_rows(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return bool(rows)

    def assert_no_receipts_saved(self):
        self.assertEqual(self.db_rows("SELECT * FROM receipts"), [])
        self.assertEqual(self.db_rows("SELECT * FROM items"), [])

    def test_empty_pdf_upload_is_rejected_without_database_write(self):
        self.login_user()

        response = self.client.post(
            "/upload_pdf",
            data={"receipt_file_pdf": (io.BytesIO(b""), "empty.pdf")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_pdf_without_receipt_data_is_rejected_without_database_write(self):
        self.login_user()

        with patch(
            "helper.ai_service.ai_parser_text",
            return_value={"success": False, "error": "parse_failed", "message": "Nepodarilo sa spracovať bloček."},
        ):
            with THESIS_PDF.open("rb") as pdf:
                response = self.client.post(
                    "/upload_pdf",
                    data={"receipt_file_pdf": (pdf, "thesis.pdf")},
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_unsupported_pdf_file_extension_is_rejected(self):
        self.login_user()

        response = self.client.post(
            "/upload_pdf",
            data={"receipt_file_pdf": (io.BytesIO(b"text"), "receipt.txt")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_unsupported_image_file_extension_is_rejected(self):
        self.login_user()

        response = self.client.post(
            "/upload_img",
            data={"receipt_file_img": (io.BytesIO(b"bitmap"), "receipt.bmp")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_manual_upload_rejects_negative_total_price(self):
        self.login_user()

        response = self.client.post("/upload_manual", json=self.manual_payload(price=-1))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_manual_upload_rejects_empty_shop_name(self):
        self.login_user()

        response = self.client.post("/upload_manual", json=self.manual_payload(shop_name=""))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_manual_upload_rejects_future_purchase_date(self):
        self.login_user()
        future_date = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")

        response = self.client.post("/upload_manual", json=self.manual_payload(date=future_date))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_duplicate_registration_is_rejected(self):
        self.register(username="tester", password="secret1")
        self.client.get("/logout")

        response = self.register(username="tester", password="secret1")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"login", response.data.lower())
        self.assertEqual(len(self.db_rows("SELECT * FROM users WHERE username = ?", ("tester",))), 1)

    def test_wrong_password_login_is_rejected(self):
        self.register(username="tester", password="secret1")
        self.client.get("/logout")

        response = self.client.post(
            "/",
            data={
                "form_type": "signin",
                "username_signin": "tester",
                "password_signin": "wrong",
            },
        )

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_email_import_with_invalid_credentials_returns_error(self):
        self.login_user()
        self.client.post(
            "/settings/update-email",
            data={
                "email": "tester@gmail.com",
                "email_password": "badpassword",
                "email_filters": "coop",
                "email_scan_limit": "20",
                "save_attachments": "on",
            },
        )

        with patch(
            "app.email_service.import_receipts_from_email",
            return_value={
                "success": False,
                "message": "Nepodarilo sa spracovať emaily, skontrolujte internetové pripojenie.",
                "results": [],
            },
        ):
            response = self.client.post("/import-email-receipts")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assert_no_receipts_saved()

    def test_sql_injection_attempt_does_not_bypass_login(self):
        self.register(username="tester", password="secret1")
        self.client.get("/logout")

        response = self.client.post(
            "/",
            data={
                "form_type": "signin",
                "username_signin": "' OR '1'='1",
                "password_signin": "' OR '1'='1",
            },
        )

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_sql_injection_registration_input_does_not_drop_users_table(self):
        malicious_username = "x'); DROP TABLE users; --"

        response = self.register(username=malicious_username, password="secret1")

        self.assertIn(response.status_code, {200, 302})
        self.assertTrue(self.table_exists("users"))
        self.assertGreaterEqual(len(self.db_rows("SELECT * FROM users")), 1)

    def test_sql_injection_filter_input_does_not_modify_database(self):
        self.login_user()
        response = self.client.post("/upload_manual", json=self.manual_payload())
        self.assertTrue(response.get_json()["success"])

        response = self.client.get("/receipts?search=' OR '1'='1")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.table_exists("receipts"))
        self.assertEqual(len(self.db_rows("SELECT * FROM receipts")), 1)

    def test_registered_password_is_stored_as_hash_not_plaintext(self):
        self.register(username="tester", password="secret1")

        row = self.db_rows("SELECT password_hashed FROM users WHERE username = ?", ("tester",))[0]
        password_hash = row["password_hashed"]

        self.assertNotEqual(password_hash, "secret1")
        self.assertTrue(password_hash.startswith(("scrypt:", "pbkdf2:")))

    def test_email_app_password_is_stored_encrypted_not_plaintext(self):
        self.login_user()

        response = self.client.post(
            "/settings/update-email",
            data={
                "email": "tester@gmail.com",
                "email_password": "abcd efgh ijkl mnop",
                "email_filters": "coop",
                "email_scan_limit": "20",
                "save_attachments": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        encrypted = self.db_rows("SELECT email_app_password FROM users WHERE id = 1")[0]["email_app_password"]
        self.assertNotIn("abcdefghijklmnop", encrypted)
        self.assertEqual(helper.get_decrypted_email_password(1), "abcdefghijklmnop")

    def test_user_cannot_access_or_delete_other_users_receipt(self):
        self.register(username="owner", password="secret1")
        response = self.client.post("/upload_manual", json=self.manual_payload())
        self.assertTrue(response.get_json()["success"])
        receipt_id = self.db_rows("SELECT id FROM receipts")[0]["id"]

        self.client.get("/logout")
        self.register(username="other", password="secret1")

        self.assertEqual(self.client.get(f"/receipt_details/{receipt_id}").get_json(), [])
        self.assertEqual(self.client.get(f"/receipt_file/{receipt_id}").status_code, 404)
        self.assertEqual(self.client.delete(f"/delete_receipt/{receipt_id}").status_code, 403)
        self.assertEqual(len(self.db_rows("SELECT * FROM receipts WHERE id = ?", (receipt_id,))), 1)

    def test_protected_pages_redirect_anonymous_user_to_login(self):
        for endpoint in ["/home", "/receipts", "/stats", "/upload", "/settings"]:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/", response.headers["Location"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
