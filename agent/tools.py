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
    """Base class for Agent Tools with schema and error handling."""
    name: str = ""
    description: str = ""
    required_inputs: List[str] = []

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        raise NotImplementedError

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_inputs": self.required_inputs
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
        "using the existing Qwen-VL vision understanding tool, preserving 1-indexed page numbers."
    )
    required_inputs: List[str] = ["documents"]

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
            res = self.underlying_tool.run(path_obj, max_pages=max_pages)
            if res.get("status") == "success":
                all_pages.extend(res.get("extracted_documents", []))
            else:
                err = res.get("error") or f"Extraction failed for {path_obj.name}"
                errors.append(err)

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

        res = self.underlying_tool.run(extracted_documents=state.extracted_data)
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

    def __init__(self, tool: Optional[MissingDocumentTool] = None):
        self.underlying_tool = tool or MissingDocumentTool()

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
        "Synthesizes intermediate observations from validation, validity checking, and missing evidence "
        "detection into a structured claim readiness package and actionable checklist."
    )
    required_inputs: List[str] = ["validation_result", "validity_result", "missing_documents"]

    def run(self, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        is_valid_dates = state.validity_result.get("valid", False) if state.validity_result else None
        validation_valid = state.validation_result.get("valid", False) if state.validation_result else None

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

        if state.errors and not state.extracted_data:
            final_status = ClaimStatus.INSUFFICIENT_INFORMATION.value
            decision_summary = "Claim processing stopped due to unreadable or missing document files."
            action_items.append("Please upload legible PDF documents.")

        elif validation_valid is False and (not state.validity_result or state.validation_result.get("valid_documents", 0) == 0):
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

        # If only policy was uploaded and no bills/claim documents are attached,
        # the primary requirement is submitting the missing evidence, not date failure.
        elif not any(d.get("document_type") not in ("insurance_policy", "unknown") for d in state.extracted_data) and missing_docs:
            final_status = ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
            decision_summary = f"Policy verified. Supporting claim evidence required: {', '.join(missing_docs)}."
            for m in missing_docs:
                action_items.append(f"Upload required document: {m}")

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

        elif validation_valid is True and is_valid_dates is True and not missing_docs:
            final_status = ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value
            decision_summary = "All documents validated, coverage dates verified, and all required evidence present."
            action_items.append("Ready to assemble final claim package and submit to insurer.")

        else:
            final_status = ClaimStatus.ACTION_REQUIRED_MISSING_EVIDENCE.value
            decision_summary = "Claim requires additional evidence or verification."
            action_items.append("Review submitted documents for completeness.")

        report = {
            "claim_id": state.claim_id,
            "status": final_status,
            "is_ready": final_status == ClaimStatus.CLAIM_READY_FOR_SUBMISSION.value,
            "decision_summary": decision_summary,
            "total_documents_processed": len(state.extracted_data),
            "validation_status": "PASS" if validation_valid else "FAIL",
            "coverage_validity_status": "PASS" if is_valid_dates else ("FAIL" if is_valid_dates is False else "NOT_CHECKED"),
            "missing_documents": missing_docs,
            "action_items": action_items
        }

        state.final_status = final_status
        state.final_report = report

        return ToolExecutionResult(
            tool_name=self.name,
            status="success",
            summary=f"Claim readiness package synthesized. Status: {final_status}.",
            data=report
        )


class InsureMateToolRegistry:
    """
    Central tool registry holding the InsureMate Agent tools.
    Provides uniform execution, lookup, alias resolution, and schema exposure
    for both Phase 5 and Phase 6 workflows.
    """

    def __init__(
        self,
        extraction_tool: Optional[QwenVLExtractionTool] = None,
        validation_tool: Optional[DocumentValidationTool] = None,
        validity_tool: Optional[ValidityCheckerTool] = None,
        missing_doc_tool: Optional[MissingDocumentTool] = None,
        offline_mode: Optional[bool] = None,
        phase6_registry: Optional[Any] = None
    ):
        self.tools: Dict[str, BaseAgentTool] = {
            "document_extraction": DocumentExtractionAdapter(tool=extraction_tool, offline_mode=offline_mode),
            "document_validation": DocumentValidationAdapter(tool=validation_tool),
            "validity_checker": ValidityCheckerAdapter(tool=validity_tool),
            "missing_document_detector": MissingDocumentDetectorAdapter(tool=missing_doc_tool),
            "claim_preparation": ClaimPreparationAdapter(),
        }

        # Bidirectional aliases between Phase 5 and Phase 6
        self.tools["document_extraction_tool"] = self.tools["document_extraction"]
        self.tools["qwen_vl_extraction_tool"] = self.tools["document_extraction"]
        self.tools["document_validation_tool"] = self.tools["document_validation"]
        self.tools["validity_checker_tool"] = self.tools["validity_checker"]
        self.tools["missing_document_tool"] = self.tools["missing_document_detector"]

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

    def execute_tool(self, tool_name: str, state: ClaimState, **kwargs: Any) -> ToolExecutionResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolExecutionResult(
                tool_name=tool_name,
                status="error",
                summary=f"Unknown tool '{tool_name}' requested by agent.",
                data={},
                error=f"Tool '{tool_name}' not registered."
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
        """Return discovery list for unique canonical tools."""
        canonical_keys = [
            "document_extraction",
            "document_validation",
            "validity_checker",
            "missing_document_detector",
            "claim_preparation"
        ]
        return [self.tools[k].get_schema() for k in canonical_keys if k in self.tools]

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return schema definitions compatible with LLM function calling."""
        return self.list_tools()

