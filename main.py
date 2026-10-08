"""
main.py
Unified Command-Line Interface for InsureMate.
Provides direct invocation of:
- Phase 1: Qwen-VL Document Extraction Tool
- Phase 2: Document Validation Tool
- Phase 3: Validity Checker Tool
- Phase 4: Dynamic Missing-Document Detector Tool
- Phase 5: InsureMate Agent Orchestrator & Planning (Autonomous Agent Workflow)
- Complete End-to-End Execution Pipeline
- Comprehensive Test Suites
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.qwen_vl_tool import QwenVLExtractionTool
from tools.document_validation_tool import DocumentValidationTool
from tools.validity_checker_tool import ValidityCheckerTool
from tools.missing_document_tool import MissingDocumentTool
from services.missing_document.detector import format_detection_table
from agent.insuremate_agent import InsureMateAgent
from agent.state import ClaimState
from tests.test_phase1 import run_phase1_tests
from tests.test_phase2 import run_phase2_tests
from tests.test_phase3 import run_phase3_tests
from tests.test_phase4 import run_phase4_all_tests
from tests.test_phase5 import run_phase5_tests
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
        extracted_data = [
            {
                "page_number": 1,
                "document_type": "insurance_policy",
                "policy_number": "POL-2025-00123",
                "policy_holder_name": "John Doe",
                "policy_start_date": "12/03/2025",
                "policy_end_date": "11/03/2028",
            },
            {
                "page_number": 2,
                "document_type": "medical_bill",
                "bill_number": "BILL-101",
                "patient_name": "Jane Doe",
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
            "policy_number": "POL-2025-00123",
            "policy_holder_name": "John Doe",
            "policy_start_date": "12/03/2025",
            "policy_end_date": "11/03/2028",
            "insured_names": ["John Doe", "Jane Doe"]
        }
    if not claim_data:
        claim_data = [
            {
                "document_type": "medical_bill",
                "page_number": 2,
                "document_date": "15/08/2026",
                "patient_name": "Jane Doe",
                "bill_amount": "25000.00"
            }
        ]
    res = tool.run(policy_data=policy_data, document_data=claim_data)
    print(json.dumps(res, indent=2))
    return res


def run_phase_4(phase1_data=None, phase2_data=None, phase3_data=None):
    print("\n" + "=" * 70)
    print("PHASE 4: DYNAMIC MISSING-DOCUMENT DETECTOR")
    print("=" * 70)
    if not phase1_data:
        raise ValueError(
            "phase1_data is required for Phase 4 missing-document detection. "
            "Structured policy JSON must be provided from Phase 1 extraction."
        )
    tool = MissingDocumentTool()
    res = tool.run(
        phase1_output=phase1_data,
        phase2_output=phase2_data,
        phase3_output=phase3_data
    )
    print(json.dumps(res, indent=2))
    print("\n" + format_detection_table(res))
    return res


def run_phase_5(
    policy_pdf: Optional[str] = None,
    claim_pdf: Optional[str] = None,
    goal: Optional[str] = None,
    max_pages: int = 2,
    offline_mode: bool = False
) -> ClaimState:
    print("\n" + "=" * 70)
    print("PHASE 5: INSUREMATE AGENT ORCHESTRATOR & PLANNING")
    print("=" * 70)

    docs = []
    if policy_pdf and Path(policy_pdf).exists():
        docs.append(str(policy_pdf))
    if claim_pdf and Path(claim_pdf).exists():
        docs.append(str(claim_pdf))

    if not docs:
        p_default = ROOT_DIR / "sample_policy.pdf"
        if not p_default.exists():
            p_default = ROOT_DIR / "policy_A.pdf"
        if not p_default.exists():
            p_default = ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf"

        c_default = ROOT_DIR / "sample_claim.pdf"
        if not c_default.exists():
            c_default = ROOT_DIR / "claim_A.pdf"
        if not c_default.exists():
            c_default = ROOT_DIR / "DOCUMENTS FOR Re- activation REQUEST OF CLAIM NO.95151709.pdf"

        if p_default.exists():
            docs.append(str(p_default))
        if c_default.exists():
            docs.append(str(c_default))

    agent = InsureMateAgent(offline_mode=offline_mode)
    state = agent.run(
        documents=docs,
        goal=goal or "Determine claim readiness.",
        max_pages=max_pages
    )
    print("\n")
    agent.print_execution_trace(state)
    print("\nFINAL CLAIM READINESS PACKAGE:")
    print(json.dumps(state.final_report, indent=2))
    return state


def run_phase_7(host: str = "0.0.0.0", port: int = 8000):
    print("\n" + "=" * 70)
    print("PHASE 7: END-TO-END APPLICATION + UI + DATABASE + CLAIM MEMORY")
    print("=" * 70)
    from app.server import run_server
    run_server(host=host, port=port)


def main():
    parser = argparse.ArgumentParser(
        description="InsureMate — Agentic Claim Preparation Pipeline & Agent Orchestrator"
    )
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5, 7], help="Execute a specific phase (1, 2, 3, 4, 5, or 7)")
    parser.add_argument("--agent", action="store_true", help="Execute InsureMate Agent Orchestrator (Phase 5)")
    parser.add_argument("--phase4", action="store_true", help="Execute Phase 4 Missing-Document Detector")
    parser.add_argument("--phase5", action="store_true", help="Execute Phase 5 InsureMate Agent Orchestrator")
    parser.add_argument("--phase7", "--serve", "--app", dest="serve", action="store_true", help="Launch the InsureMate Phase 7 Web Application & REST API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address for web server (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port for web server (default 8000)")
    parser.add_argument("--test-all", action="store_true", help="Execute all unit and integration test suites")
    parser.add_argument("--end-to-end", action="store_true", help="Execute full end-to-end pipeline on real documents")
    parser.add_argument("--policy", "-p", type=str, help="Target policy PDF file to process")
    parser.add_argument("--claim", "-c", type=str, help="Target claim documents PDF file to process")
    parser.add_argument("--pdf", type=str, help="Target PDF file to extract using Phase 1 tool")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages to extract from PDF (default 3)")
    parser.add_argument("--real", action="store_true", help="Execute complete analysis on real repository documents")
    parser.add_argument("--goal", type=str, help="Custom natural language goal for InsureMate Agent")
    parser.add_argument("--offline", action="store_true", help="Run agent in offline deterministic mode")

    args = parser.parse_args()

    default_policy = args.policy or (
        str(ROOT_DIR / "sample_policy.pdf") if (ROOT_DIR / "sample_policy.pdf").exists()
        else str(ROOT_DIR / "policy_A.pdf") if (ROOT_DIR / "policy_A.pdf").exists()
        else str(ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf") if (ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf").exists()
        else None
    )
    default_claim = args.claim or (
        str(ROOT_DIR / "sample_claim.pdf") if (ROOT_DIR / "sample_claim.pdf").exists()
        else str(ROOT_DIR / "claim_A.pdf") if (ROOT_DIR / "claim_A.pdf").exists()
        else str(ROOT_DIR / "DOCUMENTS FOR Re- activation REQUEST OF CLAIM NO.95151709.pdf") if (ROOT_DIR / "DOCUMENTS FOR Re- activation REQUEST OF CLAIM NO.95151709.pdf").exists()
        else None
    )

    if args.serve or args.phase == 7:
        run_phase_7(host=args.host, port=args.port)

    elif args.real:
        print("\n" + "=" * 80)
        print("          TESTING ON REAL REPOSITORY DOCUMENTS")
        print("================================================================================")
        success = run_end_to_end_test(policy_pdf=args.policy, claim_pdf=args.claim)
        sys.exit(0 if success else 1)

    elif args.test_all:
        print("\n=======================================================")
        print("          RUNNING COMPLETE TEST SUITE                 ")
        print("=======================================================")
        p1 = run_phase1_tests()
        p2 = run_phase2_tests()
        p3 = run_phase3_tests()
        p4 = run_phase4_all_tests()
        p5 = run_phase5_tests()
        pe2e = run_end_to_end_test(policy_pdf=args.policy, claim_pdf=args.claim)
        all_passed = p1 and p2 and p3 and p4 and p5 and pe2e
        print("\n=======================================================")
        print(f"OVERALL TEST SUITE STATUS: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        print("=======================================================")
        sys.exit(0 if all_passed else 1)

    elif args.agent or args.phase5 or args.phase == 5:
        target_policy = args.policy or default_policy
        target_claim = args.claim or default_claim
        run_phase_5(
            policy_pdf=target_policy,
            claim_pdf=target_claim,
            goal=args.goal,
            max_pages=args.max_pages,
            offline_mode=args.offline
        )

    elif args.end_to_end or (args.policy and args.claim):
        success = run_end_to_end_test(policy_pdf=args.policy, claim_pdf=args.claim)
        sys.exit(0 if success else 1)

    elif args.phase == 1:
        target_pdf = args.pdf or args.policy or default_policy
        run_phase_1(target_pdf, max_pages=args.max_pages)

    elif args.phase == 2:
        run_phase_2()

    elif args.phase == 3:
        run_phase_3()

    elif args.phase == 4 or args.phase4:
        target_policy = args.policy or default_policy
        print(f"Extracting policy evidence from: {target_policy}")
        phase1_data = run_phase_1(target_policy, max_pages=args.max_pages)
        run_phase_4(phase1_data=phase1_data)

    else:
        # Default run: Complete Agentic Demonstration
        print("Executing InsureMate Agent on repository documents...\n")
        target_policy = args.policy or default_policy
        target_claim = args.claim or default_claim
        run_phase_5(
            policy_pdf=target_policy,
            claim_pdf=target_claim,
            goal=args.goal,
            max_pages=args.max_pages,
            offline_mode=args.offline
        )


if __name__ == "__main__":
    main()

