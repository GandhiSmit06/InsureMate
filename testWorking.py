"""
InsureMate - End-to-End Pipeline CLI Test Runner (testWorking.py)

Accepts a document path via command-line arguments or interactive input,
executes Phase 1 (Document Ingestion & OCR) and Phase 2 (Document Understanding),
and prints clear, structured outputs of both phases.

Usage:
    python testWorking.py <path_to_pdf>
    python testWorking.py --file <path_to_pdf> [--mode auto|digital|ocr] [--max-pages N] [--full-text] [--json output.json]

Examples:
    python testWorking.py sample_test_invoice.pdf
    python testWorking.py "D:/claims/hospital_bill.pdf" --mode auto
    python testWorking.py scanned_receipt.pdf --mode ocr --full-text
"""

import os
import sys
import json
import argparse
from pathlib import Path

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

from AI.documentIngestion.documentIngestor import ingest_document
from AI.insuremate_pipeline import _convert_phase1_to_phase2
from AI.document_understanding.pipeline import DocumentUnderstandingPipeline


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


# -----------------------------------------------------------------------------
# Phase 1 Printer
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
    print(f"  File Name         : {file_name}")
    print(f"  File Size         : {file_size_kb:.2f} KB")
    print(f"  Total Pages       : {total_pages}")
    print(f"  Digital Pages     : {digital_pages} (softcopy text)")
    print(f"  OCR Pages         : {ocr_pages} (PaddleOCR)")
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
            # Show top lines and bottom snippet
            lines = page_text.splitlines()
            preview_lines = lines[:10]
            for line in preview_lines:
                print(f"    | {line}")
            omitted = len(lines) - 10
            if omitted > 0:
                print(f"    | ... [{omitted} lines omitted. Pass --full-text to see all] ...")


# -----------------------------------------------------------------------------
# Phase 2 Printer
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
        conf_val = top_hint.confidence.value if hasattr(top_hint.confidence, "value") else top_hint.confidence
        print(f"  Primary Doc Type  : {top_hint.candidate_type} (Confidence: {conf_val.upper()}, Score: {top_hint.confidence_score:.2f})")
        if top_hint.supporting_signals:
            print(f"  Detected Signals  : {', '.join(top_hint.supporting_signals)}")

        if len(result.document_type_hints) > 1:
            other_hints = [
                f"{h.candidate_type} ({h.confidence_score:.2f})"
                for h in result.document_type_hints[1:4]
            ]
            print(f"  Other Candidates  : {', '.join(other_hints)}")
    else:
        print("  Primary Doc Type  : unknown")

    # 2. Detected Semantic Sections
    if result.sections:
        print(f"\n--- 2. Detected Sections ({len(result.sections)}) ---")
        for sec in result.sections:
            content_preview = sec.content.strip().replace("\n", " ")
            if len(content_preview) > 70:
                content_preview = content_preview[:67] + "..."
            print(f"  - [{sec.heading}] (Page {sec.page_number}): \"{content_preview}\"")
    else:
        print("\n--- 2. Detected Sections ---")
        print("  No explicit titled sections detected.")

    # 3. Categorized Medical & Financial Entities
    entities = result.entities
    print("\n--- 3. Extracted Structured Entities ---")

    print("\n  [Patient Information]")
    print(_format_entity_field("Patient Name", entities.patient.name, indent=4))
    print(_format_entity_field("Age", entities.patient.age, indent=4))
    print(_format_entity_field("Gender", entities.patient.gender, indent=4))
    print(_format_entity_field("Patient / UHID ID", entities.patient.patient_id, indent=4))

    print("\n  [Hospital & Healthcare Provider]")
    print(_format_entity_field("Hospital Name", entities.hospital.name, indent=4))
    print(_format_entity_field("Doctor / Surgeon", entities.hospital.doctor_name, indent=4))
    print(_format_entity_field("Department", entities.hospital.department, indent=4))
    print(_format_entity_field("Hospital Address", entities.hospital.address, indent=4))
    print(_format_entity_field("Registration No", entities.hospital.registration_number, indent=4))

    print("\n  [Encounter & Clinical Timeline]")
    print(_format_entity_field("Admission Date", entities.encounter.admission_date, indent=4))
    print(_format_entity_field("Discharge Date", entities.encounter.discharge_date, indent=4))
    print(_format_entity_field("Procedure Date", entities.encounter.procedure_date, indent=4))
    print(_format_entity_field("Visit / Consult Date", entities.encounter.visit_date, indent=4))
    print(_format_entity_field("Documented Diagnosis", entities.encounter.diagnosis_text, indent=4))
    print(_format_entity_field("Documented Procedure", entities.encounter.procedure_text, indent=4))

    print("\n  [Financial & Billing Details]")
    print(_format_entity_field("Invoice Number", entities.financial.invoice_number, indent=4))
    print(_format_entity_field("Bill Date", entities.financial.bill_date, indent=4))
    print(_format_entity_field("Currency", entities.financial.currency, indent=4))
    print(_format_entity_field("Total Stated Bill", entities.financial.total_amount, indent=4))
    print(_format_entity_field("Amount Paid", entities.financial.paid_amount, indent=4))
    print(_format_entity_field("Balance Payable", entities.financial.balance_amount, indent=4))

    # 4. Itemized Charges
    charges = entities.financial.itemized_charges
    if charges:
        print(f"\n--- 4. Itemized Charges Table ({len(charges)} items) ---")
        header = f"  {'#':<3} | {'Description':<40} | {'Qty':<5} | {'Rate':<10} | {'Amount':<12}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for idx, ch in enumerate(charges, 1):
            desc = ch.description[:38] + ".." if len(ch.description) > 40 else ch.description
            qty_str = f"{ch.quantity:.0f}" if ch.quantity is not None else "-"
            rate_str = f"{ch.unit_price:.2f}" if ch.unit_price is not None else "-"
            amt_str = f"{ch.amount:.2f}" if ch.amount is not None else "-"
            print(f"  {idx:<3} | {desc:<40} | {qty_str:<5} | {rate_str:<10} | {amt_str:<12}")
    else:
        print("\n--- 4. Itemized Charges ---")
        print("  No itemized line items extracted.")

    # 5. Quality, Integrity & Reconciliation
    quality = result.quality
    recon = quality.arithmetic_reconciliation
    print("\n--- 5. Quality, Validation & Arithmetic Reconciliation ---")
    print(f"  Overall Quality Rating : {quality.overall_quality.upper()}")
    print(f"  Unreadable Char Ratio  : {quality.unreadable_char_ratio:.2%}")
    if quality.ocr_confidence_avg is not None:
        print(f"  Average OCR Confidence : {quality.ocr_confidence_avg:.1f}%")
    print(f"  Conflicting Dates Flag : {'YES (Warning)' if quality.has_conflicting_dates else 'No conflicts'}")

    if recon and recon.checked:
        match_symbol = "MATCHES" if recon.matches else "MISMATCH"
        print(f"  Arithmetic Reconciliation: [{match_symbol}]")
        print(f"    - Itemized Charges Sum : {recon.itemized_sum}")
        print(f"    - Stated Total Amount  : {recon.stated_total}")
        if not recon.matches:
            print(f"    - Discrepancy Amount   : {recon.discrepancy}")
        if recon.notes:
            print(f"    - Notes                : {recon.notes}")
    else:
        print("  Arithmetic Reconciliation: Not applicable (no itemized billing vs total pairing)")

    if result.issues:
        print(f"\n  Detected Issues & Quality Flags ({len(result.issues)}):")
        for iss in result.issues:
            sev = iss.severity.upper()
            page_info = f" [Page {iss.page_number}]" if iss.page_number else ""
            print(f"    [{sev}]{page_info} {iss.code}: {iss.description}")

    # 6. Provenance & Evidence Traceability Summary
    prov_count = 0
    all_fields = [
        entities.patient.name, entities.patient.age, entities.patient.gender, entities.patient.patient_id,
        entities.hospital.name, entities.hospital.doctor_name, entities.hospital.address,
        entities.encounter.admission_date, entities.encounter.discharge_date, entities.encounter.diagnosis_text,
        entities.financial.invoice_number, entities.financial.total_amount,
    ]
    for f in all_fields:
        if getattr(f, "provenance", None) is not None:
            prov_count += 1

    print("\n--- 6. Provenance & Evidence Traceability ---")
    print(f"  Verified Provenance-Tracked Entities : {prov_count} field(s) with page/verbatim traceability")
    print("=" * 80 + "\n")


# -----------------------------------------------------------------------------
# Main CLI Orchestrator
# -----------------------------------------------------------------------------
def run_pipeline(
    file_path: str,
    mode: str = "auto",
    max_pages: int | None = None,
    start_page: int = 1,
    show_full_text: bool = False,
    output_json_path: str | None = None,
    device: str = "auto",
):
    """Executes Phase 1 and Phase 2, displaying detailed output for each phase."""
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        print(f"\n[ERROR] File not found: '{file_path}'")
        print("Please check the path and try again.")
        sys.exit(1)

    # Resolve target device
    ocr_device = None
    if device == "gpu":
        ocr_device = "gpu:0"
    elif device == "cpu":
        ocr_device = "cpu"

    print(_banner(f"INSUREMATE PIPELINE: {os.path.basename(file_path)}"))
    print(f" Target File : {file_path}")
    print(f" Config      : mode='{mode}', device='{device}', max_pages={max_pages or 'all'}, start_page={start_page}")

    # -------------------------------------------------------------------------
    # 1. Execute Phase 1: Ingestion
    # -------------------------------------------------------------------------
    print("\n[Running Phase 1: Ingesting document...]")
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

    # Display Phase 1 Output
    display_phase1_output(phase1_result, show_full_text=show_full_text)

    # -------------------------------------------------------------------------
    # 2. Execute Phase 2: Understanding
    # -------------------------------------------------------------------------
    print("\n[Running Phase 2: Understanding & Structuring...]")
    ingested_doc = _convert_phase1_to_phase2(phase1_result, file_path)
    pipeline = DocumentUnderstandingPipeline()
    phase2_result = pipeline.process(ingested_doc)

    # Display Phase 2 Output
    display_phase2_output(phase2_result)

    # -------------------------------------------------------------------------
    # 3. Optional JSON Export
    # -------------------------------------------------------------------------
    if output_json_path:
        out_path = os.path.abspath(output_json_path)
        combined_data = {
            "phase1_ingestion": phase1_result,
            "phase2_understanding": phase2_result.model_dump(),
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        print(f"[Export] Full Phase 1 & Phase 2 JSON exported to: {out_path}")

    return phase1_result, phase2_result


def main():
    parser = argparse.ArgumentParser(
        description="InsureMate End-to-End Pipeline CLI Test (Phase 1 Ingestion + Phase 2 Understanding)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        default=None,
        help="Path to the PDF document to process.",
    )
    parser.add_argument(
        "-f", "--file",
        dest="flag_file",
        default=None,
        help="Alternative flag to specify input PDF path.",
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
        help="Save combined Phase 1 & Phase 2 output to a JSON file.",
    )

    args = parser.parse_args()

    # Determine input path
    target_path = args.file_path or args.flag_file

    # Interactive prompt if no path provided
    if not target_path:
        print("=" * 80)
        print(" InsureMate - End-to-End Pipeline CLI")
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
            # Strip quotes if copied from terminal
            target_path = user_input.strip("\"'")

    run_pipeline(
        file_path=target_path,
        mode=args.mode,
        max_pages=args.max_pages,
        start_page=args.start_page,
        show_full_text=args.full_text,
        output_json_path=args.output_json,
        device=args.device,
    )


if __name__ == "__main__":
    main()
