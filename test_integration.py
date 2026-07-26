import atexit
import io
import os
import shutil
import smtplib
import sqlite3
import time
import unittest
from contextlib import contextmanager
from email.message import EmailMessage, EmailMessage as TestEmailMessage
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
_TEST_DATA_ROOT = ROOT / "testing_runtime" / f"run_{os.getpid()}"
_TEST_DATA_ROOT.mkdir(parents=True, exist_ok=True)
atexit.register(lambda: shutil.rmtree(_TEST_DATA_ROOT, ignore_errors=True))

os.environ["LOCALAPPDATA"] = str(_TEST_DATA_ROOT)
os.environ["FLASK_ENV"] = "testing"
os.environ["RECCIO_ENV_PATH"] = str(_TEST_DATA_ROOT / ".env")

import app as flask_app_module
import config
import database
import helper
import parser
from services import ai_service


TESTING_DIR = ROOT / "TESTING"
TEST_PDF = TESTING_DIR / "pdfnatest.pdf"
TEST_IMAGE = TESTING_DIR / "obrazoknatest.jpg"
THESIS_PDF = TESTING_DIR / "thesis.pdf"


def live_ai_tests_enabled():
    return os.environ.get("RUN_LIVE_AI_TESTS") == "1" and bool(config.AI_SERVER_URL)


def live_gmail_tests_enabled():
    required = [
        "RUN_LIVE_GMAIL_TESTS",
        "RECCIO_TEST_GMAIL_ADDRESS",
        "RECCIO_TEST_GMAIL_APP_PASSWORD",
    ]
    return (
        os.environ.get("RUN_LIVE_GMAIL_TESTS") == "1"
        and all(os.environ.get(name) for name in required[1:])
    )


def performance_tests_enabled():
    return os.environ.get("RUN_PERFORMANCE_TESTS") == "1"


def performance_pdf_files():
    files = sorted(TESTING_DIR.glob("perf_*.pdf"))
    return files if files else [TEST_PDF]


@contextmanager
def working_directory(path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


class ReccioIntegrationTests(unittest.TestCase):
    performance_offline_results = {}

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

        relative_email_uploads = _TEST_DATA_ROOT / "uploads"
        if relative_email_uploads.exists():
            shutil.rmtree(relative_email_uploads, ignore_errors=True)

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

    def login(self, username="tester", password="secret1"):
        return self.client.post(
            "/",
            data={
                "form_type": "signin",
                "username_signin": username,
                "password_signin": password,
            },
            follow_redirects=False,
        )

    def login_user(self):
        self.register()

    def db_rows(self, query, params=()):
        con = sqlite3.connect(config.DATABASE_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(query, params).fetchall()
        con.close()
        return rows

    def manual_receipt_payload(self, shop_name="Manual Shop", date="12.05.2026", time="09:30", price=12.34):
        return {
            "shop_name": shop_name,
            "date": date,
            "time": time,
            "price": price,
            "items": [
                {"item_name": "Chlieb test", "amount": 1, "price": 2.5},
                {"item_name": "Mlieko test", "amount": 2, "price": 3.2},
            ],
        }

    def ai_receipt_data(self, shop_name="AI Shop", date="11.05.2026", time="08:15", price=9.99):
        return {
            "success": True,
            "data": {
                "shop_name": shop_name,
                "date": date,
                "time": time,
                "price": price,
                "items": [
                    {"item_name": "AI rozok", "amount": 3, "price": 1.2, "category": "Pecivo"},
                    {"item_name": "AI syr", "amount": 1, "price": 4.5, "category": "Mliecne"},
                ],
            },
        }

    def test_authentication_registration_login_logout_and_protected_pages(self):
        response = self.client.get("/home")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.headers["Location"])

        self.assertEqual(self.client.get("/").status_code, 200)

        response = self.register()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/home", response.headers["Location"])

        self.client.get("/logout")
        response = self.login(password="wrong")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"login", response.data.lower())

        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/home", response.headers["Location"])

        for endpoint in ["/home", "/receipts", "/stats", "/upload", "/settings"]:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.client.get(endpoint).status_code, 200)

        response = self.client.get("/logout")
        self.assertEqual(response.status_code, 302)

    def test_manual_receipt_crud_filtering_details_stats_and_categorization(self):
        self.login_user()

        response = self.client.post("/upload_manual", json=self.manual_receipt_payload())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        duplicate = self.client.post("/upload_manual", json=self.manual_receipt_payload())
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.get_json()["success"])

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        receipt_id = receipts[0]["id"]

        response = self.client.get(f"/receipt_details/{receipt_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 2)

        self.assertEqual(self.client.get("/receipts?search=Manual").status_code, 200)
        self.assertEqual(self.client.get("/receipts?date_from=2026-05-01&date_to=2026-05-31").status_code, 200)
        self.assertEqual(self.client.get("/stats?date_from=2026-01-01&date_to=2026-12-31").status_code, 200)
        self.assertEqual(self.client.get(f"/receipt_file/{receipt_id}").status_code, 404)

        item_ids = [row["id"] for row in self.db_rows("SELECT id FROM items ORDER BY id")]
        categorized = [{"id": item_id, "category": "Potraviny"} for item_id in item_ids]

        with patch("app.ai_service.categorize_items_ai", return_value=categorized):
            response = self.client.post("/categorize_all_items")

        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["updated_count"], 2)
        self.assertEqual(helper.get_uncategorized_count(1), 0)

        response = self.client.delete(f"/delete_receipt/{receipt_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(self.db_rows("SELECT * FROM receipts"), [])
        self.assertEqual(self.db_rows("SELECT * FROM items"), [])

    def test_pdf_upload_uses_real_testing_pdf_fixture_and_stores_original_file(self):
        self.login_user()

        with TEST_PDF.open("rb") as pdf:
            response = self.client.post(
                "/upload_pdf",
                data={"receipt_file_pdf": (pdf, "pdfnatest.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["shop_name"], "COOP")
        self.assertEqual(receipts[0]["parse_method"], "parser")
        self.assertTrue(Path(receipts[0]["file_path"]).exists())

        response = self.client.get(f"/receipt_file/{receipts[0]['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.mimetype, {"application/pdf", "application/octet-stream"})
        response.close()

        with TEST_PDF.open("rb") as pdf:
            duplicate = self.client.post(
                "/upload_pdf",
                data={"receipt_file_pdf": (pdf, "pdfnatest.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.get_json()["success"])

    def test_image_upload_uses_testing_image_fixture_with_mocked_ai_parser(self):
        self.login_user()

        with patch("app.ai_service.ai_parser_img", return_value=self.ai_receipt_data()):
            with TEST_IMAGE.open("rb") as image:
                response = self.client.post(
                    "/upload_img",
                    data={"receipt_file_img": (image, "obrazoknatest.jpg")},
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["parse_method"], "ai")
        self.assertTrue(Path(receipts[0]["file_path"]).exists())

        items = self.db_rows(
            """
            SELECT i.item_name, c.name AS category
            FROM items i
            JOIN categories c ON c.id = i.category_id
            ORDER BY i.id
            """
        )
        self.assertEqual(items[0]["category"], "Pecivo")
        self.assertEqual(items[1]["category"], "Mliecne")

    def test_upload_validation_rejects_missing_and_wrong_file_types(self):
        self.login_user()

        response = self.client.post("/upload_pdf", data={}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])

        response = self.client.post(
            "/upload_pdf",
            data={"receipt_file_pdf": (io.BytesIO(b"not a pdf"), "receipt.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])

        with THESIS_PDF.open("rb") as pdf:
            response = self.client.post(
                "/upload_img",
                data={"receipt_file_img": (pdf, "thesis.pdf")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])

    def test_pdf_upload_falls_back_to_ai_when_offline_parser_cannot_parse_text(self):
        self.login_user()

        fallback_text = "Nepodporovany format blocku s dostatocne dlhym textom pre AI fallback."

        with patch("helper.parser.extract_from_pdf", return_value=fallback_text):
            with patch("helper.parser.parse_receipt", return_value={}):
                with patch("helper.ai_service.ai_parser_text", return_value=self.ai_receipt_data(shop_name="Fallback Shop")):
                    with TEST_PDF.open("rb") as pdf:
                        response = self.client.post(
                            "/upload_pdf",
                            data={"receipt_file_pdf": (pdf, "fallback.pdf")},
                            content_type="multipart/form-data",
                        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["shop_name"], "Fallback Shop")
        self.assertEqual(receipts[0]["parse_method"], "ai")

    def test_upload_respects_disabled_attachment_archiving(self):
        self.login_user()

        response = self.client.post(
            "/settings/update-email",
            data={
                "email": "tester@gmail.com",
                "email_password": "abcd efgh ijkl mnop",
                "email_filters": "coop",
                "email_scan_limit": "20",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        with TEST_PDF.open("rb") as pdf:
            response = self.client.post(
                "/upload_pdf",
                data={"receipt_file_pdf": (pdf, "pdfnatest.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertIsNone(receipts[0]["file_path"])

    def test_receipts_are_isolated_between_users(self):
        self.register(username="owner", password="secret1")
        response = self.client.post("/upload_manual", json=self.manual_receipt_payload())
        self.assertTrue(response.get_json()["success"])
        receipt_id = self.db_rows("SELECT id FROM receipts")[0]["id"]

        self.client.get("/logout")
        self.register(username="other", password="secret1")

        details = self.client.get(f"/receipt_details/{receipt_id}")
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.get_json(), [])

        file_response = self.client.get(f"/receipt_file/{receipt_id}")
        self.assertEqual(file_response.status_code, 404)

        delete_response = self.client.delete(f"/delete_receipt/{receipt_id}")
        self.assertEqual(delete_response.status_code, 403)
        self.assertEqual(len(self.db_rows("SELECT * FROM receipts WHERE id = ?", (receipt_id,))), 1)

    def test_settings_profile_password_email_and_email_import_endpoint(self):
        self.login_user()

        response = self.client.post("/settings/update-profile", data={"username": "renamed"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        response = self.client.post("/settings/update-profile", data={"username": "ab"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

        response = self.client.post("/settings/update-password", data={"new_password": "newsecret"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        self.client.get("/logout")
        self.assertEqual(self.login(username="renamed", password="newsecret").status_code, 302)

        response = self.client.post("/settings/update-email", data={"email": "not-gmail@example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

        response = self.client.post(
            "/settings/update-email",
            data={
                "email": "tester@gmail.com",
                "email_password": "abcd efgh ijkl mnop",
                "email_filters": "coop\nterno",
                "email_scan_limit": "20",
                "save_attachments": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        with patch(
            "app.email_service.import_receipts_from_email",
            return_value={
                "success": True,
                "message": "Import emailov bol dokoncený.",
                "results": [{"file": "receipt.pdf", "status": "imported"}],
            },
        ) as import_mock:
            response = self.client.post("/import-email-receipts")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        import_mock.assert_called_once()

        settings = helper.get_user_settings(1)
        self.assertEqual(settings["email"], "tester@gmail.com")
        self.assertEqual(helper.get_decrypted_email_password(1), "abcdefghijklmnop")

    def test_email_service_imports_matching_pdf_attachment_with_mocked_imap(self):
        self.login_user()

        message = TestEmailMessage()
        message["From"] = "receipts@example.com"
        message["To"] = "tester@example.com"
        message["Subject"] = "COOP test receipt"
        message.set_content("Testovaci email s PDF prilohou.")
        message.add_attachment(
            TEST_PDF.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename="pdfnatest.pdf",
        )

        class FakeImap:
            def __init__(self, host):
                self.host = host

            def login(self, user_email, user_email_password):
                self.user_email = user_email
                self.user_email_password = user_email_password

            def select(self, folder):
                self.folder = folder

            def search(self, charset, criterion):
                return "OK", [b"1"]

            def fetch(self, eid, query):
                return "OK", [(b"1", message.as_bytes())]

            def logout(self):
                pass

        with patch("services.email_service.imaplib.IMAP4_SSL", FakeImap):
            with working_directory(_TEST_DATA_ROOT):
                from services import email_service

                result = email_service.import_receipts_from_email(
                    "tester@gmail.com",
                    "app-password",
                    ["coop"],
                    1,
                    20,
                )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["results"][0]["status"], "imported")

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["shop_name"], "COOP")

    def test_json_endpoints_return_unauthorized_for_anonymous_user(self):
        for endpoint in [
            "/categorize_all_items",
            "/settings/update-profile",
            "/settings/update-password",
            "/settings/update-email",
            "/import-email-receipts",
        ]:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint)
                self.assertEqual(response.status_code, 401)
                self.assertFalse(response.get_json()["success"])

    def test_pdf_parser_extracts_expected_data_from_testing_fixture(self):
        text = parser.extract_from_pdf(TEST_PDF)
        receipt = parser.parse_receipt(text)
        items = parser.parse_items_universal(receipt["shop_name"], text)

        self.assertEqual(receipt["shop_name"], "COOP")
        self.assertEqual(receipt["date"], "07.05.2026")
        self.assertEqual(receipt["time"], "10:45")
        self.assertEqual(receipt["price"], "39.55")
        self.assertGreaterEqual(len(items), 10)

    @unittest.skipUnless(
        live_ai_tests_enabled(),
        "Live AI tests are skipped. Set RUN_LIVE_AI_TESTS=1 and configure config.AI_SERVER_URL.",
    )
    def test_live_external_ai_server_endpoints(self):
        pdf_text = parser.extract_from_pdf(TEST_PDF)

        text_result = ai_service.ai_parser_text(pdf_text)
        self.assertTrue(text_result.get("success"), text_result)
        self.assertIn("shop_name", text_result["data"])
        self.assertIn("items", text_result["data"])

        image_result = ai_service.ai_parser_img(str(TEST_IMAGE))
        self.assertTrue(image_result.get("success"), image_result)
        self.assertIn("shop_name", image_result["data"])
        self.assertIn("items", image_result["data"])

        category_result = ai_service.categorize_items_ai(
            [
                {"id": 1, "item_name": "chlieb"},
                {"id": 2, "item_name": "sampon"},
            ]
        )
        self.assertIsInstance(category_result, list, category_result)
        self.assertEqual({item["id"] for item in category_result}, {1, 2})
        self.assertTrue(all("category" in item for item in category_result))

    @unittest.skipUnless(
        live_ai_tests_enabled(),
        "Live AI upload test is skipped. Set RUN_LIVE_AI_TESTS=1 and configure config.AI_SERVER_URL.",
    )
    def test_live_image_upload_through_real_ai_server(self):
        self.login_user()

        with TEST_IMAGE.open("rb") as image:
            response = self.client.post(
                "/upload_img",
                data={"receipt_file_img": (image, "obrazoknatest.jpg")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"], data)

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["parse_method"], "ai")

        items = self.db_rows("SELECT * FROM items")
        self.assertGreater(len(items), 0)

    @unittest.skipUnless(
        live_ai_tests_enabled(),
        "Live PDF AI fallback test is skipped. Set RUN_LIVE_AI_TESTS=1 and configure config.AI_SERVER_URL.",
    )
    def test_live_pdf_upload_falls_back_to_real_ai_server(self):
        self.login_user()

        fallback_text = """
        Nepodporovany testovaci pokladnicny blok.
        Obchod: Live AI PDF Shop
        Datum nakupu: 12.05.2026
        Cas nakupu: 13:45
        Polozky:
        Chlieb 1 ks 2.40
        Sampon 1 ks 3.90
        Celkom 6.30 EUR
        """

        with patch("helper.parser.extract_from_pdf", return_value=fallback_text):
            with patch("helper.parser.parse_receipt", return_value={}):
                with TEST_PDF.open("rb") as pdf:
                    response = self.client.post(
                        "/upload_pdf",
                        data={"receipt_file_pdf": (pdf, "live-ai-fallback.pdf")},
                        content_type="multipart/form-data",
                    )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"], data)

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["parse_method"], "ai")
        self.assertTrue(receipts[0]["shop_name"])

        items = self.db_rows("SELECT * FROM items")
        self.assertGreater(len(items), 0)

    @unittest.skipUnless(
        live_gmail_tests_enabled(),
        "Live Gmail test is skipped. Set RUN_LIVE_GMAIL_TESTS=1, RECCIO_TEST_GMAIL_ADDRESS and RECCIO_TEST_GMAIL_APP_PASSWORD.",
    )
    def test_live_gmail_import_receipt_from_real_mailbox(self):
        gmail_address = os.environ["RECCIO_TEST_GMAIL_ADDRESS"]
        gmail_password = os.environ["RECCIO_TEST_GMAIL_APP_PASSWORD"].replace(" ", "")
        subject = f"Reccio integration test {int(time.time())}"

        message = EmailMessage()
        message["From"] = gmail_address
        message["To"] = gmail_address
        message["Subject"] = subject
        message.set_content("Automaticky test Reccio importu z Gmailu.")
        message.add_attachment(
            TEST_PDF.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename="pdfnatest.pdf",
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(gmail_address, gmail_password)
            smtp.send_message(message)

        self.login_user()
        response = self.client.post(
            "/settings/update-email",
            data={
                "email": gmail_address,
                "email_password": gmail_password,
                "email_filters": subject,
                "email_scan_limit": "20",
                "save_attachments": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

        last_response = None
        with working_directory(_TEST_DATA_ROOT):
            for _ in range(6):
                time.sleep(5)
                last_response = self.client.post("/import-email-receipts")
                data = last_response.get_json()
                if data.get("success") and data.get("results"):
                    break

        self.assertIsNotNone(last_response)
        self.assertEqual(last_response.status_code, 200)
        data = last_response.get_json()
        self.assertTrue(data["success"], data)
        self.assertTrue(data["results"], data)
        self.assertEqual(data["results"][0]["status"], "imported", data)

        receipts = self.db_rows("SELECT * FROM receipts")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["shop_name"], "COOP")

    @unittest.skipUnless(
        performance_tests_enabled(),
        "Performance comparison is skipped. Set RUN_PERFORMANCE_TESTS=1 to measure offline parser speed.",
    )
    def test_performance_offline_pdf_parser(self):
        results = {}
        files = performance_pdf_files()

        for pdf_path in files:
            started = time.perf_counter()
            text = parser.extract_from_pdf(pdf_path)
            receipt = parser.parse_receipt(text)
            items = parser.parse_items_universal(receipt["shop_name"], text)
            duration = time.perf_counter() - started
            results[pdf_path.name] = {
                "duration": duration,
                "shop": receipt["shop_name"],
                "items": len(items),
            }

            self.assertTrue(receipt.get("shop_name"), pdf_path.name)
            self.assertGreater(len(items), 0)

        self.__class__.performance_offline_results = results
        durations = [row["duration"] for row in results.values()]
        average = sum(durations) / len(durations)
        print(
            "\nPERFORMANCE offline_parser_pdf completed "
            f"files={len(files)} avg={average:.3f}s "
            f"min={min(durations):.3f}s max={max(durations):.3f}s"
        )

    @unittest.skipUnless(
        performance_tests_enabled() and live_ai_tests_enabled(),
        "AI performance comparison is skipped. Set RUN_PERFORMANCE_TESTS=1, RUN_LIVE_AI_TESTS=1 and configure config.AI_SERVER_URL.",
    )
    def test_performance_ai_pdf_text_parser(self):
        offline_results = self.__class__.performance_offline_results or self._measure_offline_performance()
        ai_results = {}
        files = performance_pdf_files()

        for pdf_path in files:
            pdf_text = parser.extract_from_pdf(pdf_path)
            started = time.perf_counter()
            result = ai_service.ai_parser_text(pdf_text)
            duration = time.perf_counter() - started

            if not result.get("success"):
                ai_results[pdf_path.name] = {
                    "duration": duration,
                    "status": "FAILED",
                    "shop": "",
                    "items": 0,
                    "error": result.get("error", ""),
                }
                continue

            self.assertIn("shop_name", result["data"])
            self.assertIn("items", result["data"])
            ai_results[pdf_path.name] = {
                "duration": duration,
                "status": "OK",
                "shop": result["data"].get("shop_name", ""),
                "items": len(result["data"].get("items", [])),
                "error": "",
            }

        self._print_performance_summary(files, offline_results, ai_results)

        self.assertGreater(len([row for row in ai_results.values() if row["status"] == "OK"]), 0)

    def _measure_offline_performance(self):
        results = {}
        for pdf_path in performance_pdf_files():
            started = time.perf_counter()
            text = parser.extract_from_pdf(pdf_path)
            receipt = parser.parse_receipt(text)
            items = parser.parse_items_universal(receipt["shop_name"], text)
            results[pdf_path.name] = {
                "duration": time.perf_counter() - started,
                "shop": receipt["shop_name"],
                "items": len(items),
            }
        return results

    def _print_performance_summary(self, files, offline_results, ai_results):
        print("\n================ PERFORMANCE SUMMARY ================")
        print(f"{'Vstup':<12} | {'Pocet poloziek':<14} | {'Parser':<8} | {'AI':<8} | {'Stav AI':<7}")
        print(f"{'-' * 12}-+-{'-' * 14}-+-{'-' * 8}-+-{'-' * 8}-+-{'-' * 7}")

        for index, pdf_path in enumerate(files, start=1):
            offline = offline_results[pdf_path.name]
            ai = ai_results[pdf_path.name]
            parser_duration = f"{offline['duration']:.3f}s"
            ai_duration = f"{ai['duration']:.3f}s"
            print(
                f"{f'Pokl. blok {index}':<12} | "
                f"{offline['items']:<14} | "
                f"{parser_duration:<8} | "
                f"{ai_duration:<8} | "
                f"{ai['status']:<7}"
            )

        parser_durations = [row["duration"] for row in offline_results.values()]
        ai_durations_all = [row["duration"] for row in ai_results.values()]
        ai_durations_success = [
            row["duration"]
            for row in ai_results.values()
            if row["status"] == "OK"
        ]
        failed_files = [
            str(index)
            for index, pdf_path in enumerate(files, start=1)
            for row in [ai_results[pdf_path.name]]
            if row["status"] != "OK"
        ]

        print("-----------------------------------------------------")
        print(
            "Parser summary: "
            f"avg={sum(parser_durations) / len(parser_durations):.3f}s "
            f"min={min(parser_durations):.3f}s "
            f"max={max(parser_durations):.3f}s "
            f"success={len(parser_durations)}/{len(files)}"
        )
        print(
            "AI summary: "
            f"avg={sum(ai_durations_all) / len(ai_durations_all):.3f}s "
            f"min={min(ai_durations_all):.3f}s "
            f"max={max(ai_durations_all):.3f}s "
            f"success={len(ai_durations_success)}/{len(ai_durations_all)}"
        )
        if failed_files:
            print(f"AI failed inputs: {', '.join(failed_files)}")
        print("=====================================================")


if __name__ == "__main__":
    unittest.main(verbosity=2)
