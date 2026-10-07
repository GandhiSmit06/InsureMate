"""services/missing_document/prompt_builder.py
Dynamic LLM prompt builders for Phase 4.
Enforces zero hardcoding, zero predefined document lists, and strict anti-hallucination.
"""

import json
from typing import Any, Dict, List, Optional


SYSTEM_REQUIREMENT_EXTRACTION_PROMPT = """You are an insurance claim document requirement analyst.

Analyze the supplied policy information (including policy clauses, terms, conditions, and relevant policy text).
Identify each specific supporting document, record, certificate, or proof required for filing or processing a claim.

STRICT INSTRUCTIONS:
- Base requirements ONLY on the provided policy information.
- Do NOT invent requirements not mentioned in the policy.
- Do NOT use a predefined list of insurance documents.
- Do NOT assume every policy requires the same documents.
- You MUST return a JSON object with the root key "required_documents".
- Each item must have "document_title" and "reason".
- If the policy contains no explicit supporting document requirements, return {"required_documents": []}.
- Return ONLY valid JSON.

JSON SCHEMA:
{
  "required_documents": [
    {
      "document_title": "Title of required document",
      "reason": "Why required according to policy text"
    }
  ]
}
"""


SYSTEM_MATCHING_PROMPT = """You are the Missing Document Detection and Semantic Matching engine of InsureMate.

Your task is to:
1. Examine the required documents established for this insurance claim.
2. Compare them against the submitted documents actually present in the claim bundle.
3. For every required document, determine whether any submitted document semantically satisfies it.

STRICT INSTRUCTIONS:
- CRITICAL: PERFORM SEMANTIC MATCHING, NOT EXACT TITLE MATCHING.
  Different hospitals, diagnostic centres, and insurers use different terminology for the same documents.
  If a submitted document serves the same purpose, it satisfies the requirement.
  For example, records like 'Patient Discharge Record' or 'Discharge Card' satisfy 'Discharge Summary'; 'Final Hospital Invoice' or 'Inpatient Bill' satisfies 'Final Hospital Bill'.
  Do NOT mark a document missing merely because the words in the title are not an exact word-for-word match.
- Only mark missing = true if NO submitted document serves the purpose of the required document (for example, a billing invoice cannot satisfy a laboratory investigation report).
- For each required document:
  * If a semantically matching document is present in submitted_documents:
    - Set missing = false
    - Set matched_submitted_document = exact title of that matching submitted document
    - Set page_number = exact integer page_number of that submitted document from the input
    - Set reason = clear explanation of why the submitted document satisfies the requirement
  * If NO matching document is present in submitted_documents:
    - Set missing = true
    - Set matched_submitted_document = null
    - Set page_number = null
    - Set reason = clear explanation that no submitted document fulfills this requirement
- CRITICAL PAGE NUMBER RULE: Never invent page numbers. Select page numbers ONLY from submitted_documents.
- Every required document must appear exactly once in document_results, with sequential sr_no starting at 1.
- You MUST return a JSON object with root key "document_results".
- Return ONLY valid JSON.

JSON SCHEMA:
{
  "document_results": [
    {
      "sr_no": 1,
      "document_title": "Required Document Title",
      "missing": false,
      "page_number": 2,
      "matched_submitted_document": "Matching Submitted Title",
      "reason": "Detailed explanation of semantic match or missing determination."
    }
  ]
}
"""


def build_requirement_extraction_prompt(
    policy_documents: List[Dict[str, Any]],
    conditions: Optional[List[str]] = None,
    claim_context: Optional[Dict[str, Any]] = None
) -> str:
    """Build Call #1 prompt to dynamically extract required documents from policy text."""
    msgs = build_requirement_extraction_messages(
        policy_documents=policy_documents,
        conditions=conditions,
        claim_context=claim_context
    )
    return f"{msgs[0]['content']}\n\n{msgs[1]['content']}"


def build_matching_prompt(
    required_documents: List[Dict[str, Any]],
    submitted_documents: List[Dict[str, Any]],
    phase2_validation_notes: Optional[List[Dict[str, Any]]] = None,
    phase3_validity_context: Optional[Dict[str, Any]] = None
) -> str:
    """Build Call #2 prompt to semantically match required documents against submitted documents."""
    payload: Dict[str, Any] = {
        "required_documents": required_documents,
        "submitted_documents": submitted_documents,
    }
    if phase2_validation_notes:
        payload["phase2_validation_notes"] = phase2_validation_notes
    if phase3_validity_context:
        payload["phase3_validity_context"] = phase3_validity_context

    return f"""{SYSTEM_MATCHING_PROMPT}

CLAIM DATA TO EVALUATE:
{json.dumps(payload, indent=2)}

Output the JSON now:"""


def build_requirement_extraction_messages(
    policy_documents: List[Dict[str, Any]],
    conditions: Optional[List[str]] = None,
    claim_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """Build messages array with separate system and user roles for requirement extraction."""
    payload: Dict[str, Any] = {
        "policy_documents": policy_documents,
    }
    if conditions:
        payload["relevant_conditions"] = conditions
    if claim_context:
        payload["claim_context"] = claim_context

    lines: List[str] = []
    for p in policy_documents:
        title = p.get("document_title") or f"Policy Page {p.get('page_number', 1)}"
        lines.append(f"Policy Document: {title}")
        clauses = p.get("policy_clauses", [])
        if clauses:
            lines.append("Policy Clauses:")
            for c in clauses:
                lines.append(f"- {c}")
        if p.get("policy_relevant_text"):
            lines.append(f"Policy Relevant Text:\n{p['policy_relevant_text']}")
        if p.get("relevant_conditions"):
            lines.append("Relevant Conditions:")
            for cond in p["relevant_conditions"]:
                lines.append(f"- {cond}")
        if p.get("extracted_text_summary"):
            lines.append(f"Summary: {p['extracted_text_summary']}")

    if conditions:
        lines.append("Additional Conditions:")
        for c in conditions:
            lines.append(f"- {c}")

    formatted_text = "\n".join(lines)
    user_content = (
        f"SUPPLIED POLICY INFORMATION:\n"
        f"{formatted_text}\n\n"
        f"STRUCTURED PAYLOAD:\n{json.dumps(payload, indent=2)}\n\n"
        f"Extract the required documents now in JSON format with root key 'required_documents':"
    )

    return [
        {"role": "system", "content": SYSTEM_REQUIREMENT_EXTRACTION_PROMPT},
        {"role": "user", "content": user_content}
    ]


def build_matching_messages(
    required_documents: List[Dict[str, Any]],
    submitted_documents: List[Dict[str, Any]],
    phase2_validation_notes: Optional[List[Dict[str, Any]]] = None,
    phase3_validity_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """Build messages array with separate system and user roles for semantic document matching."""
    payload: Dict[str, Any] = {
        "required_documents": required_documents,
        "submitted_documents": submitted_documents,
    }
    if phase2_validation_notes:
        payload["phase2_validation_notes"] = phase2_validation_notes
    if phase3_validity_context:
        payload["phase3_validity_context"] = phase3_validity_context

    return [
        {"role": "system", "content": SYSTEM_MATCHING_PROMPT},
        {"role": "user", "content": f"CLAIM DATA TO EVALUATE:\n{json.dumps(payload, indent=2)}\n\nOutput the JSON now:"}
    ]


def build_retry_prompt(
    original_prompt: str,
    invalid_response: str,
    error_reason: str
) -> str:
    """Build correction prompt when initial LLM response fails validation."""
    return f"""{original_prompt}

CRITICAL: Your previous response was INVALID and failed strict schema validation.

VALIDATION ERROR:
{error_reason}

PREVIOUS INVALID RESPONSE:
{invalid_response}

CORRECTION INSTRUCTIONS:
- Fix the validation error above.
- Ensure every item has a sequential sr_no starting from 1.
- If missing is false, page_number MUST be an integer taken directly from submitted_documents and matched_submitted_document must be non-null.
- If missing is true, page_number MUST be null and matched_submitted_document must be null.
- Output ONLY valid JSON:"""
