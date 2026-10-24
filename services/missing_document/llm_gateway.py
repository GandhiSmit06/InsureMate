"""services/missing_document/llm_gateway.py
Centralized LLM Gateway for Phase 4.
Coordinates communication with Gemma 3 via OllamaClient, robust JSON parsing,
and exactly-once retry without storing hardcoded document requirements.
"""

import json
import re
from typing import Any, Dict, List, Optional
from services.missing_document.ollama_client import OllamaClient, OllamaError
from services.missing_document.prompt_builder import (
    SYSTEM_MATCHING_PROMPT,
    SYSTEM_REQUIREMENT_EXTRACTION_PROMPT,
    build_requirement_extraction_messages,
    build_requirement_extraction_prompt,
    build_matching_messages,
    build_matching_prompt,
    build_retry_prompt,
)
from services.missing_document.schemas import (
    MissingDocumentResponse,
    MissingDocumentSummary,
    Phase4ValidationError,
    RequiredDocumentDefinition,
    validate_detection_output,
)
from utils.logger import logger


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """Extract and parse a JSON object from raw LLM output with robust stripping and repair."""
    cleaned = raw_text.strip()
    # Strip markdown code blocks anywhere in text
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"document_results": data}
    except json.JSONDecodeError:
        pass

    # Regex substring match for outermost balanced braces
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Regex array fallback
    arr_match = re.search(r"\[[\s\S]*\]", cleaned)
    if arr_match:
        try:
            arr_data = json.loads(arr_match.group(0))
            if isinstance(arr_data, list):
                return {"document_results": arr_data}
        except json.JSONDecodeError:
            pass

    # Lightweight regex key-value extraction fallback
    act_m = re.search(r'["\']action["\']\s*:\s*["\']([^"\']+)["\']', raw_text, re.I)
    rsn_m = re.search(r'["\']reason["\']\s*:\s*["\']([^"\']+)["\']', raw_text, re.I)
    if act_m:
        inp_m = re.search(r'["\']action_input["\']\s*:\s*(\{[\s\S]*?\})', raw_text, re.I)
        inp_val = {}
        if inp_m:
            raw_inp = inp_m.group(1)
            try:
                inp_val = json.loads(raw_inp)
            except Exception:
                try:
                    import ast
                    inp_val = ast.literal_eval(raw_inp)
                except Exception:
                    inp_val = {}
        return {
            "action": act_m.group(1).strip(),
            "reason": rsn_m.group(1).strip() if rsn_m else "Autonomous decision.",
            "action_input": inp_val
        }

    raise Phase4ValidationError(f"Could not parse valid JSON from LLM response: {raw_text[:200]}")


class LLMGateway:
    """Central gateway for executing Phase 4 LLM reasoning tasks."""

    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    def _extract_policy_requirements_offline(
        self,
        policy_documents: List[Dict[str, Any]],
        conditions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Dynamically extract required documents from policy clauses and text when LLM is offline."""
        requirements: List[Dict[str, Any]] = []
        seen = set()

        candidate_texts = list(conditions or [])
        for doc in policy_documents:
            candidate_texts.extend(doc.get("policy_clauses", []))
            candidate_texts.extend(doc.get("relevant_conditions", []))
            if doc.get("policy_relevant_text"):
                candidate_texts.append(doc.get("policy_relevant_text"))

        idx = 1
        doc_keywords = [
            "bill", "receipt", "discharge", "summary", "report", "certificate",
            "prescription", "claim form", "investigation", "id proof", "cheque",
            "fir", "police", "boarding pass", "ticket", "invoice"
        ]
        for txt in candidate_texts:
            lines = [l.strip() for l in re.split(r"[\n\r;]+", str(txt)) if l.strip()]
            for line in lines:
                clean_line = re.sub(r"^[\d\.\-\*\)\s]+", "", line).strip()
                if not clean_line or len(clean_line) < 4:
                    continue
                if any(kw in clean_line.lower() for kw in doc_keywords):
                    if any(ex in clean_line.lower() for ex in ["policy certificate", "policy schedule", "clause id", "admissible expenses", "statutory", "ombudsman"]):
                        continue
                    split_c = re.split(r"\s+(?:with|stating|and payment|supporting|issued by|duly)\s+", clean_line, flags=re.I)
                    title = split_c[0].strip() if split_c else clean_line
                    if len(title) > 60:
                        title = title[:60].strip()
                    title_norm = title.lower()
                    if any(ex in title_norm for ex in ["policy", "schedule", "clause id", "admissible"]):
                        continue
                    if title_norm not in seen:
                        seen.add(title_norm)
                        requirements.append({
                            "sr_no": idx,
                            "document_title": title,
                            "source": "policy_clause",
                            "reason": clean_line
                        })
                        idx += 1

        return requirements

    def _match_submitted_documents_offline(
        self,
        required_documents: List[Dict[str, Any]],
        submitted_documents: List[Dict[str, Any]],
        valid_submitted_pages: Optional[List[int]] = None
    ) -> MissingDocumentResponse:
        """Dynamically match submitted documents against requirements when LLM is offline."""
        valid_pages = set(valid_submitted_pages or [
            (d.get("page_number") if d.get("page_number") is not None else d.get("page_no"))
            for d in submitted_documents
            if (d.get("page_number") is not None or d.get("page_no") is not None)
        ])

        results = []
        for idx, req in enumerate(required_documents, start=1):
            req_title = (req.get("document_title") or "").strip()
            req_norm = req_title.lower()

            matched_doc = None
            matched_page = None

            req_words = set(re.findall(r"\w+", req_norm)) - {"and", "the", "of", "in", "for", "with", "or", "a", "an", "original", "copy", "duly", "stamped", "signed"}

            for sub in submitted_documents:
                sub_title = (sub.get("document_title") or sub.get("document_type") or "").strip()
                sub_norm = sub_title.lower()
                sub_page = sub.get("page_number") if sub.get("page_number") is not None else sub.get("page_no")

                # 1. Exact or substring match
                if req_norm in sub_norm or sub_norm in req_norm:
                    matched_doc = sub_title
                    matched_page = sub_page
                    break

                # 2. Key category matches
                cat_pairs = [
                    ({"discharge", "summary", "card"}, {"discharge", "summary", "card"}),
                    ({"bill", "final", "invoice", "tariff"}, {"bill", "invoice", "receipt", "tariff"}),
                    ({"admission", "indoor", "triage", "entry"}, {"admission", "indoor", "triage", "entry"}),
                    ({"receipt", "payment", "deposit", "settlement"}, {"receipt", "payment", "deposit", "settlement"}),
                    ({"pharmacy", "medicine", "chemist", "drug"}, {"pharmacy", "medicine", "chemist", "drug"}),
                    ({"investigation", "lab", "pathology", "diagnostic", "report", "reports", "radiology", "ct", "mri", "x-ray", "scan", "scans", "ultrasound", "usg", "imaging", "sonography"}, {"investigation", "lab", "pathology", "test", "radiology", "report", "reports", "diagnostic", "scan", "scans", "ultrasound", "usg", "imaging"}),
                    ({"claim", "form"}, {"claim", "form", "part-a", "part-b"}),
                    ({"cheque", "cancelled", "passbook", "bank"}, {"cheque", "passbook", "bank"}),
                    ({"aadhar", "pan", "kyc", "identity", "id"}, {"aadhar", "pan", "kyc", "identity", "id"}),
                    ({"room", "rent", "boarding", "cov-002"}, {"room", "rent", "boarding", "folio", "bill", "invoice", "charges"}),
                ]
                matched_category = False
                for req_syns, sub_syns in cat_pairs:
                    if req_words.intersection(req_syns) and any(s in sub_norm for s in sub_syns):
                        matched_doc = sub_title
                        matched_page = sub_page
                        matched_category = True
                        break
                if matched_category:
                    break

                # 3. Word overlap match
                sub_words = set(re.findall(r"\w+", sub_norm))
                overlap = req_words.intersection(sub_words)
                if len(overlap) >= 2 or (len(req_words) == 1 and overlap):
                    matched_doc = sub_title
                    matched_page = sub_page
                    break

            if matched_doc and matched_page is not None:
                try:
                    p_num = int(matched_page)
                    if not valid_pages or p_num in valid_pages:
                        results.append({
                            "sr_no": idx,
                            "document_title": req_title,
                            "missing": False,
                            "page_number": p_num,
                            "matched_submitted_document": matched_doc,
                            "reason": f"Located '{matched_doc}' on page {p_num} satisfying requirement."
                        })
                        continue
                except (ValueError, TypeError):
                    pass

            results.append({
                "sr_no": idx,
                "document_title": req_title,
                "missing": True,
                "page_number": None,
                "matched_submitted_document": None,
                "reason": f"No submitted document matched '{req_title}'."
            })

        payload = {
            "required_documents": required_documents,
            "document_results": results,
            "reason": "Matched submitted documents against policy requirements dynamically."
        }
        return validate_detection_output(payload, valid_submitted_pages=list(valid_pages))

    def extract_policy_requirements(
        self,
        policy_documents: List[Dict[str, Any]],
        conditions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Call #1: Use Gemma 3 to dynamically determine required documents from policy evidence."""
        if not self.client.is_available():
            logger.missing_doc("Ollama is offline; deriving policy requirements dynamically from policy text/clauses.")
            return self._extract_policy_requirements_offline(policy_documents, conditions)

        messages = build_requirement_extraction_messages(
            policy_documents=policy_documents,
            conditions=conditions
        )
        logger.missing_doc("Calling LLM Gateway for dynamic requirement extraction...")
        try:
            raw_response = self.client.chat(
                messages=messages,
                format_type="json"
            )
        except Exception as e:
            logger.missing_doc(f"Ollama chat failed ({e}); falling back to dynamic offline requirement extraction.")
            return self._extract_policy_requirements_offline(policy_documents, conditions)

        try:
            parsed = extract_json_from_text(raw_response)
        except Exception as e:
            # Retry once on malformed requirement JSON
            retry_prompt = build_retry_prompt(messages[1]["content"], raw_response, str(e))
            try:
                raw_response = self.client.chat(
                    messages=[
                        messages[0],
                        messages[1],
                        {"role": "assistant", "content": raw_response},
                        {"role": "user", "content": retry_prompt}
                    ],
                    format_type="json"
                )
                parsed = extract_json_from_text(raw_response)
            except Exception:
                return self._extract_policy_requirements_offline(policy_documents, conditions)

        if isinstance(parsed, list):
            raw_list = parsed
        elif isinstance(parsed, dict):
            raw_list = (
                parsed.get("required_documents")
                or parsed.get("policy_requirements")
                or parsed.get("document_results")
                or []
            )
        else:
            raw_list = []
        requirements: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_list, start=1):
            if isinstance(item, str):
                requirements.append({
                    "sr_no": idx,
                    "document_title": item.strip(),
                    "source": "policy",
                    "reason": "Explicitly stated in policy content"
                })
            elif isinstance(item, dict) and item.get("document_title"):
                t = item["document_title"].strip()
                if any(ex in t.lower() for ex in ["policy schedule", "policy certificate", "insurance policy", "clause id"]):
                    continue
                requirements.append({
                    "sr_no": len(requirements) + 1,
                    "document_title": t,
                    "source": item.get("source", "policy"),
                    "reason": item.get("reason", "")
                })

        if not requirements:
            return self._extract_policy_requirements_offline(policy_documents, conditions)

        return requirements

    def match_submitted_documents(
        self,
        required_documents: List[Dict[str, Any]],
        submitted_documents: List[Dict[str, Any]],
        phase2_notes: Optional[List[Dict[str, Any]]] = None,
        phase3_context: Optional[Dict[str, Any]] = None,
        valid_submitted_pages: Optional[List[int]] = None
    ) -> MissingDocumentResponse:
        """Call #2: Use Gemma 3 to semantically match submitted documents against requirements."""
        if not self.client.is_available():
            logger.missing_doc("Ollama is offline; executing dynamic rule-based document matching.")
            return self._match_submitted_documents_offline(required_documents, submitted_documents, valid_submitted_pages)

        messages = build_matching_messages(
            required_documents=required_documents,
            submitted_documents=submitted_documents,
            phase2_validation_notes=phase2_notes,
            phase3_validity_context=phase3_context
        )

        # Attempt 1
        logger.missing_doc("Calling LLM Gateway for semantic document matching (Attempt 1/2)...")
        try:
            raw_resp = self.client.chat(
                messages=messages,
                format_type="json"
            )
        except Exception as e:
            logger.missing_doc(f"Ollama chat failed ({e}); falling back to dynamic offline document matching.")
            return self._match_submitted_documents_offline(required_documents, submitted_documents, valid_submitted_pages)

        try:
            parsed = extract_json_from_text(raw_resp)
            parsed["required_documents"] = required_documents
            return validate_detection_output(parsed, valid_submitted_pages=valid_submitted_pages)
        except Exception as first_error:
            logger.missing_doc(f"Attempt 1 validation error: {first_error}. Triggering exactly-once retry...")

            # Attempt 2 (Retry exactly once)
            retry_content = f"""CRITICAL: Your previous response was INVALID and failed strict schema validation.

VALIDATION ERROR:
{first_error}

PREVIOUS INVALID RESPONSE:
{raw_resp}

CORRECTION INSTRUCTIONS:
- Fix the validation error above.
- You MUST output a JSON object containing the root key "document_results".
- Ensure every item has a sequential sr_no starting from 1.
- If missing is false, page_number MUST be an integer taken directly from submitted_documents and matched_submitted_document must be non-null.
- If missing is true, page_number MUST be null and matched_submitted_document must be null.
- Output ONLY valid JSON:"""

            retry_messages = [
                messages[0],
                messages[1],
                {"role": "assistant", "content": raw_resp},
                {"role": "user", "content": retry_content}
            ]

            try:
                raw_retry_resp = self.client.chat(
                    messages=retry_messages,
                    format_type="json"
                )
                parsed_retry = extract_json_from_text(raw_retry_resp)
                parsed_retry["required_documents"] = required_documents
                return validate_detection_output(parsed_retry, valid_submitted_pages=valid_submitted_pages)
            except Exception as second_error:
                logger.error(f"Attempt 2 retry failed validation: {second_error}.")
                return MissingDocumentResponse(
                    status="error",
                    tool="missing_document_tool",
                    required_documents=[],
                    document_results=[],
                    summary=MissingDocumentSummary(total_required=0, present=0, missing=0),
                    reason=f"LLM response failed validation after retry: {second_error}",
                    error=str(second_error)
                )
