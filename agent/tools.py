"""agent/tools.py
Wraps existing InsureMate tools into standardized agent-callable tool adapters.
Reuses:
- QwenVLExtractionTool (Phase 1)
- DocumentValidationTool (Phase 2)
- ValidityCheckerTool (Phase 3)
- MissingDocumentTool (Phase 4)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from agent.state import ClaimState, ClaimStatus
from tools.qwen_vl_tool import QwenVLExtractionTool
from tools.document_validation_tool import DocumentValidationTool
from tools.validity_checker_tool import ValidityCheckerTool
from tools.missing_document_tool import MissingDocumentTool
from tools.policy_clause_search_tool import PolicyClauseSearchTool
from tools.cross_document_consistency_tool import CrossDocumentConsistencyTool
from utils.logger import logger


@dataclass
class ToolExecutionResult:
    """Standardized tool output returned to the InsureMate Agent."""
    tool_name: str
    status: str  # "success", "error", "warning"
    summary: str  # Concise 1-2 sentence human-readable summary
    data: Dict[str, Any]  # Full structured data
    error: Optional[str] = None


class BaseAgentTool:
    """Base class for Agent Tools with schema, manifest, and error handling."""
    name: str = ""
    description: str = ""
    required_inputs: List[str] = []
    parameters: Dict[str, Any] = {}
    expected_output: str = ""
    prerequisites: List[str] = []
    side_effects: bool = False
    requires_authorization: bool = False
    error_behavior: str = "Returns ToolExecutionResult with status='error' and error message."
    execution_constraints: Dict[str, Any] = {}

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        raise NotImplementedError

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_inputs": self.required_inputs,
            "parameters": self.parameters,
        }

    def get_manifest(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "expected_output": self.expected_output,
            "prerequisites": self.prerequisites,
            "side_effects": self.side_effects,
            "requires_authorization": self.requires_authorization,
            "error_behavior": self.error_behavior,
            "execution_constraints": self.execution_constraints,
        }


class DocumentExtractionAdapter(BaseAgentTool):
    """
    Tool 1: document_extraction
    Wraps existing QwenVLExtractionTool.
    Processes uploaded PDF documents and extracts structured claim entities.
    """
    name: str = "document_extraction"
    description: str = (
        "Extracts structured insurance entities and classifications from uploaded PDF documents "
        "using Qwen-VL / vision understanding, preserving 1-indexed page numbers."
    )
    required_inputs: List[str] = ["documents"]
    parameters: Dict[str, Any] = {
        "documents": {"type": "array", "description": "Optional list of document filepaths to extract"},
        "max_pages": {"type": "integer", "description": "Optional upper limit of pages to extract per document"}
    }
    expected_output: str = "Extracted list of document pages with entities, titles, dates, amounts, and classifications."
    prerequisites: List[str] = []
    side_effects: bool = False
    requires_authorization: bool = False
    error_behavior: str = "Returns status='error' if files do not exist or cannot be parsed."

    def __init__(self, tool: Optional[QwenVLExtractionTool] = None, offline_mode: Optional[bool] = None):
        self.underlying_tool = tool or QwenVLExtractionTool(offline_mode=offline_mode)

    def run(self, state: ClaimState, max_pages: Optional[int] = None, **kwargs: Any) -> ToolExecutionResult:
        if not state.documents and not state.extracted_data:
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                summary="No document filepaths or pre-extracted records found in claim state.",
                data={"total_pages": 0, "extracted_documents": []},
                error="Missing document paths."
            )

        # If data is already pre-extracted (e.g., passed in memory), preserve and summarize it
        if state.extracted_data and not state.documents:
            doc_types = [d.get("document_type", "unknown") for d in state.extracted_data]
            summary = f"Pre-extracted data verified: {len(state.extracted_data)} page(s) ({', '.join(doc_types)})."
            return ToolExecutionResult(
                tool_name=self.name,
                status="success",
                summary=summary,
                data={
                    "total_pages": len(state.extracted_data),
                    "extracted_documents": state.extracted_data
                }
            )

        all_pages: List[Dict[str, Any]] = []
        errors: List[str] = []

        for doc_path in state.documents:
            path_obj = Path(doc_path)
            if not path_obj.exists():
                err_msg = f"Required source document not found: {path_obj.name}"
                logger.error(err_msg)
                errors.append(err_msg)
                continue
            res = self.underlying_tool.run(path_obj, max_pages=max_pages)
            if res.get("status") == "success":
                pages = res.get("extracted_documents", [])
                p_norm = str(path_obj.resolve()).lower()
                pol_norms = [str(Path(p).resolve()).lower() for p in (state.policy_documents or []) if p]
                clm_norms = [str(Path(c).resolve()).lower() for c in (state.claim_documents or []) if c]
                slot = "policy" if (p_norm in pol_norms or any(Path(p).name.lower() == path_obj.name.lower() for p in (state.policy_documents or []) if p)) else (
                    "claim" if (p_norm in clm_norms or any(Path(c).name.lower() == path_obj.name.lower() for c in (state.claim_documents or []) if c)) else None
                )
                for p in pages:
                    p["source_file"] = p.get("source_file") or path_obj.name
                    p["file_path"] = p.get("file_path") or str(path_obj.resolve())
                    if slot:
                        p["slot"] = slot
                all_pages.extend(pages)
            else:
                err = res.get("error") or f"Extraction failed for {path_obj.name}"
                errors.append(err)

        if errors:
            state.errors.extend(errors)

        if not all_pages and errors:
            combined_err = "; ".join(errors)
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                summary=f"Extraction failed: {combined_err}",
                data={"total_pages": 0, "extracted_documents": []},
                error=combined_err
            )

        # Update claim state
        state.extracted_data = all_pages
        state.page_numbers = [p.get("page_number", idx + 1) for idx, p in enumerate(all_pages)]
        state.document_classifications = {
            p.get("page_number", idx + 1): p.get("document_type", "unknown")
            for idx, p in enumerate(all_pages)
        }

        # Form concise summary
        type_counts: Dict[str, int] = {}
        for p in all_pages:
            dt = p.get("document_type", "unknown")
            type_counts[dt] = type_counts.get(dt, 0) + 1

        types_str = ", ".join(f"{cnt} {t.replace('_', ' ')}" for t, cnt in type_counts.items())
        summary = f"Extracted {len(all_pages)} document page(s) ({types_str})."

        return ToolExecutionResult(
            tool_name=self.name,
            status="success",
            summary=summary,
            data={"total_pages": len(all_pages), "extracted_documents": all_pages}
        )


class DocumentValidationAdapter(BaseAgentTool):
    """
    Tool 2: document_validation
    Wraps existing DocumentValidationTool.
    Deterministically evaluates completeness of mandatory claim fields.
    """
    name: str = "document_validation"
    description: str = (
        "Deterministically validates extracted documents against required claim fields "
        "by document category (policy, medical bill, hospital record, report) and returns pass/fail."
    )
    required_inputs: List[str] = ["extracted_data"]

    def __init__(self, tool: Optional[DocumentValidationTool] = None):
        self.underlying_tool = tool or DocumentValidationTool()

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        if not state.extracted_data:
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                summary="Cannot validate documents: no extracted data available in claim state.",
                data={"valid": False, "total_documents": 0},
                error="No extracted data provided."
            )

        res = self.underlying_tool.run(
            extracted_documents=state.extracted_data,
            policy_file=state.policy_documents or None,
            claim_file=state.claim_documents or None
        )
        if res.get("status") == "error":
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                summary=f"Document validation encountered error: {res.get('error')}",
                data=res,
                error=res.get("error")
            )

        val_result = res.get("validation_result", {})
        state.validation_result = val_result

        total = res.get("total_documents", 0)
        valid_cnt = res.get("valid_documents", 0)
        invalid_cnt = res.get("invalid_documents", 0)
        is_overall_valid = res.get("valid", False)

        if is_overall_valid:
            summary = f"Documents passed validation: {valid_cnt}/{total} valid documents with all mandatory fields."
        else:
            missing_reasons = val_result.get("summary_reasons", [])
            first_reason = missing_reasons[0] if missing_reasons else f"{invalid_cnt} invalid document(s)"
            summary = f"Document validation detected issues: {first_reason} ({valid_cnt}/{total} valid)."

        return ToolExecutionResult(
            tool_name=self.name,
            status="success",
            summary=summary,
            data=val_result
        )


class ValidityCheckerAdapter(BaseAgentTool):
    """
    Tool 3: validity_checker
    Wraps existing ValidityCheckerTool.
    Evaluates bill and incident dates against policy coverage duration and matches patient identity.
    """
    name: str = "validity_checker"
    description: str = (
        "Deterministically verifies whether medical bills and claim documents fall within "
        "policy coverage dates, checks date formatting, and cross-references patient identity."
    )
    required_inputs: List[str] = ["extracted_data"]

    def __init__(self, tool: Optional[ValidityCheckerTool] = None):
        self.underlying_tool = tool or ValidityCheckerTool()

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        if not state.extracted_data:
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                summary="Cannot evaluate validity: no extracted document data available.",
                data={"valid": False},
                error="No extracted data."
            )

        # Separate policy documents from claim documents
        policy_docs = [d for d in state.extracted_data if d.get("document_type") == "insurance_policy"]
        claim_docs = [
            d for d in state.extracted_data
            if d.get("document_type") in ("medical_bill", "medical_report", "hospital_document", "invoice", "incident_document")
        ]

        if not policy_docs:
            return ToolExecutionResult(
                tool_name=self.name,
                status="warning",
                summary="Policy document not present in extracted data; cannot establish coverage duration.",
                data={"valid": False, "reasons": ["No policy document found"]},
                error="No policy document found in extraction."
            )

        if not claim_docs:
            # Fallback: if all documents are policy or unspecified, pass empty list
            claim_docs = [d for d in state.extracted_data if d.get("document_type") != "insurance_policy"]

        res = self.underlying_tool.run(policy_data=policy_docs, document_data=claim_docs)
        if res.get("status") == "error":
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                summary=f"Validity checker tool failed: {res.get('error')}",
                data=res,
                error=res.get("error")
            )

        state.validity_result = res
        is_valid = res.get("valid", False)
        reasons = res.get("reasons", [])

        if is_valid:
            summary = "VALID: All submitted document dates fall strictly within the active policy coverage period."
        else:
            issue_reason = reasons[1] if len(reasons) > 1 else (reasons[0] if reasons else "Dates outside policy period")
            summary = f"INVALID: {issue_reason}"

        return ToolExecutionResult(
            tool_name=self.name,
            status="success",
            summary=summary,
            data=res
        )


class MissingDocumentDetectorAdapter(BaseAgentTool):
    """
    Tool 4: missing_document_detector
    Wraps existing MissingDocumentTool.
    Dynamically infers policy requirements and matches against submitted claim evidence.
    """
    name: str = "missing_document_detector"
    description: str = (
        "Dynamically determines required documents for an insurance claim based on policy terms, "
        "semantically compares against submitted claim documents, and identifies missing evidence."
    )
    required_inputs: List[str] = ["extracted_data"]

    def __init__(self, tool: Optional[MissingDocumentTool] = None, offline_mode: Optional[bool] = None):
        if tool is not None:
            self.underlying_tool = tool
        elif offline_mode is True:
            from services.missing_document.llm_gateway import LLMGateway
            class OfflineOllamaClient:
                def is_available(self, force_refresh: bool = False) -> bool:
                    return False
                def chat(self, *args: Any, **kwargs: Any) -> str:
                    raise RuntimeError("Offline mode: LLM calls are disabled.")
            self.underlying_tool = MissingDocumentTool(gateway=LLMGateway(client=OfflineOllamaClient()))
        else:
            self.underlying_tool = MissingDocumentTool()

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        if not state.extracted_data:
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                summary="Cannot detect missing documents: no extracted data available.",
                data={"document_results": []},
                error="No extracted data."
            )

        phase1_payload = {
            "status": "success",
            "total_pages": len(state.extracted_data),
            "extracted_documents": state.extracted_data
        }

        res = self.underlying_tool.run(
            phase1_output=phase1_payload,
            phase2_output=state.validation_result,
            phase3_output=state.validity_result
        )

        state.missing_documents = res
        summary_info = res.get("summary", {})
        total_req = summary_info.get("total_required", 0)
        missing_cnt = summary_info.get("missing", 0)

        missing_list: List[str] = []
        raw_missing = res.get("missing_documents", [])
        for item in raw_missing:
            if isinstance(item, str):
                missing_list.append(item)
            elif isinstance(item, dict) and item.get("missing") is True:
                missing_list.append(item.get("document_title", "Unknown document"))

        if not missing_list:
            for doc in res.get("document_results", []):
                if isinstance(doc, dict) and doc.get("missing") is True:
                    missing_list.append(doc.get("document_title", "Unknown document"))

        if missing_cnt == 0 and not missing_list:
            summary = f"All required documents present ({total_req} requirement(s) satisfied)."
        else:
            missing_names = ", ".join(f"'{m}'" for m in missing_list[:3])
            summary = f"Missing evidence detected ({missing_cnt or len(missing_list)} missing): {missing_names}."

        return ToolExecutionResult(
            tool_name=self.name,
            status="success",
            summary=summary,
            data=res
        )


class ClaimPreparationAdapter(BaseAgentTool):
    """
    Tool 5: claim_preparation
    Synthesizes intermediate observations into the final claim readiness report and status.
    """
    name: str = "claim_preparation"
    description: str = (
        "Synthesizes intermediate observations from validation, validity checking, missing evidence "
        "detection, and cross-document consistency checks into a structured claim readiness package and actionable checklist."
    )
    required_inputs: List[str] = ["validation_result", "validity_result", "missing_documents", "consistency_results"]

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        # If extracted data is present, execute any unexecuted validation services without rerunning extraction
        if state.extracted_data:
            if state.validation_result is None:
                DocumentValidationAdapter().run(state)
            if state.validity_result is None:
                ValidityCheckerAdapter().run(state)
            if state.missing_documents is None:
                MissingDocumentDetectorAdapter().run(state)

        is_valid_dates = state.validity_result.get("valid", False) if state.validity_result else None
        validation_valid = state.validation_result.get("valid", False) if state.validation_result else None

        is_consistent = None
        consistency_discrepancies: List[str] = []
        consistency_severity = "NONE"
        if state.consistency_results:
            is_consistent = state.consistency_results.get("consistent", True)
            consistency_discrepancies = state.consistency_results.get("discrepancies", [])
            consistency_severity = state.consistency_results.get("severity", "NONE")

        missing_docs: List[str] = []
        if state.missing_documents:
            raw_missing = state.missing_documents.get("missing_documents", [])
            for item in raw_missing:
                if isinstance(item, str):
                    missing_docs.append(item)
                elif isinstance(item, dict) and item.get("missing") is True:
                    missing_docs.append(item.get("document_title", "Unknown document"))

            if not missing_docs:
                for doc in state.missing_documents.get("document_results", []):
                    if isinstance(doc, dict) and doc.get("missing") is True:
                        missing_docs.append(doc.get("document_title", "Unknown document"))

        # Determine final status
        action_items: List[str] = []

        has_policy_doc = any(d.get("document_type") == "insurance_policy" for d in state.extracted_data)
        has_medical_doc = any(d.get("document_type") != "insurance_policy" for d in state.extracted_data)

        if state.errors and not state.extracted_data:
            final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
            decision_summary = f"Claim processing stopped: {state.errors[0]}"
            action_items.append(f"Upload required source file: {state.errors[0]}")

        elif not state.extracted_data:
            final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
            decision_summary = "No documents available for claim assessment."
            action_items.append("Please upload policy and medical documents.")

        elif validation_valid is False:
            final_status = ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
            decision_summary = "Submitted documents failed mandatory field validation."
            reasons = []
            if state.validation_result:
                reasons = state.validation_result.get("reasons", []) or state.validation_result.get("summary_reasons", [])
                if not reasons:
                    for d in state.validation_result.get("document_results", []):
                        reasons.extend(d.get("reasons", []))
            if not reasons:
                reasons = ["Ensure all uploaded documents contain valid, legible claim details."]
            action_items.extend(reasons)

        # BLOCKING RULE: Cross-document entity contradictions (competing insurers, unassociated policy numbers, mismatched patients)
        elif is_consistent is False or consistency_severity in ("CRITICAL", "WARNING") or len(consistency_discrepancies) > 0:
            final_status = ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
            decision_summary = "Cross-document integrity check failed: Conflicting insurance entities or policy details detected across submitted documents."
            if consistency_discrepancies:
                for d in consistency_discrepancies:
                    action_items.append(f"Resolve conflicting entity: {d}")
            else:
                action_items.append("Resolve cross-document entity contradictions between submitted files.")

        # Require a valid policy document
        elif not has_policy_doc:
            final_status = ClaimStatus.ACTION_REQUIRED_INVALID_DOCUMENTS.value
            decision_summary = "Insurance policy document required: No verified insurance policy schedule found among uploaded documents."
            action_items.append("Upload a valid insurance policy schedule or certificate of insurance.")

        # If only policy was uploaded and no bills/claim documents are attached
        elif not has_medical_doc:
            final_status = ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
            decision_summary = "Policy verified. Supporting claim evidence required: Please upload hospital discharge summary, medical bills, or diagnostic reports."
            action_items.append("Upload supporting medical bills and clinical records.")

        elif is_valid_dates is False:
            final_status = ClaimStatus.INVALID_CLAIM_DATES.value
            reasons = state.validity_result.get("reasons", []) if state.validity_result else []
            date_reason = reasons[1] if len(reasons) > 1 else (reasons[0] if reasons else "Incident date outside coverage period")
            decision_summary = f"Claim validity check failed: {date_reason}."
            action_items.append(f"Verify incident date against coverage dates: {date_reason}")

        elif missing_docs:
            final_status = ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
            decision_summary = f"Claim requires additional evidence: {', '.join(missing_docs)}."
            for m in missing_docs:
                action_items.append(f"Upload required document: {m}")

        elif validation_valid is None or is_valid_dates is None:
            final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
            decision_summary = "Claim assessment is incomplete: mandatory document validation or validity checks have not been executed."
            action_items.append("Execute complete claim verification before submission.")

        elif (
            validation_valid is True
            and is_valid_dates is True
            and not missing_docs
            and (is_consistent is not False)
            and consistency_severity != "CRITICAL"
            and len(consistency_discrepancies) == 0
            and has_policy_doc
            and has_medical_doc
        ):
            final_status = ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
            decision_summary = "All documents validated, coverage dates verified, entities consistent, and all required evidence present."
            action_items.append("Ready to assemble final claim package and submit to insurer.")

        else:
            final_status = ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
            decision_summary = "Claim requires additional evidence or verification."
            action_items.append("Review submitted documents for completeness.")

        report = {
            "claim_id": state.claim_id,
            "status": final_status,
            "verdict": final_status,
            "is_ready": final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value,
            "decision_summary": decision_summary,
            "total_documents_processed": len(state.extracted_data),
            "validation_status": "PASS" if validation_valid else "FAIL",
            "coverage_validity_status": "PASS" if is_valid_dates else ("FAIL" if is_valid_dates is False else "NOT_CHECKED"),
            "consistency_status": "PASS" if (is_consistent is True) else ("FAIL" if is_consistent is False else "NOT_CHECKED"),
            "consistency_severity": consistency_severity,
            "discrepancies": consistency_discrepancies,
            "missing_documents": missing_docs,
            "action_items": action_items,
            "policy_period": (state.validity_result.get("policy_period", {}) if state.validity_result else {}),
            "validity_check": state.validity_result or {}
        }

        state.final_status = final_status
        state.final_report = report

        return ToolExecutionResult(
            tool_name=self.name,
            status="success",
            summary=f"Claim readiness package synthesized. Status: {final_status}.",
            data=report
        )


ClaimReadinessSynthesizer = ClaimPreparationAdapter



class PolicyClauseSearchAdapter(BaseAgentTool):
    """
    Tool: policy_clause_search
    Wraps PolicyClauseSearchTool.
    Inspects policy clauses, terms, conditions, waiting periods, and exclusions.
    """
    name: str = "policy_clause_search"
    description: str = (
        "Searches extracted policy clauses, conditions, exclusions, waiting periods, "
        "room rent caps, and benefits for specific user queries or insurance topics."
    )
    required_inputs: List[str] = ["query"]

    def __init__(self, tool: Optional[PolicyClauseSearchTool] = None):
        self.underlying_tool = tool or PolicyClauseSearchTool()

    def run(self, state: ClaimState, query: Optional[str] = None, **kwargs: Any) -> ToolExecutionResult:
        search_query = query or kwargs.get("search_query") or state.goal
        res = self.underlying_tool.run(query=search_query, extracted_data=state.extracted_data)
        state.clause_search_results = res
        summary = res.get("summary", "Policy clause search completed.")
        return ToolExecutionResult(
            tool_name=self.name,
            status=res.get("status", "success"),
            summary=summary,
            data=res,
            error=res.get("error")
        )


class CrossDocumentConsistencyAdapter(BaseAgentTool):
    """
    Tool: cross_document_consistency_check
    Wraps CrossDocumentConsistencyTool.
    Cross-checks patient names, hospital facilities, and amounts across all submitted documents.
    """
    name: str = "cross_document_consistency_check"
    description: str = (
        "Cross-checks consistency between submitted documents, comparing patient names, "
        "hospital names, dates, and amounts to detect contradictions or discrepancies."
    )
    required_inputs: List[str] = ["extracted_data"]

    def __init__(self, tool: Optional[CrossDocumentConsistencyTool] = None):
        self.underlying_tool = tool or CrossDocumentConsistencyTool()

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        res = self.underlying_tool.run(extracted_data=state.extracted_data)
        state.consistency_results = res
        summary = res.get("summary", "Cross-document consistency check completed.")
        return ToolExecutionResult(
            tool_name=self.name,
            status=res.get("status", "success"),
            summary=summary,
            data=res
        )


class InsureMateToolRegistry:
    """
    Central tool registry holding the InsureMate Agent tools.
    Provides uniform execution, lookup, alias resolution, and schema exposure
    for dynamic agent orchestration.
    """

    def __init__(
        self,
        extraction_tool: Optional[QwenVLExtractionTool] = None,
        validation_tool: Optional[DocumentValidationTool] = None,
        validity_tool: Optional[ValidityCheckerTool] = None,
        missing_doc_tool: Optional[MissingDocumentTool] = None,
        clause_tool: Optional[PolicyClauseSearchTool] = None,
        consistency_tool: Optional[CrossDocumentConsistencyTool] = None,
        offline_mode: Optional[bool] = None,
        phase6_registry: Optional[Any] = None
    ):
        self.tools: Dict[str, BaseAgentTool] = {
            "document_extraction": DocumentExtractionAdapter(tool=extraction_tool, offline_mode=offline_mode),
            "document_validation": DocumentValidationAdapter(tool=validation_tool),
            "validity_checker": ValidityCheckerAdapter(tool=validity_tool),
            "missing_document_detector": MissingDocumentDetectorAdapter(tool=missing_doc_tool, offline_mode=offline_mode),
            "policy_clause_search": PolicyClauseSearchAdapter(tool=clause_tool),
            "cross_document_consistency_check": CrossDocumentConsistencyAdapter(tool=consistency_tool),
            "claim_preparation": ClaimPreparationAdapter(),
        }

        # Bidirectional aliases
        self.tools["document_extraction_tool"] = self.tools["document_extraction"]
        self.tools["qwen_vl_extraction_tool"] = self.tools["document_extraction"]
        self.tools["document_validation_tool"] = self.tools["document_validation"]
        self.tools["validity_checker_tool"] = self.tools["validity_checker"]
        self.tools["missing_document_tool"] = self.tools["missing_document_detector"]
        self.tools["policy_clause_search_tool"] = self.tools["policy_clause_search"]
        self.tools["clause_search"] = self.tools["policy_clause_search"]
        self.tools["cross_document_consistency_tool"] = self.tools["cross_document_consistency_check"]
        self.tools["consistency_check"] = self.tools["cross_document_consistency_check"]

        self.phase6_registry = phase6_registry

    def register(self, tool: Any, name: Optional[str] = None, alias: Optional[str] = None) -> None:
        """Register custom tool or adapter into registry."""
        tool_name = name or getattr(tool, "name", None)
        if not tool_name:
            raise ValueError(f"Tool {tool} must have a name.")
        self.tools[tool_name] = tool
        if alias:
            self.tools[alias] = tool

    def get_tool(self, tool_name: str) -> Optional[BaseAgentTool]:
        return self.tools.get(tool_name)

    def has(self, tool_name: str) -> bool:
        return tool_name in self.tools

    def get_tool_names(self) -> List[str]:
        return list(self.tools.keys())

    def execute_tool(
        self,
        tool_name: str,
        state: ClaimState,
        authorization_granted: bool = True,
        **kwargs: Any
    ) -> ToolExecutionResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolExecutionResult(
                tool_name=tool_name,
                status="error",
                summary=f"Unknown tool '{tool_name}' requested. Not available in registry.",
                data={},
                error=f"Tool '{tool_name}' not registered."
            )

        # Check authorization
        if getattr(tool, "requires_authorization", False) and not authorization_granted:
            return ToolExecutionResult(
                tool_name=tool_name,
                status="error",
                summary=f"Execution of '{tool_name}' requires explicit user authorization.",
                data={},
                error="Authorization required."
            )

        # Check prerequisites
        prereqs = getattr(tool, "prerequisites", [])
        if "extracted_data" in prereqs and not state.extracted_data and not state.documents:
            return ToolExecutionResult(
                tool_name=tool_name,
                status="error",
                summary=f"Tool '{tool_name}' prerequisite failed: requires extracted document data.",
                data={},
                error="Prerequisite missing: extracted_data."
            )

        try:
            return tool.run(state, **kwargs)
        except Exception as e:
            logger.error(f"Execution error running tool '{tool_name}': {e}")
            return ToolExecutionResult(
                tool_name=tool_name,
                status="error",
                summary=f"Tool '{tool_name}' crashed: {e}",
                data={},
                error=str(e)
            )

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return discovery manifest for unique canonical tools."""
        canonical_keys = [
            "document_extraction",
            "document_validation",
            "validity_checker",
            "missing_document_detector",
            "policy_clause_search",
            "cross_document_consistency_check",
            "claim_preparation"
        ]
        manifests = []
        for k in canonical_keys:
            if k in self.tools:
                t = self.tools[k]
                manifests.append(t.get_manifest() if hasattr(t, "get_manifest") else t.get_schema())
        return manifests

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return schema definitions compatible with LLM function calling."""
        return self.list_tools()

