"""
tests/test_phase3.py
Deterministic validity tests for Phase 3: Validity Checker Tool.
Directly implements the 8 mandatory test cases specified in the project requirements:
TEST 1: Valid policy + bill date inside policy period
TEST 2: Bill date before policy start
TEST 3: Bill date after policy expiry
TEST 4: Missing policy start date
TEST 5: Missing policy end date
TEST 6: Missing bill/report date
TEST 7: Invalid date format
TEST 8: Multiple documents with mixed valid/invalid dates
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.validity_checker.checker import ValidityChecker, validity_checker
from tools.validity_checker_tool import ValidityCheckerTool


def print_test_banner(title: str):
    print("\n" + "=" * 70)
    print(f"PHASE 3 TEST: {title}")
    print("=" * 70)


def run_phase3_tests():
    validity_tool = ValidityCheckerTool()
    passed = 0
    total = 8

    # Standard policy fixture for 2026
    standard_policy = {
        "policy_number": "POL-2026-9900",
        "policy_holder_name": "Maulikkumar Pathak",
        "policy_start_date": "01/01/2026",
        "policy_end_date": "31/12/2026",
        "insured_names": ["Maulikkumar Pathak", "Parth Pathak"],
    }

    # -------------------------------------------------------------
    # TEST 1: Valid policy + bill date inside policy period
    # -------------------------------------------------------------
    print_test_banner("TEST 1: Valid Policy + Bill Date Inside Policy Period")
    bill_1 = {
        "document_type": "medical_bill",
        "page_number": 1,
        "document_date": "15/08/2026",
        "patient_name": "Parth Pathak",
        "bill_amount": "25000",
    }
    res_1 = validity_tool.run(policy_data=standard_policy, document_data=bill_1)
    exp_1 = "valid=True, reason mentions 'falls within the policy validity period'"
    act_1 = f"valid={res_1['valid']}, checks_count={len(res_1['checks'])}, reasons={res_1['reasons']}"
    p_1 = res_1["valid"] is True and any("within" in r.lower() for r in res_1["reasons"])
    print(f"INPUT POLICY:    {standard_policy['policy_start_date']} -> {standard_policy['policy_end_date']}")
    print(f"INPUT BILL:      {bill_1['document_date']}")
    print(f"EXPECTED RESULT: {exp_1}")
    print(f"ACTUAL RESULT:   {act_1}")
    print(f"STATUS:          {'PASS' if p_1 else 'FAIL'}")
    if p_1: passed += 1

    # -------------------------------------------------------------
    # TEST 2: Bill date before policy start
    # -------------------------------------------------------------
    print_test_banner("TEST 2: Bill Date Before Policy Start")
    bill_2 = {
        "document_type": "medical_bill",
        "page_number": 2,
        "document_date": "15/10/2025",  # Prior to 01/01/2026!
        "patient_name": "Parth Pathak",
    }
    res_2 = validity_tool.run(policy_data=standard_policy, document_data=bill_2)
    exp_2 = "valid=False, reason mentions 'prior to policy inception' or 'outside'"
    act_2 = f"valid={res_2['valid']}, reasons={res_2['reasons']}"
    p_2 = res_2["valid"] is False and any("prior to" in r.lower() or "outside" in r.lower() for r in res_2["reasons"])
    print(f"INPUT POLICY:    {standard_policy['policy_start_date']} -> {standard_policy['policy_end_date']}")
    print(f"INPUT BILL:      {bill_2['document_date']}")
    print(f"EXPECTED RESULT: {exp_2}")
    print(f"ACTUAL RESULT:   {act_2}")
    print(f"STATUS:          {'PASS' if p_2 else 'FAIL'}")
    if p_2: passed += 1

    # -------------------------------------------------------------
    # TEST 3: Bill date after policy expiry
    # -------------------------------------------------------------
    print_test_banner("TEST 3: Bill Date After Policy Expiry")
    bill_3 = {
        "document_type": "medical_bill",
        "page_number": 3,
        "document_date": "15/01/2027",  # After 31/12/2026!
        "patient_name": "Parth Pathak",
    }
    res_3 = validity_tool.run(policy_data=standard_policy, document_data=bill_3)
    exp_3 = "valid=False, reason mentions 'after policy expiry' or 'outside'"
    act_3 = f"valid={res_3['valid']}, reasons={res_3['reasons']}"
    p_3 = res_3["valid"] is False and any("after policy expiry" in r.lower() or "outside" in r.lower() for r in res_3["reasons"])
    print(f"INPUT POLICY:    {standard_policy['policy_start_date']} -> {standard_policy['policy_end_date']}")
    print(f"INPUT BILL:      {bill_3['document_date']}")
    print(f"EXPECTED RESULT: {exp_3}")
    print(f"ACTUAL RESULT:   {act_3}")
    print(f"STATUS:          {'PASS' if p_3 else 'FAIL'}")
    if p_3: passed += 1

    # -------------------------------------------------------------
    # TEST 4: Missing policy start date
    # -------------------------------------------------------------
    print_test_banner("TEST 4: Missing Policy Start Date")
    policy_no_start = {
        "policy_number": "POL-999",
        "policy_start_date": None,  # Missing!
        "policy_end_date": "31/12/2026",
    }
    res_4 = validity_tool.run(policy_data=policy_no_start, document_data=bill_1)
    exp_4 = "valid=False, reason mentions 'Policy start date is missing'"
    act_4 = f"valid={res_4['valid']}, reasons={res_4['reasons']}"
    p_4 = res_4["valid"] is False and any("start date is missing" in r.lower() for r in res_4["reasons"])
    print(f"INPUT POLICY:    start=None, end=31/12/2026")
    print(f"INPUT BILL:      {bill_1['document_date']}")
    print(f"EXPECTED RESULT: {exp_4}")
    print(f"ACTUAL RESULT:   {act_4}")
    print(f"STATUS:          {'PASS' if p_4 else 'FAIL'}")
    if p_4: passed += 1

    # -------------------------------------------------------------
    # TEST 5: Missing policy end date
    # -------------------------------------------------------------
    print_test_banner("TEST 5: Missing Policy End Date")
    policy_no_end = {
        "policy_number": "POL-999",
        "policy_start_date": "01/01/2026",
        "policy_end_date": None,  # Missing!
    }
    res_5 = validity_tool.run(policy_data=policy_no_end, document_data=bill_1)
    exp_5 = "valid=False, reason mentions 'Policy end date is missing'"
    act_5 = f"valid={res_5['valid']}, reasons={res_5['reasons']}"
    p_5 = res_5["valid"] is False and any("end date is missing" in r.lower() for r in res_5["reasons"])
    print(f"INPUT POLICY:    start=01/01/2026, end=None")
    print(f"INPUT BILL:      {bill_1['document_date']}")
    print(f"EXPECTED RESULT: {exp_5}")
    print(f"ACTUAL RESULT:   {act_5}")
    print(f"STATUS:          {'PASS' if p_5 else 'FAIL'}")
    if p_5: passed += 1

    # -------------------------------------------------------------
    # TEST 6: Missing bill/report date
    # -------------------------------------------------------------
    print_test_banner("TEST 6: Missing Bill/Report Date")
    bill_no_date = {
        "document_type": "medical_bill",
        "page_number": 4,
        "document_date": None,  # Missing!
        "patient_name": "Parth Pathak",
    }
    res_6 = validity_tool.run(policy_data=standard_policy, document_data=bill_no_date)
    exp_6 = "valid=False, reason mentions 'missing date on medical_bill'"
    act_6 = f"valid={res_6['valid']}, reasons={res_6['reasons']}"
    p_6 = res_6["valid"] is False and any("missing date" in r.lower() for r in res_6["reasons"])
    print(f"INPUT POLICY:    01/01/2026 -> 31/12/2026")
    print(f"INPUT BILL:      date=None")
    print(f"EXPECTED RESULT: {exp_6}")
    print(f"ACTUAL RESULT:   {act_6}")
    print(f"STATUS:          {'PASS' if p_6 else 'FAIL'}")
    if p_6: passed += 1

    # -------------------------------------------------------------
    # TEST 7: Invalid date format
    # -------------------------------------------------------------
    print_test_banner("TEST 7: Invalid Date Format")
    bill_invalid_date = {
        "document_type": "medical_bill",
        "page_number": 5,
        "document_date": "not_a_real_calendar_date_99/99/9999",  # Invalid!
        "patient_name": "Parth Pathak",
    }
    res_7 = validity_tool.run(policy_data=standard_policy, document_data=bill_invalid_date)
    exp_7 = "valid=False, reason mentions 'Invalid date format'"
    act_7 = f"valid={res_7['valid']}, reasons={res_7['reasons']}"
    p_7 = res_7["valid"] is False and any("invalid date format" in r.lower() for r in res_7["reasons"])
    print(f"INPUT POLICY:    01/01/2026 -> 31/12/2026")
    print(f"INPUT BILL:      {bill_invalid_date['document_date']}")
    print(f"EXPECTED RESULT: {exp_7}")
    print(f"ACTUAL RESULT:   {act_7}")
    print(f"STATUS:          {'PASS' if p_7 else 'FAIL'}")
    if p_7: passed += 1

    # -------------------------------------------------------------
    # TEST 8: Multiple documents with mixed valid/invalid dates
    # -------------------------------------------------------------
    print_test_banner("TEST 8: Multiple Documents With Mixed Valid/Invalid Dates")
    mixed_docs = [
        {
            "document_type": "hospital_document",
            "page_number": 1,
            "document_date": "10/05/2026",  # VALID (in 2026)
            "patient_name": "Parth Pathak",
        },
        {
            "document_type": "medical_bill",
            "page_number": 2,
            "document_date": "15/01/2027",  # INVALID (after 31/12/2026)
            "patient_name": "Parth Pathak",
        },
        {
            "document_type": "medical_report",
            "page_number": 3,
            "document_date": "12/05/2026",  # VALID (in 2026)
            "patient_name": "Parth Pathak",
        },
    ]
    res_8 = validity_tool.run(policy_data=standard_policy, document_data=mixed_docs)
    exp_8 = "overall valid=False, individual checks: 2 PASS, 1 FAIL"
    act_checks = [(c["document_type"], c["page_number"], c["valid"]) for c in res_8["checks"]]
    act_8 = f"overall valid={res_8['valid']}, individual checks={act_checks}"
    valid_checks_count = sum(1 for c in res_8["checks"] if c["valid"])
    invalid_checks_count = sum(1 for c in res_8["checks"] if not c["valid"])
    p_8 = (
        res_8["valid"] is False and
        valid_checks_count == 2 and
        invalid_checks_count == 1
    )
    print(f"INPUT POLICY:    01/01/2026 -> 31/12/2026")
    print(f"INPUT DOCS:      Page 1: 10/05/2026, Page 2: 15/01/2027, Page 3: 12/05/2026")
    print(f"EXPECTED RESULT: {exp_8}")
    print(f"ACTUAL RESULT:   {act_8}")
    print(f"STATUS:          {'PASS' if p_8 else 'FAIL'}")
    if p_8: passed += 1

    print("\n" + "=" * 70)
    print(f"PHASE 3 SUMMARY: {passed}/{total} TESTS PASSED")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    success = run_phase3_tests()
    sys.exit(0 if success else 1)
