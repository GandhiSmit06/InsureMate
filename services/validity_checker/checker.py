"""
services/validity_checker/checker.py
Deterministic Validity Checker for InsureMate.
Compares policy coverage periods against claim dates (hospital admission, medical bills, reports),
validates identity consistency, and handles multi-format date normalization.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from utils.logger import logger


@dataclass
class DateCheckItem:
    """Individual document date verification record."""
    document_type: str
    page_number: int
    raw_date: Optional[str]
    normalized_date: Optional[str]
    valid: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["page"] = self.page_number
        return d


@dataclass
class ValidityCheckResult:
    """Overall validity check result returned to the agent."""
    valid: bool
    reasons: List[str] = field(default_factory=list)
    checks: List[DateCheckItem] = field(default_factory=list)
    policy_period: Dict[str, Optional[str]] = field(default_factory=dict)
    identity_match: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "reasons": self.reasons,
            "policy_period": self.policy_period,
            "identity_match": self.identity_match,
            "checks": [c.to_dict() for c in self.checks],
        }


class ValidityChecker:
    """
    Deterministic validity evaluation tool.
    Normalizes dates, compares them to policy coverage dates,
    and flags any claims occurring outside the policy window.
    """

    MONTH_MAP = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    def parse_and_normalize_date(self, date_str: Optional[str]) -> Tuple[Optional[datetime], Optional[str]]:
        """
        Parse and normalize date strings in various formats:
        - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        - YYYY-MM-DD, YYYY/MM/DD
        - DD Month YYYY (e.g. 12-Mar-2025, 12 March 2025)

        Returns:
            Tuple of (datetime object, normalized string 'DD/MM/YYYY') or (None, None)
        """
        if not date_str or not isinstance(date_str, str):
            return None, None

        cleaned = date_str.strip().strip("'\"")
        if not cleaned:
            return None, None

        # Try standard datetime formats first
        standard_formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
            "%Y-%m-%d", "%Y/%m/%d",
            "%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%d-%B-%Y",
            "%b %d, %Y", "%B %d, %Y",
            "%Y%m%d"
        ]

        for fmt in standard_formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt, dt.strftime("%d/%m/%Y")
            except ValueError:
                continue

        # Regex fallback for named months: e.g. "19/Oct/2024" or "19-10-2024"
        parts = re.split(r"[-/\s,.]+", cleaned)
        if len(parts) >= 3:
            p1, p2, p3 = parts[0], parts[1], parts[2]
            try:
                # Case: DD Month YYYY
                if p2.lower() in self.MONTH_MAP and p1.isdigit() and p3.isdigit():
                    day = int(p1)
                    month = self.MONTH_MAP[p2.lower()]
                    year = int(p3)
                    dt = datetime(year, month, day)
                    return dt, dt.strftime("%d/%m/%Y")

                # Case: Month DD YYYY
                if p1.lower() in self.MONTH_MAP and p2.isdigit() and p3.isdigit():
                    month = self.MONTH_MAP[p1.lower()]
                    day = int(p2)
                    year = int(p3)
                    dt = datetime(year, month, day)
                    return dt, dt.strftime("%d/%m/%Y")

                # Case: Numeric parts
                if p1.isdigit() and p2.isdigit() and p3.isdigit():
                    num1, num2, num3 = int(p1), int(p2), int(p3)
                    if num1 > 1900:  # YYYY/MM/DD
                        dt = datetime(num1, num2, num3)
                    else:  # DD/MM/YYYY
                        dt = datetime(num3, num2, num1)
                    return dt, dt.strftime("%d/%m/%Y")
            except (ValueError, OverflowError):
                pass

        return None, None

    START_DATE_CANDIDATES = [
        "policy_start_date",
        "policy_inception_date",
        "inception_date",
        "coverage_start_date",
        "effective_date",
        "start_date",
        "from_date",
    ]

    END_DATE_CANDIDATES = [
        "policy_end_date",
        "policy_expiry_date",
        "expiry_date",
        "coverage_end_date",
        "expiration_date",
        "end_date",
        "to_date",
    ]

    @classmethod
    def _find_date_candidate(cls, data: Any, candidates: List[str]) -> Optional[str]:
        """Find non-empty date value among candidate keys, including nested containers."""
        if not isinstance(data, dict):
            return None
        for k in candidates:
            v = data.get(k)
            if v and isinstance(v, (str, int)) and str(v).strip():
                return str(v).strip()
        # Also check nested policy_period, period, coverage_period
        for container_key in ("policy_period", "period", "coverage_period", "validity_period"):
            container = data.get(container_key)
            if isinstance(container, dict):
                for k in candidates:
                    v = container.get(k)
                    if v and isinstance(v, (str, int)) and str(v).strip():
                        return str(v).strip()
                if "start" in container and candidates == cls.START_DATE_CANDIDATES:
                    v = container.get("start")
                    if v and str(v).strip():
                        return str(v).strip()
                if "end" in container and candidates == cls.END_DATE_CANDIDATES:
                    v = container.get("end")
                    if v and str(v).strip():
                        return str(v).strip()
        return None

    def check_validity(
        self,
        policy_data: Union[Dict[str, Any], List[Dict[str, Any]]],
        document_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> ValidityCheckResult:
        """
        Validate document dates against policy coverage duration and identity.
        """
        logger.validity("Initiating claim validity assessment")

        reasons: List[str] = []
        checks: List[DateCheckItem] = []

        # 1. Resolve policy metadata
        policy_info = self._extract_policy_info(policy_data)
        raw_start = self._find_date_candidate(policy_info, self.START_DATE_CANDIDATES)
        raw_end = self._find_date_candidate(policy_info, self.END_DATE_CANDIDATES)
        policy_number = policy_info.get("policy_number") or policy_info.get("policy_id") or policy_info.get("policy_no")

        start_dt, norm_start = self.parse_and_normalize_date(raw_start)
        end_dt, norm_end = self.parse_and_normalize_date(raw_end)

        policy_period_dict = {
            "policy_start_date": norm_start or raw_start,
            "policy_end_date": norm_end or raw_end,
            "start": norm_start or raw_start,
            "end": norm_end or raw_end,
            "policy_number": policy_number,
        }

        # Check required policy date fields
        policy_dates_valid = True
        if not raw_start:
            reasons.append("Policy start date is missing; cannot establish coverage period.")
            policy_dates_valid = False
        elif not start_dt:
            reasons.append(f"Policy start date '{raw_start}' has an invalid or unparseable format.")
            policy_dates_valid = False

        if not raw_end:
            reasons.append("Policy end date is missing; cannot establish coverage period.")
            policy_dates_valid = False
        elif not end_dt:
            reasons.append(f"Policy end date '{raw_end}' has an invalid or unparseable format.")
            policy_dates_valid = False

        if start_dt and end_dt:
            if start_dt > end_dt:
                reasons.append(
                    f"Policy start date ({norm_start}) is after policy end date ({norm_end}); invalid policy period."
                )
                policy_dates_valid = False
            else:
                reasons.append(f"Policy dates are available and valid ({norm_start} to {norm_end}).")

        # 2. Normalize submitted documents list
        docs_list: List[Dict[str, Any]] = []
        if isinstance(document_data, list):
            docs_list = document_data
        elif isinstance(document_data, dict):
            docs_list = [document_data]

        if not docs_list:
            reasons.append("No claim documents or bills provided for validity checking.")
            return ValidityCheckResult(
                valid=False,
                reasons=reasons,
                checks=[],
                policy_period=policy_period_dict,
            )

        # 3. Check each document's date against policy window
        all_doc_checks_passed = True
        has_at_least_one_bill_or_report = False

        for doc in docs_list:
            doc_type = doc.get("document_type", "unknown")
            page_num = doc.get("page_number") or doc.get("page_no") or doc.get("page") or 0

            # Skip policy copy itself when checking claim event dates
            if doc_type == "insurance_policy":
                continue

            has_at_least_one_bill_or_report = True

            # Extract document date
            raw_doc_date = doc.get("document_date") or doc.get("bill_date") or doc.get("report_date")

            if not raw_doc_date:
                reasons.append(f"Missing date on '{doc_type}' (Page {page_num}); cannot verify coverage.")
                checks.append(DateCheckItem(
                    document_type=doc_type,
                    page_number=page_num,
                    raw_date=None,
                    normalized_date=None,
                    valid=False,
                    reason=f"Date is missing on {doc_type} (Page {page_num}).",
                ))
                all_doc_checks_passed = False
                continue

            doc_dt, norm_doc_date = self.parse_and_normalize_date(raw_doc_date)

            if not doc_dt:
                reasons.append(
                    f"Invalid date format '{raw_doc_date}' on '{doc_type}' (Page {page_num})."
                )
                checks.append(DateCheckItem(
                    document_type=doc_type,
                    page_number=page_num,
                    raw_date=raw_doc_date,
                    normalized_date=None,
                    valid=False,
                    reason=f"Invalid date format '{raw_doc_date}' (Page {page_num}).",
                ))
                all_doc_checks_passed = False
                continue

            # Compare against policy period if policy dates are valid
            if not policy_dates_valid or not start_dt or not end_dt:
                checks.append(DateCheckItem(
                    document_type=doc_type,
                    page_number=page_num,
                    raw_date=raw_doc_date,
                    normalized_date=norm_doc_date,
                    valid=False,
                    reason="Cannot verify document date because policy coverage period is invalid or missing.",
                ))
                all_doc_checks_passed = False
                continue

            if doc_dt < start_dt:
                reason = (
                    f"Document date ({norm_doc_date}) falls outside the policy validity period: "
                    f"prior to policy inception ({norm_start}) on page {page_num}."
                )
                logger.validity(f"Page {page_num} FAIL: {reason}")
                reasons.append(reason)
                checks.append(DateCheckItem(
                    document_type=doc_type,
                    page_number=page_num,
                    raw_date=raw_doc_date,
                    normalized_date=norm_doc_date,
                    valid=False,
                    reason=reason,
                ))
                all_doc_checks_passed = False
            elif doc_dt > end_dt:
                reason = (
                    f"Document date ({norm_doc_date}) falls outside the policy validity period: "
                    f"after policy expiry ({norm_end}) on page {page_num}."
                )
                logger.validity(f"Page {page_num} FAIL: {reason}")
                reasons.append(reason)
                checks.append(DateCheckItem(
                    document_type=doc_type,
                    page_number=page_num,
                    raw_date=raw_doc_date,
                    normalized_date=norm_doc_date,
                    valid=False,
                    reason=reason,
                ))
                all_doc_checks_passed = False
            else:
                reason = (
                    f"Document date ({norm_doc_date}) falls within the policy validity period "
                    f"({norm_start} to {norm_end}) on page {page_num}."
                )
                logger.validity(f"Page {page_num} PASS: {reason}")
                reasons.append(reason)
                checks.append(DateCheckItem(
                    document_type=doc_type,
                    page_number=page_num,
                    raw_date=raw_doc_date,
                    normalized_date=norm_doc_date,
                    valid=True,
                    reason=reason,
                ))

        if not has_at_least_one_bill_or_report and policy_dates_valid:
            reasons.append("Only policy documents provided; no medical bills or reports to verify dates against.")
            all_doc_checks_passed = False

        # 4. Identity & Floater Member Verification
        identity_report = self._verify_identity(policy_info, docs_list)
        identity_valid = True
        if identity_report:
            if identity_report.get("note"):
                reasons.append(identity_report["note"])
            if identity_report.get("all_matched") is False:
                identity_valid = False
                reasons.append("Patient identity mismatch: Patient does not match covered policy members.")

        overall_valid = policy_dates_valid and all_doc_checks_passed and has_at_least_one_bill_or_report and identity_valid

        logger.result(
            f"Validity evaluation result: valid={overall_valid} | checks={len(checks)} | reasons={len(reasons)}"
        )

        return ValidityCheckResult(
            valid=overall_valid,
            reasons=reasons,
            checks=checks,
            policy_period=policy_period_dict,
            identity_match=identity_report,
        )

    def _extract_policy_info(self, policy_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Extract policy fields whether passed as dict or list of pages, searching candidate keys."""
        if not policy_data:
            return {}

        pages: List[Dict[str, Any]] = []
        if isinstance(policy_data, dict):
            pages = [policy_data]
        elif isinstance(policy_data, list):
            pages = [p for p in policy_data if isinstance(p, dict)]

        if not pages:
            return {}

        # Merge fields across all pages (preserving first found)
        merged_policy: Dict[str, Any] = {}
        for p in pages:
            for k, v in p.items():
                if v is not None and k not in merged_policy:
                    merged_policy[k] = v

        # Resolve start date candidate across all pages
        start_val = self._find_date_candidate(merged_policy, self.START_DATE_CANDIDATES)
        if not start_val:
            for p in pages:
                start_val = self._find_date_candidate(p, self.START_DATE_CANDIDATES)
                if start_val:
                    break

        # Resolve end date candidate across all pages
        end_val = self._find_date_candidate(merged_policy, self.END_DATE_CANDIDATES)
        if not end_val:
            for p in pages:
                end_val = self._find_date_candidate(p, self.END_DATE_CANDIDATES)
                if end_val:
                    break

        if start_val:
            merged_policy["policy_start_date"] = start_val
            merged_policy["start"] = start_val
        if end_val:
            merged_policy["policy_end_date"] = end_val
            merged_policy["end"] = end_val

        return merged_policy

    def _verify_identity(
        self,
        policy_info: Dict[str, Any],
        docs_list: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Verify whether patient matches policyholder or floater family members."""
        insured_list = policy_info.get("insured_names", []) or []
        holder = policy_info.get("policy_holder_name")
        if holder and holder not in insured_list:
            insured_list.append(holder)

        if not insured_list:
            return None

        patient_matches = []
        for doc in docs_list:
            p_name = doc.get("patient_name")
            if p_name:
                matched = any(
                    self._names_match(p_name, ins)
                    for ins in insured_list
                )
                patient_matches.append({
                    "patient_name": p_name,
                    "matched": matched,
                    "page_number": doc.get("page_number"),
                })

        if patient_matches:
            all_matched = all(m["matched"] for m in patient_matches)
            first_name = patient_matches[0]["patient_name"]
            if all_matched:
                note = f"Patient name '{first_name}' successfully matched against covered policy member(s)."
            else:
                note = f"Patient name '{first_name}' does not match any registered floater policy members."
            return {
                "covered_members": insured_list,
                "matches": patient_matches,
                "all_matched": all_matched,
                "note": note,
            }

        return None

    @classmethod
    def _names_match(cls, patient_raw: str, member_raw: str) -> bool:
        """Check if patient name matches a member name, supporting initials, middle names, and order."""
        p_clean = re.sub(r"\b(mr|mrs|ms|dr|master|shri|smt)\b", "", patient_raw.lower())
        m_clean = re.sub(r"\b(mr|mrs|ms|dr|master|shri|smt)\b", "", member_raw.lower())
        p_tokens = [t for t in re.split(r"[\s._,-]+", p_clean) if t]
        m_tokens = [t for t in re.split(r"[\s._,-]+", m_clean) if t]
        if not p_tokens or not m_tokens:
            return False

        required_matches = min(2, len(p_tokens), len(m_tokens))
        # Direct token intersection (e.g. ['john', 'doe'] vs ['john', 'sample', 'doe'])
        p_set = set(p_tokens)
        m_set = set(m_tokens)
        if len(p_set.intersection(m_set)) >= required_matches:
            return True

        # Check token and initial alignment
        matches = 0
        used_m = set()
        for pt in p_tokens:
            for idx, mt in enumerate(m_tokens):
                if idx in used_m:
                    continue
                if pt == mt or (len(pt) == 1 and mt.startswith(pt)) or (len(mt) == 1 and pt.startswith(mt)):
                    matches += 1
                    used_m.add(idx)
                    break

        return matches >= required_matches


def validity_checker(
    policy_data: Union[Dict[str, Any], List[Dict[str, Any]]],
    document_data: Union[Dict[str, Any], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Callable functional interface for Validity Checker.
    """
    checker = ValidityChecker()
    result = checker.check_validity(policy_data, document_data)
    return result.to_dict()
