import re
import logging
from typing import List, Optional, Tuple, Dict, Any
from ..schema.models import (
    PageText,
    RequirementItem,
    Category,
    Priority,
)
from .base import BaseExtractor

logger = logging.getLogger("insuremate.requirement_extraction.extractor.rule")


class RuleExtractor(BaseExtractor):
    """Deterministic, high-precision domain-aware requirement extraction engine.

    Parses policy text page-by-page to detect documents, required actions,
    conditions, deadlines, and financial requirements with zero hallucination.
    """

    def __init__(self):
        self._init_patterns()

    def _init_patterns(self):
        """Initialize comprehensive medical insurance patterns."""

        # Document requirement patterns with their canonical metadata
        self.doc_specs = [
            {
                "name": "Claim Form",
                "patterns": [
                    r"(?:duly\s+)?(?:filled|completed)(?:\s+and\s+signed)?\s+claim\s+form",
                    r"claim\s+form(?:\s+part\s+[ab])?",
                    r"original\s+claim\s+form",
                ],
                "description": "Duly filled and signed official claim form (Part A and/or Part B).",
                "evidence_type": "claim_form",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "policy_number",
                    "claimant_name",
                    "treating_doctor_signature",
                    "hospital_seal",
                ],
            },
            {
                "name": "Hospital Discharge Summary",
                "patterns": [
                    r"discharge\s+summary",
                    r"discharge\s+card",
                    r"case\s+summary",
                    r"discharge\s+certificate",
                ],
                "description": "Official discharge summary or card issued by the treating hospital.",
                "evidence_type": "hospital_document",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "patient_name",
                    "admission_date",
                    "discharge_date",
                    "diagnosis",
                    "treatment_given",
                    "doctor_signature",
                ],
            },
            {
                "name": "Itemized Hospital Final Bill",
                "patterns": [
                    r"(?:original\s+)?(?:final\s+)?hospital\s+bill(?:s)?(?:\s+with\s+breakup)?",
                    r"itemized\s+(?:hospital\s+)?bill(?:s)?",
                    r"detailed\s+bill\s+breakup",
                    r"hospital\s+break-?up\s+bill",
                ],
                "description": "Original itemized final hospital bill showing line-item cost breakup.",
                "evidence_type": "financial_receipt",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "bill_number",
                    "room_rent_breakup",
                    "doctor_consultation_fees",
                    "investigation_charges",
                    "operation_charges",
                ],
            },
            {
                "name": "Hospital Payment Receipts",
                "patterns": [
                    r"(?:original\s+)?payment\s+receipts?",
                    r"money\s+receipts?",
                    r"settlement\s+receipts?",
                    r"cash\s+receipts?",
                ],
                "description": "Original payment receipts with hospital seal and revenue stamp if required.",
                "evidence_type": "financial_receipt",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "receipt_number",
                    "paid_amount",
                    "payment_mode",
                    "hospital_seal",
                ],
            },
            {
                "name": "Doctor Prescriptions and Consultation Papers",
                "patterns": [
                    r"doctor(?:'?s)?\s+prescription(?:s)?",
                    r"consultation\s+paper(?:s)?",
                    r"medical\s+practitioner(?:'?s)?\s+prescription(?:s)?",
                ],
                "description": "Attending doctor's consultation papers and medical prescriptions.",
                "evidence_type": "medical_report",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "doctor_name",
                    "consultation_date",
                    "advised_medicines",
                    "clinical_notes",
                ],
            },
            {
                "name": "Diagnostic and Investigation Reports",
                "patterns": [
                    r"investigation\s+report(?:s)?",
                    r"diagnostic\s+report(?:s)?",
                    r"patholog(?:y|ical)\s+report(?:s)?",
                    r"radiology\s+report(?:s)?",
                    r"(?:x-ray|ecg|ct\s+scan|mri|usg|blood\s+test)\s+report(?:s)?",
                ],
                "description": "All medical diagnostic, pathological, imaging and laboratory investigation reports.",
                "evidence_type": "medical_report",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "investigation_name",
                    "test_date",
                    "findings",
                    "pathologist_radiologist_signature",
                ],
            },
            {
                "name": "Pharmacy and Medicine Bills",
                "patterns": [
                    r"pharmacy\s+bill(?:s)?",
                    r"chemist\s+bill(?:s)?",
                    r"medicine\s+bill(?:s)?(?:\s+with\s+prescriptions?)?",
                ],
                "description": "Original pharmacy cash memos accompanied by relevant doctor prescriptions.",
                "evidence_type": "financial_receipt",
                "category": Category.DOCUMENT,
                "priority": Priority.MEDIUM,
                "required_info": [
                    "pharmacy_name",
                    "dl_number",
                    "medicine_batch_numbers",
                    "cost_per_item",
                ],
            },
            {
                "name": "Operation Theatre Notes",
                "patterns": [
                    r"operation\s+theatre\s+notes?",
                    r"ot\s+notes?",
                    r"surgeon(?:'?s)?\s+notes?",
                    r"anaesthesia\s+notes?",
                ],
                "description": "Surgeon's operative notes and anaesthetist records in case of surgical treatment.",
                "evidence_type": "hospital_document",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "surgical_procedure",
                    "surgeon_name",
                    "anaesthesia_details",
                    "incision_and_findings",
                ],
                "default_condition": "In case of surgery or operative procedure",
            },
            {
                "name": "Implant Invoice and Stickers",
                "patterns": [
                    r"implant\s+(?:invoice|bill|sticker|barcode)",
                    r"stent\s+(?:invoice|sticker|barcode)",
                    r"implant\s+purchase\s+invoice",
                ],
                "description": "Manufacturer's implant invoice and original device barcode/stickers used in procedure.",
                "evidence_type": "financial_receipt",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "implant_invoice_number",
                    "serial_number_or_barcode",
                    "batch_number",
                    "manufacturer_name",
                ],
                "default_condition": "In case of surgical procedure involving implants, stents, or prostheses",
            },
            {
                "name": "Police FIR and Medico-Legal Certificate (MLC)",
                "patterns": [
                    r"(?:police\s+)?fir(?:\s+copy)?",
                    r"first\s+information\s+report",
                    r"medico-?legal\s+certificate",
                    r"\bmlc(?:\s+copy)?\b",
                    r"panchnama",
                ],
                "description": "First Information Report (FIR) and Medico-Legal Certificate (MLC) from police / hospital.",
                "evidence_type": "legal_document",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "fir_number",
                    "police_station_name",
                    "mlc_number",
                    "injury_description",
                    "accident_timestamp",
                ],
                "default_condition": "In case of accidental injury, trauma, or road traffic accident (RTA)",
            },
            {
                "name": "Alcohol and Toxicology Screening Report",
                "patterns": [
                    r"alcohol\s+(?:influence\s+)?test",
                    r"toxicology\s+report",
                    r"blood\s+alcohol\s+content",
                    r"substance\s+abuse\s+test",
                ],
                "description": "Toxicology and blood alcohol analysis report in medico-legal accident cases.",
                "evidence_type": "medical_report",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "blood_alcohol_level",
                    "toxicology_findings",
                    "sample_collection_timestamp",
                ],
                "default_condition": "In case of accidental injury or suspected substance involvement",
            },
            {
                "name": "KYC and Bank Account Details",
                "patterns": [
                    r"kyc\s+documents?",
                    r"pan\s+card(?:\s+copy)?",
                    r"cancelled\s+cheque",
                    r"bank\s+passbook\s+copy",
                    r"aadhaar\s+card",
                ],
                "description": "Know Your Customer (KYC) identity and bank payout documents (PAN, Cancelled Cheque).",
                "evidence_type": "identity_proof",
                "category": Category.DOCUMENT,
                "priority": Priority.MEDIUM,
                "required_info": [
                    "pan_number",
                    "bank_account_number",
                    "ifsc_code",
                    "claimant_id_proof",
                ],
                "default_condition": "Mandatory for claim amounts exceeding INR 1,00,000 or electronic payout",
            },
            {
                "name": "Indoor Case Papers (ICP)",
                "patterns": [
                    r"indoor\s+case\s+papers?",
                    r"\bicp\b",
                    r"daily\s+progress\s+notes?",
                    r"nursing\s+notes?",
                    r"temperature\s+charts?",
                ],
                "description": "Hospital indoor case papers, daily clinical progress notes, and nursing observation charts.",
                "evidence_type": "hospital_document",
                "category": Category.DOCUMENT,
                "priority": Priority.MEDIUM,
                "required_info": [
                    "daily_clinical_notes",
                    "nursing_vitals_chart",
                    "medication_administration_record",
                ],
                "default_condition": "If required by insurer or hospital stay exceeds 5 days / ICU admission",
            },
            {
                "name": "Cashless Pre-Authorization Approval",
                "patterns": [
                    r"pre-?authorization\s+(?:request|form|approval|letter)",
                    r"cashless\s+authorization\s+letter",
                    r"tpa\s+approval\s+letter",
                ],
                "description": "Duly authorized cashless pre-authorization form and approval letter from TPA/Insurer.",
                "evidence_type": "claim_form",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "preauth_reference_number",
                    "sanctioned_amount",
                    "tpa_approval_stamp",
                    "treatment_authorized",
                ],
                "default_condition": "For cashless treatment at empanelled network hospitals",
            },
            {
                "name": "Death Certificate and Post Mortem Report",
                "patterns": [
                    r"death\s+certificate",
                    r"death\s+summary",
                    r"post-?mortem\s+report",
                ],
                "description": "Official municipal Death Certificate and hospital Post Mortem report.",
                "evidence_type": "legal_document",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "date_of_death",
                    "cause_of_death",
                    "issuing_authority",
                ],
                "default_condition": "In the unfortunate event of death of the insured patient",
            },
            {
                "name": "Treating Doctor Certificate",
                "patterns": [
                    r"treating\s+doctor(?:'?s)?\s+certificate",
                    r"medical\s+certificate\s+from\s+treating\s+doctor",
                    r"attending\s+physician(?:'?s)?\s+statement",
                ],
                "description": "Certificate from attending doctor specifying illness duration, etiology, and history.",
                "evidence_type": "medical_report",
                "category": Category.DOCUMENT,
                "priority": Priority.HIGH,
                "required_info": [
                    "doctor_registration_number",
                    "disease_history_and_duration",
                    "etiology",
                    "doctor_signature_and_seal",
                ],
            },
        ]

        # Action & Deadline patterns
        self.action_deadline_specs = [
            {
                "name": "Claim Intimation to Insurer / TPA",
                "patterns": [
                    r"(?:notice\s+of\s+claim|intimat(?:e|ion)\s+(?:to\s+)?(?:insurer|tpa|company|us))",
                    r"intimate\s+within\s+(\d+\s*(?:hours|hrs|days))",
                    r"claim\s+intimation",
                ],
                "description": "Formal notice of hospitalization claim must be given to the insurer or TPA.",
                "category": Category.ACTION,
                "priority": Priority.HIGH,
                "applies_when": "All claims",
            },
            {
                "name": "Emergency Hospitalization Intimation Deadline",
                "patterns": [
                    r"(?:in\s+case\s+of\s+emergency|emergency\s+hospitalization)[^.\n]*?within\s+(\d+\s*(?:hours|hrs|days))",
                    r"within\s+(\d+\s*(?:hours|hrs))\s+of\s+(?:emergency\s+)?admission",
                ],
                "description": "Intimation must be submitted to the insurer within the stated hours of emergency hospitalization.",
                "category": Category.DEADLINE,
                "priority": Priority.HIGH,
                "condition": "In case of emergency hospitalization",
            },
            {
                "name": "Planned Hospitalization Prior Notice Deadline",
                "patterns": [
                    r"(?:planned\s+hospitalization)[^.\n]*?(?:at\s+least|within)\s+(\d+\s*(?:hours|hrs|days))\s+prior",
                    r"prior\s+to\s+admission[^.\n]*?(\d+\s*(?:hours|hrs|days))",
                    r"at\s+least\s+(\d+\s*(?:hours|hrs|days))\s+(?:prior|before)\s+admission",
                ],
                "description": "Prior notice must be given before planned hospital admission.",
                "category": Category.DEADLINE,
                "priority": Priority.HIGH,
                "condition": "In case of planned hospitalization",
            },
            {
                "name": "Claim Documents Submission Deadline",
                "patterns": [
                    r"submit(?:ted)?\s+(?:all\s+)?(?:claim\s+)?documents?\s+within\s+(\d+\s*days)\s+(?:of|from)\s+discharge",
                    r"within\s+(\d+\s*days)\s+(?:of|from|after)\s+(?:hospital\s+)?discharge",
                    r"claim\s+papers\s+within\s+(\d+\s*days)",
                ],
                "description": "All original claim documents and bills must be submitted within the specified days of discharge.",
                "category": Category.DEADLINE,
                "priority": Priority.HIGH,
                "applies_when": "Reimbursement claim",
            },
            {
                "name": "Query Reply Deadline",
                "patterns": [
                    r"(?:respond|reply)\s+to\s+queries?\s+within\s+(\d+\s*days)",
                    r"within\s+(\d+\s*days)\s+of\s+receipt\s+of\s+(?:claim\s+)?query",
                ],
                "description": "Insured must respond with clarification/documents within specified days of query letter.",
                "category": Category.DEADLINE,
                "priority": Priority.MEDIUM,
            },
        ]

        # Condition & Policy clause patterns
        self.condition_specs = [
            {
                "name": "Continuous 24-Hour Hospitalization Requirement",
                "patterns": [
                    r"minimum\s+(?:period\s+of\s+)?(?:24|twenty[- ]four)\s+hours\s+hospitalization",
                    r"in-?patient\s+care\s+for\s+minimum\s+24\s+hours",
                ],
                "description": "Treatment requires continuous in-patient admission of minimum 24 hours, except for listed day care procedures.",
                "category": Category.CONDITION,
                "priority": Priority.HIGH,
                "condition": "Exempted only for specified day care procedures / surgeries",
            },
            {
                "name": "Network Hospital Requirement for Cashless Treatment",
                "patterns": [
                    r"cashless\s+facility\s+(?:is\s+)?available\s+(?:only|exclusively)\s+at\s+network\s+hospital(?:s)?",
                    r"empanelled\s+network\s+hospital(?:s)?",
                ],
                "description": "Cashless treatment facility is strictly conditioned on admission at an empanelled Network Hospital.",
                "category": Category.CONDITION,
                "priority": Priority.HIGH,
                "condition": "Only available at approved network hospitals",
            },
            {
                "name": "Day Care Procedure Clause",
                "patterns": [
                    r"day\s+care\s+procedure(?:s)?\s+(?:as\s+listed|specified\s+in\s+annexure)",
                    r"day\s+care\s+treatment",
                ],
                "description": "Medical treatments completed within under 24 hours must be pre-listed eligible Day Care Procedures.",
                "category": Category.CONDITION,
                "priority": Priority.MEDIUM,
                "condition": "For procedures not requiring 24 hours hospitalization",
            },
            {
                "name": "Organ Donor Medical Fitness and Screening",
                "patterns": [
                    r"organ\s+donor(?:'?s)?\s+(?:medical|screening|expenses)",
                    r"donor\s+screening\s+certificate",
                ],
                "description": "Organ harvesting requires certified donor screening and legal organ donation clearance.",
                "category": Category.CONDITION,
                "priority": Priority.MEDIUM,
                "condition": "In case of organ donor transplantation claim",
            },
            {
                "name": "ICU Stay Medical Justification",
                "patterns": [
                    r"icu\s+stay\s+exceed(?:s|ing)?\s+(\d+\s*(?:hours|days))",
                    r"intensive\s+care\s+unit\s+admission",
                ],
                "description": "Intensive Care Unit stay requires treating intensivist clinical chart and justification.",
                "category": Category.CONDITION,
                "priority": Priority.HIGH,
                "condition": "When admission involves ICU stay",
            },
        ]

        # Financial Requirement patterns
        self.financial_specs = [
            {
                "name": "Co-Payment Obligation",
                "patterns": [
                    r"co-?payment\s+of\s+(\d+(?:\.\d+)?\s*%)",
                    r"(\d+(?:\.\d+)?\s*%)\s+co-?payment",
                ],
                "description": "Policyholder must bear a specified co-payment percentage on every admissible claim.",
                "category": Category.FINANCIAL,
                "priority": Priority.HIGH,
                "applies_when": "Admissible claim settlement",
            },
            {
                "name": "Deductible Amount",
                "patterns": [
                    r"deductible\s+of\s+(?:inr|rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)",
                    r"aggregate\s+deductible\s+of\s+(?:inr|rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)",
                ],
                "description": "Mandatory deductible amount must be borne by the insured before policy coverage triggers.",
                "category": Category.FINANCIAL,
                "priority": Priority.HIGH,
                "applies_when": "Admissible claim settlement",
            },
            {
                "name": "Room Rent Sub-Limit Capping",
                "patterns": [
                    r"room\s+rent\s+(?:limit|capping|sub-?limit)\s+(?:of\s+)?(\d+(?:\.\d+)?\s*%\s+of\s+sum\s+insured)",
                    r"room\s+rent\s+capped\s+at",
                ],
                "description": "Hospital room rent is subject to daily sub-limit capping as specified in the schedule.",
                "category": Category.FINANCIAL,
                "priority": Priority.MEDIUM,
                "applies_when": "Hospital room selection",
            },
        ]

        # Ambiguous wording & discretionary requirements
        self.ambiguous_specs = [
            {
                "name": "Discretionary Additional Documentation Clause",
                "patterns": [
                    r"(?:any\s+other|such\s+other)\s+document(?:s)?\s+(?:as\s+)?(?:may\s+be\s+)?(?:required|deemed\s+necessary|requested)\s+by\s+(?:the\s+)?(?:insurer|tpa|company)",
                    r"reasonable\s+and\s+customary\s+documents?",
                    r"as\s+deemed\s+fit\s+by\s+the\s+insurer",
                ],
                "description": "The insurer/TPA reserves discretionary authority to request further reasonable and customary documents during claim assessment.",
                "category": Category.CONDITION,
                "priority": Priority.LOW,
                "condition": "At insurer's or TPA's claim assessment discretion",
            }
        ]

    def extract(
        self,
        pages: List[PageText],
        claim_type: Optional[str] = None,
    ) -> List[RequirementItem]:
        """Extract all claim requirements from pages."""
        if not pages:
            return []

        results: List[RequirementItem] = []
        req_counter = 1

        # Determine general claim context string
        claim_context = self._determine_claim_context(claim_type)

        # Iterate over pages to preserve source_page
        for page in pages:
            page_text = page.text
            if not page_text or len(page_text.strip()) < 10:
                continue

            # 1. Document Requirements
            for doc in self.doc_specs:
                matched, match_str, clause_header = self._check_patterns(
                    doc["patterns"], page_text
                )
                if matched:
                    # Determine condition
                    is_conditional, cond_text = self._detect_condition_in_context(
                        page_text, match_str, doc.get("default_condition")
                    )

                    req = RequirementItem(
                        requirement_id=f"REQ-{req_counter:03d}",
                        category=doc["category"],
                        name=doc["name"],
                        description=doc["description"],
                        mandatory=not is_conditional,
                        priority=doc["priority"],
                        applies_when=claim_context,
                        condition=cond_text if is_conditional else None,
                        deadline=None,
                        evidence_type=doc.get("evidence_type"),
                        required_information=list(doc.get("required_info", [])),
                        source_clause=clause_header or "Documents Required for Claim",
                        source_page=page.page_number,
                    )
                    results.append(req)
                    req_counter += 1

            # 2. Action & Deadline Requirements
            for action in self.action_deadline_specs:
                matched, match_str, clause_header = self._check_patterns(
                    action["patterns"], page_text
                )
                if matched:
                    deadline_val = self._extract_deadline_value(page_text, match_str)
                    cond = action.get("condition")

                    req = RequirementItem(
                        requirement_id=f"REQ-{req_counter:03d}",
                        category=action["category"],
                        name=action["name"],
                        description=action["description"],
                        mandatory=cond is None,
                        priority=action["priority"],
                        applies_when=action.get("applies_when", claim_context),
                        condition=cond,
                        deadline=deadline_val,
                        evidence_type=action.get("evidence_type"),
                        required_information=[],
                        source_clause=clause_header or "Claims Procedure / Notice of Claim",
                        source_page=page.page_number,
                    )
                    results.append(req)
                    req_counter += 1

            # 3. Policy Conditions
            for cond in self.condition_specs:
                matched, match_str, clause_header = self._check_patterns(
                    cond["patterns"], page_text
                )
                if matched:
                    req = RequirementItem(
                        requirement_id=f"REQ-{req_counter:03d}",
                        category=cond["category"],
                        name=cond["name"],
                        description=cond["description"],
                        mandatory=False,
                        priority=cond["priority"],
                        applies_when=claim_context,
                        condition=cond.get("condition"),
                        deadline=None,
                        evidence_type=None,
                        required_information=[],
                        source_clause=clause_header or "Policy Terms and Conditions",
                        source_page=page.page_number,
                    )
                    results.append(req)
                    req_counter += 1

            # 4. Financial Requirements
            for fin in self.financial_specs:
                matched, match_str, clause_header = self._check_patterns(
                    fin["patterns"], page_text
                )
                if matched:
                    # Extract percentage or amount if available
                    desc = fin["description"]
                    m = re.search(fin["patterns"][0], page_text, re.IGNORECASE)
                    if m and m.groups():
                        val = m.group(1)
                        desc = f"{fin['description']} (Stated: {val})"

                    req = RequirementItem(
                        requirement_id=f"REQ-{req_counter:03d}",
                        category=fin["category"],
                        name=fin["name"],
                        description=desc,
                        mandatory=True,
                        priority=fin["priority"],
                        applies_when=fin.get("applies_when", claim_context),
                        condition=None,
                        deadline=None,
                        evidence_type="financial_receipt",
                        required_information=[],
                        source_clause=clause_header or "Financial Limits and Copay",
                        source_page=page.page_number,
                    )
                    results.append(req)
                    req_counter += 1

            # 5. Ambiguous / Discretionary Requirements
            for amb in self.ambiguous_specs:
                matched, match_str, clause_header = self._check_patterns(
                    amb["patterns"], page_text
                )
                if matched:
                    req = RequirementItem(
                        requirement_id=f"REQ-{req_counter:03d}",
                        category=amb["category"],
                        name=amb["name"],
                        description=amb["description"],
                        mandatory=False,
                        priority=amb["priority"],
                        applies_when=claim_context,
                        condition=amb.get("condition"),
                        deadline=None,
                        evidence_type=None,
                        required_information=[],
                        source_clause=clause_header or "General Claim Conditions",
                        source_page=page.page_number,
                    )
                    results.append(req)
                    req_counter += 1

        return results

    def _check_patterns(
        self, patterns: List[str], text: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if any regex pattern matches in the text.
        Returns (matched, matched_snippet, detected_section_header).
        """
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                snippet = match.group(0)
                # Find nearby section header if possible
                header = self._find_enclosing_header(text, match.start())
                return True, snippet, header
        return False, None, None

    def _find_enclosing_header(self, text: str, match_pos: int) -> Optional[str]:
        """Find the preceding section or clause title before match_pos."""
        preceding = text[:match_pos]
        # Look for headers like: SECTION X, CLAUSE Y, 1.2 ..., or CAPITALIZED LINES
        lines = preceding.split("\n")
        header_patterns = [
            re.compile(r"^(?:Section|Clause|Article|Condition|Part)\s+[\dA-Z.-]+[:\s-].*$", re.I),
            re.compile(r"^\d+(?:\.\d+)*\s+[A-Z].*$"),
            re.compile(r"^[A-Z\s]{4,40}$"),
        ]

        for line in reversed(lines):
            clean_line = line.strip()
            if not clean_line or len(clean_line) < 3:
                continue
            for hp in header_patterns:
                if hp.match(clean_line):
                    return clean_line[:80]
            # Check for common headings
            if any(
                h in clean_line.lower()
                for h in [
                    "documents required",
                    "claims procedure",
                    "notice of claim",
                    "cashless",
                    "reimbursement",
                    "duties of insured",
                    "terms and conditions",
                ]
            ):
                return clean_line[:80]

        return None

    def _detect_condition_in_context(
        self, text: str, match_str: str, default_cond: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """Examine text surrounding match to determine if it is conditional."""
        if default_cond:
            return True, default_cond

        # Check a window of 150 chars around match
        pos = text.lower().find(match_str.lower())
        if pos != -1:
            start = max(0, pos - 100)
            end = min(len(text), pos + len(match_str) + 100)
            window = text[start:end].lower()

            cond_triggers = [
                (r"\bif\s+(?:applicable|required|any|treatment|surgery|accident)\b", "If applicable according to nature of claim"),
                (r"\bin\s+case\s+of\b", "In case specified circumstances arise"),
                (r"\bin\s+the\s+event\s+of\b", "In the event of specified circumstances"),
                (r"\bwherever\s+applicable\b", "Wherever applicable"),
                (r"\bonly\s+when\b", "Only when specifically mandated"),
            ]
            for trigger_pat, label in cond_triggers:
                if re.search(trigger_pat, window):
                    return True, label

        return False, None

    def _extract_deadline_value(self, text: str, match_str: str) -> Optional[str]:
        """Extract deadline timeframe (e.g. 'within 24 hours', 'within 30 days')."""
        pos = text.lower().find(match_str.lower())
        if pos != -1:
            start = max(0, pos - 80)
            end = min(len(text), pos + len(match_str) + 80)
            window = text[start:end]
            m = re.search(
                r"within\s+(\d+\s*(?:hours|hrs|days|working\s+days|weeks))\b",
                window,
                re.IGNORECASE,
            )
            if m:
                return f"within {m.group(1)}"
            m_prior = re.search(
                r"(?:at\s+least|prior\s+to)\s+(\d+\s*(?:hours|hrs|days))\b",
                window,
                re.IGNORECASE,
            )
            if m_prior:
                return f"{m_prior.group(1)} prior to admission"

        return None

    def _determine_claim_context(self, claim_type: Optional[str]) -> str:
        """Format claim context label."""
        if not claim_type:
            return "Hospitalization claim"
        ct = claim_type.strip().lower()
        if "cashless" in ct:
            return "Cashless hospitalization claim"
        elif "reimbursement" in ct:
            return "Reimbursement claim"
        elif "accident" in ct:
            return "Accident-related claim"
        elif "day" in ct and "care" in ct:
            return "Day care claim"
        return f"{claim_type.capitalize()} claim"
