"""
Text normalization utilities for document understanding.
Preserves multilingual characters (Hindi, Gujarati, etc.) while standardizing whitespace and Unicode.
"""

import unicodedata
import re
from typing import Tuple


def normalize_unicode_and_whitespace(text: str) -> str:
    """
    Normalizes Unicode representations (NFKC), converts CRLF to LF,
    collapses excessive spaces, and trims lines while preserving multi-language text.
    """
    if not text:
        return ""

    # Normalize unicode to NFKC (compatibility decomposition followed by canonical composition)
    normalized = unicodedata.normalize("NFKC", text)

    # Standardize line breaks
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # Replace non-breaking spaces and tabs with standard spaces
    normalized = normalized.replace("\u00a0", " ").replace("\t", " ")

    # Preserve columnar spacing: collapse 4+ spaces into 4 spaces (column gap),
    # while collapsing 2-3 spaces into a single space
    lines = normalized.split("\n")
    cleaned_lines = []
    for line in lines:
        line_clean = re.sub(r"[ ]{4,}", "    ", line)
        line_clean = re.sub(r"[ ]{2,3}", " ", line_clean)
        cleaned_lines.append(line_clean.strip())

    # Rejoin lines, collapsing more than 1 consecutive blank line
    result = []
    blank_count = 0
    for line in cleaned_lines:
        if not line:
            blank_count += 1
            if blank_count <= 1:
                result.append("")
        else:
            blank_count = 0
            result.append(line)

    return "\n".join(result).strip()


def calculate_unreadable_char_ratio(text: str) -> float:
    """
    Calculates the ratio of unreadable, replacement, or garbled characters.
    Handles Unicode scripts properly so valid Hindi/Gujarati characters are NOT marked as garbled.
    """
    if not text:
        return 0.0

    total_chars = len(text)
    if total_chars == 0:
        return 0.0

    garbled_count = 0
    for ch in text:
        # Replacement character from failed encoding
        if ch == "\ufffd":
            garbled_count += 1
            continue

        # Non-printable control characters (excluding tab and newline)
        category = unicodedata.category(ch)
        if category.startswith("C") and ch not in ("\n", "\r", "\t"):
            garbled_count += 1
            continue

        # Common OCR garble artifacts: isolated unusual punctuation clusters like ^ ~ ` | \
        # Only count if extremely odd; we prioritize replacement & control chars
        if ch in ("\x00", "\x01", "\x02", "\x03", "\x04", "\x05", "\x06", "\x07", "\x08", "\x0b", "\x0c", "\x0e", "\x0f"):
            garbled_count += 1

    return round(garbled_count / total_chars, 4)
