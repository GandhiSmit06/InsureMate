"""
main.py
Unified Command-Line Interface for InsureMate.
Provides direct invocation of:
- Phase 1: Qwen-VL Document Extraction Tool
- Phase 2: Document Validation Tool
- Phase 3: Validity Checker Tool
- Complete End-to-End Execution Pipeline
- Comprehensive Test Suites
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.qwen_vl_tool import QwenVLExtractionTool
from tools.document_validation_tool import DocumentValidationTool
from tools.validity_checker_tool import ValidityCheckerTool
from tests.test_phase1 import run_phase1_tests
from tests.test_phase2 import run_phase2_tests
from tests.test_phase3 import run_phase3_tests
from tests.test_end_to_end import run_end_to_end_test
from utils.logger import logger


def run_phase_1(pdf_path: str, max_pages: int = 2):
    print("\n" + "=" * 70)
    print("PHASE 1: QWEN-VL DOCUMENT EXTRACTION")
    print("=" * 70)
    tool = QwenVLExtractionTool()
    res = tool.run(pdf_path, max_pages=max_pages)
    print(f"Status: {res['status']}")
    print(f"Total Pages Processed: {res['total_pages']}")
    print(json.dumps(res["extracted_documents"], indent=2))
    return res


def run_phase_2(extracted_data=None):
    print("\n" + "=" * 70)
    print("PHASE 2: DOCUMENT VALIDATION")
    print("=" * 70)
    tool = DocumentValidationTool()
    if not extracted_data:
        # Sample document for quick demonstration
        extracted_data = [
            {
                "page_number": 1,
                "document_type": "insurance_policy",
                "policy_number": "4225i/ELVT/384538792/00/000",
                "policy_holder_name": "Maulikkumar Pathak",
                "policy_start_date": "12/03/2025",
                "policy_end_date": "11/03/2028",
            },
            {
                "page_number": 2,
                "document_type": "medical_bill",
                "bill_number": "BILL-101",
                "patient_name": "Parth Pathak",
                "document_date": "15/08/2026",
                "bill_amount": "25000.00",
            }
        ]
    res = tool.run(extracted_data)
    print(json.dumps(res["validation_result"], indent=2))
    return res


def run_phase_3(policy_data=None, claim_data=None):
    print("\n" + "=" * 70)
    print("PHASE 3: CLAIM VALIDITY CHECKER")
    print("=" * 70)
    tool = ValidityCheckerTool()
    if not policy_data:
        policy_data = {
            "policy_number": "4225i/ELVT/384538792/00/000",
            "policy_holder_name": "Maulikkumar Pathak",
            "policy_start_date": "12/03/2025",
            "policy_end_date": "11/03/2028",
            "insured_names": ["Maulikkumar Pathak", "Parth Pathak"]
        }
    if not claim_data:
        claim_data = [
            {
                "document_type": "medical_bill",
                "page_number": 2,
                "document_date": "15/08/2026",
                "patient_name": "Parth Pathak",
                "bill_amount": "25000.00"
            }
        ]
    res = tool.run(policy_data=policy_data, document_data=claim_data)
    print(json.dumps(res, indent=2))
    return res


def main():
    parser = argparse.ArgumentParser(
        description="InsureMate — Phase 1, 2, 3 Document Understanding, Validation & Validity Checker"
    )
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], help="Execute a specific phase (1, 2, or 3)")
    parser.add_argument("--test-all", action="store_true", help="Execute all unit and integration test suites")
    parser.add_argument("--end-to-end", action="store_true", help="Execute full end-to-end pipeline on real documents")
    parser.add_argument("--pdf", type=str, help="Target PDF file to extract using Phase 1 tool")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages to extract from PDF (default 3)")

    parser.add_argument("--real", action="store_true", help="Execute complete analysis on real repository documents")

    args = parser.parse_args()

    default_policy = str(ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf")

    if args.real:
        print("\n" + "=" * 80)
        print("          TESTING ON REAL REPOSITORY DOCUMENTS")
        print("================================================================================")
        success = run_end_to_end_test()
        sys.exit(0 if success else 1)

    elif args.test_all:
        print("\n=======================================================")
        print("          RUNNING COMPLETE TEST SUITE                 ")
        print("=======================================================")
        p1 = run_phase1_tests()
        p2 = run_phase2_tests()
        p3 = run_phase3_tests()
        pe2e = run_end_to_end_test()
        all_passed = p1 and p2 and p3 and pe2e
        print("\n=======================================================")
        print(f"OVERALL TEST SUITE STATUS: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        print("=======================================================")
        sys.exit(0 if all_passed else 1)

    elif args.end_to_end:
        success = run_end_to_end_test()
        sys.exit(0 if success else 1)

    elif args.phase == 1:
        target_pdf = args.pdf or default_policy
        run_phase_1(target_pdf, max_pages=args.max_pages)

    elif args.phase == 2:
        run_phase_2()

    elif args.phase == 3:
        run_phase_3()

    else:
        # Default run: Complete end-to-end demonstration
        print("No specific flag provided. Running complete End-to-End demonstration...\n")
        run_end_to_end_test()


if __name__ == "__main__":
    main()
