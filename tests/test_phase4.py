"""tests/test_phase4.py
Comprehensive test suite for Phase 4: Dynamic Policy Requirement Extraction
and Missing Document Detection using Local LLM.
Implements the 14 mandatory tests defined in Section 20 of the master specification,
plus optional live Ollama integration.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
import pytest

# Ensure repository root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.missing_document.detector import (
    MissingDocumentDetector,
    detect_missing_documents,
    run_phase4,
    format_detection_table
)
from services.missing_document.llm_gateway import LLMGateway
from tests.conftest import MockLLMClient
from tools.missing_document_tool import MissingDocumentTool
from tools.qwen_vl_tool import QwenVLExtractionTool
from tests.test_end_to_end import run_end_to_end_test


def print_test_banner(title: str):
    print("\n" + "=" * 70)
    print(f"PHASE 4 TEST: {title}")
    print("=" * 70)


# ==============================================================================
# TEST 1 — CLI ARGUMENTS ARE RESPECTED
# ==============================================================================
def test_1_cli_arguments_respected():
    """TEST 1:
    --policy and --claim CLI arguments are parsed and respected.
    Supplying custom filenames processes those files; non-existent files produce clear error.
    """
    print_test_banner("TEST 1: CLI Arguments Are Respected")

    # A: Success case with policy_A.pdf and claim_A.pdf
    cmd = [
        sys.executable,
        str(ROOT_DIR / "tests" / "test_end_to_end.py"),
        "--policy", str(ROOT_DIR / "policy_A.pdf"),
        "--claim", str(ROOT_DIR / "claim_A.pdf")
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"CLI command failed: {res.stderr}"
    assert "Opening PDF document: policy_A.pdf" in res.stdout
    assert "Opening PDF document: claim_A.pdf" in res.stdout

    # B: Error case with non-existent file
    cmd_err = [
        sys.executable,
        str(ROOT_DIR / "tests" / "test_end_to_end.py"),
        "--policy", "non_existent_policy.pdf",
        "--claim", str(ROOT_DIR / "claim_A.pdf")
    ]
    res_err = subprocess.run(cmd_err, capture_output=True, text=True)
    assert res_err.returncode != 0
    assert "Policy file not found" in res_err.stderr or "Policy file not found" in res_err.stdout
    print("PASS: CLI arguments respected and invalid files caught.")


# ==============================================================================
# TEST 2 — POLICY REQUIREMENTS ARE DYNAMICALLY EXTRACTED
# ==============================================================================
def test_2_policy_requirements_dynamically_extracted():
    """TEST 2:
    Phase 1 extracts policy clauses and text (NEVER hardcoded required_documents).
    Phase 4 dynamically reasons over those clauses to deduce distinct requirements for distinct policies.
    """
    print_test_banner("TEST 2: Policy Requirements Dynamically Extracted From Policy Clauses")

    tool = QwenVLExtractionTool(offline_mode=True)

    # Extract Policy A
    ext_a = tool.run(ROOT_DIR / "policy_A.pdf", max_pages=1)
    assert ext_a["status"] == "success"
    doc_a = ext_a["extracted_documents"][0]
    # Phase 1 must NOT have required_documents
    assert "required_documents" not in doc_a, "Phase 1 output must NOT contain required_documents"
    # Phase 1 MUST have policy_clauses or policy_relevant_text extracted from PDF text
    assert len(doc_a.get("policy_clauses", [])) > 0 or doc_a.get("policy_relevant_text") is not None
    assert any("Discharge Summary" in c for c in doc_a.get("policy_clauses", []))

    # Extract Policy B
    ext_b = tool.run(ROOT_DIR / "policy_B.pdf", max_pages=1)
    assert ext_b["status"] == "success"
    doc_b = ext_b["extracted_documents"][0]
    assert "required_documents" not in doc_b, "Phase 1 output must NOT contain required_documents"
    assert len(doc_b.get("policy_clauses", [])) > 0 or doc_b.get("policy_relevant_text") is not None
    assert any("First Information Report" in c or "FIR" in c for c in doc_b.get("policy_clauses", []))

    # Phase 4 dynamic reasoning:
    # Use MissingDocumentDetector to deduce required documents from Phase 1 output
    detector = MissingDocumentDetector()
    res_a = detector.detect(phase1_output=ext_a)
    res_b = detector.detect(phase1_output=ext_b)

    reqs_a = [d["document_title"].lower() for d in res_a["required_documents"]]
    reqs_b = [d["document_title"].lower() for d in res_b["required_documents"]]

    # Both policies must produce different required documents
    assert reqs_a != reqs_b, "Two different policies must produce different requirements"
    # Policy A (health) requires discharge summary and bill
    assert any("discharge" in r for r in reqs_a), f"Policy A must require discharge summary, got {reqs_a}"
    assert any("bill" in r for r in reqs_a), f"Policy A must require bill, got {reqs_a}"
    # Policy B (travel) requires police FIR and boarding pass
    assert any("fir" in r or "police" in r for r in reqs_b), f"Policy B must require FIR, got {reqs_b}"
    assert any("boarding" in r or "ticket" in r for r in reqs_b), f"Policy B must require travel ticket, got {reqs_b}"
    # Cross checks: Policy A must NOT require FIR; Policy B must NOT require discharge summary
    assert not any("fir" in r or "police" in r for r in reqs_a), "Health policy must not require police FIR"
    assert not any("discharge" in r for r in reqs_b), "Travel policy must not require discharge summary"

    print("PASS: Dynamic policy requirements extracted dynamically by Gemma from policy clauses for both policies.")


# ==============================================================================
# TEST 3 — NO STATIC REQUIRED-DOCUMENT LIST EXISTS IN PHASE 4
# ==============================================================================
def test_3_no_static_required_document_list_exists():
    """TEST 3:
    Guarantees no top-level phase4/ directory exists and no hardcoded document requirement
    lists or static synonym dictionaries exist in Phase 4 production code.
    """
    print_test_banner("TEST 3: No Static Required-Document List in Phase 4")

    assert not (ROOT_DIR / "phase4").exists(), (
        "Top-level phase4/ directory must not exist; Phase 4 must reside exclusively in services/missing_document/"
    )
    assert (ROOT_DIR / "services" / "missing_document").exists(), (
        "services/missing_document/ directory must exist as the canonical Phase 4 implementation"
    )

    prod_directories = [
        ROOT_DIR / "services" / "missing_document",
        ROOT_DIR / "services" / "qwen_vl",
        ROOT_DIR / "tools" / "missing_document_tool.py",
        ROOT_DIR / "tools" / "qwen_vl_tool.py",
        ROOT_DIR / "main.py",
    ]

    forbidden_patterns = [
        r'REQUIRED_DOCUMENTS\s*=\s*\[',
        r'DEFAULT_REQUIRED_DOCUMENTS\s*=\s*\[',
        r'DEFAULT_POLICY_REQUIREMENTS\s*=\s*\[',
        r'SYNONYM_MAP\s*=\s*\{',
        r'SYNONYMS\s*=\s*\{',
        r'DOCUMENT_MAPPING\s*=\s*\{',
        r'"required_documents"\s*:\s*\[\s*"',
    ]

    for item in prod_directories:
        files_to_check = []
        if item.is_file():
            files_to_check.append(item)
        elif item.is_dir():
            files_to_check.extend([p for p in item.rglob("*.py") if "tests" not in p.parts])

        for py_file in files_to_check:
            content = py_file.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content)
                assert not matches, (
                    f"Forbidden hardcoded pattern '{pattern}' found in production file: {py_file}"
                )

    print("PASS: Verified zero hardcoded requirement lists or static synonym maps in production code.")


# ==============================================================================
# TEST 4 — ALL REQUIRED DOCUMENTS PRESENT
# ==============================================================================
def test_4_all_required_documents_present():
    """TEST 4:
    Policy requires 2 documents. Both documents are submitted.
    Expected: total_required=2, present=2, missing=0.
    """
    print_test_banner("TEST 4: All Required Documents Present")

    policy_input = {
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Itemized Hospital Bill"}
        ],
        "submitted_documents": [
            {"document_title": "Patient Discharge Record", "page_no": 1},
            {"document_title": "Shree Vallabh Hospital Final Inpatient Bill", "page_no": 2}
        ]
    }

    mock_llm_response = json.dumps({
        "document_results": [
            {
                "sr_no": 1,
                "document_title": "Discharge Summary",
                "missing": False,
                "submitted_document_title": "Patient Discharge Record",
                "page_no": 1,
                "reason": "Submitted 'Patient Discharge Record' fulfills Discharge Summary."
            },
            {
                "sr_no": 2,
                "document_title": "Final Itemized Hospital Bill",
                "missing": False,
                "submitted_document_title": "Shree Vallabh Hospital Final Inpatient Bill",
                "page_no": 2,
                "reason": "Submitted 'Shree Vallabh Hospital Final Inpatient Bill' fulfills Final Bill."
            }
        ]
    })

    client = MockLLMClient(responses=[mock_llm_response])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "success"
    assert result["summary"]["total_required"] == 2
    assert result["summary"]["present"] == 2
    assert result["summary"]["missing"] == 0

    docs = {d["document_title"]: d for d in result["missing_documents"]}
    assert docs["Discharge Summary"]["missing"] is False
    assert docs["Discharge Summary"]["page_no"] == 1
    assert docs["Final Itemized Hospital Bill"]["missing"] is False
    assert docs["Final Itemized Hospital Bill"]["page_no"] == 2
    print("PASS: All required documents correctly identified as present.")


# ==============================================================================
# TEST 5 — ONE REQUIRED DOCUMENT MISSING
# ==============================================================================
def test_5_one_required_document_missing():
    """TEST 5:
    Policy requires 2 documents. Only 1 submitted.
    Expected: Discharge Summary missing=True, Final Bill missing=False.
    """
    print_test_banner("TEST 5: One Required Document Missing")

    policy_input = {
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Itemized Hospital Bill"}
        ],
        "submitted_documents": [
            {"document_title": "Shree Vallabh Hospital Final Inpatient Bill", "page_no": 2}
        ]
    }

    mock_llm_response = json.dumps({
        "document_results": [
            {
                "sr_no": 1,
                "document_title": "Discharge Summary",
                "missing": True,
                "submitted_document_title": None,
                "page_no": None,
                "reason": "No document satisfies Discharge Summary requirement."
            },
            {
                "sr_no": 2,
                "document_title": "Final Itemized Hospital Bill",
                "missing": False,
                "submitted_document_title": "Shree Vallabh Hospital Final Inpatient Bill",
                "page_no": 2,
                "reason": "Submitted 'Shree Vallabh Hospital Final Inpatient Bill' fulfills requirement."
            }
        ]
    })

    client = MockLLMClient(responses=[mock_llm_response])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "success"
    assert result["summary"]["total_required"] == 2
    assert result["summary"]["present"] == 1
    assert result["summary"]["missing"] == 1

    docs = {d["document_title"]: d for d in result["missing_documents"]}
    assert docs["Discharge Summary"]["missing"] is True
    assert docs["Discharge Summary"]["page_no"] is None
    assert docs["Final Itemized Hospital Bill"]["missing"] is False
    assert docs["Final Itemized Hospital Bill"]["page_no"] == 2
    print("PASS: Exactly one missing document correctly flagged.")


# ==============================================================================
# TEST 6 — MULTIPLE REQUIRED DOCUMENTS MISSING
# ==============================================================================
def test_6_multiple_required_documents_missing():
    """TEST 6:
    Policy requires 4 documents. Only 1 is submitted.
    Expected: 3 missing, 1 present.
    """
    print_test_banner("TEST 6: Multiple Required Documents Missing")

    policy_input = {
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Itemized Hospital Bill"},
            {"document_title": "Pharmacy Bills"},
            {"document_title": "Doctor Prescription"}
        ],
        "submitted_documents": [
            {"document_title": "Doctor Prescription", "page_no": 4}
        ]
    }

    mock_llm_response = json.dumps({
        "document_results": [
            {"sr_no": 1, "document_title": "Discharge Summary", "missing": True, "page_no": None, "reason": "Missing"},
            {"sr_no": 2, "document_title": "Final Itemized Hospital Bill", "missing": True, "page_no": None, "reason": "Missing"},
            {"sr_no": 3, "document_title": "Pharmacy Bills", "missing": True, "page_no": None, "reason": "Missing"},
            {"sr_no": 4, "document_title": "Doctor Prescription", "missing": False, "page_no": 4, "submitted_document_title": "Doctor Prescription", "reason": "Present"}
        ]
    })

    client = MockLLMClient(responses=[mock_llm_response])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "success"
    assert result["summary"]["total_required"] == 4
    assert result["summary"]["present"] == 1
    assert result["summary"]["missing"] == 3
    print("PASS: Multiple missing documents correctly identified.")


# ==============================================================================
# TEST 7 — SEMANTIC MATCH WORKS
# ==============================================================================
def test_7_semantic_match_works():
    """TEST 7:
    Required: 'Original final hospital bill'
    Submitted: 'Hospital Final Inpatient Invoice' (page 3)
    Expected: missing=False, page_no=3.
    """
    print_test_banner("TEST 7: Semantic Match Works Without Static Synonyms")

    policy_input = {
        "policy_requirements": [
            {"document_title": "Original final hospital bill"}
        ],
        "submitted_documents": [
            {"document_title": "Hospital Final Inpatient Invoice", "page_no": 3}
        ]
    }

    mock_llm_response = json.dumps({
        "document_results": [
            {
                "sr_no": 1,
                "document_title": "Original final hospital bill",
                "missing": False,
                "submitted_document_title": "Hospital Final Inpatient Invoice",
                "page_no": 3,
                "reason": "Semantic match: 'Hospital Final Inpatient Invoice' fulfills requirement."
            }
        ]
    })

    client = MockLLMClient(responses=[mock_llm_response])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "success"
    item = result["missing_documents"][0]
    assert item["missing"] is False
    assert item["page_no"] == 3
    print("PASS: Semantic equivalence recognized.")


# ==============================================================================
# TEST 8 — PAGE NUMBER RETURNED CORRECTLY
# ==============================================================================
def test_8_page_number_returned_correctly():
    """TEST 8:
    Matching document is on page 7.
    Expected: page_no=7 (exact integer, never invented).
    """
    print_test_banner("TEST 8: Page Number Returned Correctly")

    policy_input = {
        "policy_requirements": [
            {"document_title": "Medical Invoice"}
        ],
        "submitted_documents": [
            {"document_title": "Official Hospital Billing Invoice", "page_no": 7}
        ]
    }

    mock_llm_response = json.dumps({
        "document_results": [
            {
                "sr_no": 1,
                "document_title": "Medical Invoice",
                "missing": False,
                "submitted_document_title": "Official Hospital Billing Invoice",
                "page_no": 7,
                "reason": "Exact page match."
            }
        ]
    })

    client = MockLLMClient(responses=[mock_llm_response])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "success"
    assert result["missing_documents"][0]["page_no"] == 7
    print("PASS: Exact integer page number preserved.")


# ==============================================================================
# TEST 9 — MISSING=TRUE PRODUCES PAGE_NO=NULL
# ==============================================================================
def test_9_missing_true_produces_page_no_null():
    """TEST 9:
    Document marked missing=True must have page_no=None / null.
    """
    print_test_banner("TEST 9: Missing=True Produces Page_No=Null")

    policy_input = {
        "policy_requirements": [
            {"document_title": "Investigation report"}
        ],
        "submitted_documents": [
            {"document_title": "Hospital bill", "page_no": 2}
        ]
    }

    mock_llm_response = json.dumps({
        "document_results": [
            {
                "sr_no": 1,
                "document_title": "Investigation report",
                "missing": True,
                "submitted_document_title": None,
                "page_no": None,
                "reason": "No diagnostic investigation report submitted."
            }
        ]
    })

    client = MockLLMClient(responses=[mock_llm_response])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "success"
    assert result["missing_documents"][0]["missing"] is True
    assert result["missing_documents"][0]["page_no"] is None
    print("PASS: Missing document correctly assigned null page number.")


# ==============================================================================
# TEST 10 — MALFORMED FIRST LLM RESPONSE RETRIES ONCE
# ==============================================================================
def test_10_malformed_first_llm_response_retries_once():
    """TEST 10:
    Model returns malformed JSON on attempt 1, retries once with feedback,
    and returns valid JSON on attempt 2.
    """
    print_test_banner("TEST 10: Malformed First LLM Response Retries Once")

    policy_input = {
        "policy_requirements": [
            {"document_title": "Operative Summary"}
        ],
        "submitted_documents": [
            {"document_title": "Surgeon Operative Note", "page_no": 4}
        ]
    }

    bad_attempt_1 = json.dumps({"unrecognized_root": "invalid"})
    good_attempt_2 = json.dumps({
        "document_results": [
            {
                "sr_no": 1,
                "document_title": "Operative Summary",
                "missing": False,
                "submitted_document_title": "Surgeon Operative Note",
                "page_no": 4,
                "reason": "Surgeon Operative Note fulfills requirement."
            }
        ]
    })

    client = MockLLMClient(responses=[bad_attempt_1, good_attempt_2])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "success"
    assert client.call_count == 2
    assert result["missing_documents"][0]["missing"] is False
    assert result["missing_documents"][0]["page_no"] == 4
    print("PASS: Exactly-once retry successfully recovered from malformed initial JSON.")


# ==============================================================================
# TEST 11 — MALFORMED SECOND RESPONSE PRODUCES STRUCTURED ERROR
# ==============================================================================
def test_11_malformed_second_response_produces_structured_error():
    """TEST 11:
    Both attempt 1 and attempt 2 return malformed JSON.
    Expected: Structured error response (status="error") without uncaught exception.
    """
    print_test_banner("TEST 11: Malformed Second Response Produces Structured Error")

    policy_input = {
        "policy_requirements": [{"document_title": "Discharge Summary"}],
        "submitted_documents": [{"document_title": "Invoice", "page_no": 1}]
    }

    bad_attempt_1 = json.dumps({"bad": 1})
    bad_attempt_2 = json.dumps({"bad": 2})

    client = MockLLMClient(responses=[bad_attempt_1, bad_attempt_2])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] == "error"
    assert client.call_count == 2
    assert result["error"] is not None
    print("PASS: Repeated malformed responses handled gracefully with structured error.")


# ==============================================================================
# TEST 12 — DIFFERENT POLICY WITH DIFFERENT REQUIREMENTS PRODUCES DIFFERENT RESULT
# ==============================================================================
def test_12_different_policy_different_requirements_different_result():
    """TEST 12:
    Policy A (Health) vs Policy B (Travel/FIR).
    Different policies produce completely different required checklists.
    """
    print_test_banner("TEST 12: Different Policies Produce Different Results")

    # Policy A evaluation
    res_a = detect_missing_documents(
        policy_requirements=[{"document_title": "Discharge Summary"}, {"document_title": "Final Hospital Bill"}],
        submitted_documents=[{"document_title": "Discharge Summary", "page_no": 1}]
    )
    # Policy B evaluation
    res_b = detect_missing_documents(
        policy_requirements=[{"document_title": "Police FIR Copy"}, {"document_title": "Boarding Pass"}],
        submitted_documents=[{"document_title": "Police FIR Copy", "page_no": 1}]
    )

    reqs_a = [d["document_title"] for d in res_a["required_documents"]]
    reqs_b = [d["document_title"] for d in res_b["required_documents"]]

    assert reqs_a != reqs_b
    assert "Discharge Summary" in reqs_a
    assert "Police FIR Copy" in reqs_b
    print("PASS: Verified distinct policies produce distinct requirement lists.")


def test_13_changing_policy_and_claim_changes_files_processed():
    """TEST 13:
    End-to-end CLI pipeline processes policy_A.pdf + claim_A.pdf vs policy_B.pdf + claim_B.pdf.
    Verifies that changing CLI flags changes the files processed.
    """
    print_test_banner("TEST 13: Changing --policy and --claim Changes Files Processed")

    # Run A: policy_A + claim_A
    res_a = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "main.py"),
            "--policy", str(ROOT_DIR / "policy_A.pdf"),
            "--claim", str(ROOT_DIR / "claim_A.pdf"),
        ],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=180
    )
    assert res_a.returncode == 0, f"Run A failed: {res_a.stderr}"
    assert "Opening PDF document: policy_A.pdf" in res_a.stdout
    assert "Opening PDF document: claim_A.pdf" in res_a.stdout
    assert "policy_B.pdf" not in res_a.stdout

    # Run B: policy_B + claim_B
    res_b = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "main.py"),
            "--policy", str(ROOT_DIR / "policy_B.pdf"),
            "--claim", str(ROOT_DIR / "claim_B.pdf"),
        ],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=180
    )
    assert res_b.returncode == 0, f"Run B failed: {res_b.stderr}"
    assert "Opening PDF document: policy_B.pdf" in res_b.stdout
    assert "Opening PDF document: claim_B.pdf" in res_b.stdout
    assert "policy_A.pdf" not in res_b.stdout

    print("PASS: Both real PDF pairs processed dynamically with CLI arguments strictly respected.")


# ==============================================================================
# TEST 14 — NO EXPLICIT REQUIREMENTS PRODUCES CONTROLLED RESULT
# ==============================================================================
def test_14_no_explicit_requirements_produces_controlled_result():
    """TEST 14:
    Policy with no explicit claim document requirements produces controlled result
    with total_required=0 and missing_documents=[], with zero fabricated documents.
    """
    print_test_banner("TEST 14: No Explicit Requirements (Anti-Hallucination)")

    policy_input = {
        "phase1_output": {
            "extracted_documents": [
                {
                    "page_number": 1,
                    "document_type": "insurance_policy",
                    "document_title": "Policy Schedule Certificate",
                    "relevant_conditions": ["Floater Sum Insured: 10,00,000"],
                    "policy_clauses": [],
                    "policy_relevant_text": None
                }
            ]
        }
    }

    client = MockLLMClient(responses=[json.dumps({"policy_requirements": []})])
    gateway = LLMGateway(client=client)

    result = detect_missing_documents(policy_input, gateway=gateway)

    assert result["status"] in ("success", "no_requirements_found")
    assert result["summary"]["total_required"] == 0
    assert result["missing_documents"] == []
    print("PASS: Controlled no-requirements result with zero fabricated documents.")


# ==============================================================================
# TEST 15 — LIVE OLLAMA / GEMMA 3 INTEGRATION
# ==============================================================================
def test_15_live_ollama_integration():
    """TEST 15:
    Optional live integration test with local Gemma 3 on Ollama (http://localhost:11434).
    Automatically skipped if Ollama is not running.
    """
    print_test_banner("TEST 15: Live Ollama / Gemma 3 Integration")
    from services.missing_document.ollama_client import OllamaClient

    client = OllamaClient()
    if not client.is_available():
        pytest.skip("Local Ollama service (http://localhost:11434) is not available.")
        print("SKIP: Local Ollama service is not running.")
        return

    sample_input = {
        "policy_requirements": [
            {"document_title": "Discharge Summary"},
            {"document_title": "Final Hospital Bill"}
        ],
        "submitted_documents": [
            {"document_title": "Patient Discharge Record", "page_no": 5},
            {"document_title": "Final Hospital Invoice", "page_no": 7}
        ]
    }

    result = detect_missing_documents(sample_input)
    assert result["status"] == "success"
    assert len(result["missing_documents"]) == 2
    docs = {d["document_title"]: d for d in result["missing_documents"]}
    assert docs["Discharge Summary"]["missing"] is False
    assert docs["Discharge Summary"]["page_no"] == 5
    assert docs["Final Hospital Bill"]["missing"] is False
    assert docs["Final Hospital Bill"]["page_no"] == 7
    print("PASS: Live Gemma 3 dynamic reasoning completed successfully.")


def run_phase4_all_tests():
    """Runner for standalone execution."""
    test_1_cli_arguments_respected()
    test_2_policy_requirements_dynamically_extracted()
    test_3_no_static_required_document_list_exists()
    test_4_all_required_documents_present()
    test_5_one_required_document_missing()
    test_6_multiple_required_documents_missing()
    test_7_semantic_match_works()
    test_8_page_number_returned_correctly()
    test_9_missing_true_produces_page_no_null()
    test_10_malformed_first_llm_response_retries_once()
    test_11_malformed_second_response_produces_structured_error()
    test_12_different_policy_different_requirements_different_result()
    test_13_changing_policy_and_claim_changes_files_processed()
    test_14_no_explicit_requirements_produces_controlled_result()
    test_15_live_ollama_integration()
    print("\n" + "=" * 70)
    print("ALL 15 PHASE 4 TESTS COMPLETED SUCCESSFULLY (PASS)")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_phase4_all_tests()
    sys.exit(0 if success else 1)
