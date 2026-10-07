"""
tests/test_phase2.py
Deterministic validation tests for Phase 2: Document Validation Tool.
Directly implements the 8 mandatory test cases specified in the project requirements:
1. Valid policy document
2. Policy missing required field
3. Valid medical bill
4. Medical bill missing required field
5. Valid medical report
6. Unrecognized document
7. Empty extraction result
8. Invalid extracted value
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.document_validation.validator import DocumentValidator, document_validation
from tools.document_validation_tool import DocumentValidationTool


def print_test_banner(title: str):
    print("\n" + "=" * 70)
    print(f"PHASE 2 TEST: {title}")
    print("=" * 70)


def run_phase2_tests():
    validator_tool = DocumentValidationTool()
    passed = 0
    total = 8

    # -------------------------------------------------------------
    # TEST 1: Valid policy document
    # -------------------------------------------------------------
    print_test_banner("TEST 1: Valid Policy Document")
    doc_1 = {
        "page_number": 1,
        "document_type": "insurance_policy",
        "document_title": "ICICI Lombard Policy Certificate",
        "policy_number": "4225i/ELVT/384538792/00/000",
        "policy_holder_name": "Maulikkumar Pathak",
        "policy_start_date": "12/03/2025",
        "policy_end_date": "11/03/2028",
    }
    res_1 = validator_tool.run(doc_1)
    exp_1 = "valid=True, total_documents=1, missing_fields=[]"
    act_1 = f"valid={res_1['valid']}, total_documents={res_1['total_documents']}, missing_fields={res_1['validation_result']['document_results'][0]['missing_fields']}"
    p_1 = res_1["valid"] is True and len(res_1["validation_result"]["document_results"][0]["missing_fields"]) == 0
    print(f"INPUT:           {doc_1}")
    print(f"EXPECTED RESULT: {exp_1}")
    print(f"ACTUAL RESULT:   {act_1}")
    print(f"STATUS:          {'PASS' if p_1 else 'FAIL'}")
    if p_1: passed += 1

    # -------------------------------------------------------------
    # TEST 2: Policy missing required field
    # -------------------------------------------------------------
    print_test_banner("TEST 2: Policy Missing Required Field (missing policy_number)")
    doc_2 = {
        "page_number": 1,
        "document_type": "insurance_policy",
        "document_title": "Policy Document",
        "policy_number": None,  # Missing!
        "policy_holder_name": "Maulikkumar Pathak",
        "policy_start_date": "12/03/2025",
        "policy_end_date": "11/03/2028",
    }
    res_2 = validator_tool.run(doc_2)
    doc_res_2 = res_2["validation_result"]["document_results"][0]
    exp_2 = "valid=False, missing_fields=['policy_number']"
    act_2 = f"valid={res_2['valid']}, missing_fields={doc_res_2['missing_fields']}, reasons={doc_res_2['reasons']}"
    p_2 = res_2["valid"] is False and "policy_number" in doc_res_2["missing_fields"]
    print(f"INPUT:           {doc_2}")
    print(f"EXPECTED RESULT: {exp_2}")
    print(f"ACTUAL RESULT:   {act_2}")
    print(f"STATUS:          {'PASS' if p_2 else 'FAIL'}")
    if p_2: passed += 1

    # -------------------------------------------------------------
    # TEST 3: Valid medical bill
    # -------------------------------------------------------------
    print_test_banner("TEST 3: Valid Medical Bill")
    doc_3 = {
        "page_number": 2,
        "document_type": "medical_bill",
        "document_title": "Final Inpatient Bill",
        "bill_number": "BILL-2024-95151",
        "patient_name": "Parth M. Pathak",
        "document_date": "25/10/2024",
        "bill_amount": "48,500.00",
    }
    res_3 = validator_tool.run(doc_3)
    exp_3 = "valid=True, missing_fields=[]"
    act_3 = f"valid={res_3['valid']}, missing_fields={res_3['validation_result']['document_results'][0]['missing_fields']}"
    p_3 = res_3["valid"] is True and len(res_3["validation_result"]["document_results"][0]["missing_fields"]) == 0
    print(f"INPUT:           {doc_3}")
    print(f"EXPECTED RESULT: {exp_3}")
    print(f"ACTUAL RESULT:   {act_3}")
    print(f"STATUS:          {'PASS' if p_3 else 'FAIL'}")
    if p_3: passed += 1

    # -------------------------------------------------------------
    # TEST 4: Medical bill missing required field
    # -------------------------------------------------------------
    print_test_banner("TEST 4: Medical Bill Missing Required Field (missing document_date)")
    doc_4 = {
        "page_number": 2,
        "document_type": "medical_bill",
        "document_title": "Hospital Bill",
        "bill_number": "BILL-2024-95151",
        "patient_name": "Parth M. Pathak",
        "document_date": None,  # Missing!
        "bill_amount": "48,500.00",
    }
    res_4 = validator_tool.run(doc_4)
    doc_res_4 = res_4["validation_result"]["document_results"][0]
    exp_4 = "valid=False, missing_fields=['document_date'], reason='Bill date could not be identified.'"
    act_4 = f"valid={res_4['valid']}, missing_fields={doc_res_4['missing_fields']}, reasons={doc_res_4['reasons']}"
    p_4 = res_4["valid"] is False and "document_date" in doc_res_4["missing_fields"]
    print(f"INPUT:           {doc_4}")
    print(f"EXPECTED RESULT: {exp_4}")
    print(f"ACTUAL RESULT:   {act_4}")
    print(f"STATUS:          {'PASS' if p_4 else 'FAIL'}")
    if p_4: passed += 1

    # -------------------------------------------------------------
    # TEST 5: Valid medical report
    # -------------------------------------------------------------
    print_test_banner("TEST 5: Valid Medical Report")
    doc_5 = {
        "page_number": 3,
        "document_type": "medical_report",
        "document_title": "Pathology Diagnostic Report",
        "patient_name": "Parth M. Pathak",
        "hospital_name": "Shree Vallabh Hospital Pathology Lab",
        "document_date": "20/10/2024",
    }
    res_5 = validator_tool.run(doc_5)
    exp_5 = "valid=True, missing_fields=[]"
    act_5 = f"valid={res_5['valid']}, missing_fields={res_5['validation_result']['document_results'][0]['missing_fields']}"
    p_5 = res_5["valid"] is True and len(res_5["validation_result"]["document_results"][0]["missing_fields"]) == 0
    print(f"INPUT:           {doc_5}")
    print(f"EXPECTED RESULT: {exp_5}")
    print(f"ACTUAL RESULT:   {act_5}")
    print(f"STATUS:          {'PASS' if p_5 else 'FAIL'}")
    if p_5: passed += 1

    # -------------------------------------------------------------
    # TEST 6: Unrecognized document
    # -------------------------------------------------------------
    print_test_banner("TEST 6: Unrecognized Document")
    doc_6 = {
        "page_number": 5,
        "document_type": "unknown",
        "document_title": "Random Brochure",
    }
    res_6 = validator_tool.run(doc_6)
    doc_res_6 = res_6["validation_result"]["document_results"][0]
    exp_6 = "valid=False, missing_fields=['recognized_document_type'], reason mentions unrecognized/unsupported"
    act_6 = f"valid={res_6['valid']}, missing_fields={doc_res_6['missing_fields']}, reasons={doc_res_6['reasons']}"
    p_6 = res_6["valid"] is False and "recognized_document_type" in doc_res_6["missing_fields"]
    print(f"INPUT:           {doc_6}")
    print(f"EXPECTED RESULT: {exp_6}")
    print(f"ACTUAL RESULT:   {act_6}")
    print(f"STATUS:          {'PASS' if p_6 else 'FAIL'}")
    if p_6: passed += 1

    # -------------------------------------------------------------
    # TEST 7: Empty extraction result
    # -------------------------------------------------------------
    print_test_banner("TEST 7: Empty Extraction Result")
    doc_7 = []
    res_7 = validator_tool.run(doc_7)
    exp_7 = "valid=False, total_documents=0, reasons=['No extracted documents provided for validation.']"
    act_7 = f"valid={res_7['valid']}, total_documents={res_7['total_documents']}, reasons={res_7['validation_result']['reasons']}"
    p_7 = res_7["valid"] is False and res_7["total_documents"] == 0
    print(f"INPUT:           {doc_7}")
    print(f"EXPECTED RESULT: {exp_7}")
    print(f"ACTUAL RESULT:   {act_7}")
    print(f"STATUS:          {'PASS' if p_7 else 'FAIL'}")
    if p_7: passed += 1

    # -------------------------------------------------------------
    # TEST 8: Invalid extracted value (e.g. invalid date syntax or negative bill amount)
    # -------------------------------------------------------------
    print_test_banner("TEST 8: Invalid Extracted Value (Negative bill amount)")
    doc_8 = {
        "page_number": 4,
        "document_type": "medical_bill",
        "document_title": "Corrupt Inpatient Bill",
        "bill_number": "BILL-999",
        "patient_name": "Parth M. Pathak",
        "document_date": "25/10/2024",
        "bill_amount": "-500.00",  # Illegal negative amount!
    }
    res_8 = validator_tool.run(doc_8)
    doc_res_8 = res_8["validation_result"]["document_results"][0]
    exp_8 = "valid=False, missing_fields=['bill_amount'], reason mentions 'cannot be negative'"
    act_8 = f"valid={res_8['valid']}, missing_fields={doc_res_8['missing_fields']}, reasons={doc_res_8['reasons']}"
    p_8 = res_8["valid"] is False and any("negative" in r.lower() for r in doc_res_8["reasons"])
    print(f"INPUT:           {doc_8}")
    print(f"EXPECTED RESULT: {exp_8}")
    print(f"ACTUAL RESULT:   {act_8}")
    print(f"STATUS:          {'PASS' if p_8 else 'FAIL'}")
    if p_8: passed += 1

    print("\n" + "=" * 70)
    print(f"PHASE 2 SUMMARY: {passed}/{total} TESTS PASSED")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    success = run_phase2_tests()
    sys.exit(0 if success else 1)
