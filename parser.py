import pdfplumber, re
import json
import config


#extraction from pdf to text
def extract_from_pdf(path):
    text = ""
    #opening file
    with pdfplumber.open(path) as pdf:
        #for loop to loop trough all pdf pages
        for page in pdf.pages:
            #extract text from page and add to txt if there is any text to read, else continue
            page_text = page.extract_text()
            if page_text:
                text +=page_text
            else:
                continue
    return text

#                                    parser for receipt section
#--------------------------------------------------------------------------------------------------

#parser for receipt -> shop,date,time,price
def parse_receipt(txt):
    
    shop_name = find_shop_name(txt)
    price = find_price(txt)
    
    if (shop_name == "COOP"):
        date = find_date_coop(txt)
        time = find_time_coop(txt)
    else:
        date = find_date(txt)
        time = find_time(txt)


    #podmienky:
    if not shop_name or not date or not time or not price:
        return {}

    #return dictionary type 
    return {
        "shop_name" : shop_name,
        "date" : date,
        "time" : time,
        "price" : price,
    }

#function for getting name of shop of out e-block txt, using regex syntax
def find_shop_name(txt):

    patterns = {
            "Dr.Max" : r"Dr\.?\s*Max",
            "TERNO" : r"TERNO",
            "DM": r"\bdm\b|drogerie\s*markt",
            "KAUFLAND": r"\bKaufland\b",
            "COOP": r"COOP\s+Jednota|COOP"
    }

    #iterate trough our dict shop-regex, if found return name of shop, else unknown
    for shop, pattern in patterns.items():
        if re.search(pattern,txt,re.IGNORECASE):
            return shop
    
    return ""

#function for getting date 
def find_date(txt):
    pattern = r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2}|\d{4})\b"

    date = re.search(pattern, txt)

    if date:
        day = date.group(1).zfill(2)
        month = date.group(2).zfill(2)
        year = date.group(3)

        if len(year) == 2:
            year = "20" + year

        return f"{day}.{month}.{year}"

    return ""
        
def find_date_coop(txt):
    pattern = r"Pokladn\.\s*dokl\.\s*\d+\/(\d{2}\.\d{2}\.\d{4})\s+\d{2}:\d{2}:\d{2}"

    date = re.search(pattern, txt, re.IGNORECASE)

    if date:
        return date.group(1)

    return ""
#function for getting time
def find_time(txt):
    pattern = r"\b(\d{1,2})\s*:\s*(\d{1,2})(?:\s*:\s*\d{1,2})?\b"

    time = re.search(pattern, txt)

    if time:
        hour = time.group(1).zfill(2)
        minute = time.group(2).zfill(2)

        return f"{hour}:{minute}"

    return ""

def find_time_coop(txt):
    pattern = r"Pokladn\.\s*dokl\.\s*\d+\/\d{2}\.\d{2}\.\d{4}\s+(\d{2}:\d{2}:\d{2})"

    time = re.search(pattern, txt, re.IGNORECASE)

    if time:
        return time.group(1)[:5]

    return ""

def find_price(txt):
    pattern = r"(?:CELKOM|Celkom|Suma|Súčet|Sucet|SPOLU)\s*:?\s*(\d+(?:[.,]\d{1,2}))"

    price = re.search(pattern,txt,re.IGNORECASE)

    if price:
        return price.group(1)
    
    return ""

#                           parser universal (items) section
#-----------------------------------------------------------------------------------------------

#parser for unique shop
def parse_items_universal(shopName, txt):
    parsers = {
        "Dr.Max" : parse_items_drmax,
        "TERNO" : parse_items_terno,
        "DM" : parse_items_dm,
        "KAUFLAND" : parse_items_kaufland,
        "COOP" : parse_items_coop
    }

    parser = parsers.get(shopName)

    if (parser):
        return parser(txt)

    else:
        return []

#                            parser for unique shop type (items) seciton
#----------------------------------------------------------------------------------------------------
#parser for DRMAX
def parse_items_drmax(txt):
    
    #list of dict for all items
    items = []

    pattern_start = r"Názov liek"
    pattern_end = r"Zaokrúhlenie|CELKOM"
    pattern_items = r"#?\s*(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(-?\d+[.,]\d+)\s+(-?\d+[.,]\d+)\s+([A-Z])"

    #spliting text to list of lines
    lines = txt.splitlines()
 
    start_index = None
    end_index = None

    for i, line in enumerate(lines):
        if(re.search(pattern_start,line,re.IGNORECASE)):
            start_index = i + 2
            break
    
    #podmienka
    if start_index is None:
        return []

    for i, line in enumerate(lines[start_index:]):
        if(re.search(pattern_end,line,re.IGNORECASE)):
            end_index = i + start_index
            break

    #podmienka
    if end_index is None:
        return []
    

    item_text_lines = lines[start_index:end_index]

    i = 0
    while i < len(item_text_lines):

        item_name = item_text_lines[i].strip()

        #ak nenaslo tak na dalsi riadok
        if not item_name:
            i += 1
            continue

        #ak nenaslo tak na dalsi riadok
        if re.search(r"Položky na|Voľnopredajné|ZLAVA|predpis|\(\*|-->", item_name, re.IGNORECASE):
            i += 1
            continue

        #ak nenaslo tak na dalsi riadok
        if re.search(r"^-{3,}$", item_name):
            i += 1
            continue

        #ak naslo, skontrolujeme ci su na dalsom prislusne data
        if i + 1 < len(item_text_lines):
            data_line = item_text_lines[i + 1].strip()
            match = re.search(pattern_items, data_line)

            #ak sedi
            if match:
                mnozstvo = match.group(3).replace(",", ".")
                cena = match.group(4).replace(",", ".")

                # ak naslo zaporne polozky tak preskocime, tie neratame do databazy, ani nulove polozky neratame
                if float(mnozstvo) > 0 and float(cena) > 0:
                    items.append({
                        "item_name": item_name,
                        "amount": mnozstvo,
                        "price": cena,
                    })
                    
                i += 2
                continue
            
        i += 1

    if items == []:
        return []
    
    return items

#parser for TERNO
def parse_items_terno(txt):

    #list of dict for all items
    items = []

    pattern_start = r"Množstvo\s+Cena\s+DPH\s+SUMA"
    pattern_end = r"Suma\s*:"
    pattern_items = r"(\d+(?:\.\d+)?)x\s+\d+(?:\.|,)\d+\s+(?:\d+\s*%\s+)?(\d+(?:\.|,)\d+)"

    #spliting text to list of lines
    txt = re.sub(r"(?<!\n)(?<!\d\.)\b(\d+)x(?=\s+\d)", r"\n\1x", txt)
    lines = txt.splitlines()

    start_index = None
    end_index = None

    for i, line in enumerate(lines):
        if(re.search(pattern_start,line,re.IGNORECASE)):
            start_index = i
            break
    
    #podmienka
    if start_index is None:
        return []

    for i, line in enumerate(lines[start_index+2:]):
        if(re.search(pattern_end,line,re.IGNORECASE)):
            end_index = i + start_index+2
            break
    #podmienka
    if end_index is None:
        return []
    

    item_text_lines = lines[start_index+2:end_index-1]

    i = 0
    while i < len(item_text_lines) - 1:

        item_name = item_text_lines[i].strip()
        item = re.search(pattern_items,item_text_lines[i+1])

        if item:

            #ak su to zlavy tak to skipneme
            if re.search(r"zlava|zľava|bonus|body", item_name, re.IGNORECASE):
                i += 2
                continue

            i += 2
            items.append({
                "item_name" : item_name,
                "amount" : item.group(1),
                "price" : item.group(2),
            })
        else:
            i += 1
            continue

    if items == []:
        return []
    
    return items
    
def parse_items_dm(txt):

    #list of dict for all items
    items = []

    pattern_start = r"č\.?\s*bloku"
    pattern_end = r"MEDZISÚČET|MEDZISUCET"
    pattern_items = r"(\d+(?:[.,]\d+)?)\s*ks\s*\*\s*\d+(?:[.,]\d+)\s+(\d+(?:[.,]\d+))\s+[A-Z]"

    #spliting text to list of lines
    lines = txt.splitlines()

    start_index = None
    end_index = None

    for i, line in enumerate(lines):
        if(re.search(pattern_start, line, re.IGNORECASE)):
            start_index = i
            break

    #podmienka
    if start_index is None:
        return []

    for i, line in enumerate(lines[start_index+1:]):
        if(re.search(pattern_end, line, re.IGNORECASE)):
            end_index = i + start_index+1
            break

    #podmienka
    if end_index is None:
        return []

    item_text_lines = lines[start_index+1:end_index]

    i = 0
    while i < len(item_text_lines) - 1:

        item_name = item_text_lines[i].strip()
        item = re.search(pattern_items, item_text_lines[i+1], re.IGNORECASE)

        if item:

            #ak su to zlavy tak to skipneme
            if re.search(r"zlava|zľava|bonus|body", item_name, re.IGNORECASE):
                i += 2
                continue

            i += 2
            items.append({
                "item_name" : item_name,
                "amount" : item.group(1).replace(",", "."),
                "price" : item.group(2).replace(",", "."),
            })
        else:
            i += 1
            continue

    if items == []:
        return []

    return items

def parse_items_kaufland(txt):

    #list of dict for all items
    items = []

    pattern_start = r"Cena\s+EUR"
    pattern_end = r"Súčet|Sucet"

    pattern_multiline = r"(\d+(?:[.,]\d+)?)\s*\*\s*\d+(?:[.,]\d+)\s+(\d+(?:[.,]\d+))\s+[A-Z]$"
    pattern_multiline_weight = r"(\d+(?:[.,]\d+)?)\s*KG\s+(\d+(?:[.,]\d+))\s+[A-Z]$"
    pattern_singleline_count = r"(.+?)\s+(\d+(?:[.,]\d+)?)\s*\*\s*\d+(?:[.,]\d+)\s+(\d+(?:[.,]\d+))\s+[A-Z]$"
    pattern_singleline = r"(.+?)\s+(\d+(?:[.,]\d+))\s+[A-Z]$"
    pattern_weight = r"(.+?)\s+(\d+(?:[.,]\d+))\s*KG\s+(\d+(?:[.,]\d+))\s+[A-Z]$"

    lines = txt.splitlines()

    start_index = None
    end_index = None

    for i, line in enumerate(lines):
        if re.search(pattern_start, line, re.IGNORECASE):
            start_index = i
            break

    if start_index is None:
        return []

    for i, line in enumerate(lines[start_index+1:]):
        if re.search(pattern_end, line, re.IGNORECASE):
            end_index = i + start_index+1
            break

    if end_index is None:
        return []

    item_text_lines = lines[start_index+1:end_index]

    i = 0
    while i < len(item_text_lines):
        matched = False
        line = item_text_lines[i].strip()

        if re.search(r"zlava|zľava|bonus|ušetrili|usetrili", line, re.IGNORECASE):
            i += 1
            continue

        single_count = re.search(pattern_singleline_count, line)
        if single_count:
            matched = True
            items.append({
                "item_name": single_count.group(1).strip(),
                "amount": single_count.group(2).replace(",", "."),
                "price": single_count.group(3).replace(",", "."),
            })
            i += 1
            continue

        weight = re.search(pattern_weight, line)
        if weight:
            matched = True
            items.append({
                "item_name": weight.group(1).strip(),
                "amount": weight.group(2).replace(",", "."),
                "price": weight.group(3).replace(",", "."),
            })
            i += 1
            continue

        single = re.search(pattern_singleline, line)
        if single:
            matched = True
            items.append({
                "item_name": single.group(1).strip(),
                "amount": "1",
                "price": single.group(2).replace(",", "."),
            })
            i += 1
            continue

        if i < len(item_text_lines) - 1:
            next_line = item_text_lines[i+1].strip()

            multi = re.search(pattern_multiline, next_line)
            if multi:
                matched = True
                items.append({
                    "item_name": line,
                    "amount": multi.group(1).replace(",", "."),
                    "price": multi.group(2).replace(",", "."),
                })
                i += 2
                continue

            multi_weight = re.search(pattern_multiline_weight, next_line)
            if multi_weight:
                matched = True
                items.append({
                    "item_name": line,
                    "amount": multi_weight.group(1).replace(",", "."),
                    "price": multi_weight.group(2).replace(",", "."),
                })
                i += 2
                continue

        i += 1

    if items == []:
        return []

    return items

def parse_items_coop(txt):

    #list of dict for all items
    items = []

    pattern_start = r"Typ retazca|Typ reťazca"
    pattern_end = r"SPOLU\s*:"

    pattern_multiline_count = r"(\d+(?:[.,]\d+)?)\s*ks\s+\d+(?:[.,]\d+)\s+(\d+(?:[.,]\d+))\s+[A-Z]$"
    pattern_multiline_weight = r"(\d+(?:[.,]\d+)?)\s*kg\s+\d+(?:[.,]\d+)\s+(\d+(?:[.,]\d+))\s+[A-Z]$"

    pattern_singleline_count = r"(.+?)\s+(\d+(?:[.,]\d+)?)\s*ks\s+\d+(?:[.,]\d+)\s+(\d+(?:[.,]\d+))\s+[A-Z]$"
    pattern_singleline_one = r"(.+?)\s+1\s*ks\s+(\d+(?:[.,]\d+))\s+[A-Z]$"

    #spliting text to list of lines
    lines = txt.splitlines()

    start_index = None
    end_index = None

    for i, line in enumerate(lines):
        if(re.search(pattern_start, line, re.IGNORECASE)):
            start_index = i
            break

    #podmienka
    if start_index is None:
        return []

    for i, line in enumerate(lines[start_index+1:]):
        if(re.search(pattern_end, line, re.IGNORECASE)):
            end_index = i + start_index+1
            break

    #podmienka
    if end_index is None:
        return []

    item_text_lines = lines[start_index+1:end_index]

    i = 0
    while i < len(item_text_lines):
        line = item_text_lines[i].strip()

        #ak su to zlavy tak to skipneme
        if re.search(r"zlava|zľava|bonus|body", line, re.IGNORECASE):
            i += 1
            continue

        # 1. jednoriadkova polozka s 1 ks
        item = re.search(pattern_singleline_one, line, re.IGNORECASE)
        if item:
            items.append({
                "item_name" : item.group(1).strip(),
                "amount" : "1",
                "price" : item.group(2).replace(",", "."),
            })
            i += 1
            continue

        # 2. jednoriadkova polozka s viac ks
        item = re.search(pattern_singleline_count, line, re.IGNORECASE)
        if item:
            items.append({
                "item_name" : item.group(1).strip(),
                "amount" : item.group(2).replace(",", "."),
                "price" : item.group(3).replace(",", "."),
            })
            i += 1
            continue

        # 3. dvojriadkova polozka
        if i < len(item_text_lines) - 1:
            next_line = item_text_lines[i+1].strip()

            item = re.search(pattern_multiline_count, next_line, re.IGNORECASE)
            if item:
                items.append({
                    "item_name" : line,
                    "amount" : item.group(1).replace(",", "."),
                    "price" : item.group(2).replace(",", "."),
                })
                i += 2
                continue

            item = re.search(pattern_multiline_weight, next_line, re.IGNORECASE)
            if item:
                items.append({
                    "item_name" : line,
                    "amount" : item.group(1).replace(",", "."),
                    "price" : item.group(2).replace(",", "."),
                })
                i += 2
                continue

        i += 1

    if items == []:
        return []

    return items