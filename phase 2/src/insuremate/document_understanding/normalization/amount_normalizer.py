"""
Financial amount and currency normalization utilities.
Handles Indian comma formats (e.g. 1,50,000.00), Western formats (150,000.00),
currency symbols (₹, $, €, £), and suffixes (/-).
"""

import re
from typing import Optional, Tuple
from ..schemas.common import FieldStatus
from ..config import CURRENCY_MAP


# Matches currency symbol or word + number
AMOUNT_PATTERN = re.compile(
    r"(?P<curr>[₹$€£]|Rs\.?|INR|USD|EUR|GBP)?\s*"
    r"(?P<amount>\d{1,3}(?:[,\s]\d{2,3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*"
    r"(?P<suffix>\/\-)?",
    re.IGNORECASE,
)


def normalize_amount_string(amount_text: str) -> Tuple[Optional[float], Optional[str], FieldStatus, Optional[str]]:
    """
    Parses a string containing a currency amount into a float and standard ISO currency code.
    
    Returns:
        (amount_float, currency_code, FieldStatus, notes)
    """
    if not amount_text or not amount_text.strip():
        return None, None, FieldStatus.NOT_FOUND, "Empty amount text"

    cleaned = amount_text.strip()
    match = AMOUNT_PATTERN.search(cleaned)
    if not match:
        return None, None, FieldStatus.EXTRACTION_ERROR, f"Could not parse numeric amount from '{cleaned}'"

    curr_raw = match.group("curr")
    amount_str = match.group("amount")

    if not amount_str:
        return None, None, FieldStatus.EXTRACTION_ERROR, "No numeric component found"

    # Normalize currency
    currency_code = "INR"  # Default fallback for Indian insurance context if symbol found or unstated
    if curr_raw:
        curr_lower = curr_raw.lower().strip()
        currency_code = CURRENCY_MAP.get(curr_lower, curr_raw.upper())

    # Remove commas and spaces from the number
    clean_num_str = amount_str.replace(",", "").replace(" ", "")

    try:
        amount_val = float(clean_num_str)
        # Avoid negative amounts unless explicitly required, medical bills have positive charges
        if amount_val < 0:
            return amount_val, currency_code, FieldStatus.AMBIGUOUS, "Negative amount detected"

        return round(amount_val, 2), currency_code, FieldStatus.EXTRACTED, None

    except ValueError:
        return None, currency_code, FieldStatus.EXTRACTION_ERROR, f"Failed to convert '{clean_num_str}' to float"


def extract_amounts_from_text(text: str) -> list[dict]:
    """
    Finds all potential amount occurrences in text.
    """
    results = []
    if not text:
        return results

    for match in AMOUNT_PATTERN.finditer(text):
        amount_str = match.group("amount")
        if not amount_str:
            continue
        # Skip small standalone integers that look like dates or IDs (e.g. 1 or 2 digits with no currency)
        if not match.group("curr") and not match.group("suffix"):
            if len(amount_str) <= 2 or ("." not in amount_str and "," not in amount_str and int(amount_str) < 100):
                continue

        raw = match.group(0).strip()
        val, curr, status, notes = normalize_amount_string(raw)
        if val is not None:
            results.append({
                "raw_text": raw,
                "amount": val,
                "currency": curr,
                "status": status,
                "notes": notes,
                "start": match.start(),
                "end": match.end(),
            })

    return results
