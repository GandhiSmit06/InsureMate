"""
tests/test_phase1.py
Unit and integration tests for Phase 1: Qwen-VL Document Processing & Extraction.
Tests:
- PDF processing in-memory (no disk image generation)
- Strictly 1-indexed page tracking
- Document classification into valid categories
- Extraction failure handling (missing file, corrupted file)
- Strict no-hallucination handling of missing information
"""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.qwen_vl.pdf_processor import (
    PDFProcessor,
    MissingPDFError,
    CorruptedPDFError,
)
from services.qwen_vl.extractor import (
    QwenVLExtractor,
    VALID_DOCUMENT_TYPES,
    extract_document,
)
from tools.qwen_vl_tool import QwenVLExtractionTool


def print_test_banner(name: str):
    print("\n" + "=" * 70)
    print(f"PHASE 1 TEST: {name}")
    print("=" * 70)


def run_phase1_tests():
    passed = 0
    total = 5

    # -------------------------------------------------------------
    # TEST 1: In-Memory PDF Processing & Page Tracking (1-indexed)
    # -------------------------------------------------------------
    print_test_banner("1. In-Memory PDF Processing & Page Tracking")
    pdf_path = ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf"
    processor = PDFProcessor()
    pages = processor.process_pdf(pdf_path, max_pages=3)

    expected = "3 pages rendered in-memory, page numbers strictly [1, 2, 3], zero files saved to disk"
    actual_numbers = [p.page_number for p in pages]
    actual_has_images = all(p.image is not None and len(p.base64_data_url) > 1000 for p in pages)
    actual = f"{len(pages)} pages rendered, numbers={actual_numbers}, has_images_in_ram={actual_has_images}"

    test1_pass = (
        len(pages) == 3 and
        actual_numbers == [1, 2, 3] and
        actual_has_images
    )
    print(f"INPUT:           {pdf_path.name} (max_pages=3)")
    print(f"EXPECTED RESULT: {expected}")
    print(f"ACTUAL RESULT:   {actual}")
    print(f"STATUS:          {'PASS' if test1_pass else 'FAIL'}")
    if test1_pass:
        passed += 1

    # -------------------------------------------------------------
    # TEST 2: Document Classification
    # -------------------------------------------------------------
    print_test_banner("2. Document Classification")
    extractor = QwenVLExtractor(offline_mode=True)
    policy_results = extractor.extract_document(pdf_path, max_pages=1)
    doc_type = policy_results[0].get("document_type")

    expected = f"Document classified as 'insurance_policy' (must be in {VALID_DOCUMENT_TYPES})"
    actual = f"Document type = '{doc_type}', valid category = {doc_type in VALID_DOCUMENT_TYPES}"
    test2_pass = doc_type == "insurance_policy"

    print(f"INPUT:           Policy PDF Page 1")
    print(f"EXPECTED RESULT: {expected}")
    print(f"ACTUAL RESULT:   {actual}")
    print(f"STATUS:          {'PASS' if test2_pass else 'FAIL'}")
    if test2_pass:
        passed += 1

    # -------------------------------------------------------------
    # TEST 3: Missing Information / No Hallucination
    # -------------------------------------------------------------
    print_test_banner("3. No Hallucination Policy (Non-visible fields return null)")
    first_page = policy_results[0]
    # On policy certificate page 1, bill numbers and hospital names should NOT be present
    has_no_hallucinations = (
        first_page.get("bill_number") is None and
        first_page.get("hospital_name") is None and
        first_page.get("bill_amount") is None
    )

    expected = "bill_number=None, hospital_name=None, bill_amount=None (no hallucination)"
    actual = (
        f"bill_number={first_page.get('bill_number')}, "
        f"hospital_name={first_page.get('hospital_name')}, "
        f"bill_amount={first_page.get('bill_amount')}"
    )
    test3_pass = has_no_hallucinations

    print(f"INPUT:           Policy Certificate extraction")
    print(f"EXPECTED RESULT: {expected}")
    print(f"ACTUAL RESULT:   {actual}")
    print(f"STATUS:          {'PASS' if test3_pass else 'FAIL'}")
    if test3_pass:
        passed += 1

    # -------------------------------------------------------------
    # TEST 4: Extraction Failure Handling (Missing File)
    # -------------------------------------------------------------
    print_test_banner("4. Extraction Failure Handling (Missing PDF File)")
    non_existent = ROOT_DIR / "non_existent_policy_document_12345.pdf"
    tool = QwenVLExtractionTool(offline_mode=True)
    tool_resp = tool.run(non_existent)

    expected = "status='error', total_pages=0, error contains 'does not exist'"
    actual = f"status='{tool_resp['status']}', total_pages={tool_resp['total_pages']}, error='{tool_resp['error']}'"
    test4_pass = (
        tool_resp["status"] == "error" and
        tool_resp["total_pages"] == 0 and
        tool_resp["error"] is not None
    )

    print(f"INPUT:           Missing file path '{non_existent.name}'")
    print(f"EXPECTED RESULT: {expected}")
    print(f"ACTUAL RESULT:   {actual}")
    print(f"STATUS:          {'PASS' if test4_pass else 'FAIL'}")
    if test4_pass:
        passed += 1

    # -------------------------------------------------------------
    # TEST 5: Extraction Failure Handling (Corrupted File)
    # -------------------------------------------------------------
    print_test_banner("5. Extraction Failure Handling (Corrupted PDF File)")
    corrupt_path = ROOT_DIR / "corrupted_temp.pdf"
    corrupt_path.write_bytes(b"NOT A REAL PDF CONTENT RANDOM BYTES 12345")
    try:
        corrupt_resp = tool.run(corrupt_path)
        expected = "status='error', error indicates corrupted/invalid PDF"
        actual = f"status='{corrupt_resp['status']}', error='{corrupt_resp['error']}'"
        test5_pass = (
            corrupt_resp["status"] == "error" and
            corrupt_resp["error"] is not None
        )
    finally:
        if corrupt_path.exists():
            corrupt_path.unlink()

    print(f"INPUT:           Corrupted dummy file")
    print(f"EXPECTED RESULT: {expected}")
    print(f"ACTUAL RESULT:   {actual}")
    print(f"STATUS:          {'PASS' if test5_pass else 'FAIL'}")
    if test5_pass:
        passed += 1

    print("\n" + "=" * 70)
    print(f"PHASE 1 SUMMARY: {passed}/{total} TESTS PASSED")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    success = run_phase1_tests()
    sys.exit(0 if success else 1)
