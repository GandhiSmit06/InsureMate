"""tests/test_master_fixes.py
Comprehensive verification of all Master Prompt fixes:
1. Concurrency Lock & Idempotent Agent Execution (duplicate run returns 409 / prevents parallel runs)
2. Real Scanned PDF OCR & Information Extraction on 4225IELVT38453879200000_policy_copy.pdf
3. Document Classification (Identified as insurance_policy, not hospital_document)
4. No Fabricated Fallback Data (Real ICICI Lombard policy details, no fake POL-2025-00123)
5. Dynamic Missing Document Detection returns named titles, never generic 'Evidence Document'
"""

import sys
import tempfile
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.agent_service import AgentService
from services.qwen_vl.extractor import QwenVLExtractor
from services.qwen_vl.pdf_processor import PDFProcessor
from services.missing_document.detector import MissingDocumentDetector


POLICY_PDF = ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf"


def test_concurrency_lock_prevents_duplicate_runs():
    """Verify that execution locks prevent concurrent agent executions on the same claim."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        service = AgentService(db_path=Path(tmp_dir) / "test.db", upload_dir=Path(tmp_dir) / "uploads")
        claim_id = "CLM-TEST-LOCK-001"
        
        # Initial state: not running
        assert not service.is_claim_running(claim_id)
        
        # First acquisition succeeds
        assert service.acquire_claim_lock(claim_id) is True
        assert service.is_claim_running(claim_id) is True
        
        # Second acquisition for same claim MUST fail (prevent duplicate run)
        assert service.acquire_claim_lock(claim_id) is False
        
        # Release lock
        service.release_claim_lock(claim_id)
        assert not service.is_claim_running(claim_id)
        
        # Re-acquisition succeeds
        assert service.acquire_claim_lock(claim_id) is True
        service.release_claim_lock(claim_id)


def test_real_pdf_ocr_extraction_and_classification():
    """Verify that 4225IELVT38453879200000_policy_copy.pdf is correctly processed via OCR,
    classified as insurance_policy, and extracts true policy details rather than fake placeholders.
    """
    assert POLICY_PDF.exists(), f"Diagnostic file {POLICY_PDF} must exist"
    
    processor = PDFProcessor()
    # Process first 4 pages
    pages = processor.process_pdf(POLICY_PDF, max_pages=4)
    assert len(pages) == 4
    
    # Verify OCR text was extracted from the scanned pages
    assert len(pages[0].text.strip()) > 50, "Page 1 OCR text must be populated by OCR engine"
    
    extractor = QwenVLExtractor(offline_mode=True)
    results = extractor.extract_document(POLICY_PDF, max_pages=4)
    
    p1 = results[0]
    p3 = results[2]
    p4 = results[3]
    
    # 1. Document classification must be insurance_policy
    assert p1["document_type"] == "insurance_policy", f"Expected insurance_policy, got {p1['document_type']}"
    
    # 2. Insurer must be ICICI Lombard
    assert p1.get("insurer_name") == "ICICI Lombard", f"Expected ICICI Lombard, got {p1.get('insurer_name')}"
    
    # 3. Policy number must be the real policy number, NEVER fake POL-2025-00123
    assert p1.get("policy_number") == "4225i/ELVT/384538792/00/000", f"Unexpected policy number: {p1.get('policy_number')}"
    assert "POL-2025-00123" not in str(p1.get("policy_number")), "Must not contain fake fallback policy number!"
    
    # 4. Policy holder / insured must be Pathak Maulikkumar
    assert "Pathak Maulikkumar" in str(p1.get("policy_holder_name")) or any("Pathak Maulikkumar" in n for n in p1.get("insured_names", []))
    
    # 5. Coverage dates must be extracted on the policy schedule page (Page 3)
    assert p3.get("policy_start_date") == "12/03/2025"
    assert p3.get("policy_end_date") == "11/03/2028"
    
    # 6. Sum insured must be 10,00,000 on the insured details page (Page 4)
    assert p4.get("sum_insured") == "10,00,000"


def test_missing_document_detector_uses_real_document_titles():
    """Verify that MissingDocumentDetector outputs named document titles and aliases,
    preventing any fallback to generic 'Evidence Document' in the UI.
    """
    phase1_output = {
        "status": "success",
        "extracted_documents": [
            {
                "page_number": 1,
                "document_type": "insurance_policy",
                "document_title": "ICICI Lombard Elevate Policy Schedule",
                "policy_clauses": [
                    "1. Original Discharge Summary with hospital seal and admission/discharge timestamps.",
                    "2. Final Itemized Hospital Bill with break-up of room rent and surgical charges.",
                    "3. Diagnostic and laboratory reports supporting medical necessity."
                ]
            }
        ]
    }
    
    detector = MissingDocumentDetector()
    res = detector.detect(phase1_output=phase1_output, submitted_documents=[])
    
    reqs = res["required_documents"]
    assert len(reqs) >= 2
    
    for req in reqs:
        # Title must not be generic 'Evidence Document'
        title = req.get("document_title") or req.get("required_document") or req.get("document_name")
        assert title is not None and title.strip() != ""
        assert title != "Evidence Document", f"Document title must be a specific name, got {title}"
        assert any(term in title.lower() for term in ["discharge", "bill", "invoice", "summary", "report", "diagnostic"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
