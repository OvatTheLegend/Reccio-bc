from openai import OpenAI
import json
import config
import base64


def ai_parser_text(pdf_text):
    print("AI SERVICE CALLED")
    #ak nie je nastaveny ai kluc tak nespadne appka, len sa preskoci funkcionalita
    if not config.OPENAI_API_KEY:
        return None

    #nastavime kluc
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    prompt = f"""
    Toto je pokladničný blok. Extrahuj z neho tieto údaje a vráť ONLY JSON bez akéhokoľvek iného textu:
    {{
        "shop_name": "názov obchodu",
        "date": "DD.MM.YYYY",
        "time": "HH:MM:SS",
        "prize": 0.00,
        "items": [
            {{
                "item_name": "názov položky",
                "amount": "pocet položiek",
                "prize": "cena položky",
                "category": "kategoria položky"
            }}
        ]
    }}
    Pravidlá su nasledovné:
    - shop_name je nazov obchody, teda TERNO, TESCO, KAUFLAND atd...
    - date musí byť formát DD.MM.YYYY
    - time musí byť formát HH:MM:SS
    - prize je celková suma nakupu ako float cislo
    - items sú jednotlivé položky, ak je samostnatna položka nejaka zlava, teda napriklad seniorska zlava -4.30 tak tieto neposielaj, iba položky ktore sme kupili a maju kladnu sumu.
    - item_name je celý nazov položky
    - amount je počet kupených kusov, teda napriklad pri kuracich prsiach to moze byt aj 0.675
    - prize je cena danej položky
    - category je kategoria položky musis vybrat jednu z: "Potraviny", "Drogéria", "Lieky", "Elektronika", "Oblečenie", "Ostatné",
    - vitaminy a vyzivove doplnky považuj za lieky
    - hocijake jedlo, ci už to je tycinka, alebo su to chrumky, čipsy -> zarad ako Potraviny
    - takisto hocijake pitie, dzus, vodka, pivo, voda, preliva voda magnesium atd -> zarad ako potraviny
    text blocku:
    {pdf_text}
    """
    
    #skusime odoslat
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                "role": "user", 
                "content": prompt
                }
            ],
            max_tokens=1000,
        )

        ai_result = response.choices[0].message.content.strip()

        #odstranime obalenie json bloku
        ai_result = ai_result.replace("```json", "").replace("```", "").strip()

        data = json.loads(ai_result)
        return data

    except json.JSONDecodeError as e:
        print(f"AI vratilo neplatny JSON: {e}")
        return None
        
    except Exception as e:
        print(f"AI parser chyba: {e}")
        return None

def ai_parser_img(file_path):
    #ak nie je nastaveny ai kluc tak nespadne appka, len sa preskoci funkcionalita
    if not config.OPENAI_API_KEY:
        return None

    #nastavime kluc
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    #najrpv nacitame obrazok
    with open(file_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    #potrebujeme zistit typ suboru (png,jpeg,jpg)
    #ak png
    if file_path.lower().endswith('.png'):
        media_type = "image/png"
    
    #inak jpeg
    else:
        media_type = "image/jpeg"

    #teraz promt
    prompt = f"""
    Toto je pokladničný blok. Extrahuj z neho tieto údaje a vráť ONLY JSON bez akéhokoľvek iného textu:
    {{
        "shop_name": "názov obchodu",
        "date": "DD.MM.YYYY",
        "time": "HH:MM:SS",
        "prize": 0.00,
        "items": [
            {{
                "item_name": "názov položky",
                "amount": "pocet položiek",
                "prize": "cena položky",
                "category": "kategoria položky"
            }}
        ]
    }}
    Pravidlá su nasledovné:
    - shop_name je nazov obchody, teda TERNO, TESCO, KAUFLAND atd...
    - date musí byť formát DD.MM.YYYY
    - time musí byť formát HH:MM:SS
    - prize je celková suma nakupu ako float cislo
    - items sú jednotlivé položky, ak je samostnatna položka nejaka zlava, teda napriklad seniorska zlava -4.30 tak tieto neposielaj, iba položky ktore sme kupili a maju kladnu sumu.
    - item_name je celý nazov položky
    - amount je počet kupených kusov, teda napriklad pri kuracich prsiach to moze byt aj 0.675
    - prize je cena danej položky
    - category je kategoria položky musis vybrat jednu z: "Potraviny", "Drogéria", "Lieky", "Elektronika", "Oblečenie", "Ostatné",
    - vitaminy a vyzivove doplnky považuj za lieky
    - hocijake jedlo, ci už to je tycinka, alebo su to chrumky, čipsy -> zarad ako Potraviny
    - takisto hocijake pitie, čaje , dzus, vodka, pivo, voda, preliva voda magnesium atd -> zarad ako potraviny
    """
    
    #skusime odoslat
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                "role": "user", 
                "content": [
                    {
                        "type" : "image_url",
                        "image_url" : {
                            "url" : f'data:{media_type};base64,{image_data}'
                        }
                    },
                    {
                        "type" : "text",
                        "text" : prompt
                    }
                ]
                }
            ],
            max_tokens=1000,
        )

        ai_result = response.choices[0].message.content.strip()

        #odstranime obalenie json bloku
        ai_result = ai_result.replace("```json", "").replace("```", "").strip()

        data = json.loads(ai_result)
        return data

    except json.JSONDecodeError as e:
        print(f"AI vratilo neplatny JSON: {e}")
        return None
        
    except Exception as e:
        print(f"AI parser chyba: {e}")
        return None

#funkcia na kategorizaciu poloziek
def categorize_items_ai(items):

    #ak nie je nastaveny ai kluc tak nespadne appka, len sa preskoci funkcionalita
    if not config.OPENAI_API_KEY:
        return None

    #nastavime kluc
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    items_for_promt = []

    for item in items:
        items_for_promt.append({
            "id": item["id"],
            "item_name": item["item_name"]
        })

    #promt
    prompt = f"""
    Toto su položky z pokladničného bloku, tvojou ulohou je urcit kategoriiu danej položky, nižšie su povolene kategorie a pravidla uvedene.
    VRÁŤ IBA ČISTÉ JSON POLE.
    NEPÍŠ žiadny úvod, vysvetlenie ani markdown.
    
    Pravidlá su nasledovné:

    - category je kategoria položky musis vybrat jednu z: "Potraviny", "Drogéria", "Lieky", "Elektronika", "Oblečenie", "Ostatné",
    - vitaminy a vyzivove doplnky považuj za lieky
    - hocijake jedlo, ci už to je tycinka, alebo su to chrumky, čipsy -> zarad ako Potraviny
    - takisto hocijake pitie, čaje, dzus, vodka, pivo, voda, preliva voda magnesium atd -> zarad ako potraviny
    - každá položka musi mať presne priradene id,category

    položky:
    {json.dumps(items_for_promt, ensure_ascii=False)}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                "role": "user", 
                "content": prompt
                }
            ],
            max_tokens=700,
        )

        ai_result = response.choices[0].message.content.strip()

        #odstranime obalenie json bloku
        ai_result = ai_result.replace("```json", "").replace("```", "").strip()

        data = json.loads(ai_result)

        return_data = []

        for item in data:
            #ak nahodou nieco chyba tak skip
            if "id" not in item or "category" not in item:
                continue

            return_data.append({
                "id": item["id"],
                "category" : item["category"]
            })
            
        return return_data

    except json.JSONDecodeError as e:
        print(f"AI vratilo neplatny JSON: {e}")
        return None
        
    except Exception as e:
        print(f"AI parser chyba: {e}")
        return None
    