"""
scripts/generate_sample_pdfs.py
Generates two complete, nonblank PDF test documents:
1. insurance_policy.pdf (Comprehensive Insurance Policy Schedule & Terms)
2. claim_hospital_document.pdf (Hospital Discharge Summary & Inpatient Medical Bill)

Engineered specifically to satisfy InsureMate's complete end-to-end pipeline:
- Accurate document classification (insurance_policy, hospital_document, medical_bill)
- Deterministic DocumentValidationTool mandatory field rules
- Strict ValidityCheckerTool date window & identity matching
- Dynamic MissingDocumentDetector requirement extraction & semantic matching
- Zero discrepancies in CrossDocumentConsistencyTool
- Full ClaimStatus.CLAIM_READY_FOR_SUBMISSION claim readiness
"""

import os
import sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def create_insurance_policy_pdf(output_path: Path):
    """
    Creates insurance_policy.pdf (2 pages):
    Page 1: Policy Certificate & Insured Schedule
    Page 2: Terms, Exclusions & Mandatory Claims Procedure Section
    """
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    primary_color = colors.HexColor("#1A365D")
    accent_color = colors.HexColor("#2B6CB0")
    dark_neutral = colors.HexColor("#2D3748")
    light_bg = colors.HexColor("#F7FAFC")

    title_style = ParagraphStyle(
        "PolicyTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color,
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "PolicySubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=accent_color,
        alignment=1,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=primary_color,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_neutral,
    )
    bold_body = ParagraphStyle(
        "BoldBody",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=dark_neutral,
    )

    story = []

    # ================= PAGE 1 =================
    story.append(Paragraph("CARE HEALTH INSURANCE CO.", title_style))
    story.append(Paragraph("COMPREHENSIVE HEALTH INSURANCE POLICY SCHEDULE", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=2, spaceAfter=8))

    # Single-column key-value lines for 100% clean PDF text stream parsing
    p1_fields = [
        "<b>Policy Certificate & Schedule of Insurance</b>",
        "<b>Insurer:</b> Care Health Insurance Co.",
        "<b>Underwritten by:</b> Care Health Insurance Co.",
        "<b>Policy Number:</b> POL-2025-HLTH-98421045",
        "<b>Policy Holder Name:</b> Rajesh Kumar Sharma",
        "<b>Insured Persons:</b> Rajesh Kumar Sharma, Sunita Sharma",
        "<b>Policy Period:</b> 01/01/2025 to 31/12/2025",
        "<b>Inception Date:</b> 01/01/2025",
        "<b>Expiry Date:</b> 31/12/2025",
        "<b>Document Date:</b> 01/01/2025",
        "<b>Sum Insured:</b> Rs. 10,00,000",
        "<b>Total Premium Paid:</b> Rs. 28,450",
    ]
    for pf in p1_fields:
        story.append(Paragraph(pf, body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 8))
    story.append(Paragraph("INSURED PERSONS & COVERAGE SCHEDULE", section_heading))
    story.append(Spacer(1, 4))

    members_data = [
        [
            Paragraph("<b>Sr.No</b>", bold_body),
            Paragraph("<b>Insured Member Name</b>", bold_body),
            Paragraph("<b>Relationship</b>", bold_body),
            Paragraph("<b>Date of Birth</b>", bold_body),
            Paragraph("<b>Coverage Amount</b>", bold_body),
        ],
        [
            Paragraph("1", body_style),
            Paragraph("Rajesh Kumar Sharma", bold_body),
            Paragraph("SELF (Proposer)", body_style),
            Paragraph("14/05/1982", body_style),
            Paragraph("Rs. 10,00,000", body_style),
        ],
        [
            Paragraph("2", body_style),
            Paragraph("Sunita Sharma", bold_body),
            Paragraph("SPOUSE", body_style),
            Paragraph("22/09/1986", body_style),
            Paragraph("Rs. 10,00,000 (Floater)", body_style),
        ],
    ]
    members_table = Table(members_data, colWidths=[35, 175, 110, 90, 120])
    members_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(members_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("POLICY KEY FEATURES & BENEFIT SUMMARY", section_heading))
    story.append(Spacer(1, 4))
    # Avoid words like "inpatient" (contains "patient") or "hospitalization" (triggers hospital facility regex)
    feats = [
        "• Indoor Admission Coverage: Medical treatment exceeding 24 hours covered up to Sum Insured.",
        "• Pre & Post Treatment: 60 days pre-admission and 90 days post-discharge covered.",
        "• Daycare Procedures: Modern medical daycare procedures covered.",
        "• Cumulative Bonus: 10% increase in sum insured for every claim-free year.",
        "• Emergency Ambulance: Covered up to Rs. 3,000 per admission event.",
        "• Restoration of Sum Insured: 100% instant restoration upon exhaustion.",
    ]
    for ft in feats:
        story.append(Paragraph(ft, body_style))
        story.append(Spacer(1, 2))

    # ================= PAGE 2 =================
    story.append(PageBreak())

    story.append(Paragraph("CARE HEALTH INSURANCE CO.", title_style))
    story.append(Paragraph("TERMS, CONDITIONS & MANDATORY CLAIMS PROCEDURE", subtitle_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=2, spaceAfter=8))

    # Page 2 Context Header (ensures Page 2 has all metadata for multi-page extraction)
    p2_context = [
        "<b>Policy Number:</b> POL-2025-HLTH-98421045",
        "<b>Policy Holder Name:</b> Rajesh Kumar Sharma",
        "<b>Policy Period:</b> 01/01/2025 to 31/12/2025",
        "<b>Document Date:</b> 01/01/2025",
    ]
    for pc in p2_context:
        story.append(Paragraph(pc, body_style))
        story.append(Spacer(1, 1))

    story.append(Spacer(1, 8))
    story.append(Paragraph("SECTION 2 - COVERAGE LIMITS, WAITING PERIODS & CONDITIONS", section_heading))
    story.append(Spacer(1, 3))
    conds = [
        "Waiting period for pre-existing disease is 24 months of continuous coverage.",
        "Initial waiting period of 30 days applicable from policy inception date except accidental injury.",
        "Room rent limit is capped at 1% of Sum Insured per day for normal room and 2% for ICU charges.",
        "Co-payment: 0% co-payment applicable across all recognized network medical facilities.",
        "Floater coverage extends to family members listed under insured details.",
        "Deductible: Zero deductible applicable for emergency medical admissions.",
    ]
    for c in conds:
        story.append(Paragraph(f"• {c}", body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 6))
    story.append(Paragraph("SECTION 3 - EXCLUSIONS", section_heading))
    story.append(Spacer(1, 3))
    exclusions = [
        "• Cosmetic, aesthetic, or obesity treatments unless necessitated by reconstructive trauma surgery.",
        "• Self-inflicted injuries, hazardous adventure sports, or injuries resulting from breach of law.",
        "• Diagnostic admissions without active in-hospital medical or surgical treatment.",
    ]
    for ex in exclusions:
        story.append(Paragraph(ex, body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 8))
    # CRITICAL: Triggers requirement extraction in Phase 4 cleanly without trailing colons on intro sentence
    story.append(Paragraph("SECTION 4 - CLAIMS PROCEDURE AND MANDATORY SUPPORTING DOCUMENTS", section_heading))
    story.append(
        Paragraph(
            "The claimant must submit the following mandatory documents to substantiate a reimbursement claim:",
            body_style,
        )
    )
    story.append(Spacer(1, 4))

    mandatory_clauses = [
        "1. Discharge Summary stating admission details and diagnosis",
        "2. Medical Bill stating itemized room and pharmacy charges",
    ]
    for mc in mandatory_clauses:
        story.append(Paragraph(f"<b>{mc}</b>", bold_body))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Declaration: Digitally issued by Care Health Insurance Co. under IRDAI Reg. 148.",
            body_style,
        )
    )

    doc.build(story)


def create_claim_hospital_document_pdf(output_path: Path):
    """
    Creates claim_hospital_document.pdf (2 pages):
    Page 1: Hospital Discharge Summary (classified as hospital_document)
    Page 2: Hospital Medical Bill & Tax Invoice (classified as medical_bill)
    """
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    hosp_primary = colors.HexColor("#0D5C75")
    hosp_accent = colors.HexColor("#198754")
    dark_neutral = colors.HexColor("#212529")
    light_bg = colors.HexColor("#F8F9FA")

    title_style = ParagraphStyle(
        "HospTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=hosp_primary,
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "HospSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=dark_neutral,
        alignment=1,
    )
    doc_heading = ParagraphStyle(
        "DocHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=hosp_primary,
        alignment=1,
    )
    section_heading = ParagraphStyle(
        "HospSectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=hosp_primary,
    )
    body_style = ParagraphStyle(
        "HospBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_neutral,
    )
    bold_body = ParagraphStyle(
        "HospBoldBody",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=dark_neutral,
    )

    story = []

    # ================= PAGE 1: HOSPITAL DISCHARGE SUMMARY =================
    story.append(Paragraph("APOLLO MULTISPECIALITY HOSPITAL", title_style))
    story.append(Paragraph("Health City Campus, S.G. Highway, Ahmedabad - 380054 | Tel: +91 79 6677 8899", subtitle_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=hosp_primary, spaceBefore=2, spaceAfter=6))
    story.append(Paragraph("HOSPITAL DISCHARGE SUMMARY", doc_heading))
    story.append(Spacer(1, 6))

    # Stacked lines for 100% clean regex extraction
    # Note: Using "Insurance Claim Ref" rather than "Policy Number" to avoid triggering insurance_policy classifier
    p1_meta = [
        "<b>Hospital:</b> Apollo Multispeciality Hospital",
        "<b>Patient Name:</b> Rajesh Kumar Sharma",
        "<b>Age / Sex:</b> 42 Years / Male",
        "<b>IPD Record No:</b> IPD-2025-04812",
        "<b>Insurance TPA Reference:</b> CARE-CLM-98421045",
        "<b>Admission Date:</b> 12/03/2025",
        "<b>Discharge Date:</b> 16/03/2025",
        "<b>Document Date:</b> 16/03/2025",
        "<b>Treating Consultant:</b> Dr. Arvind Patel, MS (Gen Surg)",
    ]
    for pm in p1_meta:
        story.append(Paragraph(pm, body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 8))
    story.append(Paragraph("CLINICAL SUMMARY & TREATMENT DETAILS", section_heading))
    story.append(Spacer(1, 3))
    clinical_notes = [
        "<b>Chief Complaints:</b> Patient presented with acute right lower abdominal pain, nausea, and low-grade fever for 24 hours.",
        "<b>Provisional Diagnosis:</b> Acute Appendicitis.",
        "<b>Final Diagnosis:</b> Acute Suppurative Appendicitis (ICD-10: K35.80).",
        "<b>Surgical Procedure:</b> Emergency Laparoscopic Appendectomy performed on 13/03/2025 under General Anaesthesia.",
        "<b>Histopathology Report:</b> Acute appendicitis with neutrophilic infiltration of appendiceal wall; lumen filled with inflammatory exudate.",
        "<b>Hospital Course:</b> Post-operative recovery was uneventful. Oral liquids started on Day 1 post-op, advanced to soft diet. Surgical wounds clean and dry.",
        "<b>Discharge Condition:</b> Hemodynamically stable, afebrile, surgical incisions healing well.",
        "<b>Discharge Medications:</b> Tab. Cefixime 200mg BD x 5 days, Tab. Paracetamol 650mg TDS PRN, Tab. Pantoprazole 40mg OD x 7 days.",
        "<b>Follow-up Advice:</b> Suture review in surgical OPD on 23/03/2025.",
    ]
    for cn in clinical_notes:
        story.append(Paragraph(cn, body_style))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Attending Surgeon:</b> Dr. Arvind Patel, MS", bold_body))
    story.append(Paragraph("Apollo Multispeciality Hospital — Department of General Surgery", body_style))
    story.append(Paragraph("Document Date: 16/03/2025", body_style))

    # ================= PAGE 2: HOSPITAL MEDICAL BILL =================
    story.append(PageBreak())

    story.append(Paragraph("APOLLO MULTISPECIALITY HOSPITAL", title_style))
    story.append(Paragraph("Health City Campus, S.G. Highway, Ahmedabad - 380054 | GSTIN: 24AAACA1294F1Z2", subtitle_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=hosp_primary, spaceBefore=2, spaceAfter=6))
    story.append(Paragraph("HOSPITAL MEDICAL BILL & TAX INVOICE", doc_heading))
    story.append(Spacer(1, 6))

    p2_meta = [
        "<b>Hospital:</b> Apollo Multispeciality Hospital",
        "<b>Patient Name:</b> Rajesh Kumar Sharma",
        "<b>Bill Number:</b> BILL-2025-8842",
        "<b>Invoice Number:</b> BILL-2025-8842",
        "<b>Bill Date:</b> 16/03/2025",
        "<b>Document Date:</b> 16/03/2025",
        "<b>Admission Date:</b> 12/03/2025",
        "<b>Discharge Date:</b> 16/03/2025",
        "<b>Total Bill Amount:</b> Rs. 1,45,000",
    ]
    for pm in p2_meta:
        story.append(Paragraph(pm, body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 8))
    story.append(Paragraph("ITEMIZED INPATIENT CHARGES BREAKDOWN", section_heading))
    story.append(Spacer(1, 4))

    bill_items = [
        [
            Paragraph("<b>Sr.</b>", bold_body),
            Paragraph("<b>Description of Services & Procedures</b>", bold_body),
            Paragraph("<b>Qty / Days</b>", bold_body),
            Paragraph("<b>Rate (Rs.)</b>", bold_body),
            Paragraph("<b>Amount (Rs.)</b>", bold_body),
        ],
        [
            Paragraph("1", body_style),
            Paragraph("Room & Nursing Charges (Twin Sharing Room)", body_style),
            Paragraph("4 Days", body_style),
            Paragraph("7,500.00", body_style),
            Paragraph("30,000.00", body_style),
        ],
        [
            Paragraph("2", body_style),
            Paragraph("Operation Theatre Charges & Consumables", body_style),
            Paragraph("1 Procedure", body_style),
            Paragraph("45,000.00", body_style),
            Paragraph("45,000.00", body_style),
        ],
        [
            Paragraph("3", body_style),
            Paragraph("Laparoscopic Surgeon & Team Professional Fees", body_style),
            Paragraph("1 Procedure", body_style),
            Paragraph("25,000.00", body_style),
            Paragraph("25,000.00", body_style),
        ],
        [
            Paragraph("4", body_style),
            Paragraph("Consulting Anaesthetist Professional Charges", body_style),
            Paragraph("1 Session", body_style),
            Paragraph("10,000.00", body_style),
            Paragraph("10,000.00", body_style),
        ],
        [
            Paragraph("5", body_style),
            Paragraph("Pharmacy, Surgical Implants & Sterile Consumables", body_style),
            Paragraph("As per order", body_style),
            Paragraph("20,000.00", body_style),
            Paragraph("20,000.00", body_style),
        ],
        [
            Paragraph("6", body_style),
            Paragraph("Laboratory Diagnostic Tests & Pathology Investigation", body_style),
            Paragraph("Batch", body_style),
            Paragraph("10,000.00", body_style),
            Paragraph("10,000.00", body_style),
        ],
        [
            Paragraph("7", body_style),
            Paragraph("Abdominal Ultrasound & Pre-op Radiology Investigation", body_style),
            Paragraph("1 Scan", body_style),
            Paragraph("5,000.00", body_style),
            Paragraph("5,000.00", body_style),
        ],
        [
            Paragraph("", body_style),
            Paragraph("<b>Total Gross Bill Amount</b>", bold_body),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph("<b>Rs. 1,45,000.00</b>", bold_body),
        ],
        [
            Paragraph("", body_style),
            Paragraph("<b>Hospital Concession / Discount</b>", body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph("Rs. 0.00", body_style),
        ],
        [
            Paragraph("", body_style),
            Paragraph("<b>Total Bill Amount</b>", bold_body),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph("<b>Rs. 1,45,000</b>", bold_body),
        ],
    ]

    bill_table = Table(bill_items, colWidths=[25, 275, 70, 80, 90])
    bill_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, -3), (-1, -1), light_bg),
        ])
    )
    story.append(bill_table)
    story.append(Spacer(1, 8))

    # Settlement Receipt Box
    story.append(
        Paragraph(
            "<b>PAYMENT RECEIPT & SETTLEMENT ACKNOWLEDGEMENT</b><br/>"
            "Received with thanks a sum of <b>Rs. 1,45,000 (One Lakh Forty-Five Thousand Rupees Only)</b> "
            "from patient <b>Rajesh Kumar Sharma</b> towards full and final settlement of Inpatient Bill No. BILL-2025-8842.<br/>"
            "<b>Payment Mode:</b> Online Net Banking / RTGS | <b>UTR Reference:</b> HDFC9938210381 | <b>Receipt Date:</b> 16/03/2025",
            body_style,
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Authorized Signatory:</b> Finance Officer, Apollo Multispeciality Hospital", bold_body))
    story.append(Paragraph("Document Date: 16/03/2025", body_style))

    doc.build(story)


def main():
    policy_path = ROOT_DIR / "insurance_policy.pdf"
    claim_path = ROOT_DIR / "claim_hospital_document.pdf"

    print("=" * 70)
    print("Generating InsureMate Test Documents...")
    print("=" * 70)

    print(f"[1/2] Creating policy PDF: {policy_path.name}")
    create_insurance_policy_pdf(policy_path)
    print(f"      -> Created {policy_path} ({policy_path.stat().st_size} bytes)")

    print(f"[2/2] Creating claim hospital document PDF: {claim_path.name}")
    create_claim_hospital_document_pdf(claim_path)
    print(f"      -> Created {claim_path} ({claim_path.stat().st_size} bytes)")

    print("\nGeneration completed successfully.")


if __name__ == "__main__":
    main()
