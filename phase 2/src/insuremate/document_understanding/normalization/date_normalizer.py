"""
Date normalization utilities for medical and insurance documents.
Supports Indian (DD/MM/YYYY), ISO (YYYY-MM-DD), and textual date formats.
"""

import re
from datetime import datetime
from typing import Optional, Tuple
from dateutil import parser
from ..schemas.common import FieldStatus
from ..config import MIN_REASONABLE_YEAR, MAX_REASONABLE_YEAR


# Regex patterns for common dates in medical/insurance documents
DATE_PATTERNS = [
    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    r"\b(?P<day>\d{1,2})[\/\-\.](?P<month>\d{1,2})[\/\-\.](?P<year>\d{4})\b",
    # YYYY-MM-DD, YYYY/MM/DD
    r"\b(?P<year>\d{4})[\/\-\.](?P<month>\d{1,2})[\/\-\.](?P<day>\d{1,2})\b",
    # 15 Aug 2023, 15 August 2023, 15th Aug, 2023
    r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month>[A-Za-z]{3,9})[\s,]+(?P<year>\d{4})\b",
    # Aug 15, 2023, August 15 2023
    r"\b(?P<month>[A-Za-z]{3,9})\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?[\s,]+(?P<year>\d{4})\b",
]


def normalize_date_string(date_text: str, prefer_day_first: bool = True) -> Tuple[Optional[str], FieldStatus, Optional[str]]:
    """
    Normalizes a date string into ISO-8601 'YYYY-MM-DD' format.
    
    Returns:
        (normalized_date_str, FieldStatus, notes)
    """
    if not date_text or not date_text.strip():
        return None, FieldStatus.NOT_FOUND, "Empty date text"

    cleaned = date_text.strip()

    # Try dateutil parser with dayfirst setting
    try:
        parsed_dt = parser.parse(cleaned, dayfirst=prefer_day_first, fuzzy=True)
        year = parsed_dt.year
        if year < MIN_REASONABLE_YEAR or year > MAX_REASONABLE_YEAR:
            return None, FieldStatus.AMBIGUOUS, f"Year {year} is outside reasonable range ({MIN_REASONABLE_YEAR}-{MAX_REASONABLE_YEAR})"

        normalized_iso = parsed_dt.strftime("%Y-%m-%d")

        # Check for ambiguity (e.g. 05/06/2023 where both day and month <= 12)
        ambiguous_match = re.search(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})\b", cleaned)
        is_ambiguous = False
        notes = None
        if ambiguous_match:
            d1, d2 = int(ambiguous_match.group(1)), int(ambiguous_match.group(2))
            if d1 <= 12 and d2 <= 12 and d1 != d2:
                is_ambiguous = True
                notes = f"Ambiguous day/month in '{cleaned}'. Parsed with dayfirst={prefer_day_first} as {normalized_iso}"

        status = FieldStatus.AMBIGUOUS if is_ambiguous else FieldStatus.EXTRACTED
        return normalized_iso, status, notes

    except (ValueError, OverflowError, re.error) as e:
        return None, FieldStatus.EXTRACTION_ERROR, f"Failed to parse date: {str(e)}"


def extract_dates_from_text(text: str) -> list[dict]:
    """
    Finds all date occurrences within a text string.
    Returns list of dicts with: raw_text, normalized_date, status, notes.
    """
    found_dates = []
    if not text:
        return found_dates

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw_match = match.group(0)
            norm_date, status, notes = normalize_date_string(raw_match, prefer_day_first=True)
            if norm_date:
                found_dates.append({
                    "raw_text": raw_match,
                    "normalized_date": norm_date,
                    "status": status,
                    "notes": notes,
                    "start": match.start(),
                    "end": match.end(),
                })

    return found_dates
