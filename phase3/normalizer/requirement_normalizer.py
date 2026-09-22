import re
import logging
from typing import List, Optional
from phase3.schema.models import RequirementItem, Category, Priority

logger = logging.getLogger("phase3.normalizer")


class RequirementNormalizer:
    """Normalizes requirement items: standardizes fields, canonical names, categories, and deadlines."""

    CATEGORY_MAP = {
        "DOC": Category.DOCUMENT,
        "DOCUMENT": Category.DOCUMENT,
        "DOCUMENTS": Category.DOCUMENT,
        "PAPER": Category.DOCUMENT,
        "INFO": Category.INFORMATION,
        "INFORMATION": Category.INFORMATION,
        "COND": Category.CONDITION,
        "CONDITION": Category.CONDITION,
        "CONDITIONAL": Category.CONDITION,
        "CONDITIONS": Category.CONDITION,
        "ACT": Category.ACTION,
        "ACTION": Category.ACTION,
        "PROCEDURE": Category.ACTION,
        "DEADLINE": Category.DEADLINE,
        "TIME_LIMIT": Category.DEADLINE,
        "TIMELINE": Category.DEADLINE,
        "FINANCIAL": Category.FINANCIAL,
        "COST": Category.FINANCIAL,
        "MONEY": Category.FINANCIAL,
    }

    PRIORITY_MAP = {
        "HIGH": Priority.HIGH,
        "URGENT": Priority.HIGH,
        "CRITICAL": Priority.HIGH,
        "MEDIUM": Priority.MEDIUM,
        "NORMAL": Priority.MEDIUM,
        "STANDARD": Priority.MEDIUM,
        "LOW": Priority.LOW,
        "OPTIONAL": Priority.LOW,
    }

    CANONICAL_NAMES = {
        "discharge card": "Hospital Discharge Summary",
        "discharge summary": "Hospital Discharge Summary",
        "hospital discharge card": "Hospital Discharge Summary",
        "hospital discharge summary": "Hospital Discharge Summary",
        "final hospital bill": "Itemized Hospital Final Bill",
        "hospital bill": "Itemized Hospital Final Bill",
        "itemized bill": "Itemized Hospital Final Bill",
        "detailed hospital bill": "Itemized Hospital Final Bill",
        "payment receipt": "Hospital Payment Receipts",
        "payment receipts": "Hospital Payment Receipts",
        "cash receipts": "Hospital Payment Receipts",
        "doctor prescription": "Doctor Prescriptions and Consultation Papers",
        "prescriptions": "Doctor Prescriptions and Consultation Papers",
        "investigation report": "Diagnostic and Investigation Reports",
        "diagnostic report": "Diagnostic and Investigation Reports",
        "lab reports": "Diagnostic and Investigation Reports",
        "fir": "Police FIR and Medico-Legal Certificate (MLC)",
        "police fir": "Police FIR and Medico-Legal Certificate (MLC)",
        "mlc": "Police FIR and Medico-Legal Certificate (MLC)",
        "claim form": "Claim Form",
        "pre-auth": "Cashless Pre-Authorization Approval",
        "pre authorization": "Cashless Pre-Authorization Approval",
        "kyc": "KYC and Bank Account Details",
    }

    @classmethod
    def normalize(cls, item: RequirementItem) -> RequirementItem:
        """Normalize a single RequirementItem in place or return cleaned copy."""
        # 1. Clean and normalize category
        if isinstance(item.category, str):
            cat_str = item.category.strip().upper()
            item.category = cls.CATEGORY_MAP.get(cat_str, Category.DOCUMENT)

        # 2. Clean and normalize priority
        if isinstance(item.priority, str):
            prio_str = item.priority.strip().upper()
            item.priority = cls.PRIORITY_MAP.get(prio_str, Priority.HIGH)

        # 3. Clean and normalize name
        clean_name = item.name.strip()
        # Remove trailing periods or colons
        clean_name = re.sub(r"[:.]+$", "", clean_name)
        lower_name = clean_name.lower()
        for key, canonical in cls.CANONICAL_NAMES.items():
            if key in lower_name:
                clean_name = canonical
                break
        item.name = clean_name

        # 4. Clean description
        item.description = item.description.strip()
        if not item.description.endswith("."):
            item.description += "."

        # 5. Clean deadlines
        if item.deadline:
            item.deadline = cls._normalize_deadline(item.deadline)

        # 6. Normalize required_information list
        if item.required_information:
            cleaned_info = []
            seen = set()
            for info in item.required_information:
                cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", info.strip().lower()).strip("_")
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    cleaned_info.append(cleaned)
            item.required_information = cleaned_info

        # 7. Normalize condition
        if item.condition:
            item.condition = item.condition.strip()
            # If condition exists, ensure mandatory is false
            item.mandatory = False
        else:
            item.condition = None

        return item

    @classmethod
    def normalize_list(cls, items: List[RequirementItem]) -> List[RequirementItem]:
        """Normalize a collection of RequirementItem instances."""
        return [cls.normalize(item) for item in items]

    @classmethod
    def _normalize_deadline(cls, deadline_str: str) -> str:
        """Normalize deadline strings to a clear concise format."""
        s = deadline_str.strip()
        m_within = re.search(r"within\s+(\d+\s*(?:hours|hrs|days|working\s+days|weeks))", s, re.I)
        if m_within:
            return f"Within {m_within.group(1).lower()}"
        m_prior = re.search(r"(\d+\s*(?:hours|hrs|days))\s+(?:prior|before)", s, re.I)
        if m_prior:
            return f"At least {m_prior.group(1).lower()} prior"
        return s
