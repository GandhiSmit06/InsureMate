"""tests/test_end_to_end.py
End-to-end pipeline test integrating Phase 1, Phase 2, Phase 3, and Phase 4:
PDF -> Qwen-VL Tool -> Document Validation Tool -> Validity Checker Tool -> Missing-Document Detector Tool.
Accepts dynamic --policy and --claim arguments, eliminating hardcoded input files and mock demonstrations.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Union

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.qwen_vl_tool import QwenVLExtractionTool
from tools.document_validation_tool import DocumentValidationTool
from tools.validity_checker_tool import ValidityCheckerTool
from tools.missing_document_tool import MissingDocumentTool
from services.missing_document.detector import format_detection_table
from utils.logger import logger


def print_banner(msg: str):
    print("\n" + "=" * 80)
    print(f" {msg} ")
    print("=" * 80)


def run_end_to_end_test(
    policy_pdf: Optional[Union[str, Path]] = None,
    claim_pdf: Optional[Union[str, Path]] = None,
    max_policy_pages: Optional[int] = None,
    max_claim_pages: Optional[int] = None
) -> bool:
    """
    Execute full 4-phase pipeline on real input PDFs.
    Phase 1 (Qwen-VL) -> Phase 2 (Validation) -> Phase 3 (Validity) -> Phase 4 (Missing Document Detector).
    """
    print_banner("INSUREMATE END-TO-END INTEGRATION TEST (PHASE 1 -> 2 -> 3 -> 4)")

    # 1. Resolve Policy and Claim PDF paths
    if policy_pdf is not None:
        p_path = Path(policy_pdf).resolve()
        if not p_path.exists() or not p_path.is_file():
            print(f"Error: Policy PDF file not found: {policy_pdf}", file=sys.stderr)
            return False
    else:
        # Default policy search
        p_candidate = ROOT_DIR / "sample_policy.pdf"
        if not p_candidate.exists():
            p_candidate = ROOT_DIR / "policy_A.pdf"
        if not p_candidate.exists():
            p_candidate = ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf"
        p_path = p_candidate

    if claim_pdf is not None:
        c_path = Path(claim_pdf).resolve()
        if not c_path.exists() or not c_path.is_file():
            print(f"Error: Claim PDF file not found: {claim_pdf}", file=sys.stderr)
            return False
    else:
        # Default claim search
        c_candidate = ROOT_DIR / "sample_claim.pdf"
        if not c_candidate.exists():
            c_candidate = ROOT_DIR / "claim_A.pdf"
        if not c_candidate.exists():
            c_candidate = ROOT_DIR / "DOCUMENTS FOR Re- activation REQUEST OF CLAIM NO.95151709.pdf"
        c_path = c_candidate


    if not p_path.exists():
        print(f"Error: Target policy document does not exist: {p_path}", file=sys.stderr)
        return False
    if not c_path.exists():
        print(f"Error: Target claim document does not exist: {c_path}", file=sys.stderr)
        return False

    extraction_tool = QwenVLExtractionTool(offline_mode=True)
    validation_tool = DocumentValidationTool()
    validity_tool = ValidityCheckerTool()
    detector_tool = MissingDocumentTool()

    # Step 1: Extraction via QwenVLExtractionTool
    print("\n[STEP 1] Calling QwenVLExtractionTool...")
    policy_ext = extraction_tool.run(p_path, max_pages=max_policy_pages)
    claim_ext = extraction_tool.run(c_path, max_pages=max_claim_pages)

    assert policy_ext["status"] == "success", f"Policy extraction failed: {policy_ext.get('error')}"
    assert claim_ext["status"] == "success", f"Claim extraction failed: {claim_ext.get('error')}"

    all_extracted = policy_ext["extracted_documents"] + claim_ext["extracted_documents"]
    print(f"-> Successfully extracted {len(all_extracted)} total pages.")
    for doc in all_extracted:
        clauses_info = f" (Clauses: {len(doc.get('policy_clauses', []))})" if doc.get("policy_clauses") else ""
        print(f"   * Page {doc['page_number']}: [{doc['document_type']}] {doc['document_title']}{clauses_info}")

    # Step 2: Document Validation via DocumentValidationTool
    print("\n[STEP 2] Calling DocumentValidationTool...")
    validation_res = validation_tool.run(all_extracted)
    assert validation_res["status"] == "success", "Validation tool failed"
    print(f"-> Validation result: overall_valid={validation_res['valid']}")
    print(f"   Total docs checked: {validation_res['total_documents']} | Valid: {validation_res['valid_documents']} | Invalid: {validation_res['invalid_documents']}")

    # Step 3: Validity Checker via ValidityCheckerTool
    print("\n[STEP 3] Calling ValidityCheckerTool...")
    policy_docs = policy_ext["extracted_documents"]
    claim_docs = claim_ext["extracted_documents"]
    validity_res = validity_tool.run(policy_data=policy_docs, document_data=claim_docs)
    assert validity_res["status"] == "success", "Validity tool failed"

    print(f"-> Validity check result: valid={validity_res['valid']}")
    if validity_res.get("policy_period"):
        print(f"   Policy window: {validity_res['policy_period']['policy_start_date']} to {validity_res['policy_period']['policy_end_date']}")
    for check in validity_res.get("checks", []):
        print(f"   * Page {check['page_number']} ({check['document_type']}): date={check.get('normalized_date')} -> valid={check['valid']} ({check.get('reason')})")

    # Step 4: Missing-Document Detection via MissingDocumentDetectorTool (Phase 4)
    print("\n[STEP 4] Calling MissingDocumentDetectorTool (Phase 4)...")
    phase1_payload = {
        "status": "success",
        "total_pages": len(all_extracted),
        "extracted_documents": all_extracted
    }
    detector_res = detector_tool.run(
        phase1_output=phase1_payload,
        phase2_output=validation_res,
        phase3_output=validity_res
    )
    assert detector_res["status"] in ("success", "no_requirements_found"), f"Detector tool failed: {detector_res.get('error')}"

    print(f"-> Missing-Document Detection Completed:")
    summary = detector_res.get("summary", {})
    total_req = summary.get("total_required", 0)
    found = summary.get("present", summary.get("total_found", 0))
    missing = summary.get("missing", summary.get("total_missing", 0))
    print(f"   Required: {total_req} | Found: {found} | Missing: {missing}")
    print("\n" + format_detection_table(detector_res))

    print_banner("FULL 4-PHASE END-TO-END PIPELINE COMPLETED SUCCESSFULLY (PASS)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="InsureMate End-to-End Pipeline Execution (Phases 1 -> 2 -> 3 -> 4)"
    )
    parser.add_argument("--policy", "-p", type=str, default=None, help="Path to insurance policy PDF file")
    parser.add_argument("--claim", "-c", type=str, default=None, help="Path to submitted claim documents PDF file")
    parser.add_argument("--max-policy-pages", type=int, default=None, help="Maximum policy pages to extract")
    parser.add_argument("--max-claim-pages", type=int, default=None, help="Maximum claim pages to extract")

    args = parser.parse_args()

    # Validate file presence before proceeding
    if args.policy and not Path(args.policy).exists():
        print(f"Error: Policy file not found: '{args.policy}'", file=sys.stderr)
        sys.exit(1)
    if args.claim and not Path(args.claim).exists():
        print(f"Error: Claim file not found: '{args.claim}'", file=sys.stderr)
        sys.exit(1)

    success = run_end_to_end_test(
        policy_pdf=args.policy,
        claim_pdf=args.claim,
        max_policy_pages=args.max_policy_pages,
        max_claim_pages=args.max_claim_pages
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
