import atexit
import os
import shutil
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
_TEST_DATA_ROOT = ROOT / "testing_runtime_unit" / f"run_{os.getpid()}"
_TEST_DATA_ROOT.mkdir(parents=True, exist_ok=True)
atexit.register(lambda: shutil.rmtree(_TEST_DATA_ROOT, ignore_errors=True))

os.environ["LOCALAPPDATA"] = str(_TEST_DATA_ROOT)
os.environ["FLASK_ENV"] = "testing"
os.environ["RECCIO_ENV_PATH"] = str(_TEST_DATA_ROOT / ".env")

import config
import database
import helper
import parser


class ParserUnitTests(unittest.TestCase):
    def test_find_shop_name_recognizes_supported_shops(self):
        samples = {
            "Dr. Max lekaren": "Dr.Max",
            "TERNO potraviny": "TERNO",
            "dm drogerie markt": "DM",
            "Kaufland Slovensko": "KAUFLAND",
            "COOP Jednota": "COOP",
        }

        for text, expected in samples.items():
            with self.subTest(text=text):
                self.assertEqual(parser.find_shop_name(text), expected)

    def test_find_shop_name_returns_empty_for_unknown_shop(self):
        self.assertEqual(parser.find_shop_name("Neznamy obchod"), "")

    def test_find_date_normalizes_one_digit_values_and_short_year(self):
        self.assertEqual(parser.find_date("Datum: 7.5.26"), "07.05.2026")

    def test_find_date_returns_empty_when_missing(self):
        self.assertEqual(parser.find_date("Bez datumu"), "")

    def test_find_time_normalizes_one_digit_values(self):
        self.assertEqual(parser.find_time("Cas nakupu 8:5:03"), "08:05")

    def test_find_price_accepts_total_keywords(self):
        self.assertEqual(parser.find_price("SPOLU: 12,34 EUR"), "12,34")
        self.assertEqual(parser.find_price("CELKOM 9.99"), "9.99")

    def test_find_coop_date_and_time_from_receipt_line(self):
        text = "Pokladn. dokl. 123/07.05.2026 10:45:22"
        self.assertEqual(parser.find_date_coop(text), "07.05.2026")
        self.assertEqual(parser.find_time_coop(text), "10:45")

    def test_parse_receipt_returns_header_when_required_fields_exist(self):
        text = """
        TERNO
        Datum: 01.05.2026
        Cas: 12:30
        CELKOM: 15.40
        """

        self.assertEqual(
            parser.parse_receipt(text),
            {
                "shop_name": "TERNO",
                "date": "01.05.2026",
                "time": "12:30",
                "price": "15.40",
            },
        )

    def test_parse_receipt_returns_empty_dict_when_field_is_missing(self):
        self.assertEqual(parser.parse_receipt("TERNO\nDatum: 01.05.2026"), {})

    def test_parse_items_universal_returns_empty_for_unsupported_shop(self):
        self.assertEqual(parser.parse_items_universal("UNKNOWN", "text"), [])


class HelperUnitTests(unittest.TestCase):
    def setUp(self):
        if Path(config.DATABASE_PATH).exists():
            Path(config.DATABASE_PATH).unlink()
        database.init_database()

    def test_split_into_groups_splits_items_by_requested_size(self):
        groups = helper.split_into_groups(list(range(5)), group_size=2)
        self.assertEqual(groups, [[0, 1], [2, 3], [4]])

    def test_split_into_groups_returns_empty_list_for_empty_input(self):
        self.assertEqual(helper.split_into_groups([], group_size=10), [])

    def test_encrypt_and_decrypt_value_roundtrip(self):
        encrypted = helper.encrypt_value("tajne-heslo")
        self.assertNotEqual(encrypted, "tajne-heslo")
        self.assertEqual(helper.decrypt_value(encrypted), "tajne-heslo")

    def test_decrypt_value_returns_empty_string_for_invalid_token(self):
        self.assertEqual(helper.decrypt_value("neplatny-token"), "")

    def test_validate_register_accepts_valid_unique_user(self):
        is_valid, error = helper.validate_register("tester", "secret1", "secret1")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_register_rejects_empty_fields(self):
        is_valid, error = helper.validate_register("", "secret1", "secret1")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_register_rejects_short_username(self):
        is_valid, error = helper.validate_register("ab", "secret1", "secret1")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_register_rejects_short_password(self):
        is_valid, error = helper.validate_register("tester", "1234", "1234")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_register_rejects_password_mismatch(self):
        is_valid, error = helper.validate_register("tester", "secret1", "secret2")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_register_user_and_validate_signin_success(self):
        success, user_id = helper.register_user("tester", "secret1")
        self.assertTrue(success)
        self.assertIsNotNone(user_id)

        is_valid, signed_user_id, error = helper.validate_signin("tester", "secret1")
        self.assertTrue(is_valid)
        self.assertEqual(signed_user_id, user_id)
        self.assertIsNone(error)

    def test_validate_signin_rejects_wrong_password(self):
        helper.register_user("tester", "secret1")
        is_valid, user_id, error = helper.validate_signin("tester", "wrong")
        self.assertFalse(is_valid)
        self.assertIsNone(user_id)
        self.assertIsNotNone(error)

    def test_is_unique_username_detects_existing_user(self):
        helper.register_user("tester", "secret1")
        self.assertFalse(helper.is_unique_username("tester"))
        self.assertTrue(helper.is_unique_username("newtester"))

    def test_get_or_create_category_id_reuses_existing_category(self):
        first_id = helper.get_or_create_category_id("Potraviny")
        second_id = helper.get_or_create_category_id("Potraviny")
        self.assertEqual(first_id, second_id)

        con = sqlite3.connect(config.DATABASE_PATH)
        count = con.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        con.close()
        self.assertEqual(count, 1)

    def test_get_category_for_item_reuses_previous_user_category(self):
        success, user_id = helper.register_user("tester", "secret1")
        self.assertTrue(success)

        receipt = {
            "shop_name": "Manual Shop",
            "date": "12.05.2026",
            "time": "10:15",
            "price": 5.0,
        }
        items = [{"item_name": "Chlieb", "amount": 1, "price": 2.5, "category": "Potraviny"}]
        helper.save_receipt(receipt, items, user_id, "ai")

        category_id = helper.get_category_for_item("Chlieb", user_id)
        self.assertIsNotNone(category_id)

    def test_save_receipt_prefers_existing_category_over_ai_category(self):
        success, user_id = helper.register_user("tester", "secret1")
        self.assertTrue(success)

        first_receipt = {
            "shop_name": "AI Shop",
            "date": "12.05.2026",
            "time": "10:15",
            "price": 5.0,
        }
        first_items = [{"item_name": "Chlieb", "amount": 1, "price": 2.5, "category": "Potraviny"}]
        helper.save_receipt(first_receipt, first_items, user_id, "ai")

        second_receipt = {
            "shop_name": "AI Shop",
            "date": "13.05.2026",
            "time": "10:15",
            "price": 6.0,
        }
        second_items = [{"item_name": "Chlieb", "amount": 1, "price": 3.0, "category": "Ostatné"}]
        helper.save_receipt(second_receipt, second_items, user_id, "ai")

        rows = self.category_rows_for_item("Chlieb")
        self.assertEqual(rows[0]["category"], "Potraviny")
        self.assertEqual(rows[1]["category"], "Potraviny")

    def test_save_receipt_uses_ai_category_when_no_existing_category_exists(self):
        success, user_id = helper.register_user("tester", "secret1")
        self.assertTrue(success)

        receipt = {
            "shop_name": "AI Shop",
            "date": "12.05.2026",
            "time": "10:15",
            "price": 5.0,
        }
        items = [{"item_name": "Sampon", "amount": 1, "price": 2.5, "category": "Drogéria"}]
        helper.save_receipt(receipt, items, user_id, "ai_pdf_image")

        rows = self.category_rows_for_item("Sampon")
        self.assertEqual(rows[0]["category"], "Drogéria")

    def test_save_receipt_leaves_parser_item_uncategorized_when_no_history_exists(self):
        success, user_id = helper.register_user("tester", "secret1")
        self.assertTrue(success)

        receipt = {
            "shop_name": "Manual Shop",
            "date": "12.05.2026",
            "time": "10:15",
            "price": 5.0,
        }
        items = [{"item_name": "Nova polozka", "amount": 1, "price": 2.5}]
        helper.save_receipt(receipt, items, user_id, "parser")

        rows = self.category_rows_for_item("Nova polozka")
        self.assertIsNone(rows[0]["category"])

    def category_rows_for_item(self, item_name):
        con = sqlite3.connect(config.DATABASE_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT i.item_name, c.name AS category
            FROM items i
            LEFT JOIN categories c ON c.id = i.category_id
            WHERE i.item_name = ?
            ORDER BY i.id
            """,
            (item_name,),
        ).fetchall()
        con.close()
        return rows

    def test_validate_register_rejects_duplicate_username(self):
        helper.register_user("tester", "secret1")
        is_valid, error = helper.validate_register("tester", "secret1", "secret1")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
