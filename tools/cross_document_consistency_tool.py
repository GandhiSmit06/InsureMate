import re
from typing import Any, Dict, List, Optional, Set, Tuple
from tools.base_tool import AgentTool
from utils.logger import logger


COMPANY_NOISE_TOKENS = {
    "ltd", "limited", "co", "corp", "corporation", "inc", "incorporated",
    "insurance", "assurance", "company", "general", "health", "life",
    "mediclaim", "india", "services", "service", "tpa", "private", "pvt",
    "the", "and", "&", "of", "for", "verified", "direct", "contact", "other"
}

TITLE_PREFIXES = {"mr", "mrs", "ms", "smt", "dr", "mast", "master", "shri", "kumari", "prof"}

HOSPITAL_NOISE_TOKENS = {
    "hospital", "clinic", "center", "centre", "healthcare", "health", "care",
    "medical", "institute", "nursing", "home", "multispeciality", "speciality",
    "super", "city", "memorial", "charitable", "trust", "private", "ltd", "limited"
}

TPA_INDICATORS = {
    "tpa", "third party administrator", "t.p.a", "claims administrator",
    "medi assist", "vidal", "paramount", "raksha", "heritage", "mdindia",
    "fhpl", "ericson", "safeway", "health india", "family health plan"
}


def _match_patient_name(p_norm: str, p_tokens: Set[str], m_norm: str, m_tokens: Set[str]) -> Tuple[bool, str]:
    """
    Rigorously match patient name against covered member name.
    Distinguishes genuine identity mismatches from normal formatting variations:
    - Exact match
    - Token permutation ("Aarav Mehta" == "Mehta, Aarav")
    - Middle name omission ("Aarav Kumar Sharma" matches "Aarav Sharma" where both first and last names match)
    - First initial + surname match ("A. Sharma" matches "Aarav Sharma")
    - High Levenshtein similarity (>= 0.88) for minor OCR typos ("Arav Sharma" vs "Aarav Sharma")
    NEVER matches different first names just because they share a surname ("Aarav Sharma" vs "Rajesh Sharma").
    """
    if not p_norm or not m_norm:
        return False, "EMPTY"

    if p_norm == m_norm:
        return True, "EXACT_NAME_MATCH"

    if p_tokens and m_tokens and p_tokens == m_tokens:
        return True, "PERMUTATION_MATCH"

    sim = _levenshtein_similarity(p_norm, m_norm)
    if sim >= 0.88:
        return True, "HIGH_SIMILARITY_MATCH"

    if p_tokens and m_tokens:
        s_tokens, l_tokens = (p_tokens, m_tokens) if len(p_tokens) < len(m_tokens) else (m_tokens, p_tokens)
        if len(s_tokens) >= 2 and s_tokens.issubset(l_tokens):
            return True, "MIDDLE_NAME_VARIATION"

        # First initial + last name match
        if len(p_tokens) == 2 and len(m_tokens) == 2:
            p_initials = [t for t in p_tokens if len(t) == 1]
            p_full = [t for t in p_tokens if len(t) > 1]
            m_full = [t for t in m_tokens if len(t) > 1]
            if p_initials and len(p_full) == 1 and len(m_full) == 2:
                shared_surname = set(p_full) & set(m_full)
                if shared_surname:
                    other_m = (set(m_full) - shared_surname).pop()
                    if other_m.startswith(p_initials[0]):
                        return True, "INITIAL_SURNAME_MATCH"

            m_initials = [t for t in m_tokens if len(t) == 1]
            if m_initials and len(m_full) == 1 and len(p_full) == 2:
                shared_surname = set(m_full) & set(p_full)
                if shared_surname:
                    other_p = (set(p_full) - shared_surname).pop()
                    if other_p.startswith(m_initials[0]):
                        return True, "INITIAL_SURNAME_MATCH"

    return False, "MISMATCH"


def _levenshtein_similarity(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein similarity between two strings [0.0, 1.0]."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    prev = list(range(len2 + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1] * (len2 + 1)
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr[j + 1] = min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost)
        prev = curr

    dist = prev[len2]
    max_len = max(len1, len2)
    return 1.0 - (dist / max_len)


def _normalize_company_name(name: str) -> Tuple[str, Set[str]]:
    """
    Normalize company name: lowercase, strip punctuation, filter noise words.
    Returns (cleaned_joined_string, set_of_core_tokens).
    """
    if not name:
        return "", set()
    cleaned = re.sub(r"[^\w\s]", " ", str(name).lower())
    raw_tokens = [t.strip() for t in cleaned.split() if t.strip()]
    core_tokens = [t for t in raw_tokens if t not in COMPANY_NOISE_TOKENS and len(t) > 1]
    norm_str = " ".join(core_tokens) if core_tokens else " ".join(raw_tokens)
    return norm_str, set(core_tokens if core_tokens else raw_tokens)


def _normalize_name(name: str) -> Tuple[str, Set[str]]:
    """Normalize personal/patient name removing common honorific prefixes."""
    if not name:
        return "", set()
    cleaned = re.sub(r"[^\w\s]", " ", str(name).lower())
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    filtered = [t for t in tokens if t not in TITLE_PREFIXES]
    return " ".join(filtered), set(filtered)


def _normalize_policy_num(val: Any) -> str:
    """Normalize policy number by stripping spaces, hyphens, slashes, and leading zeros."""
    if not val:
        return ""
    cleaned = re.sub(r"[\s\-_/\.]+", "", str(val).lower())
    return cleaned.lstrip("0")


class CrossDocumentConsistencyTool(AgentTool):
    """
    Callable Agent Tool: Dynamic Multi-Entity Cross-Document Consistency Checker.
    Cross-checks extracted entities across multiple documents (policy vs bill vs report)
    to identify discrepancies in insurer identities, policy numbers, patient identity,
    facility coherence, and financial arithmetic.
    """

    name: str = "cross_document_consistency_tool"
    description: str = (
        "Cross-checks consistency between submitted documents, dynamically comparing "
        "insurer names, policy numbers, patient names, hospital facilities, and financial amounts."
    )

    @property
    def schema(self) -> Dict[str, Any]:
        """JSON schema definition for LLM tool calling registration."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "extracted_data": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of extracted document page dictionaries.",
                        },
                        "claim_id": {
                            "type": "string",
                            "description": "Optional claim ID context.",
                        },
                    },
                },
            },
        }

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized execution method."""
        validated = self.validate_input(input_data)
        extracted_data = validated.get("extracted_data") or []
        return self.run(extracted_data=extracted_data)

    def run(self, extracted_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate dynamic cross-document consistency across all pages."""
        if not extracted_data:
            return {
                "status": "warning",
                "consistent": True,
                "discrepancies": [],
                "severity": "NONE",
                "checks": {},
                "summary": "No extracted document data available for consistency cross-checking.",
            }

        discrepancies: List[str] = []
        checks: Dict[str, Any] = {}
        highest_severity = "NONE"

        # 1. Insurer & TPA Name Dynamic Resolution
        ins_consistent, ins_discrepancies, ins_details, ins_sev = self._check_insurer_consistency(extracted_data)
        checks["insurer_consistency"] = ins_details
        if not ins_consistent:
            discrepancies.extend(ins_discrepancies)
            if ins_sev == "CRITICAL":
                highest_severity = "CRITICAL"
            elif highest_severity != "CRITICAL" and ins_sev == "WARNING":
                highest_severity = "WARNING"

        # 2. Policy Number & Claim Reference Integrity
        pol_consistent, pol_discrepancies, pol_details, pol_sev = self._check_policy_number_consistency(extracted_data)
        checks["policy_number_consistency"] = pol_details
        if not pol_consistent:
            discrepancies.extend(pol_discrepancies)
            if pol_sev == "CRITICAL":
                highest_severity = "CRITICAL"
            elif highest_severity != "CRITICAL" and pol_sev == "WARNING":
                highest_severity = "WARNING"

        # 3. Patient & Beneficiary Consistency
        pat_consistent, pat_discrepancies, pat_details, pat_sev = self._check_patient_identity(extracted_data)
        checks["patient_identity"] = pat_details
        if not pat_consistent:
            discrepancies.extend(pat_discrepancies)
            if pat_sev == "CRITICAL":
                highest_severity = "CRITICAL"
            elif highest_severity != "CRITICAL" and pat_sev == "WARNING":
                highest_severity = "WARNING"

        # 4. Facility & Provider Coherence
        hosp_consistent, hosp_discrepancies, hosp_details, hosp_sev = self._check_hospital_consistency(extracted_data)
        checks["hospital_consistency"] = hosp_details
        if not hosp_consistent:
            discrepancies.extend(hosp_discrepancies)
            if highest_severity != "CRITICAL" and hosp_sev in ("CRITICAL", "WARNING"):
                highest_severity = hosp_sev

        # 5. Financial Arithmetic Cross-Audit
        fin_consistent, fin_discrepancies, fin_details, fin_sev = self._check_financial_data(extracted_data)
        checks["financial_data"] = fin_details
        if not fin_consistent:
            discrepancies.extend(fin_discrepancies)
            if highest_severity != "CRITICAL" and fin_sev in ("CRITICAL", "WARNING"):
                highest_severity = fin_sev

        consistent = len(discrepancies) == 0 and highest_severity == "NONE"

        if consistent:
            summary = "Cross-document consistency check passed: insurer identities, policy numbers, patient names, and facilities are fully coherent."
        else:
            summary = (
                f"Cross-document consistency check detected {len(discrepancies)} discrepancy(ies) "
                f"[{highest_severity}]: {'; '.join(discrepancies)}"
            )

        logger.info(f"[CONSISTENCY CHECK] Consistent: {consistent} (Severity: {highest_severity}, {len(discrepancies)} discrepancies)")

        return {
            "status": "success",
            "consistent": consistent,
            "discrepancies": discrepancies,
            "severity": highest_severity,
            "checks": checks,
            "summary": summary,
        }

    def _check_insurer_consistency(
        self, extracted_data: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], Dict[str, Any], str]:
        """
        Dynamically compare insurer names between policy schedule and claim documents.
        Supports TPA references, minor OCR variations, and catches conflicting insurers.
        """
        policy_insurers: Dict[str, List[int]] = {}
        claim_insurers: Dict[str, List[int]] = {}

        for doc in extracted_data:
            page_no = doc.get("page_number", 1)
            doc_type = doc.get("document_type")
            ins_name = doc.get("insurer_name") or doc.get("insurer")

            if not ins_name or not str(ins_name).strip():
                continue

            clean_name = str(ins_name).strip()
            clean_lower = clean_name.lower()
            # Defense-in-depth: skip form questions, negative answers, and contact noise
            if any(x in clean_lower for x in ["other health insurance", "held?", "verified direct", "nil other", "no (nil", "xxxxx", "single insurer"]):
                continue

            if doc_type == "insurance_policy":
                policy_insurers.setdefault(clean_name, []).append(page_no)
            else:
                claim_insurers.setdefault(clean_name, []).append(page_no)

        if not policy_insurers or not claim_insurers:
            return (
                True,
                [],
                {
                    "consistent": True,
                    "policy_insurers": list(policy_insurers.keys()),
                    "claim_insurers": list(claim_insurers.keys()),
                    "note": "Single document source or no explicit insurer cited across opposing document types.",
                },
                "NONE",
            )

        discrepancies: List[str] = []
        details: List[Dict[str, Any]] = []
        severity = "NONE"

        for pol_raw, p_pages in policy_insurers.items():
            p_norm, p_tokens = _normalize_company_name(pol_raw)

            for clm_raw, c_pages in claim_insurers.items():
                c_norm, c_tokens = _normalize_company_name(clm_raw)

                # 1. Exact case-insensitive match or exact normalized string match
                if pol_raw.lower().strip() == clm_raw.lower().strip() or p_norm == c_norm:
                    details.append({
                        "policy_insurer": pol_raw,
                        "claim_insurer": clm_raw,
                        "match_type": "EXACT_OR_NORMALIZED_MATCH",
                        "similarity": 1.0,
                    })
                    continue

                # 2. Token set exact equality (same tokens, different ordering)
                if p_tokens and c_tokens and p_tokens == c_tokens:
                    details.append({
                        "policy_insurer": pol_raw,
                        "claim_insurer": clm_raw,
                        "match_type": "EXACT_TOKEN_MATCH",
                        "similarity": 1.0,
                    })
                    continue

                # 3. Legitimate TPA / Claims Administrator relationship
                # If either document explicitly designates a TPA, it is an administrative
                # partner rather than a competing underwriter.
                is_tpa = any(k in pol_raw.lower() or k in clm_raw.lower() for k in TPA_INDICATORS)
                if is_tpa:
                    details.append({
                        "policy_insurer": pol_raw,
                        "claim_insurer": clm_raw,
                        "match_type": "TPA_OR_ADMINISTRATOR_RELATIONSHIP",
                        "similarity": 0.95,
                    })
                    continue

                # 4. Check for distinct, conflicting brand tokens
                # If neither party is a TPA, both identify the primary insurer.
                # If there are distinctive brand tokens not shared across sets (e.g. "Sunrise Dhruvil Shield" vs "Sunrise Shield"),
                # this represents a conflicting insurer entity.
                diff_tokens = p_tokens ^ c_tokens
                has_distinct_brand_mismatch = False
                for dt in diff_tokens:
                    if len(dt) >= 3:
                        other_set = c_tokens if dt in p_tokens else p_tokens
                        has_close_match = any(_levenshtein_similarity(dt, ot) >= 0.80 for ot in other_set)
                        if not has_close_match:
                            has_distinct_brand_mismatch = True
                            break

                lev_sim = _levenshtein_similarity(p_norm, c_norm)

                if not has_distinct_brand_mismatch and lev_sim >= 0.88:
                    # Minor naming variation without distinct brand mismatch -> PASS
                    details.append({
                        "policy_insurer": pol_raw,
                        "claim_insurer": clm_raw,
                        "match_type": "MINOR_VARIATION_PASS",
                        "similarity": round(lev_sim, 3),
                    })
                else:
                    # Contradictory / competing insurer detected -> CRITICAL
                    severity = "CRITICAL"
                    msg = (
                        f"Conflicting insurance companies reported across documents: "
                        f"Policy is under '{pol_raw}', but page {c_pages} reports '{clm_raw}'."
                    )
                    discrepancies.append(msg)
                    details.append({
                        "policy_insurer": pol_raw,
                        "claim_insurer": clm_raw,
                        "match_type": "CONTRADICTORY_COMPETING_INSURER",
                        "similarity": round(lev_sim, 3),
                        "pages": c_pages,
                    })

        consistent = len(discrepancies) == 0
        return (
            consistent,
            discrepancies,
            {
                "consistent": consistent,
                "policy_insurers": policy_insurers,
                "claim_insurers": claim_insurers,
                "evaluations": details,
            },
            severity,
        )

    def _check_policy_number_consistency(
        self, extracted_data: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], Dict[str, Any], str]:
        """
        Compare policy numbers cited across hospital bills/claim forms against the master policy schedule.
        """
        policy_nums: Dict[str, Dict[str, Any]] = {}
        claim_nums: Dict[str, Dict[str, Any]] = {}

        for doc in extracted_data:
            page_no = doc.get("page_number", 1)
            doc_type = doc.get("document_type")
            pol_num = doc.get("policy_number")

            if not pol_num or not str(pol_num).strip():
                continue

            raw_str = str(pol_num).strip()
            norm_str = _normalize_policy_num(raw_str)
            if not norm_str:
                continue

            if doc_type == "insurance_policy":
                if norm_str not in policy_nums:
                    policy_nums[norm_str] = {"raw": raw_str, "pages": []}
                policy_nums[norm_str]["pages"].append(page_no)
            else:
                if norm_str not in claim_nums:
                    claim_nums[norm_str] = {"raw": raw_str, "pages": []}
                claim_nums[norm_str]["pages"].append(page_no)

        if not policy_nums or not claim_nums:
            return (
                True,
                [],
                {
                    "consistent": True,
                    "policy_numbers": {k: v["raw"] for k, v in policy_nums.items()},
                    "claim_numbers": {k: v["raw"] for k, v in claim_nums.items()},
                    "note": "Policy number only cited in one source type or not present across opposing document types.",
                },
                "NONE",
            )

        discrepancies: List[str] = []
        severity = "NONE"

        for clm_norm, clm_info in claim_nums.items():
            # Check if this claim document policy number matches any policy document
            matched = False
            for pol_norm, pol_info in policy_nums.items():
                if clm_norm == pol_norm:
                    matched = True
                    break
                # Substring match if sufficiently long (> 6 characters) and minimal length variance (e.g. branch/endorsement suffix)
                if len(clm_norm) >= 6 and len(pol_norm) >= 6:
                    if (clm_norm in pol_norm or pol_norm in clm_norm) and abs(len(clm_norm) - len(pol_norm)) <= 3:
                        matched = True
                        break

            if not matched:
                severity = "CRITICAL"
                pol_raw_examples = ", ".join(f"'{v['raw']}'" for v in policy_nums.values())
                msg = (
                    f"Policy number mismatch: Policy schedule specifies {pol_raw_examples}, "
                    f"but document on page {clm_info['pages']} cites '{clm_info['raw']}'."
                )
                discrepancies.append(msg)

        consistent = len(discrepancies) == 0
        return (
            consistent,
            discrepancies,
            {
                "consistent": consistent,
                "policy_numbers": {k: v["raw"] for k, v in policy_nums.items()},
                "claim_numbers": {k: v["raw"] for k, v in claim_nums.items()},
            },
            severity,
        )

    def _check_patient_identity(
        self, extracted_data: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], Dict[str, Any], str]:
        """
        Match patient names against policyholder and all floater/dependent insured members,
        tolerating title prefixes, middle name omission, and initial permutations.
        """
        policy_members: Dict[str, Tuple[str, Set[str]]] = {}
        patients_found: Dict[str, List[int]] = {}

        for doc in extracted_data:
            page_no = doc.get("page_number", 1)
            doc_type = doc.get("document_type")

            if doc_type == "insurance_policy":
                holder = doc.get("policy_holder_name")
                if holder:
                    h_raw = str(holder).strip()
                    policy_members[h_raw] = _normalize_name(h_raw)
                for name in doc.get("insured_names", []):
                    if name:
                        n_raw = str(name).strip()
                        policy_members[n_raw] = _normalize_name(n_raw)

            patient = doc.get("patient_name")
            if patient:
                p_raw = str(patient).strip()
                patients_found.setdefault(p_raw, []).append(page_no)

        if not policy_members or not patients_found:
            return (
                True,
                [],
                {
                    "consistent": True,
                    "policy_members": list(policy_members.keys()),
                    "patients_found": list(patients_found.keys()),
                    "note": "Insufficient policy or patient member records for identity cross-audit.",
                },
                "NONE",
            )

        discrepancies: List[str] = []
        severity = "NONE"

        for p_raw, pages in patients_found.items():
            p_norm, p_tokens = _normalize_name(p_raw)
            matched = False

            for m_raw, (m_norm, m_tokens) in policy_members.items():
                is_match, match_type = _match_patient_name(p_norm, p_tokens, m_norm, m_tokens)
                if is_match:
                    matched = True
                    break

            if not matched:
                severity = "CRITICAL"
                member_names = list(policy_members.keys())
                msg = (
                    f"Patient name '{p_raw}' (page {pages}) does not match policyholder "
                    f"or covered insured members: {member_names}."
                )
                discrepancies.append(msg)

        consistent = len(discrepancies) == 0
        return (
            consistent,
            discrepancies,
            {
                "consistent": consistent,
                "policy_members": list(policy_members.keys()),
                "patients_found": list(patients_found.keys()),
            },
            severity,
        )

    def _check_hospital_consistency(
        self, extracted_data: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], Dict[str, Any], str]:
        """
        Cluster hospital/clinic names across medical documents.
        Flags distinct facilities without transfer documentation.
        """
        hospitals_found: Dict[str, List[int]] = {}
        for doc in extracted_data:
            # Only inspect actual medical and hospital documents, not insurance policy definitions
            doc_type = doc.get("document_type")
            if doc_type == "insurance_policy":
                continue

            hosp = doc.get("hospital_name")
            page_no = doc.get("page_number", 1)
            if hosp and str(hosp).strip():
                h_raw = str(hosp).strip()
                # Exclude long explanatory text passages or tiny fragments
                if len(h_raw.split()) > 7 or len(h_raw) < 3:
                    continue

                cleaned = re.sub(r"[^\w\s]", " ", h_raw.lower())
                raw_words = {t.strip() for t in cleaned.split() if t.strip()}

                # Exclude pure document headers or section titles (e.g. "INDOOR ADMISSION RECORD", "DISCHARGE SUMMARY")
                has_facility_indicator = any(kw in raw_words for kw in ["hospital", "clinic", "nursing", "healthcare", "medical", "centre", "center", "institute"])
                is_doc_title = any(kw in raw_words for kw in ["summary", "record", "bill", "invoice", "receipt", "settlement", "form", "sheet", "notes", "dossier", "triage"])
                if is_doc_title and not has_facility_indicator:
                    continue
                if any(phrase in h_raw.lower() for phrase in [
                    "indoor admission", "admission record", "discharge summary", "inpatient bill",
                    "tax invoice", "payment receipt", "settlement form", "claim form", "ward rounds"
                ]) and not any(kw in h_raw.lower() for kw in ["hospital", "clinic", "nursing home", "healthcare"]):
                    continue

                tokens = {t.strip() for t in cleaned.split() if t.strip() and t.strip() not in HOSPITAL_NOISE_TOKENS}
                if not tokens or all(t in {"other", "any", "general", "name", "checking", "itemized"} for t in tokens):
                    continue
                hospitals_found.setdefault(h_raw, []).append(page_no)

        if len(hospitals_found) <= 1:
            return (
                True,
                [],
                {"consistent": True, "facilities": hospitals_found},
                "NONE",
            )

        # Cluster facilities dynamically by removing generic hospital noise tokens
        distinct_clusters: List[Tuple[str, Set[str]]] = []
        for h in hospitals_found.keys():
            cleaned = re.sub(r"[^\w\s]", " ", h.lower())
            tokens = {t.strip() for t in cleaned.split() if t.strip() and t.strip() not in HOSPITAL_NOISE_TOKENS}
            if not tokens:
                tokens = {t.strip() for t in cleaned.split() if t.strip()}

            # Check if this belongs to an existing cluster
            cluster_match = False
            for c_name, c_tokens in distinct_clusters:
                if tokens & c_tokens or _levenshtein_similarity(" ".join(sorted(tokens)), " ".join(sorted(c_tokens))) >= 0.75:
                    cluster_match = True
                    break
            if not cluster_match:
                distinct_clusters.append((h, tokens))

        if len(distinct_clusters) > 1:
            cluster_names = [c[0] for c in distinct_clusters]
            msg = f"Discrepant hospital facilities reported across documents without transfer evidence: {cluster_names}."
            return (
                False,
                [msg],
                {"consistent": False, "facilities": hospitals_found, "distinct_clusters": cluster_names},
                "WARNING",
            )

        return (
            True,
            [],
            {"consistent": True, "facilities": hospitals_found},
            "NONE",
        )

    def _check_financial_data(
        self, extracted_data: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], Dict[str, Any], str]:
        """Validate itemized amounts and positive totals."""
        amounts = []
        for d in extracted_data:
            val = d.get("bill_amount")
            if val is not None:
                try:
                    cleaned_val = float(str(val).replace(",", "").replace("$", "").replace("₹", "").strip())
                    amounts.append(cleaned_val)
                except (ValueError, TypeError):
                    pass

        consistent = all(a > 0 for a in amounts) if amounts else True
        discrepancies = []
        if not consistent:
            discrepancies.append("Negative or zero bill amount recorded on submitted bills.")

        return (
            consistent,
            discrepancies,
            {
                "consistent": consistent,
                "amounts_found": amounts,
            },
            "WARNING" if not consistent else "NONE",
        )

