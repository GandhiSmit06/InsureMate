"""
Realistic mock inputs simulating various outputs from Phase 1 ingestion.
Used for independent development, verification, and automated testing.
"""

from typing import Dict, Any
from ..schemas.input_schema import (
    IngestedDocument,
    RawPageInput,
    RawTableInput,
    RawBlockInput,
)
from ..schemas.common import BoundingBox


def create_mock_hospital_invoice() -> IngestedDocument:
    """Simulates an itemized hospital bill / tax invoice."""
    text = (
        "APOLLO HOSPITALS AHMEDABAD\n"
        "Plot No. 1A, Bhat GIDC, Gandhinagar - 382428\n"
        "FINAL INPATIENT BILL / TAX INVOICE\n\n"
        "Patient Name: Ramesh Sharma                 Patient ID: UHID-2024-9812\n"
        "Age / Sex: 52 Yrs / Male                   Date of Admission: 12/03/2024\n"
        "Treating Doctor: Dr. Rajiv Mehta           Date of Discharge: 15/03/2024\n"
        "Invoice No: INV-2024-00452                 Invoice Date: 15/03/2024\n\n"
        "ITEMIZED CHARGES\n"
        "Description                       Qty    Rate       Amount\n"
        "ICU Room Charges                    3    5000.00   15000.00\n"
        "Nursing Care Charges                3    1200.00    3600.00\n"
        "Consultation Charges                1    2500.00    2500.00\n"
        "Pharmacy & Consumables              1    4400.00    4400.00\n\n"
        "Total Amount: ₹ 25,500.00\n"
        "Paid Amount: ₹ 25,500.00\n"
        "Balance Amount: ₹ 0.00\n"
    )

    table_rows = [
        ["Description", "Qty", "Rate", "Amount"],
        ["ICU Room Charges", "3", "5000.00", "15000.00"],
        ["Nursing Care Charges", "3", "1200.00", "3600.00"],
        ["Consultation Charges", "1", "2500.00", "2500.00"],
        ["Pharmacy & Consumables", "1", "4400.00", "4400.00"],
    ]

    page = RawPageInput(
        page_number=1,
        raw_text=text,
        tables=[RawTableInput(page_number=1, rows=table_rows)],
        is_scanned=False,
    )

    return IngestedDocument(
        document_id="doc_inv_001",
        filename="apollo_hospital_invoice_ramesh.pdf",
        source_type="pdf",
        page_count=1,
        pages=[page],
        metadata={"author": "Apollo Billing Dept", "format": "PDF 1.7"},
    )


def create_mock_discharge_summary() -> IngestedDocument:
    """Simulates a hospital discharge summary document."""
    text = (
        "STERLING HOSPITAL - MULTISPECIALTY CENTER\n"
        "DISCHARGE SUMMARY\n\n"
        "Patient Name: Sunita Patel                 UHID: ST-90214\n"
        "Age / Sex: 42 Yrs / Female                 DOA: 10/02/2024\n"
        "Consultant: Dr. Arvind Joshi               DOD: 14/02/2024\n\n"
        "CLINICAL SUMMARY\n"
        "Patient presented with acute right lower quadrant abdominal pain, nausea, and low-grade fever of 2 days duration.\n\n"
        "FINAL DIAGNOSIS\n"
        "Acute Appendicitis with localized peritonitis.\n\n"
        "TREATMENT GIVEN\n"
        "Emergency Laparoscopic Appendectomy performed under general anesthesia on 10/02/2024. Post-operative recovery uneventful.\n\n"
        "DISCHARGE ADVICE\n"
        "Tab Cefixime 200 mg BD for 5 days.\n"
        "Tab Paracetamol 650 mg SOS for pain.\n"
        "Follow up in surgical OPD after 7 days for suture check.\n"
    )

    page = RawPageInput(
        page_number=1,
        raw_text=text,
        tables=[],
        is_scanned=False,
    )

    return IngestedDocument(
        document_id="doc_ds_002",
        filename="sterling_discharge_summary_sunita.pdf",
        source_type="pdf",
        page_count=1,
        pages=[page],
        metadata={"created_by": "Sterling Records"},
    )


def create_mock_prescription() -> IngestedDocument:
    """Simulates a doctor prescription slip."""
    text = (
        "DR. A. K. VERMA, MD (Medicine)\n"
        "Consultant Physician | Reg. No: G-34821\n"
        "City Health Clinic, Navrangpura\n\n"
        "Patient Name: Priya Shah                   Date: 05/01/2024\n"
        "Age: 29 Yrs                                Gender: Female\n\n"
        "Rx\n"
        "1. Tab Pantoprazole 40mg - 1 OD (Before Breakfast) x 14 days\n"
        "2. Tab Paracetamol 650mg - 1 TDS x 3 days\n"
        "3. Syp Sucralfate 10ml - BD x 7 days\n\n"
        "Advice: Avoid spicy food, drink plenty of water.\n"
    )

    page = RawPageInput(
        page_number=1,
        raw_text=text,
        is_scanned=False,
    )

    return IngestedDocument(
        document_id="doc_rx_003",
        filename="prescription_priya_shah.pdf",
        source_type="pdf",
        page_count=1,
        pages=[page],
    )


def create_mock_diagnostic_report() -> IngestedDocument:
    """Simulates a laboratory pathology/diagnostic report."""
    text = (
        "DR. LAL PATHLABS - CLINICAL LABORATORY REPORT\n"
        "DEPARTMENT OF HEMATOLOGY\n\n"
        "Patient Name: Rajesh Gupta                 Patient ID: DLP-88129\n"
        "Age / Gender: 38 / Male                    Sample Date: 11/02/2024\n"
        "Referred By: Dr. Rajiv Mehta               Report Date: 11/02/2024\n\n"
        "COMPLETE BLOOD COUNT (CBC)\n"
        "Test Name               Observed Value    Units        Biological Reference\n"
        "Hemoglobin              14.2              g/dL         13.0 - 17.0\n"
        "Total Leukocyte Count   8,500             /cumm        4,000 - 11,000\n"
        "Platelet Count          2.4               Lakhs/cumm   1.5 - 4.5\n"
        "Packed Cell Volume      42.1              %            40.0 - 50.0\n"
    )

    table_rows = [
        ["Test Name", "Observed Value", "Units", "Biological Reference"],
        ["Hemoglobin", "14.2", "g/dL", "13.0 - 17.0"],
        ["Total Leukocyte Count", "8500", "/cumm", "4000 - 11000"],
        ["Platelet Count", "2.4", "Lakhs/cumm", "1.5 - 4.5"],
        ["Packed Cell Volume", "42.1", "%", "40.0 - 50.0"],
    ]

    page = RawPageInput(
        page_number=1,
        raw_text=text,
        tables=[RawTableInput(page_number=1, rows=table_rows)],
        is_scanned=False,
    )

    return IngestedDocument(
        document_id="doc_diag_004",
        filename="cbc_report_rajesh.pdf",
        source_type="pdf",
        page_count=1,
        pages=[page],
    )


def create_mock_poor_ocr() -> IngestedDocument:
    """Simulates a scanned document with poor OCR quality and garbled characters."""
    text = (
        "H0SP1TAL INVO1CE \ufffd\ufffd\ufffd\n"
        "P@tient N@me: R@m\ufffdsh Sh@rma\n"
        "T0tal: Rs. ??500.00\n"
        "\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\n"
    )

    page = RawPageInput(
        page_number=1,
        raw_text=text,
        is_scanned=True,
        ocr_confidence_avg=38.5,
    )

    return IngestedDocument(
        document_id="doc_poor_ocr_005",
        filename="scanned_poor_invoice.pdf",
        source_type="scanned_pdf",
        page_count=1,
        pages=[page],
        ingestion_warnings=["Low OCR confidence detected on page 1"],
    )


def create_mock_conflicting_dates() -> IngestedDocument:
    """Simulates a document where admission date is chronologically after discharge date."""
    text = (
        "CITY HOSPITAL DISCHARGE CARD\n"
        "Patient Name: Anil Verma\n"
        "Date of Admission: 25/03/2024\n"
        "Date of Discharge: 10/03/2024\n"
        "Diagnosis: Viral Fever\n"
    )

    page = RawPageInput(
        page_number=1,
        raw_text=text,
        is_scanned=False,
    )

    return IngestedDocument(
        document_id="doc_conflict_006",
        filename="conflicting_dates.pdf",
        source_type="pdf",
        page_count=1,
        pages=[page],
    )


def create_mock_blank_document() -> IngestedDocument:
    """Simulates an empty or blank document."""
    page = RawPageInput(
        page_number=1,
        raw_text="",
        is_scanned=False,
    )

    return IngestedDocument(
        document_id="doc_blank_007",
        filename="blank_doc.pdf",
        source_type="pdf",
        page_count=1,
        pages=[page],
    )
