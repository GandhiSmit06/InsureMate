"""services/missing_document/detector.py
Phase 4 Missing Document Detection Engine.
Consumes real Phase 1, Phase 2, and Phase 3 outputs and uses Gemma 3 via LLMGateway
to dynamically reason about policy requirements and detect missing documents.
"""

import re
from typing import Any, Dict, List, Optional, Union
from services.missing_document.llm_gateway import LLMGateway
from services.missing_document.schemas import (
    MissingDocumentResponse,
    MissingDocumentSummary,
    RequiredDocumentDefinition,
    DocumentResultItem,
    validate_detection_output,
)
from utils.logger import logger


def format_detection_table(result: Dict[str, Any]) -> str:
    """Format Phase 4 result as the user-required markdown table:
    | Sr.No | Document Title | Missing or not | Page No. |
    """
    lines = [
        "| Sr.No | Document Title | Missing or not | Page No. |",
        "| :---: | :------------- | :------------: | :------: |"
    ]
    docs = result.get("document_results") or result.get("missing_documents") or []
    if not docs:
        lines.append("| - | No required documents specified in policy | - | - |")
        return "\n".join(lines)

    for doc in docs:
        sr = doc.get("sr_no", "-")
        title = doc.get("document_title", "Unknown")
        missing_text = "Yes" if doc.get("missing") else "No"
        page = doc.get("page_number") if doc.get("page_number") is not None else doc.get("page_no")
        page_text = str(page) if page is not None else "null"
        lines.append(f"| {sr} | {title} | {missing_text} | {page_text} |")

    return "\n".join(lines)


class MissingDocumentDetector:
    """Dynamic detector coordinating policy requirement extraction and semantic matching."""

    def __init__(self, gateway: Optional[LLMGateway] = None):
        self.gateway = gateway or LLMGateway()

    def detect(
        self,
        phase1_output: Optional[Dict[str, Any]] = None,
        phase2_output: Optional[Dict[str, Any]] = None,
        phase3_output: Optional[Dict[str, Any]] = None,
        *,
        policy_requirements: Optional[List[Any]] = None,
        submitted_documents: Optional[List[Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Detect missing documents from pipeline outputs or direct parameters."""
        logger.missing_doc("Initiating dynamic missing document detection...")

        # 1. Normalize Phase 1 documents and input configurations
        if phase1_output and isinstance(phase1_output, dict):
            if not policy_requirements and "policy_requirements" in phase1_output:
                policy_requirements = phase1_output["policy_requirements"]
            if not submitted_documents and "submitted_documents" in phase1_output:
                submitted_documents = phase1_output["submitted_documents"]
            if not phase2_output and "phase2_output" in phase1_output:
                phase2_output = phase1_output["phase2_output"]
            if not phase3_output and "phase3_output" in phase1_output:
                phase3_output = phase1_output["phase3_output"]
            if "phase1_output" in phase1_output and isinstance(phase1_output["phase1_output"], dict):
                phase1_output = phase1_output["phase1_output"]

        if not policy_requirements and "policy_requirements" in kwargs:
            policy_requirements = kwargs["policy_requirements"]
        if not submitted_documents and "submitted_documents" in kwargs:
            submitted_documents = kwargs["submitted_documents"]
        if not phase1_output and "phase1_output" in kwargs and isinstance(kwargs["phase1_output"], dict):
            phase1_output = kwargs["phase1_output"]

        extracted_docs: List[Dict[str, Any]] = []
        if phase1_output and isinstance(phase1_output, dict):
            extracted_docs = phase1_output.get("extracted_documents", [])
        elif kwargs.get("input_data") and isinstance(kwargs["input_data"], dict):
            extracted_docs = kwargs["input_data"].get("phase1_output", {}).get("extracted_documents", [])

        policy_docs: List[Dict[str, Any]] = []
        submitted_docs: List[Dict[str, Any]] = []

        if submitted_documents:
            for d in submitted_documents:
                if isinstance(d, dict):
                    page = d.get("page_number") if d.get("page_number") is not None else d.get("page_no")
                    title = d.get("document_title") or d.get("submitted_document_title") or str(d)
                    submitted_docs.append({
                        "page_number": page,
                        "page_no": page,
                        "document_type": d.get("document_type", ""),
                        "document_title": title,
                        "patient_name": d.get("patient_name"),
                        "hospital_name": d.get("hospital_name"),
                        "bill_number": d.get("bill_number") or d.get("invoice_number"),
                        "document_date": d.get("document_date"),
                    })
                else:
                    page = getattr(d, "page_number", getattr(d, "page_no", None))
                    title = getattr(d, "document_title", str(d))
                    submitted_docs.append({
                        "document_title": title,
                        "page_number": page,
                        "page_no": page,
                    })

        for doc in extracted_docs:
            doc_type = doc.get("document_type", "").lower()
            if doc_type in ("insurance_policy", "policy", "policy_schedule"):
                policy_docs.append(doc)
            else:
                # Document submitted by claimant
                submitted_docs.append({
                    "page_number": doc.get("page_number"),
                    "page_no": doc.get("page_number"),
                    "document_type": doc.get("document_type"),
                    "document_title": doc.get("document_title") or f"{doc_type.replace('_', ' ').title()} (Page {doc.get('page_number')})",
                    "patient_name": doc.get("patient_name"),
                    "hospital_name": doc.get("hospital_name"),
                    "bill_number": doc.get("bill_number") or doc.get("invoice_number"),
                    "document_date": doc.get("document_date"),
                })

        # Track valid submitted pages for page number integrity checking
        valid_submitted_pages = [
            (d.get("page_number") if d.get("page_number") is not None else d.get("page_no"))
            for d in submitted_docs
            if (d.get("page_number") is not None or d.get("page_no") is not None)
        ]

        # 2. Extract / Establish Required Documents dynamically
        req_docs: List[Dict[str, Any]] = []

        # Case A: Direct dynamic policy requirements supplied (e.g. standalone test)
        if policy_requirements:
            for idx, r in enumerate(policy_requirements, start=1):
                if isinstance(r, dict):
                    req_docs.append({
                        "sr_no": idx,
                        "document_title": r.get("document_title", ""),
                        "source": r.get("source", "policy"),
                        "reason": r.get("reason", "Supplied requirement")
                    })
                elif hasattr(r, "document_title"):
                    req_docs.append({
                        "sr_no": idx,
                        "document_title": r.document_title,
                        "source": "policy",
                        "reason": ""
                    })
                elif isinstance(r, str):
                    req_docs.append({
                        "sr_no": idx,
                        "document_title": r,
                        "source": "policy",
                        "reason": "Supplied requirement"
                    })

        # Case B: Derive dynamically from Phase 1 policy evidence using LLM
        if not req_docs and policy_docs:
            all_conditions: List[str] = []
            for p in policy_docs:
                all_conditions.extend(p.get("relevant_conditions", []))
                all_conditions.extend(p.get("policy_clauses", []))
                if p.get("policy_relevant_text"):
                    all_conditions.append(p.get("policy_relevant_text"))

            extracted_from_llm = self.gateway.extract_policy_requirements(
                policy_documents=policy_docs,
                conditions=all_conditions
            )
            req_docs.extend(extracted_from_llm)

            if not req_docs:
                # Dynamic derivation from verified policy clauses extracted from source document
                clause_idx = 1
                for p in policy_docs:
                    for c in p.get("policy_clauses", []):
                        clean_c = re.sub(r"^\d+[\.\)]\s*", "", c).strip()
                        split_c = re.split(r"\s+(?:with|stating|and payment|supporting)\s+", clean_c, flags=re.I)
                        title = split_c[0].strip() if split_c else clean_c
                        if len(title) > 60:
                            title = title[:60].strip()
                        if title and not any(r["document_title"].lower() == title.lower() for r in req_docs):
                            req_docs.append({
                                "sr_no": clause_idx,
                                "document_title": title,
                                "source": "policy_clause",
                                "reason": c
                            })
                            clause_idx += 1

        # Case C: No explicit requirements found in policy
        if not req_docs:
            logger.missing_doc("No explicit required documents established in policy.")
            empty_resp = MissingDocumentResponse(
                status="success",
                tool="missing_document_tool",
                required_documents=[],
                document_results=[],
                summary=MissingDocumentSummary(total_required=0, present=0, missing=0),
                reason="No specific supporting documents are explicitly mandated in the provided policy evidence.",
                error=None
            )
            return empty_resp.to_dict()

        # If no documents were submitted at all, all requirements are marked missing
        if not submitted_docs:
            logger.missing_doc("No submitted documents provided; all required documents marked missing.")
            doc_results = [
                DocumentResultItem(
                    sr_no=r.get("sr_no", idx),
                    document_title=r.get("document_title", ""),
                    missing=True,
                    page_number=None,
                    matched_submitted_document=None,
                    reason="No claim documents were submitted to fulfill this requirement."
                )
                for idx, r in enumerate(req_docs, start=1)
            ]
            req_defs = [
                RequiredDocumentDefinition(
                    sr_no=r.get("sr_no", idx),
                    document_title=r.get("document_title", ""),
                    source=r.get("source", "policy"),
                    reason=r.get("reason", "")
                )
                for idx, r in enumerate(req_docs, start=1)
            ]
            resp = MissingDocumentResponse(
                status="success",
                tool="missing_document_tool",
                required_documents=req_defs,
                document_results=doc_results,
                summary=MissingDocumentSummary(
                    total_required=len(req_defs),
                    present=0,
                    missing=len(req_defs)
                ),
                reason="Policy requirements established dynamically; no claim documents were submitted.",
                error=None
            )
            return resp.to_dict()

        # 3. Extract Phase 2 & Phase 3 context
        phase2_notes: List[Dict[str, Any]] = []
        if phase2_output and isinstance(phase2_output, dict):
            val_res = phase2_output.get("validation_result", {})
            for d in val_res.get("document_results", []):
                phase2_notes.append({
                    "page_number": d.get("page_number"),
                    "document_type": d.get("document_type"),
                    "is_complete": d.get("valid", True),
                    "missing_fields": d.get("missing_fields", [])
                })

        phase3_context: Optional[Dict[str, Any]] = None
        if phase3_output and isinstance(phase3_output, dict):
            phase3_context = {
                "valid": phase3_output.get("valid"),
                "policy_period": phase3_output.get("policy_period"),
                "reasons": phase3_output.get("reasons", [])
            }

        # 4. Perform semantic matching via LLM Gateway (Call #2)
        response_obj = self.gateway.match_submitted_documents(
            required_documents=req_docs,
            submitted_documents=submitted_docs,
            phase2_notes=phase2_notes,
            phase3_context=phase3_context,
            valid_submitted_pages=valid_submitted_pages
        )

        return response_obj.to_dict()


def detect_missing_documents(
    phase1_output: Optional[Dict[str, Any]] = None,
    phase2_output: Optional[Dict[str, Any]] = None,
    phase3_output: Optional[Dict[str, Any]] = None,
    gateway: Optional[LLMGateway] = None,
    *,
    policy_requirements: Optional[List[Any]] = None,
    submitted_documents: Optional[List[Any]] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """Primary Phase 4 function consuming Phase 1-3 outputs and detecting missing documents."""
    detector = MissingDocumentDetector(gateway=gateway)
    return detector.detect(
        phase1_output=phase1_output,
        phase2_output=phase2_output,
        phase3_output=phase3_output,
        policy_requirements=policy_requirements,
        submitted_documents=submitted_documents,
        **kwargs
    )


# Alias for clean integration
run_phase4 = detect_missing_documents
