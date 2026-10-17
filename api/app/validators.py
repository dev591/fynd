import re

INDIAN_STATES = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "36": "Telangana",
    "37": "Andhra Pradesh",
}

STATE_NAME_TO_CODE = {v.lower(): k for k, v in INDIAN_STATES.items()}


def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r"[\s\-\+]", "", phone)
    if cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    return bool(re.match(r"^[6-9]\d{9}$", cleaned))


def validate_gstin(gstin: str) -> bool:
    cleaned = gstin.strip().upper()
    return bool(re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", cleaned))


def validate_pan(pan: str) -> bool:
    cleaned = pan.strip().upper()
    return bool(re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", cleaned))


def mask_pan(pan: str | None) -> str | None:
    if not pan:
        return None
    p = pan.strip().upper()
    if len(p) != 10:
        return None
    return f"{p[:5]}XXXX{p[9]}"


def cross_check_tax(gstin: str, pan: str, state_name: str) -> dict:
    clean_gstin = gstin.strip().upper()
    clean_pan = pan.strip().upper()

    gstin_valid = validate_gstin(clean_gstin)
    pan_valid = validate_pan(clean_pan)

    expected_state_code = STATE_NAME_TO_CODE.get(state_name.strip().lower())
    state_match = False
    if expected_state_code and len(clean_gstin) >= 2:
        state_match = clean_gstin[:2] == expected_state_code

    pan_match = False
    if len(clean_pan) == 10 and len(clean_gstin) >= 12:
        pan_match = clean_gstin[2:12] == clean_pan

    consistent = gstin_valid and pan_valid and state_match and pan_match

    return {
        "consistent": consistent,
        "gstin_valid": gstin_valid,
        "pan_valid": pan_valid,
        "state_match": state_match,
        "pan_match": pan_match,
        "state_code": expected_state_code,
        "pan_masked": mask_pan(clean_pan) if pan_valid else None,
    }
