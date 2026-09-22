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
# Regex patterns for common dates in medical/insurance documents
DATE_PATTERNS = [
    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, DD/MM/YY
    r"\b(?P<day>\d{1,2})[\/\-\.](?P<month>\d{1,2})[\/\-\.](?P<year>\d{2,4})\b",
    # YYYY-MM-DD, YYYY/MM/DD
    r"\b(?P<year>\d{4})[\/\-\.](?P<month>\d{1,2})[\/\-\.](?P<day>\d{1,2})\b",
    # 15 Aug 2023, 15/Nov/2024, 15 August 2023, 15th Aug, 2023
    r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?[\s\/\-]+(?P<month>[A-Za-z]{3,9})[\s,\/\-]+(?P<year>\d{2,4})\b",
    # Aug 15, 2023, August 15 2023
    r"\b(?P<month>[A-Za-z]{3,9})[\s\/\-]+(?P<day>\d{1,2})(?:st|nd|rd|th)?[\s,\/\-]+(?P<year>\d{2,4})\b",
]


def normalize_date_string(date_text: str, prefer_day_first: bool = True) -> Tuple[Optional[str], FieldStatus, Optional[str]]:
    """
    Normalizes a date string into ISO-8601 'YYYY-MM-DD' format.
    Supports Indian (DD/MM/YYYY, DD/MM/YY), textual months, and OCR-distorted dates.
    
    Returns:
        (normalized_date_str, FieldStatus, notes)
    """
    if not date_text or not date_text.strip():
        return None, FieldStatus.NOT_FOUND, "Empty date text"

    cleaned = date_text.strip()
    # Normalize common OCR noise
    cleaned = cleaned.replace("|", "/")
    # Fix OCR slash mistaken as '1' before 2-digit year (e.g. 25/10124 -> 25/10/24)
    cleaned = re.sub(r"(\d{1,2})[\/](\d{1,2})1(\d{2})\b", r"\1/\2/\3", cleaned)

    # 1. Try explicit regex match for standard numeric dates first
    # Avoids dateutil crashing on trailing timestamps or notes (e.g. '19/10/24 - 5:309m')
    m_num = re.search(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b", cleaned)
    if m_num:
        p1, p2, p3 = int(m_num.group(1)), int(m_num.group(2)), int(m_num.group(3))
        year = p3 if p3 >= 100 else (2000 + p3 if p3 < 50 else 1900 + p3)
        if prefer_day_first:
            day, month = p1, p2
        else:
            month, day = p1, p2

        if 1 <= month <= 12 and 1 <= day <= 31 and MIN_REASONABLE_YEAR <= year <= MAX_REASONABLE_YEAR:
            try:
                dt = datetime(year, month, day)
                is_ambig = (p1 <= 12 and p2 <= 12 and p1 != p2)
                status = FieldStatus.AMBIGUOUS if is_ambig else FieldStatus.EXTRACTED
                notes = f"Ambiguous day/month parsed with dayfirst={prefer_day_first}" if is_ambig else None
                return dt.strftime("%Y-%m-%d"), status, notes
            except ValueError:
                pass

    # 2. Match textual month: DD/Mon/YYYY or DD-Mon-YYYY or DD Mon YYYY
    m_text = re.search(r"\b(\d{1,2})[\/\-\s]+([A-Za-z]{3,9})[\/\-\s,]+(\d{2,4})\b", cleaned)
    if m_text:
        try:
            sub = m_text.group(0).replace("/", " ")
            dt = parser.parse(sub, dayfirst=True)
            year = dt.year if dt.year >= 100 else (2000 + dt.year if dt.year < 50 else 1900 + dt.year)
            if MIN_REASONABLE_YEAR <= year <= MAX_REASONABLE_YEAR:
                return dt.strftime("%Y-%m-%d"), FieldStatus.EXTRACTED, None
        except Exception:
            pass

    # 3. Fallback to general dateutil parser
    try:
        parsed_dt = parser.parse(cleaned, dayfirst=prefer_day_first, fuzzy=True)
        year = parsed_dt.year
        if year < MIN_REASONABLE_YEAR or year > MAX_REASONABLE_YEAR:
            return None, FieldStatus.AMBIGUOUS, f"Year {year} is outside reasonable range ({MIN_REASONABLE_YEAR}-{MAX_REASONABLE_YEAR})"

        normalized_iso = parsed_dt.strftime("%Y-%m-%d")

        # Check for ambiguity
        ambiguous_match = re.search(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b", cleaned)
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
