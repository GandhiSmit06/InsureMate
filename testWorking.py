"""
InsureMate - End-to-End Multi-Phase Pipeline CLI Test Runner (testWorking.py)

Accepts a document path via command-line arguments or interactive input,
executes Phase 1 (Document Ingestion & OCR), Phase 2 (Document Understanding),
and/or Phase 3 (Claim Requirement Extraction & Compliance Verification),
and prints clear, structured outputs for each requested phase.

Usage:
    python testWorking.py <path_to_pdf>
    python testWorking.py <path_to_pdf> --phases 1,2,3
    python testWorking.py <path_to_pdf> --phase 1          # Phase 1 only (Ingestion & OCR)
    python testWorking.py <path_to_pdf> --phase 2          # Phase 2 only (Document Understanding)
    python testWorking.py <path_to_pdf> --phase 3          # Phase 3 only (Policy Requirement Extraction)
    python testWorking.py <claim.pdf> --policy <policy.pdf> # Cross-Phase Claim Compliance Verification

Options:
    --phases, --phase, -ph   Phases to run ('1', '2', '3', '1,2', '1,2,3', 'all') [default: all]
    --policy                 Path to insurance policy document to extract requirements against
    --claim-type             Claim context ('hospitalization', 'cashless', 'reimbursement', 'accident')
    --mode                   Phase 1 mode ('auto', 'digital', 'ocr')
    --device                 OCR device ('auto', 'gpu', 'cpu')
    --full-text              Print entire extracted raw text per page in Phase 1
    --max-pages N            Limit processing to first N pages
    --start-page N           Start processing from page N (1-indexed)
    --json <output.json>     Save full output across all executed phases to a JSON file
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import Set, Optional, Tuple, Dict, Any

# Ensure UTF-8 output on Windows terminals without crashing
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Auto-delegate to .venv if current interpreter lacks paddle and .venv exists
_venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    try:
        import paddle  # type: ignore
    except ImportError:
        import subprocess
        _res = subprocess.run([str(_venv_python)] + sys.argv)
        sys.exit(_res.returncode)

from AI.documentIngestion.documentIngestor import ingest_document
from AI.insuremate_pipeline import (
    _convert_phase1_to_phase2,
    _convert_to_phase3_pages,
    verify_claim_compliance,
)
from AI.document_understanding.pipeline import DocumentUnderstandingPipeline
from AI.requirement_extraction.engine import RequirementExtractionEngine


# -----------------------------------------------------------------------------
# Terminal Formatting Helpers
# -----------------------------------------------------------------------------
def _banner(title: str, width: int = 80, char: str = "=") -> str:
    line = char * width
    return f"\n{line}\n {title}\n{line}"


def _sub_banner(title: str, width: int = 70, char: str = "-") -> str:
    return f"\n{char * 3} {title} {char * max(0, width - len(title) - 5)}"


def _format_entity_field(name: str, field_obj, indent: int = 2) -> str:
    """Format an entity FieldValue with status, value, and provenance."""
    prefix = " " * indent
    if field_obj is None:
        return f"{prefix}{name:<25}: [not_found]"

    status = getattr(field_obj, "status", None)
    status_str = status.value if hasattr(status, "value") else str(status or "not_found")
    val = getattr(field_obj, "value", None)
    raw = getattr(field_obj, "raw_text", None)
    prov = getattr(field_obj, "provenance", None)

    if status_str == "extracted" and val is not None:
        out = f"{prefix}{name:<25}: {val}"
        if raw and str(raw).strip() != str(val).strip():
            out += f"  (raw: '{raw}')"
        if prov:
            out += f"  [Pg {prov.page_number} via {prov.extraction_method}]"
        return out
    elif status_str == "extracted":
        return f"{prefix}{name:<25}: {raw or 'N/A'}  [{status_str}]"
    else:
        return f"{prefix}{name:<25}: [{status_str}]"


def _parse_phases(phase_str: str) -> Set[int]:
    """Parse phase selection string into a set of phase numbers (1, 2, 3)."""
    if not phase_str:
        return {1, 2, 3}
    cleaned = str(phase_str).strip().lower()
    if cleaned in ("all", "1,2,3", "123", "*", "full"):
        return {1, 2, 3}

    selected = set()
    tokens = re.split(r"[,+\s/]+", cleaned)
    for tok in tokens:
        if tok in ("1", "phase1", "p1"):
            selected.add(1)
        elif tok in ("2", "phase2", "p2"):
            selected.add(2)
        elif tok in ("3", "phase3", "p3"):
            selected.add(3)
        elif tok in ("all", "*"):
            return {1, 2, 3}

    return selected or {1, 2, 3}


# -----------------------------------------------------------------------------
# Phase 1 Printer: Ingestion & OCR
# -----------------------------------------------------------------------------
def display_phase1_output(phase1_result: dict, show_full_text: bool = False):
    """Prints a clear, structured breakdown of Phase 1 extraction results."""
    print(_banner("PHASE 1: DOCUMENT INGESTION & OCR EXTRACTION"))

    summary = phase1_result.get("summary", {})
    file_name = phase1_result.get("file_name", "Unknown")
    file_size_kb = phase1_result.get("file_size_kb", 0)
    total_pages = phase1_result.get("total_pages", len(phase1_result.get("pages", [])))
    digital_pages = summary.get("digital_pages", 0)
    ocr_pages = summary.get("ocr_pages", 0)
    full_text = summary.get("full_text", "")
    total_words = len(full_text.split())

    print("\n--- Ingestion Summary ---")
    print(f"  File Name             : {file_name}")
    print(f"  File Size             : {file_size_kb:.2f} KB")
    print(f"  Total Pages           : {total_pages}")
    print(f"  Digital Pages         : {digital_pages} (softcopy text)")
    print(f"  OCR Pages             : {ocr_pages} (PaddleOCR GPU)")
    print(f"  Total Extracted Words : {total_words:,}")
    print(f"  Total Characters      : {len(full_text):,}")

    print("\n--- Per-Page Extracted Data ---")
    for page in phase1_result.get("pages", []):
        p_num = page.get("page_number", 1)
        method = page.get("method", "unknown").upper()
        engine = f" - Engine: {page['ocr_engine'].upper()}" if page.get("ocr_engine") else ""
        quality = page.get("quality_score")
        q_str = f" | Quality: {quality*100:.1f}%" if quality is not None else ""
        conf = page.get("confidence")
        conf_str = f" | Conf: {conf*100:.1f}%" if conf is not None else ""
        words = page.get("word_count", 0)
        dims = f"{page.get('width', '?')} x {page.get('height', '?')} pt"

        print(f"\n  [Page {p_num}] Method: {method}{engine}{q_str}{conf_str} | Words: {words} | Size: {dims}")
        page_text = page.get("text", "").strip()

        if not page_text:
            print("    [No text extracted on this page]")
            continue

        if show_full_text or len(page_text) <= 500:
            lines = page_text.splitlines()
            for line in lines:
                print(f"    | {line}")
        else:
            lines = page_text.splitlines()
            preview_lines = lines[:10]
            for line in preview_lines:
                print(f"    | {line}")
            omitted = len(lines) - 10
            if omitted > 0:
                print(f"    | ... [{omitted} lines omitted. Pass --full-text to see all] ...")


# -----------------------------------------------------------------------------
# Phase 2 Printer: Document Understanding & Structuring
# -----------------------------------------------------------------------------
def display_phase2_output(result):
    """Prints a clear, structured breakdown of Phase 2 understanding results."""
    print(_banner("PHASE 2: DOCUMENT UNDERSTANDING & ENTITY EXTRACTION"))

    # 1. Processing Status & Classification
    print("\n--- 1. Document Status & Classification ---")
    print(f"  Document ID       : {result.document_id}")
    print(f"  Pipeline Status   : {result.status.upper()}")
    print(f"  Source Type       : {result.document_metadata.source_type}")
    print(f"  Overall Quality   : {result.quality.overall_quality.upper()}")

    if result.document_type_hints:
        top_hint = result.document_type_hints[0]
        score_pct = top_hint.confidence_score * 100
        print(f"  Detected Doc Type : {top_hint.candidate_type} (Confidence: {top_hint.confidence.value}, Score: {score_pct:.1f}%)")
        if top_hint.supporting_signals:
            print(f"  Signals           : {', '.join(top_hint.supporting_signals[:3])}")
    else:
        print("  Detected Doc Type : Unknown / Unclassified")

    # 2. Key Medical & Insurance Entities
    entities = result.entities
    print("\n--- 2. Extracted Entities ---")

    print("  [Patient Information]")
    print(_format_entity_field("Patient Name", getattr(entities.patient, "name", None), indent=4))
    print(_format_entity_field("Age", getattr(entities.patient, "age", None), indent=4))
    print(_format_entity_field("Gender", getattr(entities.patient, "gender", None), indent=4))
    print(_format_entity_field("Patient ID / UHID", getattr(entities.patient, "patient_id", None), indent=4))

    print("\n  [Hospital & Medical Provider]")
    print(_format_entity_field("Hospital Name", getattr(entities.hospital, "name", None), indent=4))
    print(_format_entity_field("Attending Doctor", getattr(entities.hospital, "doctor_name", None), indent=4))
    print(_format_entity_field("Doctor Reg No", getattr(entities.hospital, "registration_number", None), indent=4))
    print(_format_entity_field("Hospital Address", getattr(entities.hospital, "address", None), indent=4))

    print("\n  [Clinical Encounter]")
    print(_format_entity_field("Admission Date", getattr(entities.encounter, "admission_date", None), indent=4))
    print(_format_entity_field("Discharge Date", getattr(entities.encounter, "discharge_date", None), indent=4))
    print(_format_entity_field("Diagnosis", getattr(entities.encounter, "diagnosis_text", None), indent=4))
    print(_format_entity_field("Treatment Given", getattr(entities.encounter, "procedure_text", None), indent=4))

    print("\n  [Financial & Billing]")
    print(_format_entity_field("Invoice Number", getattr(entities.financial, "invoice_number", None), indent=4))
    print(_format_entity_field("Total Stated Amount", getattr(entities.financial, "total_amount", None), indent=4))
    print(_format_entity_field("Currency", getattr(entities.financial, "currency", None), indent=4))

    if entities.financial.itemized_charges:
        print(f"\n  [Itemized Charges Breakdown ({len(entities.financial.itemized_charges)} items)]")
        for i, chg in enumerate(entities.financial.itemized_charges[:10], 1):
            qty = f" x{chg.quantity}" if chg.quantity else ""
            print(f"    {i:>2}. {chg.description:<35} : {chg.amount}{qty}")
        if len(entities.financial.itemized_charges) > 10:
            print(f"    ... and {len(entities.financial.itemized_charges) - 10} more itemized line items")

    # 3. Semantic Document Sections
    print("\n--- 3. Detected Document Sections ---")
    if result.sections:
        for sec in result.sections:
            prev = sec.content.strip().replace("\n", " ")
            if len(prev) > 80:
                prev = prev[:77] + "..."
            print(f"  [Page {sec.page_number}] {sec.heading} ({sec.normalized_heading}) -> '{prev}'")
    else:
        print("  No major formal section headers detected.")

    # 4. Tables Extracted
    print("\n--- 4. Extracted Tables ---")
    if result.tables:
        print(f"  Total Tables Found: {len(result.tables)}")
        for t_idx, tbl in enumerate(result.tables, 1):
            col_names = [col.name for col in tbl.columns]
            print(f"  Table #{t_idx} (Page {tbl.page_number}): {len(tbl.rows)} rows x {len(tbl.columns)} columns")
            print(f"    Columns: {', '.join(col_names[:6])}{'...' if len(col_names) > 6 else ''}")
    else:
        print("  No structured tables detected.")

    # 5. Quality Evaluation & Consistency Checks
    print("\n--- 5. Document Quality & Consistency Checks ---")
    print(f"  Quality Rating           : {result.quality.overall_quality.upper()}")
    print(f"  Conflicting Dates Flag   : {'YES (ERROR)' if result.quality.has_conflicting_dates else 'NO (Consistent)'}")

    recon = result.quality.arithmetic_reconciliation
    if recon and recon.checked:
        match_symbol = "MATCHES" if recon.matches else "MISMATCH"
        print(f"  Arithmetic Reconciliation: [{match_symbol}]")
        print(f"    - Itemized Charges Sum : {recon.itemized_sum}")
        print(f"    - Stated Total Amount  : {recon.stated_total}")
        if not recon.matches:
            print(f"    - Discrepancy Amount   : {recon.discrepancy}")
    else:
        print("  Arithmetic Reconciliation: Not applicable")

    if result.issues:
        print(f"\n  Detected Issues & Quality Flags ({len(result.issues)}):")
        for iss in result.issues:
            sev = iss.severity.upper()
            page_info = f" [Page {iss.page_number}]" if iss.page_number else ""
            print(f"    [{sev}]{page_info} {iss.code}: {iss.description}")

    # 6. Provenance Traceability
    prov_count = 0
    all_fields = [
        getattr(entities.patient, "name", None),
        getattr(entities.patient, "age", None),
        getattr(entities.patient, "gender", None),
        getattr(entities.patient, "patient_id", None),
        getattr(entities.hospital, "name", None),
        getattr(entities.hospital, "doctor_name", None),
        getattr(entities.hospital, "registration_number", None),
        getattr(entities.hospital, "address", None),
        getattr(entities.encounter, "admission_date", None),
        getattr(entities.encounter, "discharge_date", None),
        getattr(entities.encounter, "diagnosis_text", None),
        getattr(entities.financial, "invoice_number", None),
        getattr(entities.financial, "total_amount", None),
    ]
    for f in all_fields:
        if f is not None and getattr(f, "provenance", None) is not None:
            prov_count += 1

    print("\n--- 6. Provenance & Evidence Traceability ---")
    print(f"  Verified Provenance-Tracked Entities : {prov_count} field(s) with verbatim page traceability")


# -----------------------------------------------------------------------------
# Phase 3 Printer: Requirement Extraction & Compliance Checklist
# -----------------------------------------------------------------------------
def display_phase3_output(phase3_result, compliance_eval: dict = None):
    """Prints a clear, structured breakdown of Phase 3 requirements & compliance results."""
    print(_banner("PHASE 3: CLAIM REQUIREMENT EXTRACTION & COMPLIANCE"))

    if not phase3_result or not phase3_result.success:
        err = getattr(phase3_result, "error", "No policy requirements extracted.")
        print(f"\n  [Phase 3 Status]: {err}")
        return

    summary = phase3_result.summary
    total = len(phase3_result.requirements)
    mand_count = summary.mandatory_count if summary else sum(1 for r in phase3_result.requirements if r.mandatory)
    cond_count = summary.conditional_count if summary else sum(1 for r in phase3_result.requirements if not r.mandatory)

    print("\n--- 1. Policy Extraction Summary ---")
    print(f"  Claim Context     : {(phase3_result.claim_type or 'general').upper()}")
    if phase3_result.policy_name:
        print(f"  Policy Name       : {phase3_result.policy_name}")
    print(f"  Total Requirements: {total}")
    print(f"  Mandatory Items   : {mand_count}")
    print(f"  Conditional Items : {cond_count}")

    if summary and summary.categories:
        cat_str = ", ".join(f"{k}: {v}" for k, v in summary.categories.items())
        print(f"  Categories        : {cat_str}")

    # 2. Extracted Requirements Table
    print("\n--- 2. Extracted Policy Requirements ---")
    if not phase3_result.requirements:
        print("  No requirements detected in document.")
    for req in phase3_result.requirements:
        mand_str = "MANDATORY" if req.mandatory else "CONDITIONAL"
        print(f"\n  [{req.requirement_id}] [{req.category.value}] [{req.priority.value}] [{mand_str}]")
        print(f"    Name         : {req.name}")
        print(f"    Description  : {req.description}")
        if req.deadline:
            print(f"    Deadline     : {req.deadline}")
        if req.condition:
            print(f"    Condition    : {req.condition}")
        if req.required_information:
            print(f"    Required Info: {', '.join(req.required_information)}")
        if req.source_clause:
            print(f"    Clause       : {req.source_clause}")
        if req.source_page:
            print(f"    Source Page  : Page {req.source_page}")

    # 3. Compliance & Adjudication Evaluation (if available)
    if compliance_eval:
        print(_sub_banner("Claim Compliance & Adjudication Checklist"))
        score = compliance_eval.get("compliance_score_pct", 0)
        f_cnt = compliance_eval.get("fulfilled_count", 0)
        m_cnt = compliance_eval.get("missing_mandatory", 0)
        c_cnt = compliance_eval.get("conditional_count", 0)

        print(f"\n  Overall Compliance Score : {score}%")
        print(f"  Fulfilled Requirements   : {f_cnt}")
        print(f"  Missing Mandatory Items  : {m_cnt}")
        print(f"  Conditional Items Pending: {c_cnt}\n")

        checklist = compliance_eval.get("checklist", [])
        for item in checklist:
            st = item["status"]
            if st == "FULFILLED":
                badge = "[PASSED]"
            elif st == "CONDITIONAL":
                badge = "[CONDITIONAL]"
            else:
                badge = "[MISSING]" if item["mandatory"] else "[OPTIONAL]"

            print(f"  {badge:<15} {item['requirement_id']} ({item['category']}) - {item['name']}")
            if item.get("evidence"):
                print(f"                  Evidence: {item['evidence']}")
            if item.get("deadline"):
                print(f"                  Deadline: {item['deadline']}")


# -----------------------------------------------------------------------------
# Main Multi-Phase Orchestrator
# -----------------------------------------------------------------------------
def run_pipeline(
    file_path: str,
    phases: Set[int] = {1, 2, 3},
    mode: str = "auto",
    max_pages: int | None = None,
    start_page: int = 1,
    show_full_text: bool = False,
    output_json_path: str | None = None,
    device: str = "auto",
    policy_file: str | None = None,
    claim_type: str = "hospitalization",
):
    """
    Executes specified phases (1, 2, and/or 3), displaying clear, structured output for each phase.
    """
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        print(f"\n[ERROR] File not found: '{file_path}'")
        print("Please check the path and try again.")
        sys.exit(1)

    # Resolve OCR target device
    ocr_device = None
    if device == "gpu":
        ocr_device = "gpu:0"
    elif device == "cpu":
        ocr_device = "cpu"

    phase_desc = ", ".join(f"Phase {p}" for p in sorted(phases))
    print(_banner(f"INSUREMATE PIPELINE [{phase_desc}]: {os.path.basename(file_path)}"))
    print(f" Target File : {file_path}")
    if policy_file:
        print(f" Policy File : {policy_file}")
    print(f" Config      : phases={sorted(phases)}, mode='{mode}', device='{device}', claim_type='{claim_type}'")

    phase1_result = None
    phase2_result = None
    phase3_result = None
    compliance_eval = None

    # -------------------------------------------------------------------------
    # Phase 1: Ingestion & OCR
    # (Runs if Phase 1 or Phase 2 is requested, or if Phase 3 runs on primary file)
    # -------------------------------------------------------------------------
    needs_phase1 = (1 in phases) or (2 in phases)

    if needs_phase1:
        if 1 in phases:
            print("\n[Running Phase 1: Ingesting document via PaddleOCR / PyMuPDF...]")
        else:
            print("\n[Phase 1: Ingesting document in background for Phase 2...]")

        phase1_result = ingest_document(
            file_path=file_path,
            mode=mode,
            max_pages=max_pages,
            start_page=start_page,
            verbose=False,
            device=ocr_device,
        )

        if not phase1_result.get("success", False):
            print(f"\n[ERROR] Phase 1 Ingestion Failed: {phase1_result.get('error')}")
            sys.exit(1)

        if 1 in phases:
            display_phase1_output(phase1_result, show_full_text=show_full_text)

    # -------------------------------------------------------------------------
    # Phase 2: Document Understanding & Entity Extraction
    # -------------------------------------------------------------------------
    if 2 in phases:
        print("\n[Running Phase 2: Document Understanding & Structuring...]")
        ingested_doc = _convert_phase1_to_phase2(phase1_result, file_path)
        pipeline = DocumentUnderstandingPipeline()
        phase2_result = pipeline.process(ingested_doc)

        display_phase2_output(phase2_result)

    # -------------------------------------------------------------------------
    # Phase 3: Claim Requirement Extraction & Adjudication Checklist
    # -------------------------------------------------------------------------
    if 3 in phases:
        print("\n[Running Phase 3: Requirement Extraction & Policy Analysis...]")
        engine = RequirementExtractionEngine()

        if policy_file and os.path.exists(policy_file):
            # Extract requirements from explicitly supplied policy document
            phase3_result = engine.process(file_path=policy_file, claim_type=claim_type)
        elif phase1_result and phase1_result.get("pages"):
            # Use already extracted pages from Phase 1 without re-reading PDF
            p3_pages = _convert_to_phase3_pages(phase1_result["pages"])
            phase3_result = engine.process(pages=p3_pages, claim_type=claim_type)
        else:
            # Standalone Phase 3 run directly on target PDF
            phase3_result = engine.process(file_path=file_path, claim_type=claim_type)

        # Cross-Phase Compliance Verification (if Phase 2 understanding is available)
        if phase2_result and phase3_result and phase3_result.success and phase3_result.requirements:
            compliance_eval = verify_claim_compliance(phase2_result, phase3_result)

        display_phase3_output(phase3_result, compliance_eval)

    # -------------------------------------------------------------------------
    # JSON Export (across all executed phases)
    # -------------------------------------------------------------------------
    if output_json_path:
        out_path = os.path.abspath(output_json_path)
        combined_data = {}
        if phase1_result:
            combined_data["phase1_ingestion"] = phase1_result
        if phase2_result:
            combined_data["phase2_understanding"] = phase2_result.model_dump()
        if phase3_result:
            combined_data["phase3_requirements"] = phase3_result.model_dump()
        if compliance_eval:
            combined_data["compliance_evaluation"] = compliance_eval

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        print(f"\n[Export] Full multi-phase JSON exported to: {out_path}")

    print("\n" + "=" * 80)
    print(f" PIPELINE COMPLETE: Executed {phase_desc} successfully.")
    print("=" * 80 + "\n")

    return phase1_result, phase2_result, phase3_result


# -----------------------------------------------------------------------------
# Main CLI Entrypoint
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="InsureMate Multi-Phase Pipeline CLI (Phase 1, 2, and 3)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        default=None,
        help="Path to the primary document to process (claim PDF or policy PDF).",
    )
    parser.add_argument(
        "-f", "--file",
        dest="flag_file",
        default=None,
        help="Alternative flag to specify input PDF path.",
    )
    parser.add_argument(
        "--phases", "--phase", "-ph",
        dest="phases",
        default="all",
        help="Phases to execute (default: 'all' or '1,2,3'):\n"
             "  1        : Phase 1 only (Document Ingestion & PaddleOCR)\n"
             "  2        : Phase 2 only (Document Understanding & Structuring)\n"
             "  3        : Phase 3 only (Policy Requirement Extraction)\n"
             "  1,2      : Phase 1 and Phase 2\n"
             "  1,2,3    : All three phases end-to-end\n"
             "  all      : All three phases (default)",
    )
    parser.add_argument(
        "--policy",
        dest="policy_file",
        default=None,
        help="Path to insurance policy document to extract requirements and evaluate compliance against.",
    )
    parser.add_argument(
        "--claim-type",
        dest="claim_type",
        default="hospitalization",
        choices=["hospitalization", "cashless", "reimbursement", "accident"],
        help="Claim context for requirement extraction (default: hospitalization).",
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["auto", "digital", "ocr"],
        default="auto",
        help="Extraction mode:\n  auto    : Smart hybrid (digital softcopy text if available, else PaddleOCR)\n  digital : Fast softcopy extraction only\n  ocr     : Force PaddleOCR on all pages",
    )
    parser.add_argument(
        "-p", "--max-pages",
        type=int,
        default=None,
        help="Limit number of pages to process (default: all pages).",
    )
    parser.add_argument(
        "-s", "--start-page",
        type=int,
        default=1,
        help="1-indexed starting page (default: 1).",
    )
    parser.add_argument(
        "--full-text",
        action="store_true",
        help="Print entire raw text of each page instead of truncated preview in Phase 1.",
    )
    parser.add_argument(
        "-d", "--device",
        choices=["auto", "gpu", "cpu"],
        default="auto",
        help="Compute device for OCR (default: auto, utilizes NVIDIA GPU if available).",
    )
    parser.add_argument(
        "-o", "--json",
        dest="output_json",
        default=None,
        help="Save combined output across all executed phases to a JSON file.",
    )

    args = parser.parse_args()

    # Determine input path
    target_path = args.file_path or args.flag_file
    selected_phases = _parse_phases(args.phases)
    target_policy = args.policy_file

    # Interactive prompt if no path provided via command line
    if not target_path:
        print("=" * 80)
        print(" InsureMate — Multi-Phase Pipeline CLI")
        print("=" * 80)
        default_sample = "sample_test_invoice.pdf"
        sample_hint = f" (Press Enter to use '{default_sample}')" if os.path.exists(default_sample) else ""
        try:
            user_input = input(f"Enter path to PDF document{sample_hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            sys.exit(0)

        if not user_input:
            if os.path.exists(default_sample):
                target_path = default_sample
            else:
                parser.print_help()
                sys.exit(1)
        else:
            target_path = user_input.strip("\"'")

        # Interactive phase selection
        print("\nSelect Phase(s) to execute:")
        print("  [1] Phase 1 only (Document Ingestion & PaddleOCR)")
        print("  [2] Phase 2 only (Document Understanding & Entity Extraction)")
        print("  [3] Phase 3 only (Policy Requirement Extraction)")
        print("  [4] Phase 1 & 2  (Ingestion + Understanding)")
        print("  [5] All Phases 1, 2, and 3 (Full End-to-End Pipeline) [Default]")
        try:
            choice = input("Enter choice [1-5, or comma-separated e.g. 1,2,3] (default: 5): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "5"

        if choice == "1":
            selected_phases = {1}
        elif choice == "2":
            selected_phases = {2}
        elif choice == "3":
            selected_phases = {3}
        elif choice == "4":
            selected_phases = {1, 2}
        elif choice in ("5", ""):
            selected_phases = {1, 2, 3}
        else:
            selected_phases = _parse_phases(choice)

        # Optional policy prompt if Phase 3 is active
        if 3 in selected_phases:
            try:
                pol_in = input("Optional Policy PDF path (press Enter to extract from primary file): ").strip()
                if pol_in:
                    target_policy = pol_in.strip("\"'")
            except (EOFError, KeyboardInterrupt):
                pass

    run_pipeline(
        file_path=target_path,
        phases=selected_phases,
        mode=args.mode,
        max_pages=args.max_pages,
        start_page=args.start_page,
        show_full_text=args.full_text,
        output_json_path=args.output_json,
        device=args.device,
        policy_file=target_policy,
        claim_type=args.claim_type,
    )


if __name__ == "__main__":
    main()
