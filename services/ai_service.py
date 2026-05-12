import json
import config
import requests
import base64


def ai_parser_text(pdf_text):
    print("AI SERVICE CALLED")
    #ak nie je server url
    if not config.AI_SERVER_URL:
        return {
            "success": False,
            "error": "ai_config",
            "message": "AI server nie je nastavený."
        }

    try:
        response = requests.post(
            f"{config.AI_SERVER_URL}/parse-receipt-text",
            json={"text" : pdf_text},
            timeout=90
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            return {
                "success": False,
                "error": data.get("error", "ai_error"),
                "message": data.get("message", "AI spracovanie zlyhalo.")
            }

        return {
            "success": True,
            "data": data.get("data")
        }
    
    except Exception as e:
        print(f"AI server chyba (parse): {e}")
        return {
            "success": False,
            "error": "ai_unavailable",
            "message": "AI server nie je dostupný alebo nie je správne nakonfigurovaný."
        }

def ai_parser_img(file_path):
    
    
    #ak nie je url
    if not config.AI_SERVER_URL:
        return {
            "success": False,
            "error": "ai_config",
            "message": "AI server nie je nastavený."
        }

    try:
        # nacitanie obrazka
        with open(file_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # zistenie typu suboru
        if file_path.lower().endswith(".png"):
            media_type = "image/png"
        else:
            media_type = "image/jpeg"

        response = requests.post(
            f"{config.AI_SERVER_URL}/parse-receipt-image",
            json={
                "image_base64": image_data,
                "media_type": media_type
            },
            timeout=120
        )

        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            return {
                "success": False,
                "error": data.get("error", "ai_error"),
                "message": data.get("message", "AI spracovanie zlyhalo.")
            }

        return {
            "success": True,
            "data": data.get("data")
        }

    except Exception as e:
        print(f"AI server chyba (image parse): {e}")
        return {
            "success": False,
            "error": "ai_unavailable",
            "message": "AI server nie je dostupný alebo nie je správne nakonfigurovaný."
        }

#funkcia na kategorizaciu poloziek
def categorize_items_ai(items):

    #ak nie je nastaveny server
    if not config.AI_SERVER_URL:
        return {
            "success": False,
            "error": "ai_config",
            "message": "AI server nie je nastavený."
        }

    try:
        serializable_items = []

        for item in items:
            serializable_items.append({
                "id": item["id"],
                "item_name": item["item_name"]
            })

        response = requests.post(f"{config.AI_SERVER_URL}/categorize-items",
            json={"items": serializable_items},
            timeout=90
        )

        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            return {
                "success": False,
                "error": data.get("error", "ai_error"),
                "message": data.get("message", "AI spracovanie zlyhalo.")
            }

        return data.get("items", [])

    except Exception as e:
        print(f"AI server chyba (categorize): {e}")
        return {
            "success": False,
            "error": "ai_unavailable",
            "message": "AI server nie je dostupný alebo nie je správne nakonfigurovaný."
        }