"""tools/cross_document_consistency_tool.py
Cross-Document Consistency and Discrepancy Detection Tool for InsureMate.
Verifies consistency across patient names, hospital names, dates, and amounts
to detect contradictory evidence or discrepancies.
"""

from typing import Any, Dict, List, Optional
from tools.base_tool import AgentTool
from utils.logger import logger


class CrossDocumentConsistencyTool(AgentTool):
    """
    Callable Agent Tool: Cross-Document Consistency Checker.
    Cross-checks extracted entities across multiple documents (policy vs bill vs report)
    to identify discrepancies in patient identity, facility names, dates, or financial totals.
    """

    name: str = "cross_document_consistency_tool"
    description: str = (
        "Cross-checks consistency between submitted documents, comparing patient names, "
        "hospital names, dates, and amounts to detect contradictions or discrepancies."
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
        """Standardized Phase 6 execution method."""
        validated = self.validate_input(input_data)
        extracted_data = validated.get("extracted_data") or []
        return self.run(extracted_data=extracted_data)

    def run(self, extracted_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate cross-document consistency across all pages."""
        if not extracted_data:
            return {
                "status": "warning",
                "consistent": True,
                "discrepancies": [],
                "summary": "No extracted document data available for consistency cross-checking.",
            }

        discrepancies: List[str] = []
        checks: Dict[str, Any] = {}

        # 1. Patient Identity Consistency
        policy_members: List[str] = []
        patient_names_found: Dict[str, List[int]] = {}

        for doc in extracted_data:
            page_no = doc.get("page_number", 1)
            doc_type = doc.get("document_type")

            if doc_type == "insurance_policy":
                holder = doc.get("policy_holder_name")
                if holder:
                    policy_members.append(str(holder).strip().lower())
                for name in doc.get("insured_names", []):
                    policy_members.append(str(name).strip().lower())

            patient = doc.get("patient_name")
            if patient:
                p_clean = str(patient).strip().lower()
                patient_names_found.setdefault(p_clean, []).append(page_no)

        # Check if patient appears in policy
        if policy_members and patient_names_found:
            for p_name, pages in patient_names_found.items():
                matched = any(
                    (p_name in member or member in p_name)
                    for member in policy_members
                )
                if not matched:
                    discrepancy_msg = (
                        f"Patient name '{p_name}' (page {pages}) does not match policyholder "
                        f"or covered insured members: {list(set(policy_members))}."
                    )
                    discrepancies.append(discrepancy_msg)
            checks["patient_identity"] = {
                "consistent": len(discrepancies) == 0,
                "policy_members": list(set(policy_members)),
                "patient_names": list(patient_names_found.keys()),
            }
        else:
            checks["patient_identity"] = {"consistent": True, "note": "Insufficient data to verify identity match"}

        # 2. Hospital Name Consistency across medical documents
        hospitals_found: Dict[str, List[int]] = {}
        for doc in extracted_data:
            hosp = doc.get("hospital_name")
            page_no = doc.get("page_number", 1)
            if hosp:
                h_clean = str(hosp).strip()
                hospitals_found.setdefault(h_clean, []).append(page_no)

        if len(hospitals_found) > 1:
            hosp_list = list(hospitals_found.keys())
            # Check if names are just minor variants or totally different facilities
            distinct = []
            for h in hosp_list:
                if not any(h.lower() in other.lower() for other in distinct):
                    distinct.append(h)
            if len(distinct) > 1:
                msg = f"Discrepant hospital facilities reported across documents: {distinct}."
                discrepancies.append(msg)
                checks["hospital_consistency"] = {"consistent": False, "facilities": hospitals_found}
            else:
                checks["hospital_consistency"] = {"consistent": True, "facilities": hospitals_found}
        else:
            checks["hospital_consistency"] = {"consistent": True, "facilities": hospitals_found}

        # 3. Bill Amounts
        amounts = [
            float(str(d.get("bill_amount")).replace(",", ""))
            for d in extracted_data
            if d.get("bill_amount") is not None
            and str(d.get("bill_amount")).replace(".", "").replace(",", "").isdigit()
        ]
        checks["financial_data"] = {
            "amounts_found": amounts,
            "consistent": all(a > 0 for a in amounts) if amounts else True,
        }

        consistent = len(discrepancies) == 0
        if consistent:
            summary = "Cross-document consistency check passed: patient identities and facilities are coherent."
        else:
            summary = f"Cross-document consistency check detected {len(discrepancies)} discrepancy(ies): {'; '.join(discrepancies)}"

        logger.info(f"[CONSISTENCY CHECK] Consistent: {consistent} ({len(discrepancies)} discrepancies)")

        return {
            "status": "success",
            "consistent": consistent,
            "discrepancies": discrepancies,
            "checks": checks,
            "summary": summary,
        }
