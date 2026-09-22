"""
Demonstration script for InsureMate Phase 2 — Document Understanding.
Runs the pipeline on sample documents and exports Schema v1.0 JSON outputs.
"""

import sys
import json
from pathlib import Path

# Add src to python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from insuremate.document_understanding.pipeline import DocumentUnderstandingPipeline
from insuremate.document_understanding.adapters.mock_inputs import (
    create_mock_hospital_invoice,
    create_mock_discharge_summary,
    create_mock_conflicting_dates,
)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    print("=" * 80)
    print("INSUREMATE PHASE 2: DOCUMENT UNDERSTANDING DEMO")
    print("=" * 80)

    pipeline = DocumentUnderstandingPipeline()

    # 1. Run on Sample Hospital Invoice
    invoice_doc = create_mock_hospital_invoice()
    print(f"\n[1] Processing Ingested Document: {invoice_doc.filename} ({invoice_doc.document_id})")
    invoice_result = pipeline.process(invoice_doc)

    print(f"    Status: {invoice_result.status.upper()}")
    print(f"    Top Type Hint: {invoice_result.document_type_hints[0].candidate_type} "
          f"(Confidence: {invoice_result.document_type_hints[0].confidence.value}, Score: {invoice_result.document_type_hints[0].confidence_score})")
    print(f"    Patient Name: {invoice_result.entities.patient.name.value} [{invoice_result.entities.patient.name.status.value}]")
    print(f"    Doctor Name: {invoice_result.entities.hospital.doctor_name.value}")
    print(f"    Total Amount: ₹ {invoice_result.entities.financial.total_amount.value}")
    print(f"    Itemized Charges Count: {len(invoice_result.entities.financial.itemized_charges)}")
    print(f"    Arithmetic Reconciliation: Matches={invoice_result.quality.arithmetic_reconciliation.matches} "
          f"(Sum={invoice_result.quality.arithmetic_reconciliation.itemized_sum}, Discrepancy={invoice_result.quality.arithmetic_reconciliation.discrepancy})")

    # Export to examples/output_example.json
    out_path = Path(__file__).resolve().parent / "output_example.json"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(invoice_result.model_dump_json(indent=2))
    print(f"    -> Exported valid result to: {out_path.name}")

    # 2. Run on Sample Discharge Summary
    ds_doc = create_mock_discharge_summary()
    print(f"\n[2] Processing Ingested Document: {ds_doc.filename} ({ds_doc.document_id})")
    ds_result = pipeline.process(ds_doc)
    print(f"    Status: {ds_result.status.upper()}")
    print(f"    Top Type Hint: {ds_result.document_type_hints[0].candidate_type} "
          f"(Score: {ds_result.document_type_hints[0].confidence_score})")
    print(f"    Patient Name: {ds_result.entities.patient.name.value}")
    print(f"    Admission Date: {ds_result.entities.encounter.admission_date.value}")
    print(f"    Discharge Date: {ds_result.entities.encounter.discharge_date.value}")
    print(f"    Documented Diagnosis: {ds_result.entities.encounter.diagnosis_text.value}")
    print(f"    Sections Detected ({len(ds_result.sections)}): {[s.heading for s in ds_result.sections]}")

    # 3. Run on Incomplete / Conflicting Dates Case
    conflict_doc = create_mock_conflicting_dates()
    print(f"\n[3] Processing Edge Case Document: {conflict_doc.filename}")
    conflict_result = pipeline.process(conflict_doc)
    print(f"    Status: {conflict_result.status.upper()}")
    print(f"    Quality Rating: {conflict_result.quality.overall_quality}")
    print(f"    Has Conflicting Dates: {conflict_result.quality.has_conflicting_dates}")
    print(f"    Detected Issues ({len(conflict_result.issues)}):")
    for issue in conflict_result.issues:
        print(f"      - [{issue.severity.upper()}] {issue.code}: {issue.description}")

    # Export to examples/incomplete_ambiguous_output.json
    edge_out_path = Path(__file__).resolve().parent / "incomplete_ambiguous_output.json"
    with open(edge_out_path, "w", encoding="utf-8") as f:
        f.write(conflict_result.model_dump_json(indent=2))
    print(f"    -> Exported edge-case result to: {edge_out_path.name}")

    print("\n" + "=" * 80)
    print("DEMO EXECUTION COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()
