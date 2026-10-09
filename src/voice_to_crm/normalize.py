import re 
def normalize_name(value: str | None) -> str | None:
    if value is None:
        return None
    
    return value.strip().casefold()

def normalize_company(value: str | None) -> str | None:
    stopWords= ["inc", "llc", "corp", "company","ltd", "co", "plc", "limited", "incorporated"]
    if value is None:
        return None
    cleaned = re.sub(r"[^\w\s]", "", value.strip().lower())
    words = cleaned.split()    
    filtered_words = [word for word in words if word not in stopWords]
    return  " ".join(filtered_words) if filtered_words else cleaned

def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower()

def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits=""
    for i in value.strip():
        if i.isdigit():
            digits+=i
    return digits[-10:] if digits else None

def is_valid_email(value:str| None)-> bool:
    if value is None:
        return False
    email= value.strip()
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))
         
            
    