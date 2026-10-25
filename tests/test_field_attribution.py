"""tests/test_field_attribution.py
Regression test suite for page-level OCR field attribution in InsureMate.

Validates the 10 requirements:
1. Multi-page policy where the policy schedule contains the sum insured but the exclusions page does not.
2. A document with different titles on different pages.
3. A policy number repeated across multiple pages or document-level provenance.
4. A heading containing an insurer's brand name but not identifying the insurer.
5. A page with no sum insured field returns None (not small integers or section numbers).
6. A scanned multi-page policy using the existing OCR pipeline.
7. A page with tables, headers, footers, and page numbers does not confuse table indexes for coverage.
8. A PDF with an unfamiliar insurer or layout.
9. Correct propagation of page numbers and field provenance through the API.
10. Correct frontend mapping of page-specific and document-level fields.
"""

import sys
import json
import subprocess
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.qwen_vl.extractor import QwenVLExtractor
from services.qwen_vl.pdf_processor import PDFProcessor, PDFPage


POLICY_PDF = ROOT_DIR / "4225IELVT38453879200000_policy_copy.pdf"
if not POLICY_PDF.exists():
    _candidates = list(ROOT_DIR.glob("uploads/**/4225IELVT38453879200000_policy_copy.pdf"))
    if _candidates:
        POLICY_PDF = _candidates[0]


def test_1_and_5_and_6_scanned_multipage_policy_schedule_vs_exclusions():
    """Requirement 1, 5, 6:
    Multi-page scanned policy where schedule contains sum insured (Page 4)
    but exclusions page (Page 2) does not fabricate or copy sum insured.
    """
    assert POLICY_PDF.exists(), f"Policy PDF {POLICY_PDF} must exist"
    
    extractor = QwenVLExtractor(offline_mode=True)
    results = extractor.extract_document(POLICY_PDF, max_pages=4)
    assert len(results) >= 4
    
    p1 = results[0]
    p2 = results[1]
    p3 = results[2]
    p4 = results[3]
    
    # Page 1: Policy schedule / Certificate
    assert "Schedule" in p1["document_title"] or "Certificate" in p1["document_title"]
    assert p1.get("insurer_name") == "ICICI Lombard"
    assert p1.get("sum_insured") is None, "Page 1 schedule intro must not falsely fabricate sum insured"
    
    # Page 2: General Exclusions
    assert "Exclusion" in p2["document_title"]
    assert p2.get("sum_insured") is None, "Page 2 exclusions must NOT capture '3' as sum insured"
    assert p2.get("insurer_name") is None, "Page 2 must NOT swallow heading as insurer name"
    
    # Page 4: Schedule with Insured Details & Sum Insured
    assert p4.get("sum_insured") == "10,00,000", f"Expected '10,00,000', got {p4.get('sum_insured')}"


def test_2_different_titles_on_different_pages():
    """Requirement 2: Different pages in the same PDF must identify distinct titles."""
    assert POLICY_PDF.exists(), f"Policy PDF {POLICY_PDF} must exist"
    
    extractor = QwenVLExtractor(offline_mode=True)
    results = extractor.extract_document(POLICY_PDF, max_pages=3)
    
    titles = [r["document_title"] for r in results]
    assert len(set(titles)) == len(titles), f"Each page must have a distinct page-level title: {titles}"
    assert "Page 1" in titles[0]
    assert "Page 2" in titles[1]
    assert "Page 3" in titles[2]


def test_3_policy_number_repeated_or_document_level_provenance():
    """Requirement 3: Policy number retains provenance and document-level flag."""
    extractor = QwenVLExtractor(offline_mode=True)
    text = "Certificate of Insurance Policy No: 1122/3344/5566. Coverage Details..."
    page = PDFPage(page_number=1, width=600, height=800, image=None, base64_data_url="", text=text)
    
    res = extractor.extract_page(page, filename_hint="sample_policy.pdf")
    
    assert res.policy_number == "1122/3344/5566"
    assert "policy_number" in res.field_provenance
    prov = res.field_provenance["policy_number"]
    assert prov["page_number"] == 1
    assert prov["extracted_value"] == "1122/3344/5566"
    assert "1122/3344/5566" in prov["evidence"]


def test_4_heading_containing_brand_name_not_identified_as_insurer():
    """Requirement 4: Section headings containing an insurer's name or word
    (e.g., '1 Key Features Overview Lombard') must NOT become insurer name.
    """
    extractor = QwenVLExtractor(offline_mode=True)
    
    # Heading with brand word
    heading_text = """
    1 Key Features Overview Lombard
    The policy provides comprehensive coverage for hospitalization.
    Section 2: Exclusions and waiting periods.
    """
    page_heading = PDFPage(page_number=2, width=600, height=800, image=None, base64_data_url="", text=heading_text)
    res_heading = extractor.extract_page(page_heading, filename_hint="policy.pdf")
    assert res_heading.insurer_name is None, f"Heading text must not be recognized as insurer, got: {res_heading.insurer_name}"
    
    # Legitimate corporate insurer name in text
    valid_text = """
    This policy is issued by ICICI Lombard General Insurance Company Ltd.
    Registered office: Mumbai, Maharashtra.
    """
    page_valid = PDFPage(page_number=1, width=600, height=800, image=None, base64_data_url="", text=valid_text)
    res_valid = extractor.extract_page(page_valid, filename_hint="policy.pdf")
    assert "ICICI Lombard" in str(res_valid.insurer_name), f"Expected 'ICICI Lombard' in insurer name, got: {res_valid.insurer_name}"


def test_7_table_headers_footers_page_numbers_not_confused_for_coverage():
    """Requirement 7: Numbers in tables, footers, or waiting periods must not
    be confused for sum insured.
    """
    extractor = QwenVLExtractor(offline_mode=True)
    
    text_with_tables_and_footers = """
    TABLE OF BENEFITS
    Item No | Coverage Clause | Limit
    1       | Room Rent       | Standard Single Room
    2       | ICU Charges     | Up to Sum Insured. 3 Years waiting period
    3       | Pre-existing    | Covered after 90 Days
    
    Footer: Page 2 of 12 | Form ID: 44
    """
    
    page = PDFPage(page_number=2, width=600, height=800, image=None, base64_data_url="", text=text_with_tables_and_footers)
    res = extractor.extract_page(page, filename_hint="policy.pdf")
    assert res.sum_insured is None, f"Small integers (1, 2, 3, 90, 44) must NOT be captured as sum insured, got: {res.sum_insured}"


def test_8_unfamiliar_insurer_and_layout_generalization():
    """Requirement 8: Generalizes to unfamiliar insurers and formats without hardcoding."""
    extractor = QwenVLExtractor(offline_mode=True)
    
    text_unfamiliar = """
    HEALTH CARE POLICY SCHEDULE
    Insurer Name: Apex Global Assurance Limited
    Proposer: Rajesh Sharma
    Sum Insured: ₹ 7,50,000
    Policy Period: 01/01/2026 to 31/12/2026
    """
    
    page = PDFPage(page_number=1, width=600, height=800, image=None, base64_data_url="", text=text_unfamiliar)
    res = extractor.extract_page(page, filename_hint="apex_policy.pdf")
    
    assert res.insurer_name == "Apex Global Assurance Limited", f"Got: {res.insurer_name}"
    assert res.sum_insured == "7,50,000", f"Got: {res.sum_insured}"
    assert res.policy_holder_name == "Rajesh Sharma", f"Got: {res.policy_holder_name}"


def test_9_provenance_propagation_in_page_extraction_result():
    """Requirement 9: Field provenance is stored and propagated accurately for every extracted field."""
    extractor = QwenVLExtractor(offline_mode=True)
    text = """
    Insurer: Care Health Insurance
    Policy No: CH-99887766
    Sum Insured: Rs. 5,00,000
    Valid From: 01/04/2025 To: 31/03/2026
    """
    page = PDFPage(page_number=3, width=600, height=800, image=None, base64_data_url="", text=text)
    res = extractor.extract_page(page, filename_hint="care_policy.pdf")
    d = res.to_dict()
    
    assert "field_provenance" in d
    prov = d["field_provenance"]
    
    assert "insurer_name" in prov
    assert prov["insurer_name"]["page_number"] == 3
    assert prov["insurer_name"]["extracted_value"] == "Care Health Insurance"
    
    assert "sum_insured" in prov
    assert prov["sum_insured"]["page_number"] == 3
    assert prov["sum_insured"]["extracted_value"] == "5,00,000"
    
    assert "policy_start_date" in prov
    assert prov["policy_start_date"]["extracted_value"] == "01/04/2025"


def test_10_frontend_api_provenance_normalization():
    """Requirement 10: Frontend normalization preserves page-specific provenance
    and does not conflate pages into a single card.
    """
    # Run node verification script executing frontend/js/api.js normalizeAnalysisResponse logic
    node_script = """
    const fs = require('fs');
    global.document = {
      querySelector: () => null
    };
    global.window = {
      location: { protocol: 'http:' }
    };
    const apiCode = fs.readFileSync('frontend/js/api.js', 'utf8');
    eval(apiCode);
    
    const mockBackendResponse = {
      claim_id: 'CLM-TEST-001',
      status: 'success',
      extracted_pages: [
        {
          document_type: 'insurance_policy',
          document_title: 'Policy Schedule & Certificate (Page 1)',
          page_number: 1,
          insurer_name: 'ICICI Lombard',
          policy_holder_name: 'Pathak Maulikkumar',
          policy_number: '4225i/ELVT/384538792/00/000',
          field_provenance: {
            insurer_name: { page_number: 1, evidence: 'ICICI Lombard', is_document_level: false },
            policy_number: { page_number: 1, evidence: '4225i/...', is_document_level: true }
          }
        },
        {
          document_type: 'insurance_policy',
          document_title: 'Policy General Exclusions (Page 2)',
          page_number: 2,
          // Page 2 has no sum insured and no insurer
          field_provenance: {}
        }
      ]
    };
    
    const normalized = window.API.normalizeAnalysisResponse(mockBackendResponse);
    const fields = normalized.fields || [];
    
    // 1. Group fields by source
    const page1Fields = fields.filter(f => f.source === 'Policy Schedule & Certificate (Page 1)');
    const page2Fields = fields.filter(f => f.source === 'Policy General Exclusions (Page 2)');
    
    // Assertions
    if (page1Fields.length === 0) throw new Error('Page 1 fields must be present');
    if (page2Fields.length === 0) throw new Error('Page 2 fields must be present');
    
    // Page 2 must NOT have Sum Insured or Insurer Name
    const p2SI = page2Fields.find(f => f.name.toLowerCase().includes('sum insured'));
    if (p2SI) throw new Error('Page 2 must NOT contain sum insured: ' + JSON.stringify(p2SI));
    
    const p2Insurer = page2Fields.find(f => f.name.toLowerCase().includes('insurer'));
    if (p2Insurer) throw new Error('Page 2 must NOT contain insurer name: ' + JSON.stringify(p2Insurer));
    
    // Page 2 indicates general policy terms without schedule limits
    const p2Content = page2Fields.find(f => f.name === 'Page Content');
    if (!p2Content) throw new Error('Page 2 must have informative Page Content entry');
    
    // Page 1 policy number has is_document_level === true
    const p1Pol = page1Fields.find(f => f.name === 'Policy Number');
    if (!p1Pol || !p1Pol.is_document_level) throw new Error('Page 1 policy number must have is_document_level true');
    
    console.log('SUCCESS_NODE_VERIFICATION');
    """
    
    res = subprocess.run(["node", "-e", node_script], cwd=str(ROOT_DIR), capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed with: {res.stderr}\n{res.stdout}"
    assert "SUCCESS_NODE_VERIFICATION" in res.stdout
