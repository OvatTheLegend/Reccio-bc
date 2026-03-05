import pdfplumber, re

#extraction from pdf to text
def extract_from_pdf(path):
    txt = ""
    #opening file
    with pdfplumber.open(path) as pdf:
        #for loop to loop trough all pdf pages
        for pg in pdf.pages:
            #extract text from page and add to txt if there is any text to read, else continue
            pg_txt = pg.extract_text()
            if pg_txt:
                txt +=pg_txt
            else:
                continue
    return txt

#                                    parser for receipt section
#--------------------------------------------------------------------------------------------------

#parser for receipt -> shop,date,time,prize
def parse_receipt(txt):
    
    shop_name = find_shop_name(txt)
    date = find_date(txt)
    time = find_time(txt)
    prize = find_prize(txt)

    #podmienky:
    if not shop_name or not date or not time or not prize:
        return {}

    #return dictionary type 
    return {
        "shop_name" : shop_name,
        "date" : date,
        "time" : time,
        "prize" : prize,
    }

#function for getting name of shop of out e-block txt, using regex syntax
def find_shop_name(txt):
    #what pattern to seach for? defined here
    patterns = {
            "Dr.Max" : r"Dr\.?\s*Max",
            "TERNO" : r"TERNO",
    }

    #iterate trough our dict shop-regex, if found return name of shop, else unknown
    for shop, pattern in patterns.items():
        if re.search(pattern,txt,re.IGNORECASE):
            return shop
    
    return ""

#function for getting date 
def find_date(txt):
    pattern = r"\b\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\b"

    date = re.search(pattern,txt)

    if date:
        return date.group()
    
    return ""
        
#function for getting time
def find_time(txt):
    pattern = r"\b\d{1,2}\s*:\s*\d{1,2}\s*:\s*\d{1,2}\b"

    time = re.search(pattern,txt)

    if time:
        return time.group()
    
    return ""

def find_prize(txt):
    pattern = r"(?:CELKOM|Celkom|Suma)\s*:\s*(\d+(?:\.|,)\d{1,2})\s*(?:EUR|€|EURO)"

    prize = re.search(pattern,txt,re.IGNORECASE)

    if prize:
        return prize.group(1)
    
    return ""

#                           parser universal (items) section
#-----------------------------------------------------------------------------------------------

#parser for unique shop
def parse_items_universal(shopName, txt):
    print("starting universal parser")
    parsers = {
        "Dr.Max" : parse_items_drmax,
        "TERNO" : parse_items_terno,
    }

    parser = parsers.get(shopName)

    if (parser):
        return parser(txt)

    else:
        return []

#                            parser for unique shop type (items) seciton
#----------------------------------------------------------------------------------------------------
#parser for TERNO
def parse_items_drmax(txt):
    print("drmax pareser activated")
    return []
#parser for TERNO
def parse_items_terno(txt):

    print("starting terno parser")
    #list of dict for all items
    items = []

    pattern_start = r"Množstvo\s+Cena\s+DPH\s+SUMA"
    pattern_end = r"[-—–]{6,}"
    pattern_items = r"(\d+(?:\.\d+)?)x\s+\d+(?:\.|,)\d+\s+(?:\d+\s*%\s+)?(\d+(?:\.|,)\d+)"

    #spliting text to list of lines
    txt = re.sub(r"(?<!\n)(?<!\d\.)\b(\d+)x", r"\n\1x", txt)
    lines = txt.splitlines()

    start_index = None
    end_index = None

    for i, line in enumerate(lines):
        if(re.search(pattern_start,line,re.IGNORECASE)):
            start_index = i
            print("nasiel sa zaciatok")
            break
    
    #podmienka
    if start_index is None:
        print("nenasiel sa pociatok listu")
        return []

    for i, line in enumerate(lines[start_index+2:]):
        if(re.search(pattern_end,line,re.IGNORECASE)):
            print("nasiel sa koniec")
            end_index = i + start_index+2
            break
    #podmienka
    if end_index is None:
        print("nenasiel sa koinec listu")
        return []
    

    item_text_lines = lines[start_index+2:end_index-1]

    i = 0
    while i < len(item_text_lines) - 1:

        item_name = item_text_lines[i].strip()
        item = re.search(pattern_items,item_text_lines[i+1])

        if item:
            i += 2
            items.append({
                "item_name" : item_name,
                "amount" : item.group(1),
                "prize" : item.group(2),
            })
        else:
            i += 1
            continue

    if items == []:
        return []
    
    return items
    


