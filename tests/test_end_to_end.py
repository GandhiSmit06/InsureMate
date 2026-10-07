"""
tests/test_end_to_end.py
End-to-end pipeline test integrating Phase 1, Phase 2, and Phase 3:
PDF -> Qwen-VL Tool -> Document Validation Tool -> Validity Checker Tool -> Intermediate Agent Result.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.qwen_vl_tool import QwenVLExtractionTool
from tools.document_validation_tool import DocumentValidationTool
from tools.validity_checker_tool import ValidityCheckerTool


def print_banner(msg: str):
    print("\n" + "=" * 80)
    print(f" {msg} ")
    print("=" * 80)


def run_end_to_end_test():
    print_banner("INSUREMATE END-TO-END INTEGRATION TEST (TOOL WORKFLOW)")

    extraction_tool = QwenVLExtractionTool(offline_mode=True)
    validation_tool = DocumentValidationTool()
    validity_tool = ValidityCheckerTool()

    policy_pdf = ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf"
    hospital_pdf = ROOT_DIR / "DOCUMENTS FOR Re- activation REQUEST OF CLAIM NO.95151709.pdf"

    # Step 1: Extraction via QwenVLExtractionTool
    print("\n[STEP 1] Calling QwenVLExtractionTool...")
    policy_ext = extraction_tool.run(policy_pdf, max_pages=1)
    hospital_ext = extraction_tool.run(hospital_pdf, max_pages=3)

    assert policy_ext["status"] == "success", "Policy extraction failed"
    assert hospital_ext["status"] == "success", "Hospital extraction failed"

    all_extracted = policy_ext["extracted_documents"] + hospital_ext["extracted_documents"]
    print(f"-> Successfully extracted {len(all_extracted)} total pages.")
    for doc in all_extracted:
        print(f"   * Page {doc['page_number']}: [{doc['document_type']}] {doc['document_title']}")

    # Step 2: Document Validation via DocumentValidationTool
    print("\n[STEP 2] Calling DocumentValidationTool...")
    validation_res = validation_tool.run(all_extracted)
    assert validation_res["status"] == "success", "Validation tool failed"
    print(f"-> Validation result: overall_valid={validation_res['valid']}")
    print(f"   Total docs checked: {validation_res['total_documents']} | Valid: {validation_res['valid_documents']} | Invalid: {validation_res['invalid_documents']}")

    # Step 3: Validity Checker via ValidityCheckerTool
    print("\n[STEP 3] Calling ValidityCheckerTool...")
    policy_data = policy_ext["extracted_documents"]
    claim_docs = hospital_ext["extracted_documents"]
    validity_res = validity_tool.run(policy_data=policy_data, document_data=claim_docs)
    assert validity_res["status"] == "success", "Validity tool failed"

    print(f"-> Validity check result: valid={validity_res['valid']}")
    print(f"   Policy window: {validity_res['policy_period']['policy_start_date']} to {validity_res['policy_period']['policy_end_date']}")
    for check in validity_res["checks"]:
        print(f"   * Page {check['page_number']} ({check['document_type']}): date={check['normalized_date']} -> valid={check['valid']} ({check['reason']})")

    # Step 4: Final Intermediate Observation Result Table (Agent-Ready)
    print("\n" + "=" * 80)
    print("FINAL INTERMEDIATE OBSERVATION TABLE FOR AGENT")
    print("=" * 80)
    header = f"{'Sr.No':<6} | {'Document Title':<35} | {'Type':<18} | {'Page':<5} | {'Validation':<10} | {'Period Check'}"
    print(header)
    print("-" * len(header))

    validity_checks_by_page = {c["page_number"]: c for c in validity_res["checks"]}
    val_map = {r["page_number"]: r for r in validation_res["validation_result"]["document_results"]}

    for idx, doc in enumerate(all_extracted, 1):
        p_num = doc["page_number"]
        v_info = val_map.get(p_num, {})
        val_status = "PASS" if v_info.get("valid") else "FAIL"

        if doc["document_type"] == "insurance_policy":
            period_status = "POLICY BASE"
        else:
            chk = validity_checks_by_page.get(p_num)
            period_status = "PASS (Valid)" if (chk and chk.get("valid")) else "FAIL (Pre-Policy)"

        title = (doc.get("document_title") or "Untitled")[:34]
        dtype = doc.get("document_type", "unknown")[:17]
        print(f"{idx:<6} | {title:<35} | {dtype:<18} | {p_num:<5} | {val_status:<10} | {period_status}")

    print("\nSUMMARY REASONS FOR CLAIM DECISION:")
    for r in validity_res["reasons"]:
        print(f" - {r}")

    print_banner("END-TO-END TEST COMPLETED SUCCESSFULLY (PASS)")
    return True


if __name__ == "__main__":
    success = run_end_to_end_test()
    sys.exit(0 if success else 1)
