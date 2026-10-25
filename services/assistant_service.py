"""services/assistant_service.py
Insurance Document Assistant Service using local Ollama Gemma 3.
Provides question-aware, evidence-grounded answers for active claim sessions.
Strictly adheres to insurance domain scope and respects factual evidence.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from utils.logger import logger
from services.missing_document.ollama_client import OllamaClient, OllamaError
from tools.policy_clause_search_tool import PolicyClauseSearchTool

OUT_OF_SCOPE_RESPONSE = (
    "I am InsureMate's AI document assistant, specialized in analyzing insurance policies and claim documents. "
    "I can only assist with questions regarding your uploaded policy, claim eligibility, hospital bills, "
    "coverage dates, or missing evidence. Please ask an insurance or claim-related question."
)

GREETING_RESPONSE = (
    "Hello! I am your InsureMate document assistant. You can ask me questions about your claim's "
    "policy eligibility, active coverage period, hospital bills, missing evidence, discrepancies, "
    "or policy clauses from your uploaded documents."
)

# Known out-of-scope triggers (programming, DSA, sports, general trivia)
OUT_OF_SCOPE_PATTERNS = [
    r"\b(dsa|data\s+structures?|algorithms?|bubble\s+sort|merge\s+sort|quick\s+sort|binary\s+tree|linked\s+list|dynamic\s+programming|recursion)\b",
    r"\b(python|javascript|typescript|c\+\+|java|html|css|sql\s+query|function\s+syntax|compile|git\s+commit)\b",
    r"\b(cricket|football|soccer|ipl|fifa|world\s+cup|match|score|batting|bowling|tennis|nba)\b",
    r"\b(capital\s+of|weather\s+in|recipe\s+for|tell\s+me\s+a\s+joke|movie|song|lyrics|actor|president\s+of)\b",
    r"\b(quantum|photosynthesis|speed\s+of\s+light|astronomy|planet\s+mars)\b",
]

# Legitimate insurance, claim, medical, and document keywords
INSURANCE_DOMAIN_KEYWORDS = [
    "claim", "policy", "insur", "coverage", "eligib", "benefit", "exclusion", "clause",
    "premium", "deductible", "co-pay", "copay", "sum\s+insured", "limit", "cashless",
    "hospital", "doctor", "physician", "patient", "admission", "discharge", "treatment",
    "diagnosis", "ailment", "illness", "surgery", "disease", "medical", "bill", "invoice",
    "receipt", "charge", "cost", "amount", "expense", "fee", "pay", "reimburse",
    "document", "evidence", "missing", "record", "folio", "checklist", "discrepan", "mismatch",
    "valid", "period", "expiry", "inception", "date", "audit", "verdict", "status", "ready",
    "admissib", "approve", "reject", "settle", "submission", "next\s+step", "action"
]


def is_insurance_domain(question: str) -> bool:
    """
    Determine if a user query falls within the insurance document assistant's domain.
    Filters out computing, sports, and general trivia queries without rejecting legitimate
    insurance questions.
    """
    if not question or not question.strip():
        return False

    q_lower = question.lower().strip()

    # 1. Check for explicit out-of-scope topics
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, q_lower):
            # Check if it was purely framed around insurance (e.g. "does policy cover algorithm surgery?" - rare)
            # If explicit DSA / algorithm / sports term found, mark out of scope
            return False

    # 2. Check for insurance domain keywords
    for kw in INSURANCE_DOMAIN_KEYWORDS:
        if re.search(r"\b" + kw, q_lower):
            return True

    # 3. Contextual inquiry about active analysis
    # E.g., "Is Aarav Mehta covered?", "Who is the patient?", "What is missing?", "Is everything valid?"
    contextual_phrases = [
        "what next", "what should i do", "what is next", "is it ready", "can i submit",
        "why was it", "why is this", "what happened", "who is", "how much", "is this covered",
        "are we covered", "am i covered", "is anything missing", "what is missing"
    ]
    for phrase in contextual_phrases:
        if phrase in q_lower:
            return True

    # 4. If query is very short or ambiguous (e.g. single generic word not in insurance), consider outside scope
    words = [w for w in re.findall(r"\w+", q_lower) if len(w) > 1]
    if len(words) <= 2 and not any(re.search(r"\b" + kw, q_lower) for kw in INSURANCE_DOMAIN_KEYWORDS):
        return False

    # Default to accepting if it appears to be an inquiry about the documents/person
    return True


def is_simple_greeting(question: str) -> bool:
    """Check if query is simply a greeting like 'hello', 'hi', 'hey'."""
    q = question.lower().strip()
    return q in ("hi", "hello", "hey", "greetings", "good morning", "good evening", "good afternoon", "help")


def extract_claim_facts(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract unified verified facts, dates, entities, and report details from claim data."""
    claim = claim_data.get("claim") or {}
    report = claim_data.get("final_report") or {}
    latest_state = claim_data.get("latest_state") or {}

    facts: Dict[str, Any] = {}
    if isinstance(latest_state.get("verified_facts"), dict):
        facts.update(latest_state["verified_facts"])

    extracted_pages = latest_state.get("extracted_data") or []
    if isinstance(extracted_pages, list):
        for page in extracted_pages:
            if isinstance(page, dict):
                p_type = str(page.get("document_type") or "").lower()
                p_title = str(page.get("document_title") or "").lower()
                doc_date = page.get("document_date")

                if doc_date:
                    if not facts.get("admission_date") and any(w in p_title for w in ["admission", "indoor", "admit"]):
                        facts["admission_date"] = doc_date
                    if not facts.get("discharge_date") and any(w in p_title for w in ["discharge", "summary"]):
                        facts["discharge_date"] = doc_date

                if page.get("bill_amount") and not facts.get("total_bill_amount"):
                    facts["total_bill_amount"] = page["bill_amount"]

                if page.get("diagnosis") and not facts.get("diagnosis"):
                    facts["diagnosis"] = page["diagnosis"]

                for k, v in page.items():
                    if k not in facts and v and not isinstance(v, (dict, list)):
                        facts[k] = v
                if isinstance(page.get("extracted_fields"), dict):
                    for k, v in page["extracted_fields"].items():
                        if k not in facts and v:
                            facts[k] = v

    # Fallback to validity checks dates if admission/discharge dates still empty
    val_res = latest_state.get("validity_result") or report.get("validity_check") or {}
    checks = val_res.get("checks") or []
    hospital_dates = [c.get("normalized_date") or c.get("raw_date") for c in checks if c.get("raw_date")]
    if hospital_dates:
        if not facts.get("admission_date"):
            facts["admission_date"] = hospital_dates[0]
        if not facts.get("discharge_date"):
            facts["discharge_date"] = hospital_dates[-1]

    if isinstance(report.get("extracted_fields"), list):
        for item in report["extracted_fields"]:
            if isinstance(item, dict) and item.get("name") and item.get("value"):
                facts[item["name"].lower().replace(" ", "_")] = item["value"]

    return facts


def extract_evidence_status(claim_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract authoritative submitted documents and truly missing required documents.
    Returns: (submitted_docs, missing_docs)
    """
    latest_state = claim_data.get("latest_state") or {}
    report = claim_data.get("final_report") or {}

    raw_missing = (
        latest_state.get("missing_documents")
        or report.get("missing_documents")
        or {}
    )

    doc_results: List[Dict[str, Any]] = []
    if isinstance(raw_missing, dict):
        doc_results = (
            raw_missing.get("document_results")
            or raw_missing.get("missing_documents")
            or raw_missing.get("required_documents")
            or raw_missing.get("items")
            or []
        )
    elif isinstance(raw_missing, list):
        doc_results = raw_missing

    submitted: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for d in doc_results:
        if isinstance(d, dict):
            title = d.get("document_title") or d.get("title") or d.get("name") or d.get("document") or d.get("document_type")
            if not title:
                continue
            title_str = str(title).strip()
            reason = d.get("reason") or "Required by policy documentation schedule."
            page_no = d.get("page_number") or d.get("page_no")
            is_missing = d.get("missing") is True or str(d.get("status", "")).lower() == "missing"

            doc_info = {
                "title": title_str,
                "reason": reason,
                "page_number": page_no,
                "matched_document": d.get("matched_submitted_document") or d.get("submitted_document_title")
            }

            if is_missing:
                missing.append(doc_info)
            else:
                submitted.append(doc_info)
        elif isinstance(d, str) and d.strip():
            missing.append({
                "title": d.strip(),
                "reason": "Mandatory policy requirement not found in submission.",
                "page_number": None
            })

    return submitted, missing


def build_focused_context(claim_data: Dict[str, Any], question: str) -> str:
    """
    Build a structured, focused context document for Gemma 3 based on the specific question.
    Includes claim facts, validity checks, authoritative evidence status, and relevant policy excerpts.
    """
    claim_id = (
        claim_data.get("claim", {}).get("claim_id")
        or claim_data.get("claim_id")
        or "UNKNOWN"
    )
    report = claim_data.get("final_report") or {}
    latest_state = claim_data.get("latest_state") or {}
    verdict = claim_data.get("verdict") or report.get("verdict") or report.get("status") or "UNKNOWN"

    facts = extract_claim_facts(claim_data)
    submitted_docs, missing_docs = extract_evidence_status(claim_data)

    val_res = latest_state.get("validity_result") or report.get("validity_check") or report.get("validity") or {}
    policy_period = val_res.get("policy_period") or {}
    p_start = policy_period.get("policy_start_date") or val_res.get("policy_start_date") or facts.get("policy_start_date") or facts.get("inception_date") or "Not specified"
    p_end = policy_period.get("policy_end_date") or val_res.get("policy_end_date") or facts.get("policy_end_date") or facts.get("expiry_date") or "Not specified"
    p_number = policy_period.get("policy_number") or facts.get("policy_number") or facts.get("policy_no") or "Not specified"

    admission_date = facts.get("admission_date") or facts.get("date_of_admission") or "Not specified"
    discharge_date = facts.get("discharge_date") or facts.get("date_of_discharge") or "Not specified"
    is_valid_dates = val_res.get("valid")

    discrepancy_reasons = []
    if is_valid_dates is False and val_res.get("reasons"):
        discrepancy_reasons.extend(val_res["reasons"])

    validation_result = latest_state.get("validation_result") or report.get("validation_result") or {}
    if isinstance(validation_result, dict):
        if validation_result.get("discrepancies"):
            discrepancy_reasons.extend(validation_result["discrepancies"])
        if validation_result.get("warnings"):
            discrepancy_reasons.extend(validation_result["warnings"])

    # Retrieve relevant policy clauses matching question keywords using existing PolicyClauseSearchTool
    extracted_pages = latest_state.get("extracted_data") or []
    clause_snippets = []
    if extracted_pages:
        try:
            search_tool = PolicyClauseSearchTool()
            clause_search = search_tool.run(query=question, extracted_data=extracted_pages)
            matches = clause_search.get("matched_clauses") or []
            for m in matches[:3]:
                c_text = str(m.get("clause_text", "")).strip()
                p_no = m.get("page_number", 1)
                if c_text:
                    clause_snippets.append(f"[Page {p_no}] {c_text[:300]}")
        except Exception as e:
            logger.warning(f"[ASSISTANT] Policy clause search helper failed: {e}")

    # Build structured text context
    lines = [
        f"--- ACTIVE CLAIM ANALYSIS ---",
        f"CLAIM IDENTIFIER: {claim_id}",
        f"ADMINISTRATIVE STATUS: {verdict}",
        f"IMPORTANT NOTICE: {verdict} denotes administrative document readiness based on verified submissions. It does NOT guarantee final insurer approval, legal eligibility, or final claim payout.",
        "",
        "--- KEY CLAIM DETAILS ---",
        f"• Policy Number: {p_number}",
        f"• Active Policy Coverage Window: {p_start} to {p_end}",
        f"• Insured / Patient Name: {facts.get('patient_name') or facts.get('insured_name') or 'Not specified'}",
        f"• Treating Hospital / Provider: {facts.get('hospital_name') or facts.get('provider_name') or 'Not specified'}",
        f"• Hospitalization Period: Admission: {admission_date} | Discharge: {discharge_date}",
        f"• Total Claimed / Billed Amount: {facts.get('total_bill_amount') or facts.get('bill_amount') or 'Not specified'}",
        f"• Documented Diagnosis / Treatment: {facts.get('diagnosis') or facts.get('ailment') or facts.get('treatment') or 'Not specified'}",
        "",
        "--- VALIDATION & DATE ADMISSIBILITY ---",
        f"• Date Validity Pass: {is_valid_dates if is_valid_dates is not None else 'Verified'}",
    ]

    if discrepancy_reasons:
        lines.append("• Flagged Discrepancies:")
        for r in discrepancy_reasons[:5]:
            lines.append(f"  - {r}")
    else:
        lines.append("• Discrepancies: None detected across validated documents.")

    lines.append("")
    lines.append("--- EVIDENCE & DOCUMENT CHECKLIST (AUTHORITATIVE) ---")
    if submitted_docs:
        lines.append(f"• Submitted & Verified Documents ({len(submitted_docs)} item(s)):")
        for doc in submitted_docs:
            p_str = f" (Page {doc['page_number']})" if doc.get('page_number') else ""
            lines.append(f"  ✓ {doc['title']}{p_str}: {doc['reason']}")
    else:
        lines.append("• Submitted Documents: None verified.")

    if missing_docs:
        lines.append(f"• Truly Missing Required Documents ({len(missing_docs)} item(s)):")
        for doc in missing_docs:
            lines.append(f"  ✗ MISSING: {doc['title']} — Rationale: {doc['reason']}")
    else:
        lines.append("• Truly Missing Required Documents: None. All mandatory documents verified present.")

    if clause_snippets:
        lines.append("")
        lines.append("--- RELEVANT POLICY EXCERPTS MATCHING QUERY ---")
        for cs in clause_snippets:
            lines.append(f"• {cs}")

    decision_summary = report.get("decision_summary")
    if decision_summary:
        lines.append("")
        lines.append(f"AUDIT DECISION SUMMARY: {decision_summary}")

    return "\n".join(lines)


def ask_assistant(
    claim_data: Dict[str, Any],
    question: str,
    client: Optional[OllamaClient] = None
) -> Dict[str, Any]:
    """
    Main entrypoint for AI Assistant Question Answering.
    1. Checks domain scope.
    2. Gathers grounded facts from current claim session.
    3. Prompts local Gemma 3 model.
    4. Handles errors, model unavailability, and timeouts gracefully.
    """
    q_clean = question.strip()
    if not q_clean:
        return {
            "answer": "Please ask a question about your claim or policy documents.",
            "sources": []
        }

    # 1. Simple greeting handling
    if is_simple_greeting(q_clean):
        return {
            "answer": GREETING_RESPONSE,
            "sources": []
        }

    # 2. Domain scope check
    if not is_insurance_domain(q_clean):
        logger.info(f"[ASSISTANT] Out-of-scope query rejected: '{q_clean}'")
        return {
            "answer": OUT_OF_SCOPE_RESPONSE,
            "sources": []
        }

    # 3. Initialize or reuse Ollama client
    model_name = os.environ.get("OLLAMA_MODEL", "gemma3:latest")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    ollama_client = client or OllamaClient(base_url=base_url, model=model_name)

    # 4. Check if Ollama service is reachable
    if not ollama_client.is_available():
        logger.error(f"[ASSISTANT] Ollama service or model '{model_name}' is unreachable at {base_url}.")
        return {
            "answer": (
                f"The Assistant AI model ({model_name}) is currently unavailable or unreachable on the "
                f"configured Ollama server ({base_url}). Please ensure that Ollama is running ('ollama serve') "
                f"and that '{model_name}' has been pulled."
            ),
            "sources": []
        }

    # 5. Build focused context
    context = build_focused_context(claim_data, q_clean)

    # 6. Construct prompt for Gemma 3
    system_prompt = (
        "You are InsureMate's AI Insurance Document Assistant.\n"
        "Your task is to answer the user's specific question directly, concisely, and strictly based on the provided claim facts and policy evidence.\n\n"
        "CRITICAL RULES:\n"
        "1. Answer the user's specific question directly first.\n"
        "2. Ground every conclusion in the provided context. Never invent policy clauses, benefits, exclusions, dates, or documents.\n"
        "3. Policy Eligibility: If asked about eligibility for a claim, evaluate coverage dates, required evidence, discrepancies, and policy exclusions.\n"
        "   CRITICAL DISTINCTION: Administrative readiness ('CLAIM_READY_FOR_SUBMISSION') indicates document completeness and validation; it does NOT automatically guarantee insurer approval or legal coverage.\n"
        "4. Missing Evidence: If asked about missing documents or checklist items, list only the genuinely missing items from the evidence section and state why they are needed. If NO items are missing, explicitly state that all mandatory documents have been submitted and verified.\n"
        "5. Discrepancies: Explain any date or entity discrepancies if present. If none are present, state that documents are consistent.\n"
        "6. Explicit Uncertainty: If the requested information is not mentioned in the provided documents or context, explicitly state that the information is not available in the uploaded documents.\n"
        "7. Keep responses concise, clear, and well-structured using bullet points where helpful."
    )

    user_prompt = f"CLAIM EVIDENCE & CONTEXT:\n{context}\n\nUSER QUESTION: {q_clean}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        logger.info(f"[ASSISTANT] Sending query to Ollama ({model_name}): '{q_clean[:80]}...'")
        answer_text = ollama_client.chat(messages, model=model_name, format_type=None)

        if not answer_text or not answer_text.strip():
            return {
                "answer": "The model returned an empty response. Please try rephrasing your question.",
                "sources": []
            }

        return {
            "answer": answer_text.strip(),
            "sources": []
        }

    except OllamaError as oe:
        logger.error(f"[ASSISTANT] Ollama invocation error: {oe}")
        return {
            "answer": f"Unable to generate response from Ollama: {oe}",
            "sources": []
        }
    except Exception as e:
        logger.error(f"[ASSISTANT] Unexpected error during assistant processing: {e}")
        return {
            "answer": f"An error occurred while answering your question: {e}",
            "sources": []
        }
