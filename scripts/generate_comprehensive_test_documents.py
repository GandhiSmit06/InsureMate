"""
scripts/generate_comprehensive_test_documents.py
Generates exactly two comprehensive, multi-page, realistic health insurance test PDFs:
1. InsureMate_Test_Health_Insurance_Policy.pdf (11 pages)
2. InsureMate_Test_Health_Insurance_Claim_Documents.pdf (16 pages)

Engineered specifically to satisfy InsureMate's complete end-to-end pipeline:
- Accurate document classification (insurance_policy, hospital_document, medical_bill, medical_report)
- Deterministic DocumentValidationTool mandatory field rules (100% valid)
- Strict ValidityCheckerTool date window & identity matching (100% valid)
- Dynamic MissingDocumentDetector requirement extraction & semantic matching (0 missing)
- Zero discrepancies in CrossDocumentConsistencyTool
- Full ClaimStatus.CLAIM_READY_FOR_SUBMISSION claim readiness
"""

from pathlib import Path
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

ROOT_DIR = Path(__file__).resolve().parent.parent
TEST_DOCS_DIR = ROOT_DIR / "test_documents"
TEST_DOCS_DIR.mkdir(parents=True, exist_ok=True)
POLICY_PDF = TEST_DOCS_DIR / "InsureMate_Test_Health_Insurance_Policy.pdf"
CLAIM_PDF = TEST_DOCS_DIR / "InsureMate_Test_Health_Insurance_Claim_Documents.pdf"


# ----------------------------------------------------------------------
# Numbered Canvas for Two-Pass Dynamic Page Numbering
# ----------------------------------------------------------------------
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#4A5568"))
        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count} | Confidential - Synthetic Software Test Document"
        self.drawRightString(A4[0] - 36, 20, footer_text)
        self.drawString(36, 20, "InsureMate Claim Preparation Engine - Synthetic Test Suite")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 30, A4[0] - 36, 30)
        self.restoreState()


# ----------------------------------------------------------------------
# Styles
# ----------------------------------------------------------------------
def build_styles():
    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#1E3A8A")   # Navy 900
    c_secondary = colors.HexColor("#0D9488") # Teal 600
    c_dark = colors.HexColor("#0F172A")      # Slate 900
    c_text = colors.HexColor("#1E293B")      # Slate 800

    styles.add(ParagraphStyle(
        'DocHeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        textColor=c_primary,
        alignment=0,
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        'MetaBoxText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=c_dark
    ))
    styles.add(ParagraphStyle(
        'SectionH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13.5,
        textColor=c_primary,
        spaceBefore=6,
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=5,
        spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        'BodyP',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.8,
        textColor=c_text,
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        'BodyPBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.8,
        leading=10.8,
        textColor=c_text,
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        'TableHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.2,
        textColor=colors.white,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.2,
        textColor=c_text,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.2,
        textColor=c_dark,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.2,
        textColor=c_text,
        alignment=2
    ))
    styles.add(ParagraphStyle(
        'TableCellRightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.2,
        textColor=c_dark,
        alignment=2
    ))
    styles.add(ParagraphStyle(
        'StampText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#1E3A8A"),
        alignment=1
    ))
    return styles


# ----------------------------------------------------------------------
# Generator for PDF 1: InsureMate_Test_Health_Insurance_Policy.pdf (11 pages)
# ----------------------------------------------------------------------
def generate_policy_pdf(output_path: Path):
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    w_content = A4[0] - 72

    def add_policy_header(page_title: str, section_subtitle: str):
        hdr_data = [
            [
                Paragraph("<b>Sunrise Shield Health Insurance Ltd.</b> | Comprehensive Family Protection — Gold", styles['DocHeaderTitle']),
                Paragraph("<b>CERTIFIED POLICY</b>", styles['TableCellRightBold'])
            ],
            [
                Paragraph(
                    "<b>Policy Number:</b> SSHI-TEST-2026-001 &nbsp;|&nbsp; "
                    "<b>Policy Period:</b> 01/04/2026 to 31/03/2027 (01 April 2026 to 31 March 2027)<br/>"
                    "<b>Policyholder Name:</b> Aarav Mehta &nbsp;|&nbsp; "
                    "<b>Insured Persons:</b> Aarav Mehta &nbsp;|&nbsp; "
                    "<b>Sum Insured:</b> Rs. 5,00,000",
                    styles['MetaBoxText']
                ),
                Paragraph("<b>UIN:</b> IRDAI/NL/SSHI/HLTH/P-V.2/2026<br/><b>Territory:</b> Pan-India Coverage", styles['TableCellRight'])
            ]
        ]
        t = Table(hdr_data, colWidths=[w_content * 0.72, w_content * 0.28])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 3))
        story.append(Paragraph(f"<b>{page_title}</b> — {section_subtitle}", styles['SectionH1']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0D9488"), spaceAfter=5))

    # PAGE 1: Section A - Policy Certificate
    add_policy_header("SECTION A: POLICY SCHEDULE & CERTIFICATE OF INSURANCE", "Schedule of Insurance & Premium")
    story.append(Paragraph(
        "Sunrise Shield Health Insurance Ltd. issues this Policy Certificate to the Policyholder named below. "
        "This document, together with Proposal Form, Policy Terms, Conditions, and Endorsements, constitutes the complete Contract.",
        styles['BodyP']
    ))
    sched_rows = [
        [Paragraph("<b>Policy Field</b>", styles['TableHead']), Paragraph("<b>Policyholder & Coverage Details</b>", styles['TableHead']), Paragraph("<b>Verification Value / Standard</b>", styles['TableHead'])],
        [Paragraph("Insurer Legal Entity", styles['TableCellBold']), Paragraph("Sunrise Shield Health Insurance Ltd.", styles['TableCell']), Paragraph("Registered Health Insurer (Synthetic)", styles['TableCell'])],
        [Paragraph("Product / Plan Name", styles['TableCellBold']), Paragraph("Comprehensive Family Protection — Gold", styles['TableCell']), Paragraph("Gold Tier Inpatient Benefit Plan", styles['TableCell'])],
        [Paragraph("Policy Number", styles['TableCellBold']), Paragraph("<b>SSHI-TEST-2026-001</b>", styles['TableCellBold']), Paragraph("Unique System Policy Identifier", styles['TableCell'])],
        [Paragraph("Policyholder Name", styles['TableCellBold']), Paragraph("<b>Aarav Mehta</b>", styles['TableCellBold']), Paragraph("Proposer & Primary Insured Person", styles['TableCell'])],
        [Paragraph("Insured Persons Listed", styles['TableCellBold']), Paragraph("Aarav Mehta (Self, Adult Male, Age: 34)", styles['TableCell']), Paragraph("Individual Sum Insured Schedule", styles['TableCell'])],
        [Paragraph("Policy Period (Term)", styles['TableCellBold']), Paragraph("<b>01/04/2026 to 31/03/2027</b>", styles['TableCellBold']), Paragraph("12 Months Continuous Coverage", styles['TableCell'])],
        [Paragraph("Policy Inception Date", styles['TableCellBold']), Paragraph("01 April 2026 (00:00 Hours)", styles['TableCell']), Paragraph("Coverage Commencement Date", styles['TableCell'])],
        [Paragraph("Policy Expiry Date", styles['TableCellBold']), Paragraph("31 March 2027 (23:59 Hours)", styles['TableCell']), Paragraph("Coverage Expiration Date", styles['TableCell'])],
        [Paragraph("Basic Sum Insured", styles['TableCellBold']), Paragraph("<b>Rs. 5,00,000 (INR Five Lakh Only)</b>", styles['TableCellBold']), Paragraph("Annual Floating Hospitalization Pool", styles['TableCell'])],
        [Paragraph("Net Annual Premium", styles['TableCellBold']), Paragraph("Rs. 18,500.00", styles['TableCell']), Paragraph("Actuarial Pure Risk Premium", styles['TableCell'])],
        [Paragraph("Goods & Service Tax (GST 18%)", styles['TableCellBold']), Paragraph("Rs. 3,330.00", styles['TableCell']), Paragraph("Statutory Indirect Tax Component", styles['TableCell'])],
        [Paragraph("Total Premium Paid", styles['TableCellBold']), Paragraph("<b>Rs. 21,830.00 (Paid in Full)</b>", styles['TableCellBold']), Paragraph("Receipt No: SSHI-RCP-2026-09118", styles['TableCell'])],
        [Paragraph("Coverage Territory", styles['TableCellBold']), Paragraph("Pan-India (All Licensed Hospitals)", styles['TableCell']), Paragraph("Admissible Across Registered Facilities", styles['TableCell'])],
        [Paragraph("Policy Issuance Date", styles['TableCellBold']), Paragraph("28 March 2026", styles['TableCell']), Paragraph("Prior to Policy Commencement", styles['TableCell'])],
        [Paragraph("Co-payment Requirement", styles['TableCellBold']), Paragraph("0% (Nil Co-payment for Gold Plan)", styles['TableCell']), Paragraph("Zero Co-pay Applicable to Insured", styles['TableCell'])],
        [Paragraph("Pre-existing Diseases Declared", styles['TableCellBold']), Paragraph("None (Nil Medical Pre-existing Conditions)", styles['TableCell']), Paragraph("Clean Health Status at Proposal", styles['TableCell'])],
    ]
    t_sched = Table(sched_rows, colWidths=[w_content * 0.32, w_content * 0.38, w_content * 0.30])
    t_sched.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_sched)
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        "<b>Important Notice:</b> The Insurance Cover provided under this policy schedule is subject to the terms, conditions, "
        "clauses, and exclusions enumerated in this contract. Any material non-disclosure shall render this certificate void.",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 2: Section A (cont.) - Definitions
    add_policy_header("SECTION A (CONTINUED): GENERAL DEFINITIONS & LEGAL CONSTRUCTION", "Statutory Interpretations")
    defs = [
        ("1. Policyholder", "The person named in the Schedule who has concluded this Policy with the Insurer and who is responsible for premium payment (Mr. Aarav Mehta)."),
        ("2. Insured Person", "The individual identified in the Schedule for whom coverage is operative and on whose behalf claim expenses may be reimbursed (Mr. Aarav Mehta)."),
        ("3. Insurer", "Sunrise Shield Health Insurance Ltd., licensed to underwrite general and health insurance business under statutory regulations."),
        ("4. Hospital", "Any licensed medical institution established for indoor care and treatment of sickness and injuries with minimum 10 beds, OT, and round-the-clock nursing."),
        ("5. Hospitalization", "An admission in a Hospital for a minimum period of 24 consecutive hours for Inpatient care."),
        ("6. Medically Necessary Treatment", "Any treatment, tests, medication, or stay in hospital certified by a registered medical practitioner as necessary for safe medical care."),
        ("7. Room Rent", "The amount charged by a Hospital towards room and boarding expenses including nursing charges and resident doctor fees."),
        ("8. Intensive Care Unit (ICU)", "A specially equipped hospital section for monitoring and treating patients in critical or life-threatening condition."),
        ("9. Acute Appendicitis", "Acute visceral inflammation of the vermiform appendix requiring urgent medical evaluation and operative surgical excision."),
        ("10. Laparoscopic Appendectomy", "Minimally invasive surgical excision of the vermiform appendix using laparoscopic instruments."),
        ("11. Pre-Hospitalization Expenses", "Medical expenses incurred immediately before admission, up to the maximum duration of 30 days."),
        ("12. Post-Hospitalization Expenses", "Medical expenses incurred immediately after discharge for the same illness, up to the maximum duration of 60 days."),
        ("13. Admissible Expenses", "Expenses incurred on medically necessary hospitalization conforming to policy limits and substantiated by original bills.")
    ]
    for d_title, d_text in defs:
        story.append(Paragraph(f"<b>{d_title}:</b> {d_text}", styles['BodyP']))
    story.append(PageBreak())

    # PAGE 3: Section B - Inpatient Coverage
    add_policy_header("SECTION B: COVERAGE & INPATIENT BENEFITS", "Core Hospitalization Protections")
    cov_rows = [
        [Paragraph("<b>Clause ID</b>", styles['TableHead']), Paragraph("<b>Benefit / Coverage Head</b>", styles['TableHead']), Paragraph("<b>Eligible Limits & Parameters</b>", styles['TableHead']), Paragraph("<b>Admissibility Condition</b>", styles['TableHead'])],
        [Paragraph("<b>COV-001</b>", styles['TableCellBold']), Paragraph("Inpatient Hospitalization", styles['TableCellBold']), Paragraph("Up to Remaining Sum Insured (Rs. 5,00,000)", styles['TableCell']), Paragraph("Min 24 Hours Hospitalization required", styles['TableCell'])],
        [Paragraph("<b>COV-002</b>", styles['TableCellBold']), Paragraph("Room Rent & Boarding", styles['TableCellBold']), Paragraph("<b>Up to Rs. 5,000 / Day (Standard Room)</b><br/>Eligible: Single Private / Twin Sharing", styles['TableCellBold']), Paragraph("No proportionate deduction if room within Rs. 5,000/day limit", styles['TableCell'])],
        [Paragraph("<b>COV-003</b>", styles['TableCellBold']), Paragraph("Intensive Care Unit (ICU)", styles['TableCellBold']), Paragraph("<b>Up to Rs. 10,000 / Day</b>", styles['TableCellBold']), Paragraph("Medically indicated critical care stay", styles['TableCell'])],
        [Paragraph("<b>COV-004</b>", styles['TableCellBold']), Paragraph("Surgeon & Anesthetist Fees", styles['TableCellBold']), Paragraph("As per actuals, subject to Medical Necessity", styles['TableCell']), Paragraph("Qualified registered surgeon notes required", styles['TableCell'])],
        [Paragraph("<b>COV-005</b>", styles['TableCellBold']), Paragraph("Operation Theatre (OT) Charges", styles['TableCellBold']), Paragraph("Admissible as itemized surgical cost", styles['TableCell']), Paragraph("Operation notes and procedure log mandatory", styles['TableCell'])],
        [Paragraph("<b>COV-006</b>", styles['TableCellBold']), Paragraph("Nursing & Physician Visits", styles['TableCellBold']), Paragraph("Covered up to standard facility tariffs", styles['TableCell']), Paragraph("Inpatient indoor chart documentation", styles['TableCell'])],
    ]
    t_cov = Table(cov_rows, colWidths=[w_content * 0.14, w_content * 0.28, w_content * 0.32, w_content * 0.26])
    t_cov.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_cov)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Room Rent Admissibility Rules:</b> The Insured Person is entitled to a standard room category charging up to Rs. 5,000 per day. "
        "For the test hospitalization, room charges of Rs. 5,000 per night for 3 nights (total Rs. 15,000) are within the eligible limit. "
        "No proportionate deduction shall apply to associated medical charges.",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 4: Section B (cont.) - Diagnostics, Pharmacy & Pre/Post
    add_policy_header("SECTION B (CONTINUED): DIAGNOSTIC, PHARMACY & EXTENDED BENEFITS", "Ancillary Scope")
    cov_ext_rows = [
        [Paragraph("<b>Clause ID</b>", styles['TableHead']), Paragraph("<b>Ancillary Benefit Head</b>", styles['TableHead']), Paragraph("<b>Eligible Limits & Window</b>", styles['TableHead']), Paragraph("<b>Documentation Required</b>", styles['TableHead'])],
        [Paragraph("<b>COV-007</b>", styles['TableCellBold']), Paragraph("Diagnostic Investigations", styles['TableCellBold']), Paragraph("100% of Medically Necessary pathology/radiology tests", styles['TableCell']), Paragraph("Signed diagnostic reports & bills", styles['TableCell'])],
        [Paragraph("<b>COV-008</b>", styles['TableCellBold']), Paragraph("Medicines & Consumables", styles['TableCellBold']), Paragraph("100% of prescribed pharmaceuticals & surgical disposables", styles['TableCell']), Paragraph("Detailed pharmacy invoice & doctor script", styles['TableCell'])],
        [Paragraph("<b>COV-009</b>", styles['TableCellBold']), Paragraph("Pre-Hospitalization Expenses", styles['TableCellBold']), Paragraph("<b>Up to 30 Days Prior to Admission</b>", styles['TableCellBold']), Paragraph("Prescriptions & bills directly related to illness", styles['TableCell'])],
        [Paragraph("<b>COV-010</b>", styles['TableCellBold']), Paragraph("Post-Hospitalization Expenses", styles['TableCellBold']), Paragraph("<b>Up to 60 Days Post-Discharge</b>", styles['TableCellBold']), Paragraph("Discharge advice & follow-up invoices", styles['TableCell'])],
        [Paragraph("<b>COV-011</b>", styles['TableCellBold']), Paragraph("Road Ambulance Benefit", styles['TableCellBold']), Paragraph("<b>Up to Rs. 2,000 per hospitalization</b>", styles['TableCellBold']), Paragraph("Licensed ambulance provider receipt", styles['TableCell'])],
    ]
    t_cov_ext = Table(cov_ext_rows, colWidths=[w_content * 0.14, w_content * 0.28, w_content * 0.32, w_content * 0.26])
    t_cov_ext.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_cov_ext)
    story.append(PageBreak())

    # PAGE 5: Section C - Waiting Periods
    add_policy_header("SECTION C: WAITING PERIODS & DISEASE-SPECIFIC CLAUSES", "Statutory Waiting Windows")
    wait_rows = [
        [Paragraph("<b>Clause ID</b>", styles['TableHead']), Paragraph("<b>Waiting Period Category</b>", styles['TableHead']), Paragraph("<b>Applicable Window</b>", styles['TableHead']), Paragraph("<b>Application to Test Claim Scenario</b>", styles['TableHead'])],
        [Paragraph("<b>WAIT-001</b>", styles['TableCellBold']), Paragraph("Initial Waiting Period", styles['TableCellBold']), Paragraph("30 Days from Policy Commencement (01/04/2026 to 30/04/2026)", styles['TableCell']), Paragraph("<b>COMPLETED.</b> Admission date 12/09/2026 is > 5 months past inception date.", styles['TableCellBold'])],
        [Paragraph("<b>WAIT-002</b>", styles['TableCellBold']), Paragraph("Specified Disease Waiting Period", styles['TableCellBold']), Paragraph("24 Months for elective surgeries (hernia, cataract, joint replacement)", styles['TableCell']), Paragraph("<b>NOT APPLICABLE.</b> Acute appendicitis is an emergency inflammatory condition, exempt from elective 24-month list.", styles['TableCellBold'])],
        [Paragraph("<b>WAIT-003</b>", styles['TableCellBold']), Paragraph("Pre-Existing Disease (PED) Waiting Period", styles['TableCellBold']), Paragraph("36 Months for declared chronic ailments", styles['TableCell']), Paragraph("<b>NOT APPLICABLE.</b> Nil PED declared. Acute appendicitis arose de novo during policy year.", styles['TableCellBold'])],
    ]
    t_wait = Table(wait_rows, colWidths=[w_content * 0.14, w_content * 0.28, w_content * 0.28, w_content * 0.30])
    t_wait.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_wait)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Admissibility Certification for Acute Appendicitis:</b> Mr. Aarav Mehta's acute appendicitis on 12/09/2026 is an emergency condition "
        "occurring after the initial 30-day waiting period. It is fully covered under the policy terms.",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 6: Section D - Exclusions
    add_policy_header("SECTION D: GENERAL POLICY EXCLUSIONS", "Non-Indemnifiable Expenses")
    exclusions = [
        ("EXC-001", "Non-Medically Necessary Treatment", "Admission for investigation or observation without active inpatient treatment."),
        ("EXC-002", "Cosmetic or Plastic Surgery", "Surgery undertaken purely for aesthetic modification unless necessitated by trauma."),
        ("EXC-003", "Personal Convenience Items", "Telephone, television, luxury toiletries, attendant meals, or administrative registration overheads."),
        ("EXC-004", "Unproven & Experimental Therapies", "Treatments or medicines that lack established clinical empirical evidence."),
        ("EXC-005", "Dental Surgery & Orthodontics", "Dental procedures unless requiring hospitalization as a consequence of accidental trauma."),
        ("EXC-006", "Substance Abuse & Intoxication", "Treatment directly or indirectly attributable to alcohol or narcotics."),
        ("EXC-007", "Self-Inflicted Injuries", "Intentional suicide attempt or self-harm whether sane or insane."),
        ("EXC-008", "Duplicate Claim Submissions", "Reimbursement of expenses already settled by another insurer without coordination."),
    ]
    exc_rows = [[Paragraph("<b>Exclusion ID</b>", styles['TableHead']), Paragraph("<b>Excluded Category</b>", styles['TableHead']), Paragraph("<b>Operational Definition & Boundaries</b>", styles['TableHead'])]]
    for eid, etitle, edesc in exclusions:
        exc_rows.append([Paragraph(f"<b>{eid}</b>", styles['TableCellBold']), Paragraph(etitle, styles['TableCellBold']), Paragraph(edesc, styles['TableCell'])])
    t_exc = Table(exc_rows, colWidths=[w_content * 0.16, w_content * 0.32, w_content * 0.52])
    t_exc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_exc)
    story.append(PageBreak())

    # PAGE 7: Section E - Mandatory Supporting Documents
    add_policy_header("SECTION E: CLAIM FILING REQUIREMENTS & MANDATORY EVIDENCE", "Document Intake Standards")
    story.append(Paragraph(
        "To enable swift claim adjudication, the claimant must submit the following supporting documents within 30 days of discharge:",
        styles['BodyP']
    ))
    story.append(Paragraph("<b>SECTION 5 - CLAIMS PROCEDURE AND MANDATORY SUPPORTING DOCUMENTS</b>", styles['SectionH2']))
    story.append(Paragraph(
        "The following numbered items represent the verified policy clauses for mandatory claim documentation:<br/>"
        "1. Hospital Discharge Summary stating admission details and diagnosis<br/>"
        "2. Hospital Medical Bill & COV-002 Room Rent & Boarding Folio stating itemized room and pharmacy charges<br/>"
        "3. Hospital Indoor Admission Record stating date and presenting symptoms<br/>"
        "4. Medical Diagnostic Report stating pathology and ultrasound findings",
        styles['BodyP']
    ))
    story.append(Spacer(1, 6))

    doc_tbl = [
        [Paragraph("<b>Clause ID</b>", styles['TableHead']), Paragraph("<b>Document Requirement Name</b>", styles['TableHead']), Paragraph("<b>Classification</b>", styles['TableHead']), Paragraph("<b>Validation & Compliance Rule</b>", styles['TableHead'])],
        [Paragraph("<b>DOC-001</b>", styles['TableCellBold']), Paragraph("Hospital Discharge Summary", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCellBold']), Paragraph("Must state diagnosis (Acute Appendicitis) and discharge date 15/09/2026", styles['TableCell'])],
        [Paragraph("<b>DOC-002</b>", styles['TableCellBold']), Paragraph("Hospital Medical Bill & Room Rent Boarding Folio", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCellBold']), Paragraph("Must state itemized room rent, boarding, nursing, and pharmacy charges adding to Rs. 85,000 (COV-002 compliant)", styles['TableCell'])],
        [Paragraph("<b>DOC-003</b>", styles['TableCellBold']), Paragraph("Hospital Indoor Admission Record", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCellBold']), Paragraph("Must state admission date 12/09/2026, symptoms, and clinical assessment", styles['TableCell'])],
        [Paragraph("<b>DOC-004</b>", styles['TableCellBold']), Paragraph("Medical Diagnostic Report", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCellBold']), Paragraph("Must include pathology (CBC/CRP) and ultrasound scan reports", styles['TableCell'])],
    ]
    t_d = Table(doc_tbl, colWidths=[w_content * 0.16, w_content * 0.32, w_content * 0.18, w_content * 0.34])
    t_d.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_d)
    story.append(PageBreak())

    # PAGE 8: Section F - Expense Admissibility
    add_policy_header("SECTION F: EXPENSE ADMISSIBILITY & FINANCIAL RECONCILIATION", "Financial Model")
    fin_rows = [
        [Paragraph("<b>Rule ID</b>", styles['TableHead']), Paragraph("<b>Expense Category</b>", styles['TableHead']), Paragraph("<b>Claimed Amount</b>", styles['TableHead']), Paragraph("<b>Admissible Amount</b>", styles['TableHead']), Paragraph("<b>Admissibility Computation Rationale</b>", styles['TableHead'])],
        [Paragraph("<b>FIN-001</b>", styles['TableCellBold']), Paragraph("Room Charges (3 Nights)", styles['TableCellBold']), Paragraph("Rs. 15,000", styles['TableCell']), Paragraph("<b>Rs. 15,000</b>", styles['TableCellBold']), Paragraph("3 Nights @ Rs. 5,000/night. Conforms to policy cap (COV-002).", styles['TableCell'])],
        [Paragraph("<b>FIN-002</b>", styles['TableCellBold']), Paragraph("Nursing & Patient Care", styles['TableCellBold']), Paragraph("Rs. 4,500", styles['TableCell']), Paragraph("<b>Rs. 4,500</b>", styles['TableCellBold']), Paragraph("Rs. 1,500/day for 3 days inpatient stay. Covered under COV-006.", styles['TableCell'])],
        [Paragraph("<b>FIN-003</b>", styles['TableCellBold']), Paragraph("Surgeon Professional Fees", styles['TableCellBold']), Paragraph("Rs. 20,000", styles['TableCell']), Paragraph("<b>Rs. 20,000</b>", styles['TableCellBold']), Paragraph("Laparoscopic surgical specialist tariff. Admissible under COV-004.", styles['TableCell'])],
        [Paragraph("<b>FIN-004</b>", styles['TableCellBold']), Paragraph("Anesthesia Services", styles['TableCellBold']), Paragraph("Rs. 6,000", styles['TableCell']), Paragraph("<b>Rs. 6,000</b>", styles['TableCellBold']), Paragraph("General endotracheal anesthesia administration. Admissible under COV-004.", styles['TableCell'])],
        [Paragraph("<b>FIN-005</b>", styles['TableCellBold']), Paragraph("Operation Theatre (OT)", styles['TableCellBold']), Paragraph("Rs. 10,000", styles['TableCell']), Paragraph("<b>Rs. 10,000</b>", styles['TableCellBold']), Paragraph("Laparoscopy theatre facility and instrumentation (COV-005).", styles['TableCell'])],
        [Paragraph("<b>FIN-006</b>", styles['TableCellBold']), Paragraph("Diagnostic Tests (USG/CBC)", styles['TableCellBold']), Paragraph("Rs. 5,500", styles['TableCell']), Paragraph("<b>Rs. 5,500</b>", styles['TableCellBold']), Paragraph("CBC, CRP, and Abdominal Ultrasound. Covered under COV-007.", styles['TableCell'])],
        [Paragraph("<b>FIN-007</b>", styles['TableCellBold']), Paragraph("Medicines & Pharmacy", styles['TableCellBold']), Paragraph("Rs. 9,000", styles['TableCell']), Paragraph("<b>Rs. 9,000</b>", styles['TableCellBold']), Paragraph("Inpatient IV antibiotics, analgesics, fluids, itemized under COV-008.", styles['TableCell'])],
        [Paragraph("<b>FIN-008</b>", styles['TableCellBold']), Paragraph("Surgical Consumables", styles['TableCellBold']), Paragraph("Rs. 5,000", styles['TableCell']), Paragraph("<b>Rs. 5,000</b>", styles['TableCellBold']), Paragraph("Trocars, endo-clips, sterile drapes, disposable suction tubes (COV-008).", styles['TableCell'])],
        [Paragraph("<b>FIN-009</b>", styles['TableCellBold']), Paragraph("Other Hospital Services", styles['TableCellBold']), Paragraph("Rs. 10,000", styles['TableCell']), Paragraph("<b>Rs. 10,000</b>", styles['TableCellBold']), Paragraph("Pre-op care, multi-para monitoring, biomedical disposal.", styles['TableCell'])],
        [Paragraph("<b>TOTAL</b>", styles['TableCellBold']), Paragraph("<b>Total Hospital Bill</b>", styles['TableCellBold']), Paragraph("<b>Rs. 85,000</b>", styles['TableCellBold']), Paragraph("<b>Rs. 85,000</b>", styles['TableCellBold']), Paragraph("<b>100% Admissible. Remaining Sum Insured = Rs. 4,15,000.</b>", styles['TableCellBold'])],
    ]
    t_fin = Table(fin_rows, colWidths=[w_content * 0.12, w_content * 0.25, w_content * 0.15, w_content * 0.15, w_content * 0.33])
    t_fin.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_fin)
    story.append(PageBreak())

    # PAGE 9: Section G - Workflow
    add_policy_header("SECTION G: CLAIM PROCESSING WORKFLOW & AUDIT ARCHITECTURE", "Standard Operating Procedure")
    workflow_steps = [
        ("Step 1: Document Intake", "Reception of claim bundle, digital indexing, and page extraction."),
        ("Step 2: Policy Verification", "Cross-referencing Policy Number SSHI-TEST-2026-001 in core database to confirm active policy."),
        ("Step 3: Insured Person Match", "Verifying claimant identity 'Aarav Mehta' matches covered policyholder and registered member."),
        ("Step 4: Hospitalization Date Audit", "Validating admission (12/09/2026) and discharge (15/09/2026) fall within policy window (01/04/2026 - 31/03/2027)."),
        ("Step 5: Diagnosis & Clinical Audit", "Verifying Acute Appendicitis diagnosis is corroborated by clinical notes, ultrasound, and operation notes."),
        ("Step 6: Document Completeness Check", "Deterministic audit verifying all mandatory documents (Discharge, Bill, Admission, Report) are attached."),
        ("Step 7: Financial Invoice Reconciliation", "Cross-checking itemized hospital bill line items add up to exact total of Rs. 85,000."),
        ("Step 8: Policy Clause Retrieval", "Matching claim facts against policy clauses (COV-001, COV-002, WAIT-001, DOC-001 to DOC-004)."),
        ("Step 9: Expense Admissibility Calculation", "Applying room rent caps (Rs. 5,000/day), co-payment rules (0%), and verifying remaining sum insured."),
        ("Step 10: Missing Evidence Identification", "Semantic detection to confirm zero missing documents."),
        ("Step 11: Claim Readiness Determination", "Automated synthesis of comprehensive Claim Readiness Audit Package by InsureMate Agent."),
        ("Step 12: Human Review & Settlement", "Final sign-off by insurer medical auditor and electronic NEFT disbursement to claimant's bank account.")
    ]
    wf_rows = [[Paragraph("<b>Workflow Phase</b>", styles['TableHead']), Paragraph("<b>Audit Activity & Operational Criteria</b>", styles['TableHead'])]]
    for stitle, sdesc in workflow_steps:
        wf_rows.append([Paragraph(f"<b>{stitle}</b>", styles['TableCellBold']), Paragraph(sdesc, styles['TableCell'])])
    t_wf = Table(wf_rows, colWidths=[w_content * 0.32, w_content * 0.68])
    t_wf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_wf)
    story.append(PageBreak())

    # PAGE 10: Section H - RAG Index
    add_policy_header("SECTION H: POLICY CLAUSE REFERENCE INDEX & VERIFICATION MAPPING", "Master Traceability Index")
    rag_index = [
        ("COV-001", "Inpatient Hospitalization", "Sec B / Pg 3", "Min 24h stay; remaining sum insured", "Admission 12/09 to 15/09 (72h)"),
        ("COV-002", "Room Rent & Boarding Folio", "Sec B / Pg 3", "Up to Rs. 5,000 / day; no proration", "3 Nights @ Rs. 5,000 = Rs. 15,000 certified"),
        ("COV-004", "Surgeon & Anesthetist Fees", "Sec B / Pg 3", "Medical necessity & itemized notes", "Surgeon Rs. 20,000 + Anesth Rs. 6,000"),
        ("COV-005", "Operation Theatre Charges", "Sec B / Pg 3", "Itemized hospital bill & OT record", "OT Charges Rs. 10,000"),
        ("COV-006", "Nursing & Inpatient Care", "Sec B / Pg 3", "Standard hospital tariff", "Nursing Rs. 4,500 (Rs. 1,500/day)"),
        ("COV-007", "Diagnostic Investigations", "Sec B / Pg 4", "Signed lab & radiology reports", "Pathology + USG = Rs. 5,500"),
        ("COV-008", "Medicines & Consumables", "Sec B / Pg 4", "Pharmacy bill & surgical disposables", "Pharmacy Rs. 9,000 + Cons Rs. 5,000"),
        ("WAIT-001", "Initial Waiting Period", "Sec C / Pg 5", "30 Days from commencement", "Policy: 01/04/2026; Event: 12/09/2026"),
        ("WAIT-002", "Specific Disease Wait Period", "Sec C / Pg 5", "24 Months for elective surgeries", "Appendicitis exempt (acute/emergency)"),
        ("DOC-001", "Hospital Discharge Summary", "Sec E / Pg 7", "Mandatory; diagnosis & surgery", "Discharge Summary 15/09 submitted"),
        ("DOC-002", "Hospital Medical Bill", "Sec E / Pg 7", "Mandatory; bill total Rs. 85,000", "Final Bill HMH-BILL-2026-8842"),
        ("DOC-003", "Hospital Admission Record", "Sec E / Pg 7", "Mandatory; date & symptoms", "Admission Record 12/09 submitted"),
        ("DOC-004", "Medical Diagnostic Report", "Sec E / Pg 7", "Mandatory; lab & ultrasound", "Diagnostic Reports submitted"),
        ("FIN-001", "Sum Insured Pool", "Sec F / Pg 8", "Rs. 5,00,000 per policy year", "Claim Rs. 85,000 < Rs. 5,00,000"),
    ]
    rag_rows = [[Paragraph("<b>Clause ID</b>", styles['TableHead']), Paragraph("<b>Clause Title</b>", styles['TableHead']), Paragraph("<b>Location</b>", styles['TableHead']), Paragraph("<b>Evidence Standard</b>", styles['TableHead']), Paragraph("<b>Claim Alignment</b>", styles['TableHead'])]]
    for cid, ctitle, cloc, cstd, calign in rag_index:
        rag_rows.append([Paragraph(f"<b>{cid}</b>", styles['TableCellBold']), Paragraph(ctitle, styles['TableCellBold']), Paragraph(cloc, styles['TableCell']), Paragraph(cstd, styles['TableCell']), Paragraph(calign, styles['TableCell'])])
    t_rag = Table(rag_rows, colWidths=[w_content * 0.14, w_content * 0.24, w_content * 0.16, w_content * 0.24, w_content * 0.22])
    t_rag.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_rag)
    story.append(PageBreak())

    # PAGE 11: Endorsement
    add_policy_header("SECTION I: POLICY ENDORSEMENT, GRIEVANCE & OMBUDSMAN", "Statutory Safeguards")
    story.append(Paragraph(
        "<b>Endorsement Schedule & Sign-Off:</b> Issued under the common seal of Sunrise Shield Health Insurance Ltd. "
        "and signed by its authorized officer on 28 March 2026 at Mumbai.",
        styles['BodyP']
    ))
    story.append(Spacer(1, 4))
    endorse_box = [
        [Paragraph("<b>Authorized Underwriter Signatory</b>", styles['TableCellBold']), Paragraph("<b>Grievance Redressal Officer</b>", styles['TableCellBold'])],
        [
            Paragraph(
                "<b>SUNRISE SHIELD HEALTH INSURANCE LTD.</b><br/>"
                "[Signed: Digitally Verified Key ID: SSHI-AUTH-882]<br/>"
                "<b>Dr. Vikramaditya Sen</b>, Chief Underwriting Officer<br/>"
                "Corporate Office: Tower 4, Financial District, Mumbai 400051",
                styles['TableCell']
            ),
            Paragraph(
                "<b>Customer Grievance Redressal Cell:</b><br/>"
                "Toll Free: 1800-266-9999 (Synthetic)<br/>"
                "Email: grievances@sunriseshield-test.com<br/>"
                "Statutory Redressal: Insurance Ombudsman",
                styles['TableCell']
            )
        ]
    ]
    t_end = Table(endorse_box, colWidths=[w_content * 0.5, w_content * 0.5])
    t_end.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_end)
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>SYNTHETIC DATA DISCLAIMER:</b> THIS DOCUMENT IS ENTIRELY FICTIONAL AND SYNTHETIC, PREPARED SPECIFICALLY FOR AUTOMATED END-TO-END PIPELINE TESTING OF INSUREMATE.", styles['BodyP']))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"-> Generated Policy PDF: {output_path} (11 pages)")


# ----------------------------------------------------------------------
# Generator for PDF 2: InsureMate_Test_Health_Insurance_Claim_Documents.pdf (16 pages)
# ----------------------------------------------------------------------
def generate_claim_pdf(output_path: Path):
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    w_content = A4[0] - 72

    # Clean claim header without any of the 18 policy classifier trigger strings
    def add_claim_header(page_title: str, doc_code: str, date_str: str):
        hdr_data = [
            [
                Paragraph("<b>Harmony Multispeciality Hospital</b> | Healthcare Records Department", styles['DocHeaderTitle']),
                Paragraph(f"<b>DOC CODE: {doc_code}</b>", styles['TableCellRightBold'])
            ],
            [
                Paragraph(
                    "<b>Hospital:</b> Harmony Multispeciality Hospital &nbsp;|&nbsp; "
                    "<b>Patient Name:</b> Aarav Mehta &nbsp;|&nbsp; <b>Age/Sex:</b> 34 / M<br/>"
                    "<b>Insurance TPA Reference:</b> SSHI-TEST-2026-001 &nbsp;|&nbsp; "
                    "<b>Claim Dossier Ref:</b> CLM-TEST-2026-0042 &nbsp;|&nbsp; "
                    "<b>IPD Record No:</b> HMH-IPD-2026-4402",
                    styles['MetaBoxText']
                ),
                Paragraph(f"<b>Record Date:</b> {date_str}<br/><b>Status:</b> Fully Paid", styles['TableCellRight'])
            ]
        ]
        t = Table(hdr_data, colWidths=[w_content * 0.72, w_content * 0.28])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 3))
        story.append(Paragraph(f"<b>{page_title}</b>", styles['SectionH1']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1E3A8A"), spaceAfter=5))

    # PAGE 1: Document 1: Cover Letter & Index
    add_claim_header("DOCUMENT 1: HOSPITAL INDOOR ADMISSION - SUBMISSION COVER LETTER", "DOC-001A", "15/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Discharge Date: 15/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "To, The Claims Adjudication Manager, Sunrise Shield Health Insurance Ltd.<br/>"
        "<b>Subject: Submission of Inpatient Reimbursement Claim for Aarav Mehta (Ref: CLM-TEST-2026-0042)</b>",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "Dear Sir / Madam,<br/>"
        "I am submitting the medical reimbursement claim dossier in respect of my planned inpatient "
        "hospitalization at <b>Harmony Multispeciality Hospital</b> for <b>Acute Appendicitis</b> treated with "
        "<b>Laparoscopic Appendectomy</b>. The hospitalization commenced on <b>12 September 2026 (12/09/2026)</b> and "
        "concluded with discharge on <b>15 September 2026 (15/09/2026)</b>.<br/>"
        "All inpatient hospital expenses amounting to <b>Rs. 85,000</b> have been settled in full by me directly with the hospital.",
        styles['BodyP']
    ))
    story.append(Spacer(1, 4))
    cov_idx = [
        [Paragraph("<b>Pg</b>", styles['TableHead']), Paragraph("<b>Subdocument Name</b>", styles['TableHead']), Paragraph("<b>Document Identifier</b>", styles['TableHead']), Paragraph("<b>Content / Clinical Scope</b>", styles['TableHead'])],
        [Paragraph("1", styles['TableCell']), Paragraph("Hospital Indoor Admission Cover Letter", styles['TableCellBold']), Paragraph("DOC-001A", styles['TableCell']), Paragraph("Claim cover letter & document checklist index", styles['TableCell'])],
        [Paragraph("2-3", styles['TableCell']), Paragraph("Hospital Indoor Admission Claim Form", styles['TableCellBold']), Paragraph("DOC-001B", styles['TableCell']), Paragraph("Part A & B: Identity, clinical data, signed declarations", styles['TableCell'])],
        [Paragraph("4", styles['TableCell']), Paragraph("Hospital Indoor Admission Record", styles['TableCellBold']), Paragraph("DOC-002", styles['TableCell']), Paragraph("Triage assessment, initial diagnosis, vitals, treating surgeon", styles['TableCell'])],
        [Paragraph("5-6", styles['TableCell']), Paragraph("Hospital Discharge Summary", styles['TableCellBold']), Paragraph("DOC-003", styles['TableCell']), Paragraph("Diagnosis (Acute Appendicitis), surgical summary, follow-up advice", styles['TableCell'])],
        [Paragraph("7", styles['TableCell']), Paragraph("Medical Diagnostic Report (Pathology)", styles['TableCellBold']), Paragraph("DOC-004A", styles['TableCell']), Paragraph("Complete Blood Count (CBC) with elevated WBC & CRP", styles['TableCell'])],
        [Paragraph("8", styles['TableCell']), Paragraph("Diagnostic Ultrasound Scan Report", styles['TableCellBold']), Paragraph("DOC-004B", styles['TableCell']), Paragraph("Abdominal Ultrasound Scan Report verifying acute appendicitis", styles['TableCell'])],
        [Paragraph("9", styles['TableCell']), Paragraph("Hospital Operation Notes & Surgical Record", styles['TableCellBold']), Paragraph("DOC-005", styles['TableCell']), Paragraph("Laparoscopic Appendectomy surgical findings and anesthesia", styles['TableCell'])],
        [Paragraph("10", styles['TableCell']), Paragraph("Hospital Medical Bill & COV-002 Room Rent & Boarding Folio", styles['TableCellBold']), Paragraph("DOC-006", styles['TableCell']), Paragraph("Inpatient tax invoice & COV-002 Room Rent & Boarding Certificate totaling Rs. 85,000", styles['TableCell'])],
        [Paragraph("11", styles['TableCell']), Paragraph("Official Hospital Payment Receipts", styles['TableCellBold']), Paragraph("DOC-007", styles['TableCell']), Paragraph("Receipt showing full payment of Rs. 85,000, zero balance", styles['TableCell'])],
        [Paragraph("12", styles['TableCell']), Paragraph("Hospital Pharmacy Bill & Invoices", styles['TableCellBold']), Paragraph("DOC-008", styles['TableCell']), Paragraph("Itemized medicine dispensing bills totaling Rs. 9,000", styles['TableCell'])],
        [Paragraph("13", styles['TableCell']), Paragraph("Reimbursement Bank Account Proof", styles['TableCellBold']), Paragraph("DOC-009", styles['TableCell']), Paragraph("Cancelled cheque text layout for direct NEFT bank transfer", styles['TableCell'])],
        [Paragraph("14", styles['TableCell']), Paragraph("Claim Document Verification Checklist", styles['TableCellBold']), Paragraph("DOC-010", styles['TableCell']), Paragraph("Audit status of mandatory requirements", styles['TableCell'])],
        [Paragraph("15", styles['TableCell']), Paragraph("Supporting Clinical Progress Notes", styles['TableCellBold']), Paragraph("DOC-011", styles['TableCell']), Paragraph("Daily inpatient progress timeline from 12 Sept to 15 Sept 2026", styles['TableCell'])],
        [Paragraph("16", styles['TableCell']), Paragraph("Cross-Reference & Traceability Index", styles['TableCellBold']), Paragraph("DOC-012", styles['TableCell']), Paragraph("Entity verification matrix mapping all dates, clauses, and amounts", styles['TableCell'])],
    ]
    t_cidx = Table(cov_idx, colWidths=[w_content * 0.08, w_content * 0.36, w_content * 0.18, w_content * 0.38])
    t_cidx.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    story.append(t_cidx)
    story.append(Spacer(1, 3))
    story.append(Paragraph("Yours faithfully,<br/><b>[Signed: Aarav Mehta]</b><br/>Claimant | Mobile: +91 98201 XXXXX", styles['BodyP']))
    story.append(PageBreak())

    # PAGE 2: Document 2: Claim Form Part A
    add_claim_header("DOCUMENT 2: HOSPITAL INDOOR ADMISSION - REIMBURSEMENT CLAIM FORM (PART A)", "DOC-001B-1", "15/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Discharge Date: 15/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph("<b>CLAIM FORM - PART A: DETAILS OF PRIMARY INSURED & PATIENT</b>", styles['SectionH2']))
    part_a_data = [
        [Paragraph("<b>Field Label</b>", styles['TableHead']), Paragraph("<b>Claimant Entry / Verified Value</b>", styles['TableHead']), Paragraph("<b>Coverage Benchmark</b>", styles['TableHead'])],
        [Paragraph("Insurance TPA Reference", styles['TableCellBold']), Paragraph("<b>SSHI-TEST-2026-001</b>", styles['TableCellBold']), Paragraph("Valid & Active Coverage (01/04/2026 - 31/03/2027)", styles['TableCell'])],
        [Paragraph("Claim Reference Number", styles['TableCellBold']), Paragraph("<b>CLM-TEST-2026-0042</b>", styles['TableCellBold']), Paragraph("Registered Electronic Claim Dossier", styles['TableCell'])],
        [Paragraph("Primary Insured Name", styles['TableCellBold']), Paragraph("<b>Aarav Mehta</b>", styles['TableCellBold']), Paragraph("Primary Insured Subscriber", styles['TableCell'])],
        [Paragraph("Patient Name", styles['TableCellBold']), Paragraph("<b>Aarav Mehta</b>", styles['TableCellBold']), Paragraph("Self (Identical to Primary Insured)", styles['TableCell'])],
        [Paragraph("Patient Gender & Age", styles['TableCellBold']), Paragraph("Male, 34 Years (DOB: 14/06/1992)", styles['TableCell']), Paragraph("Adult Inpatient Category", styles['TableCell'])],
        [Paragraph("Communication Address", styles['TableCellBold']), Paragraph("Flat 402, Greenfield Heights, Andheri East, Mumbai 400069", styles['TableCell']), Paragraph("Registered Residential Address", styles['TableCell'])],
        [Paragraph("Email & Mobile", styles['TableCellBold']), Paragraph("aarav.mehta.synthetic@example.com | +91 98201 XXXXX", styles['TableCell']), Paragraph("Verified Direct Contact", styles['TableCell'])],
        [Paragraph("Other Health Insurance Held?", styles['TableCellBold']), Paragraph("<b>No (Nil Other Coverage)</b>", styles['TableCellBold']), Paragraph("Single Insurer Adjudication", styles['TableCell'])],
        [Paragraph("Pre-Existing Conditions?", styles['TableCellBold']), Paragraph("<b>No (Nil Pre-Existing Medical Conditions)</b>", styles['TableCellBold']), Paragraph("Exempt from qualifying waiting threshold", styles['TableCell'])],
        [Paragraph("Accident / Trauma Cause?", styles['TableCellBold']), Paragraph("<b>No (Medical Sickness Only)</b>", styles['TableCellBold']), Paragraph("Exempt from Police report requirement", styles['TableCell'])],
        [Paragraph("Hospital Name & Facility", styles['TableCellBold']), Paragraph("<b>Harmony Multispeciality Hospital</b>", styles['TableCellBold']), Paragraph("Tertiary Network Hospital", styles['TableCell'])],
        [Paragraph("Hospital Registration No", styles['TableCellBold']), Paragraph("MOH-MH-MUM-2018-9924", styles['TableCell']), Paragraph("Accredited Medical Center", styles['TableCell'])],
    ]
    t_pa = Table(part_a_data, colWidths=[w_content * 0.32, w_content * 0.38, w_content * 0.30])
    t_pa.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_pa)
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Claimant Declaration:</b> I declare that the details furnished are true and correct.<br/><b>Signature of Patient:</b> [Signed: Aarav Mehta - Placeholder]", styles['BodyP']))
    story.append(PageBreak())

    # PAGE 3: Document 2: Claim Form Part B
    add_claim_header("DOCUMENT 2: HOSPITAL INDOOR ADMISSION - REIMBURSEMENT CLAIM FORM (PART B)", "DOC-001B-2", "15/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Discharge Date: 15/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph("<b>CLAIM FORM - PART B: HOSPITALIZATION DETAILS, EXPENSES & BANK DATA</b>", styles['SectionH2']))
    part_b_data = [
        [Paragraph("<b>Hospitalization Metric</b>", styles['TableHead']), Paragraph("<b>Clinical & Financial Data</b>", styles['TableHead']), Paragraph("<b>Coverage Benchmark</b>", styles['TableHead'])],
        [Paragraph("Hospital Admission Date", styles['TableCellBold']), Paragraph("<b>12/09/2026 (12 September 2026)</b>", styles['TableCellBold']), Paragraph("Falls within Coverage Period", styles['TableCell'])],
        [Paragraph("Hospital Discharge Date", styles['TableCellBold']), Paragraph("<b>15/09/2026 (15 September 2026)</b>", styles['TableCellBold']), Paragraph("Duration: 3 Nights / 4 Days", styles['TableCell'])],
        [Paragraph("Primary Diagnosis", styles['TableCellBold']), Paragraph("<b>Acute Appendicitis (ICD-10: K35.80)</b>", styles['TableCellBold']), Paragraph("Covered Inpatient Medical Condition", styles['TableCell'])],
        [Paragraph("Procedure Performed", styles['TableCellBold']), Paragraph("<b>Laparoscopic Appendectomy</b>", styles['TableCellBold']), Paragraph("Standard Covered Surgical Procedure", styles['TableCell'])],
        [Paragraph("Treating Surgeon", styles['TableCellBold']), Paragraph("Dr. Rajesh Sharma, MS, FMAS (Reg: MMC-2004-981)", styles['TableCell']), Paragraph("Registered General & Laparoscopic Surgeon", styles['TableCell'])],
        [Paragraph("Room Category Occupied", styles['TableCellBold']), Paragraph("Twin Sharing Room (Room 304B)", styles['TableCell']), Paragraph("Daily tariff Rs. 5,000 matches cap", styles['TableCell'])],
        [Paragraph("Total Hospital Bill Amount", styles['TableCellBold']), Paragraph("<b>Rs. 85,000.00</b>", styles['TableCellBold']), Paragraph("Invoice HMH-BILL-2026-8842", styles['TableCell'])],
        [Paragraph("Total Claimed Amount", styles['TableCellBold']), Paragraph("<b>Rs. 85,000.00</b>", styles['TableCellBold']), Paragraph("Full Reimbursement Request", styles['TableCell'])],
        [Paragraph("Total Amount Paid by Patient", styles['TableCellBold']), Paragraph("<b>Rs. 85,000.00 (Zero Balance)</b>", styles['TableCellBold']), Paragraph("Settled via Card & Netbanking", styles['TableCell'])],
        [Paragraph("Bank Name (for Credit)", styles['TableCellBold']), Paragraph("Apex National Commercial Bank (Fictional)", styles['TableCell']), Paragraph("Licensed Scheduled Commercial Bank", styles['TableCell'])],
        [Paragraph("Account Holder Name", styles['TableCellBold']), Paragraph("<b>Aarav Mehta</b>", styles['TableCellBold']), Paragraph("Matches Primary Insured Name Exactly", styles['TableCell'])],
        [Paragraph("Account Number", styles['TableCellBold']), Paragraph("XXXX-XXXX-XXXX-5521 (Masked Account)", styles['TableCell']), Paragraph("Masked Electronic Payout Format", styles['TableCell'])],
        [Paragraph("IFSC Identifier", styles['TableCellBold']), Paragraph("APEX0001928 (Fictional Identifier)", styles['TableCell']), Paragraph("RTGS/NEFT Routing Branch Identifier", styles['TableCell'])],
    ]
    t_pb = Table(part_b_data, colWidths=[w_content * 0.32, w_content * 0.38, w_content * 0.30])
    t_pb.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_pb)
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Treating Doctor Certification:</b> I certify that Mr. Aarav Mehta underwent laparoscopic appendectomy on 13/09/2026. The treatment was medically necessary.<br/><b>Doctor Signature & Stamp:</b> [Signed: Dr. Rajesh Sharma, MS, FMAS - Reg: MMC-2004-981]", styles['BodyP']))
    story.append(PageBreak())

    # PAGE 4: Document 3: Hospital Indoor Admission Record
    add_claim_header("DOCUMENT 3: HOSPITAL INDOOR ADMISSION RECORD & CLINICAL ASSESSMENT", "DOC-002", "12/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Admission Time: 09:30 AM</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>DEPARTMENT OF GENERAL & MINIMALLY INVASIVE SURGERY</b><br/>"
        "<b>Patient: Aarav Mehta</b> | Age: 34 / Male | UHID: HMH-2026-99120 | IPD No: HMH-IPD-2026-4402<br/>"
        "<b>Hospital: Harmony Multispeciality Hospital</b>, S.V. Road, Goregaon West, Mumbai 400062",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    adm_clinical = [
        [Paragraph("<b>Clinical Evaluation Head</b>", styles['TableHead']), Paragraph("<b>Emergency & Inpatient Triage Findings</b>", styles['TableHead'])],
        [Paragraph("Presenting Complaints", styles['TableCellBold']), Paragraph("Severe sharp pain in the right lower quadrant (RLQ) of abdomen since 18 hours, radiating from periumbilical area. Associated with 2 episodes of vomiting, low-grade fever, and anorexia.", styles['TableCell'])],
        [Paragraph("Clinical Examination", styles['TableCellBold']), Paragraph("Patient in moderate distress. Abdomen: Severe tenderness at McBurney's point with guarding and positive rebound tenderness (Blumberg's sign). Rovsing's sign positive. Bowel sounds sluggish.", styles['TableCell'])],
        [Paragraph("Admission Vitals", styles['TableCellBold']), Paragraph("BP: 124/82 mmHg | Pulse: 96 bpm, regular | Temp: 100.4°F (38.0°C) | Resp Rate: 18/min | SpO2: 99% on room air.", styles['TableCell'])],
        [Paragraph("Systemic Review", styles['TableCellBold']), Paragraph("CVS: S1 S2 heard. RS: Bilateral clear breath sounds. CNS: Alert, oriented x 3.", styles['TableCell'])],
        [Paragraph("Past Medical History", styles['TableCellBold']), Paragraph("No prior history of diabetes, hypertension, asthma, or cardiac disorder. No prior surgeries. No known drug allergies.", styles['TableCell'])],
        [Paragraph("Initial Diagnosis", styles['TableCellBold']), Paragraph("<b>Acute Appendicitis (Suspected Non-Perforated)</b>", styles['TableCellBold'])],
        [Paragraph("Admission Indication", styles['TableCellBold']), Paragraph("Inpatient surgical admission for intravenous resuscitation, urgent diagnostic investigation (USG/CBC), and planned laparoscopic appendectomy under general anesthesia.", styles['TableCell'])],
        [Paragraph("Treating Consultant", styles['TableCellBold']), Paragraph("Dr. Rajesh Sharma, MS, FMAS (Senior Consultant Laparoscopic Surgeon)", styles['TableCell'])],
    ]
    t_adm = Table(adm_clinical, colWidths=[w_content * 0.28, w_content * 0.72])
    t_adm.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_adm)
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Immediate Orders:</b> Nil by mouth (NBM). IV Normal Saline @ 100 ml/hr. Inj. Cefuroxime 1.5g IV stat. Urgent ultrasound and CBC.<br/><b>Attending Medical Officer:</b> Dr. Anil Verma, MBBS (Emergency Duty Registrar)", styles['BodyP']))
    story.append(PageBreak())

    # PAGE 5: Document 4: Hospital Discharge Summary (Page 1)
    add_claim_header("DOCUMENT 4: HOSPITAL DISCHARGE SUMMARY - CLINICAL SUMMARY & DIAGNOSIS", "DOC-003-1", "15/09/2026")
    story.append(Paragraph("<b>Discharge Date: 15/09/2026 | Admission Date: 12/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>Patient Name: Aarav Mehta</b> | Age: 34 / Male | Bed No: 304B (Twin Sharing)<br/>"
        "<b>Hospital: Harmony Multispeciality Hospital</b> | Dept: General & Laparoscopic Surgery<br/>"
        "<b>Primary Diagnosis: Acute Appendicitis (ICD-10: K35.80)</b><br/>"
        "<b>Procedure: Laparoscopic Appendectomy (Performed on 13/09/2026)</b>",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    ds_part1 = [
        [Paragraph("<b>Clinical Summary Section</b>", styles['TableHead']), Paragraph("<b>Recorded Findings & Inpatient Course</b>", styles['TableHead'])],
        [Paragraph("Presenting History", styles['TableCellBold']), Paragraph("A 34-year-old male presented on 12/09/2026 with severe right iliac fossa abdominal pain, vomiting, and low-grade fever. Emergency evaluation and imaging verified acute appendicitis.", styles['TableCell'])],
        [Paragraph("Pre-Operative Investigations", styles['TableCellBold']), Paragraph("USG Abdomen (12/09/2026) revealed a swollen, non-compressible appendix measuring 8.6 mm in outer diameter with surrounding periappendiceal fat stranding. CBC showed leukocytosis (WBC 14,800/mcL) with neutrophilia (84%) and elevated CRP (38 mg/L).", styles['TableCell'])],
        [Paragraph("Surgical Intervention", styles['TableCellBold']), Paragraph("Patient was stabilized, kept NBM, and taken for Laparoscopic Appendectomy on 13/09/2026 under General Endotracheal Anesthesia. Three laparoscopic ports placed. Appendix identified as acutely inflamed, congested, and retrocecal without perforation. Mesoappendix dissected using bipolar diathermy. Base ligated with Endoloop and divided. Specimen extracted intact via 10mm umbilical port.", styles['TableCell'])],
        [Paragraph("Operative Findings", styles['TableCellBold']), Paragraph("Congested, hyperemic appendix measuring 7.5 cm in length and 9 mm diameter. Minimal reactive serous fluid in pelvis aspirated. Caecum and terminal ileum normal. No evidence of purulent perforation.", styles['TableCell'])],
        [Paragraph("Surgeon & Anesthetist", styles['TableCellBold']), Paragraph("Surgeon: Dr. Rajesh Sharma, MS, FMAS | Anesthetist: Dr. Priya Desai, MD (Anesth)", styles['TableCell'])],
    ]
    t_ds1 = Table(ds_part1, colWidths=[w_content * 0.28, w_content * 0.72])
    t_ds1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_ds1)
    story.append(PageBreak())

    # PAGE 6: Document 4: Hospital Discharge Summary (Page 2)
    add_claim_header("DOCUMENT 4: HOSPITAL DISCHARGE SUMMARY - TREATMENT & FOLLOW-UP ADVICE", "DOC-003-2", "15/09/2026")
    story.append(Paragraph("<b>Discharge Date: 15/09/2026 | Admission Date: 12/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>POST-OPERATIVE INPATIENT COURSE & DISCHARGE ADVICE</b><br/>"
        "Patient: Aarav Mehta | IPD No: HMH-IPD-2026-4402 | Hospital: Harmony Multispeciality Hospital",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    ds_part2 = [
        [Paragraph("<b>Care Category</b>", styles['TableHead']), Paragraph("<b>Discharge Evaluation & Instructions</b>", styles['TableHead'])],
        [Paragraph("Hospital Course Post-Surgery", styles['TableCellBold']), Paragraph("Patient tolerated surgery well. Post-op vitals stable. Commenced on oral sips on 14/09 morning, advanced to soft diet by evening. Flatus passed on post-op day 1. Ambulated comfortably.", styles['TableCell'])],
        [Paragraph("Condition at Discharge", styles['TableCellBold']), Paragraph("Hemodynamically stable. Afebrile. Surgical port incisions clean, dry, and healthy. No discharge, hematoma, or tenderness. Abdomen soft, non-tender, bowel sounds active.", styles['TableCell'])],
        [Paragraph("Vitals at Discharge (15/09)", styles['TableCellBold']), Paragraph("BP: 120/78 mmHg | Pulse: 76 bpm | Temp: 98.4°F | Resp: 16/min | SpO2: 99% on ambient air.", styles['TableCell'])],
        [Paragraph("Discharge Medications", styles['TableCellBold']), Paragraph("1. Tab Cefpodoxime 200mg BD x 5 days (Oral antibiotic)<br/>2. Tab Paracetamol 650mg TDS PRN x 3 days (Analgesic)<br/>3. Tab Pantoprazole 40mg OD before breakfast x 7 days<br/>4. Syrup Lactulose 15ml at bedtime as needed.", styles['TableCell'])],
        [Paragraph("Activity & Wound Care", styles['TableCellBold']), Paragraph("Keep dressings dry and clean. Avoid heavy lifting (>5 kg) for 3 weeks. Normal walking encouraged.", styles['TableCell'])],
        [Paragraph("Follow-up Consultation", styles['TableCellBold']), Paragraph("Review in Surgery OPD with Dr. Rajesh Sharma on 22/09/2026 for suture inspection.", styles['TableCell'])],
    ]
    t_ds2 = Table(ds_part2, colWidths=[w_content * 0.28, w_content * 0.72])
    t_ds2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_ds2)
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        "<b>Treating Consultant Signature:</b> [Signed: Dr. Rajesh Sharma, MS, FMAS]<br/>"
        "<b>Hospital Stamp:</b> [SEAL: Harmony Multispeciality Hospital - Records Certified]",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 7: Document 5: Pathology Diagnostic Report
    add_claim_header("DOCUMENT 5: MEDICAL DIAGNOSTIC REPORT - PATHOLOGY LABORATORY INVESTIGATION", "DOC-004A", "12/09/2026")
    story.append(Paragraph("<b>Report Date: 12/09/2026 | Collection Time: 10:15 AM</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>DEPARTMENT OF CLINICAL PATHOLOGY & HEMATOLOGY</b><br/>"
        "Patient: Aarav Mehta | Age: 34 / M | Ref By: Dr. Rajesh Sharma<br/>"
        "Hospital: Harmony Multispeciality Hospital | Lab Accession No: HMH-LAB-2026-11842",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    lab_tests = [
        [Paragraph("<b>Investigation Parameter</b>", styles['TableHead']), Paragraph("<b>Observed Result</b>", styles['TableHead']), Paragraph("<b>Reference Biological Range</b>", styles['TableHead']), Paragraph("<b>Clinical Interpretation</b>", styles['TableHead'])],
        [Paragraph("Hemoglobin (Hb)", styles['TableCellBold']), Paragraph("14.6 g/dL", styles['TableCell']), Paragraph("13.0 - 17.0 g/dL", styles['TableCell']), Paragraph("Normal", styles['TableCell'])],
        [Paragraph("Total Leukocyte Count (WBC)", styles['TableCellBold']), Paragraph("<b>14,800 /mcL (High)</b>", styles['TableCellBold']), Paragraph("4,000 - 11,000 /mcL", styles['TableCell']), Paragraph("Marked Leukocytosis (Infection)", styles['TableCellBold'])],
        [Paragraph("Neutrophils", styles['TableCellBold']), Paragraph("<b>84 % (High)</b>", styles['TableCellBold']), Paragraph("40 - 70 %", styles['TableCell']), Paragraph("Neutrophilia (Left Shift)", styles['TableCellBold'])],
        [Paragraph("Lymphocytes", styles['TableCellBold']), Paragraph("12 % (Low)", styles['TableCell']), Paragraph("20 - 45 %", styles['TableCell']), Paragraph("Relative lymphopenia", styles['TableCell'])],
        [Paragraph("Platelet Count", styles['TableCellBold']), Paragraph("245,000 /mcL", styles['TableCell']), Paragraph("150,000 - 450,000 /mcL", styles['TableCell']), Paragraph("Normal", styles['TableCell'])],
        [Paragraph("C-Reactive Protein (CRP)", styles['TableCellBold']), Paragraph("<b>38.4 mg/L (High)</b>", styles['TableCellBold']), Paragraph("0.0 - 5.0 mg/L", styles['TableCell']), Paragraph("Acute Inflammatory Marker Elevated", styles['TableCellBold'])],
        [Paragraph("Serum Creatinine", styles['TableCellBold']), Paragraph("0.92 mg/dL", styles['TableCell']), Paragraph("0.70 - 1.20 mg/dL", styles['TableCell']), Paragraph("Normal Renal Function", styles['TableCell'])],
        [Paragraph("Random Blood Glucose", styles['TableCellBold']), Paragraph("104 mg/dL", styles['TableCell']), Paragraph("70 - 140 mg/dL", styles['TableCell']), Paragraph("Normoglycemic", styles['TableCell'])],
    ]
    t_lab = Table(lab_tests, colWidths=[w_content * 0.30, w_content * 0.22, w_content * 0.24, w_content * 0.24])
    t_lab.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_lab)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Laboratory Impression:</b> Peripheral blood picture demonstrates pronounced acute leukocytosis with neutrophilic shift "
        "and elevated CRP, consistent with acute suppurative inflammation (Acute Appendicitis).<br/>"
        "<b>Consultant Pathologist:</b> Dr. Meena Chawla, MD (Path) - Reg: MMC-1998-4421",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 8: Document 5: Medical Diagnostic Scan Report (Radiology Ultrasound)
    add_claim_header("DOCUMENT 5: MEDICAL DIAGNOSTIC SCAN REPORT - RADIOLOGY ULTRASOUND SCAN REPORT", "DOC-004B", "12/09/2026")
    story.append(Paragraph("<b>Report Date: 12/09/2026 | Scan Time: 11:30 AM | Modality: High-Resolution Real-Time Ultrasound Scan</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>DEPARTMENT OF RADIO-DIAGNOSIS & ULTRASONIC SCANNING</b><br/>"
        "Patient: Aarav Mehta | Age: 34 / M | Ref By: Dr. Rajesh Sharma<br/>"
        "Hospital: Harmony Multispeciality Hospital | Diagnostic Scan Study No: HMH-SCAN-2026-7822",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    usg_findings = [
        [Paragraph("<b>Anatomical Region / Scan Plane</b>", styles['TableHead']), Paragraph("<b>Radiological Scan Findings & Acoustic Observations</b>", styles['TableHead'])],
        [Paragraph("Right Iliac Fossa (Appendix Scan)", styles['TableCellBold']), Paragraph("<b>Targeted USG scan demonstrates a blind-ending, non-compressible aperistaltic tubular loop in right iliac fossa arising from cecum base. Maximum outer diameter on transverse scan measures 8.6 mm (Normal &lt; 6.0 mm). Appendiceal wall demonstrates hypervascularity on color Doppler scan interrogation. Surrounding periappendiceal echogenic fat stranding and trace free fluid visualized. Findings diagnostic of Acute Appendicitis on ultrasound scan.</b>", styles['TableCellBold'])],
        [Paragraph("Hepatobiliary Scan Survey", styles['TableCellBold']), Paragraph("Liver normal in acoustic span (14.2 cm), smooth capsular contour, homogeneous parenchymal echotexture. Gallbladder well-distended, thin-walled, calculi absent. No intrahepatic or extrahepatic biliary ductal dilatation on ultrasound scan.", styles['TableCell'])],
        [Paragraph("Pancreas & Spleen Scan", styles['TableCellBold']), Paragraph("Pancreatic parenchymal echo pattern normal across head, body, and tail. Spleen normal span (9.8 cm), homogeneous without focal scan lesion.", styles['TableCell'])],
        [Paragraph("Renal & Urinary Bladder Scan", styles['TableCellBold']), Paragraph("Bilateral kidneys normal in position and acoustic axis; intact corticomedullary differentiation. No scan evidence of hydronephrosis, calculus, or mass. Urinary bladder wall normal with clear acoustic lumen.", styles['TableCell'])],
    ]
    t_usg = Table(usg_findings, colWidths=[w_content * 0.30, w_content * 0.70])
    t_usg.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_usg)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>SCAN REPORT IMPRESSION:</b> <b>DIAGNOSTIC ULTRASOUND SCAN CONFIRMS ACUTE APPENDICITIS WITHOUT PERFORATION OR ABSCESS. "
        "SCAN REPORT SUPPORTS URGENT SURGICAL INTERVENTION.</b><br/>"
        "<b>Consultant Radiologist:</b> Dr. Sandeep Kulkarni, MD, DMRD (Consultant Radiologist & Sonologist) - Reg: MMC-2001-6552",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 9: Document 6: Operation Notes
    add_claim_header("DOCUMENT 6: HOSPITAL INDOOR ADMISSION - OPERATION NOTES & SURGICAL RECORD", "DOC-005", "13/09/2026")
    story.append(Paragraph("<b>Procedure Date: 13/09/2026 | OT Slot: 10:00 AM - 11:15 AM</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>OPERATION THEATRE NO. 2 (MINIMALLY INVASIVE SUITE)</b><br/>"
        "Patient: Aarav Mehta | IPD No: HMH-IPD-2026-4402 | Hospital: Harmony Multispeciality Hospital<br/>"
        "Surgeon: Dr. Rajesh Sharma, MS, FMAS | Anesthetist: Dr. Priya Desai, MD (Anesth)",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    op_data = [
        [Paragraph("<b>Surgical Metric</b>", styles['TableHead']), Paragraph("<b>Operative Documentation</b>", styles['TableHead'])],
        [Paragraph("Procedure Name", styles['TableCellBold']), Paragraph("<b>Laparoscopic Appendectomy</b>", styles['TableCellBold'])],
        [Paragraph("Pre-Operative Diagnosis", styles['TableCellBold']), Paragraph("Acute Appendicitis (ICD-10: K35.80)", styles['TableCell'])],
        [Paragraph("Post-Operative Diagnosis", styles['TableCellBold']), Paragraph("Acute Phlegmonous Appendicitis (Non-Perforated)", styles['TableCell'])],
        [Paragraph("Anesthesia Type", styles['TableCellBold']), Paragraph("General Endotracheal Anesthesia with Controlled Ventilation", styles['TableCell'])],
        [Paragraph("Port Placements", styles['TableCellBold']), Paragraph("10 mm infra-umbilical camera port; 5 mm suprapubic working port; 5 mm left lower quadrant working port.", styles['TableCell'])],
        [Paragraph("Operative Procedure", styles['TableCellBold']), Paragraph("Pneumoperitoneum established at 12 mmHg CO2. Retrocecal appendix mobilized. Mesoappendix dissected with bipolar electrocautery. Base double ligated using Endoloop. Appendix transected. Specimen retrieved via umbilical port in EndoBag. Peritoneal cavity lavaged. Port sites closed under direct vision.", styles['TableCell'])],
        [Paragraph("Estimated Blood Loss", styles['TableCellBold']), Paragraph("< 25 ml (Negligible). No blood transfusion required.", styles['TableCell'])],
        [Paragraph("Implants / Prostheses", styles['TableCellBold']), Paragraph("<b>None. No permanent surgical implant utilized.</b>", styles['TableCellBold'])],
        [Paragraph("Specimen", styles['TableCellBold']), Paragraph("Excised appendix (7.5 cm) sent for histopathology examination.", styles['TableCell'])],
        [Paragraph("Post-Op Condition", styles['TableCellBold']), Paragraph("Patient shifted to PACU extubated, conscious, and hemodynamically stable.", styles['TableCell'])],
    ]
    t_op = Table(op_data, colWidths=[w_content * 0.28, w_content * 0.72])
    t_op.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_op)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Operating Surgeon Signature:</b> [Signed: Dr. Rajesh Sharma, MS, FMAS]<br/>"
        "<b>Anesthesiologist Signature:</b> [Signed: Dr. Priya Desai, MD (Anesth)]",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 10: Document 7: Final Itemized Hospital Bill
    add_claim_header("DOCUMENT 7: HOSPITAL MEDICAL BILL - FINAL INPATIENT TAX INVOICE & COV-002 ROOM RENT & BOARDING FOLIO", "DOC-006", "15/09/2026")
    story.append(Paragraph(
        "<b>Bill Number: HMH-BILL-2026-8842 &nbsp;|&nbsp; Bill Date: 15/09/2026</b><br/>"
        "Patient Name: Aarav Mehta &nbsp;|&nbsp; IPD No: HMH-IPD-2026-4402 &nbsp;|&nbsp; Admission: 12/09/2026 &nbsp;|&nbsp; Discharge: 15/09/2026<br/>"
        "Hospital: Harmony Multispeciality Hospital &nbsp;|&nbsp; GSTIN: 27AABCH8821M1ZX",
        styles['BodyPBold']
    ))
    story.append(Spacer(1, 3))
    bill_items = [
        [Paragraph("<b>Sr.</b>", styles['TableHead']), Paragraph("<b>Expense Category & Service Description</b>", styles['TableHead']), Paragraph("<b>SAC / Code</b>", styles['TableHead']), Paragraph("<b>Qty / Days</b>", styles['TableHead']), Paragraph("<b>Rate (Rs.)</b>", styles['TableHead']), Paragraph("<b>Total Bill Amount (Rs.)</b>", styles['TableHead'])],
        [Paragraph("1", styles['TableCell']), Paragraph("Room Rent & Boarding Charges (Twin Sharing Room 304B) [COV-002]", styles['TableCellBold']), Paragraph("999311", styles['TableCell']), Paragraph("3 Nights", styles['TableCell']), Paragraph("5,000.00", styles['TableCellRight']), Paragraph("15,000.00", styles['TableCellRightBold'])],
        [Paragraph("2", styles['TableCell']), Paragraph("Nursing Charges & Ward Care", styles['TableCellBold']), Paragraph("999312", styles['TableCell']), Paragraph("3 Days", styles['TableCell']), Paragraph("1,500.00", styles['TableCellRight']), Paragraph("4,500.00", styles['TableCellRightBold'])],
        [Paragraph("3", styles['TableCell']), Paragraph("Surgeon and Professional Fees (Dr. R. Sharma)", styles['TableCellBold']), Paragraph("999313", styles['TableCell']), Paragraph("1 Proc", styles['TableCell']), Paragraph("20,000.00", styles['TableCellRight']), Paragraph("20,000.00", styles['TableCellRightBold'])],
        [Paragraph("4", styles['TableCell']), Paragraph("Anesthesia Professional Charges (Dr. P. Desai)", styles['TableCellBold']), Paragraph("999313", styles['TableCell']), Paragraph("1 Proc", styles['TableCell']), Paragraph("6,000.00", styles['TableCellRight']), Paragraph("6,000.00", styles['TableCellRightBold'])],
        [Paragraph("5", styles['TableCell']), Paragraph("Operation Theatre (OT) & Equipment Usage", styles['TableCellBold']), Paragraph("999314", styles['TableCell']), Paragraph("1 Major", styles['TableCell']), Paragraph("10,000.00", styles['TableCellRight']), Paragraph("10,000.00", styles['TableCellRightBold'])],
        [Paragraph("6", styles['TableCell']), Paragraph("Diagnostics and Laboratory (CBC, CRP, USG)", styles['TableCellBold']), Paragraph("999315", styles['TableCell']), Paragraph("1 Batch", styles['TableCell']), Paragraph("5,500.00", styles['TableCellRight']), Paragraph("5,500.00", styles['TableCellRightBold'])],
        [Paragraph("7", styles['TableCell']), Paragraph("Medicines and Pharmacy (Hospital Pharmacy)", styles['TableCellBold']), Paragraph("999316", styles['TableCell']), Paragraph("Itemized", styles['TableCell']), Paragraph("9,000.00", styles['TableCellRight']), Paragraph("9,000.00", styles['TableCellRightBold'])],
        [Paragraph("8", styles['TableCell']), Paragraph("Consumables & Surgical Disposables", styles['TableCellBold']), Paragraph("999317", styles['TableCell']), Paragraph("Itemized", styles['TableCell']), Paragraph("5,000.00", styles['TableCellRight']), Paragraph("5,000.00", styles['TableCellRightBold'])],
        [Paragraph("9", styles['TableCell']), Paragraph("Other Medically Related Hospital Services", styles['TableCellBold']), Paragraph("999318", styles['TableCell']), Paragraph("Care Bundle", styles['TableCell']), Paragraph("10,000.00", styles['TableCellRight']), Paragraph("10,000.00", styles['TableCellRightBold'])],
        [Paragraph("", styles['TableCell']), Paragraph("<b>TOTAL BILL AMOUNT</b>", styles['TableCellBold']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCellRightBold']), Paragraph("<b>Rs. 85,000.00</b>", styles['TableCellRightBold'])],
        [Paragraph("", styles['TableCell']), Paragraph("<b>AMOUNT PAID BY PATIENT</b>", styles['TableCellBold']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCellRightBold']), Paragraph("<b>Rs. 85,000.00</b>", styles['TableCellRightBold'])],
        [Paragraph("", styles['TableCell']), Paragraph("<b>OUTSTANDING BALANCE</b>", styles['TableCellBold']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCellRightBold']), Paragraph("<b>Rs. 0.00 (NIL)</b>", styles['TableCellRightBold'])],
    ]
    t_bill = Table(bill_items, colWidths=[w_content * 0.05, w_content * 0.45, w_content * 0.12, w_content * 0.12, w_content * 0.12, w_content * 0.14])
    t_bill.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.white, colors.HexColor("#F8FAFC")]),
        ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    story.append(t_bill)
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "<b>COV-002 Room Rent & Boarding Certification:</b> Certified that Patient Aarav Mehta occupied Twin Sharing Room 304B "
        "for 3 Nights (12/09/2026 to 15/09/2026) at standard eligible tariff Rs. 5,000.00/night = Total Rs. 15,000.00. "
        "Verified 100% compliant with policy benefit clause COV-002 Room Rent & Boarding.<br/>"
        "<b>Amount in Words:</b> INR Eighty-Five Thousand Only.<br/>"
        "<b>Billing Authority:</b> Harmony Multispeciality Hospital Billing Desk | Authorized Billing Cashier: S. Ramesh",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 11: Document 8: Hospital Payment Receipts
    add_claim_header("DOCUMENT 8: HOSPITAL MEDICAL BILL - OFFICIAL SETTLEMENT & PAYMENT RECEIPT", "DOC-007", "15/09/2026")
    story.append(Paragraph(
        "<b>Bill Number: HMH-REC-2026-9931 &nbsp;|&nbsp; Bill Date: 15/09/2026</b><br/>"
        "Receipt Number: HMH-REC-2026-9931 &nbsp;|&nbsp; Patient Name: Aarav Mehta &nbsp;|&nbsp; IPD No: HMH-IPD-2026-4402<br/>"
        "Hospital: Harmony Multispeciality Hospital",
        styles['BodyPBold']
    ))
    story.append(Spacer(1, 3))
    rcpt_data = [
        [Paragraph("<b>Receipt Parameter</b>", styles['TableHead']), Paragraph("<b>Settlement Transaction Particulars</b>", styles['TableHead'])],
        [Paragraph("Hospital Name", styles['TableCellBold']), Paragraph("Harmony Multispeciality Hospital", styles['TableCell'])],
        [Paragraph("Bill Number / Receipt No", styles['TableCellBold']), Paragraph("<b>HMH-REC-2026-9931</b>", styles['TableCellBold'])],
        [Paragraph("Reference Invoice Number", styles['TableCellBold']), Paragraph("HMH-BILL-2026-8842", styles['TableCell'])],
        [Paragraph("Payment Date & Time", styles['TableCellBold']), Paragraph("<b>15/09/2026 at 11:45 AM</b>", styles['TableCellBold'])],
        [Paragraph("Received From", styles['TableCellBold']), Paragraph("<b>Aarav Mehta (Self)</b>", styles['TableCellBold'])],
        [Paragraph("Payment Mode 1 (Card)", styles['TableCellBold']), Paragraph("Debit Card (Apex Bank ending 5521) - Auth Ref: TXN-APX-8841029 : <b>Rs. 50,000.00</b>", styles['TableCell'])],
        [Paragraph("Payment Mode 2 (Netbanking)", styles['TableCellBold']), Paragraph("Online Netbanking Transfer - UTR Ref: APEXNB20260915998 : <b>Rs. 35,000.00</b>", styles['TableCell'])],
        [Paragraph("Total Amount Paid", styles['TableCellBold']), Paragraph("<b>Total Bill Amount: Rs. 85,000.00 (Paid in Full)</b>", styles['TableCellBold'])],
        [Paragraph("Balance Due", styles['TableCellBold']), Paragraph("<b>Rs. 0.00 (Zero Balance - Account Settled)</b>", styles['TableCellBold'])],
    ]
    t_rcpt = Table(rcpt_data, colWidths=[w_content * 0.32, w_content * 0.68])
    t_rcpt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_rcpt)
    story.append(Spacer(1, 6))
    stamp_box = [
        [Paragraph("<b>HOSPITAL CASHIER STAMP & RECEIPT ACKNOWLEDGMENT</b>", styles['StampText'])],
        [Paragraph(
            "RECEIVED PAYMENT IN FULL WITH THANKS<br/>"
            "HARMONY MULTISPECIALITY HOSPITAL — CASH COUNTER #1<br/>"
            "Date: 15-SEP-2026 | S. Ramesh (Authorized Billing Officer)<br/>"
            "*** NO DUES OUTSTANDING ***",
            styles['StampText']
        )]
    ]
    t_stamp = Table(stamp_box, colWidths=[w_content * 0.7])
    t_stamp.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor("#1E3A8A")),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_stamp)
    story.append(PageBreak())

    # PAGE 12: Document 9: Pharmacy Bill
    add_claim_header("DOCUMENT 9: HOSPITAL MEDICAL BILL - PHARMACY TAX INVOICE", "DOC-008", "15/09/2026")
    story.append(Paragraph(
        "<b>Bill Number: HMH-PHARM-2026-4421 &nbsp;|&nbsp; Bill Date: 15/09/2026</b><br/>"
        "Patient Name: Aarav Mehta &nbsp;|&nbsp; Prescribing Doctor: Dr. Rajesh Sharma, MS &nbsp;|&nbsp; Hospital: Harmony Multispeciality Hospital",
        styles['BodyPBold']
    ))
    story.append(Spacer(1, 3))
    pharm_items = [
        [Paragraph("<b>Rx Code</b>", styles['TableHead']), Paragraph("<b>Medication / Consumable Name</b>", styles['TableHead']), Paragraph("<b>Batch / Exp</b>", styles['TableHead']), Paragraph("<b>Qty</b>", styles['TableHead']), Paragraph("<b>Unit (Rs.)</b>", styles['TableHead']), Paragraph("<b>Total Bill Amount (Rs.)</b>", styles['TableHead'])],
        [Paragraph("RX-01", styles['TableCell']), Paragraph("Inj. Cefuroxime 1.5g IV (Zinacef)", styles['TableCellBold']), Paragraph("B721 / 2028", styles['TableCell']), Paragraph("6 Vials", styles['TableCell']), Paragraph("450.00", styles['TableCellRight']), Paragraph("2,700.00", styles['TableCellRight'])],
        [Paragraph("RX-02", styles['TableCell']), Paragraph("Inj. Metronidazole 500mg IV Infusion", styles['TableCellBold']), Paragraph("M912 / 2027", styles['TableCell']), Paragraph("6 Btls", styles['TableCell']), Paragraph("110.00", styles['TableCellRight']), Paragraph("660.00", styles['TableCellRight'])],
        [Paragraph("RX-03", styles['TableCell']), Paragraph("Inj. Tramadol 100mg / Inj. Paracetamol IV", styles['TableCellBold']), Paragraph("T440 / 2028", styles['TableCell']), Paragraph("4 Amps", styles['TableCell']), Paragraph("210.00", styles['TableCellRight']), Paragraph("840.00", styles['TableCellRight'])],
        [Paragraph("RX-04", styles['TableCell']), Paragraph("Inj. Pantoprazole 40mg IV (Pantocid)", styles['TableCellBold']), Paragraph("P881 / 2028", styles['TableCell']), Paragraph("4 Vials", styles['TableCell']), Paragraph("180.00", styles['TableCellRight']), Paragraph("720.00", styles['TableCellRight'])],
        [Paragraph("RX-05", styles['TableCell']), Paragraph("IV Fluids (RL, DNS 500ml) & Infusion Sets", styles['TableCellBold']), Paragraph("F201 / 2027", styles['TableCell']), Paragraph("8 Units", styles['TableCell']), Paragraph("160.00", styles['TableCellRight']), Paragraph("1,280.00", styles['TableCellRight'])],
        [Paragraph("RX-06", styles['TableCell']), Paragraph("Surgical Dressings, Gauze, Tegaderm Port Films", styles['TableCellBold']), Paragraph("D331 / 2029", styles['TableCell']), Paragraph("1 Kit", styles['TableCell']), Paragraph("950.00", styles['TableCellRight']), Paragraph("950.00", styles['TableCellRight'])],
        [Paragraph("RX-07", styles['TableCell']), Paragraph("Endoloop Ligature (Ethicon Vicryl 0)", styles['TableCellBold']), Paragraph("E992 / 2028", styles['TableCell']), Paragraph("2 Pks", styles['TableCell']), Paragraph("925.00", styles['TableCellRight']), Paragraph("1,850.00", styles['TableCellRight'])],
        [Paragraph("TOTAL", styles['TableCellBold']), Paragraph("<b>TOTAL PHARMACY BILL AMOUNT</b>", styles['TableCellBold']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCell']), Paragraph("", styles['TableCellRightBold']), Paragraph("<b>Rs. 9,000.00</b>", styles['TableCellRightBold'])],
    ]
    t_pharm = Table(pharm_items, colWidths=[w_content * 0.10, w_content * 0.40, w_content * 0.16, w_content * 0.10, w_content * 0.12, w_content * 0.12])
    t_pharm.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_pharm)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Reconciliation Note:</b> Pharmacy total of Rs. 9,000 matches Item #7 on Final Hospital Bill HMH-BILL-2026-8842 exactly.<br/>"
        "<b>Chief Pharmacist:</b> R. K. Gupta, M.Pharm | Pharmacy Dispensing Counter, Harmony Hospital",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 13: Document 10: Bank Proof & Cancelled Cheque
    add_claim_header("DOCUMENT 10: HOSPITAL INDOOR ADMISSION - REIMBURSEMENT BANK ACCOUNT PROOF", "DOC-009", "15/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Discharge Date: 15/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>ELECTRONIC DIRECT BENEFIT TRANSFER (NEFT/RTGS) ACCOUNT VALIDATION</b><br/>"
        "The claimant submits the following bank account details and cancelled cheque text representation for reimbursement payout:",
        styles['BodyP']
    ))
    story.append(Spacer(1, 4))
    cheque_data = [
        [
            Paragraph("<b>APEX NATIONAL COMMERCIAL BANK</b><br/>Andheri East Branch, Mumbai 400069", styles['TableCellBold']),
            Paragraph("<b>DATE: 15 / 09 / 2026</b>", styles['TableCellRightBold'])
        ],
        [
            Paragraph("<font size=14 color='#DC2626'><b>*** CANCELLED ***</b></font><br/>PAY: <b>FOR REIMBURSEMENT VALIDATION ONLY</b>", styles['TableCellBold']),
            Paragraph("OR BEARER", styles['TableCellRight'])
        ],
        [
            Paragraph("RUPEES: <b>SYNTHETIC TEST ACCOUNT - NON-NEGOTIABLE</b>", styles['TableCell']),
            Paragraph("<b>Rs. ******</b>", styles['TableCellRightBold'])
        ],
        [
            Paragraph(
                "<b>Account Holder: Aarav Mehta</b><br/>"
                "<b>A/c No: XXXX-XXXX-XXXX-5521 (Masked Account)</b><br/>"
                "<b>IFSC: APEX0001928 (Fictional Identifier)</b>",
                styles['MetaBoxText']
            ),
            Paragraph(
                "[Signed: Aarav Mehta]<br/><b>AUTHORIZED SIGNATORY</b>",
                styles['TableCellRightBold']
            )
        ],
        [
            Paragraph("⑆ 400028019 ⑆ &nbsp;&nbsp;&nbsp;&nbsp; 0001928 &nbsp;&nbsp;&nbsp;&nbsp; 10", styles['TableCell']),
            Paragraph("CHEQUE NO: 099241", styles['TableCellRight'])
        ]
    ]
    t_chq = Table(cheque_data, colWidths=[w_content * 0.65, w_content * 0.35])
    t_chq.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.25, colors.HexColor("#475569")),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor("#CBD5E1")),
        ('LINEBELOW', (0, -2), (-1, -2), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_chq)
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        "<b>Bank Details Audit Attestation:</b> Account Holder Name: <b>Aarav Mehta</b> matches the Patient identity exactly.<br/>"
        "Fictional IFSC code: APEX0001928 is registered for direct electronic credit.",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 14: Document 11: Checklist
    add_claim_header("DOCUMENT 11: HOSPITAL INDOOR ADMISSION - CLAIM DOCUMENT VERIFICATION CHECKLIST", "DOC-010", "15/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Discharge Date: 15/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>PRE-SUBMISSION VERIFICATION & AUDIT CHECKLIST</b><br/>"
        "Patient: Aarav Mehta | TPA Ref: SSHI-TEST-2026-001 | Claim Ref: CLM-TEST-2026-0042",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    chk_rows = [
        [Paragraph("<b>Doc ID</b>", styles['TableHead']), Paragraph("<b>Document Requirement Name</b>", styles['TableHead']), Paragraph("<b>Category</b>", styles['TableHead']), Paragraph("<b>Status</b>", styles['TableHead']), Paragraph("<b>Audit Verification Notes</b>", styles['TableHead'])],
        [Paragraph("DOC-001", styles['TableCellBold']), Paragraph("Hospital Discharge Summary", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Discharge 15/09/2026, diagnosis Acute Appendicitis recorded", styles['TableCell'])],
        [Paragraph("DOC-002", styles['TableCellBold']), Paragraph("Hospital Medical Bill & COV-002 Room Rent & Boarding Folio", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Total bill Rs. 85,000 with COV-002 Room Rent & Boarding certificate verified", styles['TableCell'])],
        [Paragraph("DOC-003", styles['TableCellBold']), Paragraph("Hospital Indoor Admission Record", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Date 12/09/2026, symptoms, and initial diagnosis recorded", styles['TableCell'])],
        [Paragraph("DOC-004", styles['TableCellBold']), Paragraph("Diagnostic Scan & Lab Reports", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("CBC, CRP, and Abdominal Ultrasound scan reports included", styles['TableCell'])],
        [Paragraph("DOC-005", styles['TableCellBold']), Paragraph("Reimbursement Claim Form (Part A & B)", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Fully completed and signed by Aarav Mehta", styles['TableCell'])],
        [Paragraph("DOC-006", styles['TableCellBold']), Paragraph("Hospital Operation Notes", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Laparoscopic Appendectomy surgical record on 13/09/2026", styles['TableCell'])],
        [Paragraph("DOC-007", styles['TableCellBold']), Paragraph("Official Hospital Payment Receipts", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Full payment Rs. 85,000 acknowledged, zero balance", styles['TableCell'])],
        [Paragraph("DOC-008", styles['TableCellBold']), Paragraph("Pharmacy Dispensing Bill & Invoices", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Itemized medicine bills total Rs. 9,000 exactly", styles['TableCell'])],
        [Paragraph("DOC-009", styles['TableCellBold']), Paragraph("Reimbursement Bank Account Proof", styles['TableCellBold']), Paragraph("Mandatory", styles['TableCell']), Paragraph("<b>PRESENT</b>", styles['TableCellBold']), Paragraph("Cancelled cheque with matching account holder Aarav Mehta", styles['TableCell'])],
    ]
    t_chk = Table(chk_rows, colWidths=[w_content * 0.12, w_content * 0.32, w_content * 0.14, w_content * 0.14, w_content * 0.28])
    t_chk.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_chk)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Checklist Summary:</b> All mandatory baseline requirements are PRESENT and validly substantiated. Zero missing documents detected.",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 15: Document 12: Progress Notes
    add_claim_header("DOCUMENT 12: HOSPITAL INDOOR ADMISSION - CLINICAL SUMMARY & WARD ROUNDS", "DOC-011", "14/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Discharge Date: 15/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>INPATIENT CLINICAL PROGRESS NOTES & CHRONOLOGICAL TIMELINE</b><br/>"
        "Patient: Aarav Mehta | Hospital: Harmony Multispeciality Hospital | Consultant: Dr. Rajesh Sharma",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    timeline_data = [
        [Paragraph("<b>Date & Time</b>", styles['TableHead']), Paragraph("<b>Clinical Milestone & Medical Evaluation</b>", styles['TableHead']), Paragraph("<b>Attending Clinician</b>", styles['TableHead'])],
        [Paragraph("12/09/2026<br/>09:30 AM", styles['TableCellBold']), Paragraph("Patient presented to Emergency Room with acute RLQ abdominal pain, tenderness at McBurney's point. Admitted to Twin Sharing Room 304B. IV access established. Kept NBM.", styles['TableCell']), Paragraph("Dr. Anil Verma (EMO)", styles['TableCell'])],
        [Paragraph("12/09/2026<br/>12:00 PM", styles['TableCellBold']), Paragraph("USG Abdomen and CBC/CRP completed. Ultrasound demonstrates 8.6 mm acutely inflamed appendix. WBC 14,800. Diagnosis of Acute Appendicitis verified. Pre-anesthesia check completed.", styles['TableCell']), Paragraph("Dr. Rajesh Sharma (Surgeon)<br/>Dr. Priya Desai (Anesth)", styles['TableCell'])],
        [Paragraph("13/09/2026<br/>10:00 AM", styles['TableCellBold']), Paragraph("Patient shifted to OT 2. Underwent uneventful Laparoscopic Appendectomy under General Anesthesia. Inflamed retrocecal appendix excised. Shifted to PACU in stable condition.", styles['TableCell']), Paragraph("Dr. Rajesh Sharma (Surgeon)", styles['TableCell'])],
        [Paragraph("13/09/2026<br/>06:00 PM", styles['TableCellBold']), Paragraph("Evening post-op ward rounds. Patient awake, alert. Vitals: BP 122/80, HR 82, Temp 98.6°F. Mild port discomfort managed with analgesia. IV fluids maintained.", styles['TableCell']), Paragraph("Dr. Rajesh Sharma", styles['TableCell'])],
        [Paragraph("14/09/2026<br/>10:00 AM", styles['TableCellBold']), Paragraph("Post-op Day 1 rounds. Patient passed flatus, tolerated oral sips and soft diet. IV cannula site clean. Port dressings dry. Mobilizing well in corridor.", styles['TableCell']), Paragraph("Dr. Rajesh Sharma", styles['TableCell'])],
        [Paragraph("15/09/2026<br/>09:00 AM", styles['TableCellBold']), Paragraph("Discharge evaluation rounds. Hemodynamically stable. Afebrile. Port sites healthy. Tolerating full diet, bowel and bladder function normal. Cleared for discharge.", styles['TableCell']), Paragraph("Dr. Rajesh Sharma", styles['TableCell'])],
    ]
    t_time = Table(timeline_data, colWidths=[w_content * 0.18, w_content * 0.58, w_content * 0.24])
    t_time.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_time)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Clinical Verification:</b> The chronological timeline aligns with admission (12/09/2026), surgery (13/09/2026), and discharge (15/09/2026).",
        styles['BodyP']
    ))
    story.append(PageBreak())

    # PAGE 16: Document 13: Cross-Reference Index
    add_claim_header("DOCUMENT 13: HOSPITAL INDOOR ADMISSION - CROSS-REFERENCE & IDENTITY INDEX", "DOC-012", "15/09/2026")
    story.append(Paragraph("<b>Admission Date: 12/09/2026 | Discharge Date: 15/09/2026</b>", styles['BodyPBold']))
    story.append(Paragraph(
        "<b>MULTI-DOCUMENT ENTITY RECONCILIATION & TRACEABILITY MATRIX</b><br/>"
        "This master cross-reference table binds all clinical and financial entities across both test documents:",
        styles['BodyP']
    ))
    story.append(Spacer(1, 3))
    xref_data = [
        [Paragraph("<b>Entity Field</b>", styles['TableHead']), Paragraph("<b>Coverage Standard (PDF 1)</b>", styles['TableHead']), Paragraph("<b>Claim Document Value (PDF 2)</b>", styles['TableHead']), Paragraph("<b>Consistency Audit Verdict</b>", styles['TableHead'])],
        [Paragraph("Certificate Identifier", styles['TableCellBold']), Paragraph("SSHI-TEST-2026-001", styles['TableCell']), Paragraph("SSHI-TEST-2026-001", styles['TableCell']), Paragraph("<b>EXACT MATCH</b>", styles['TableCellBold'])],
        [Paragraph("Insured Primary Member", styles['TableCellBold']), Paragraph("Aarav Mehta", styles['TableCell']), Paragraph("Aarav Mehta", styles['TableCell']), Paragraph("<b>EXACT MATCH</b>", styles['TableCellBold'])],
        [Paragraph("Patient Name", styles['TableCellBold']), Paragraph("Aarav Mehta", styles['TableCell']), Paragraph("Aarav Mehta", styles['TableCell']), Paragraph("<b>EXACT MATCH</b>", styles['TableCellBold'])],
        [Paragraph("Hospital Name", styles['TableCellBold']), Paragraph("Licensed Hospital Facility", styles['TableCell']), Paragraph("Harmony Multispeciality Hospital", styles['TableCell']), Paragraph("<b>COHERENT FACILITY</b>", styles['TableCellBold'])],
        [Paragraph("Coverage Window", styles['TableCellBold']), Paragraph("01/04/2026 to 31/03/2027", styles['TableCell']), Paragraph("Admission: 12/09/2026 | Disch: 15/09/2026", styles['TableCell']), Paragraph("<b>WITHIN VALID WINDOW</b>", styles['TableCellBold'])],
        [Paragraph("Diagnosis", styles['TableCellBold']), Paragraph("Acute Appendicitis (Covered)", styles['TableCell']), Paragraph("Acute Appendicitis (ICD K35.80)", styles['TableCell']), Paragraph("<b>CLINICALLY COHERENT</b>", styles['TableCellBold'])],
        [Paragraph("Procedure", styles['TableCellBold']), Paragraph("Laparoscopic Appendectomy", styles['TableCell']), Paragraph("Laparoscopic Appendectomy", styles['TableCell']), Paragraph("<b>EXACT MATCH</b>", styles['TableCellBold'])],
        [Paragraph("Room Eligibility", styles['TableCellBold']), Paragraph("Up to Rs. 5,000 / Day (COV-002)", styles['TableCell']), Paragraph("3 Nights @ Rs. 5,000 = Rs. 15,000", styles['TableCell']), Paragraph("<b>WITHIN ROOM CAP</b>", styles['TableCellBold'])],
        [Paragraph("Total Claimed", styles['TableCellBold']), Paragraph("Master Coverage Rs. 5,00,000", styles['TableCell']), Paragraph("Claimed: Rs. 85,000.00", styles['TableCell']), Paragraph("<b>WITHIN COVERAGE</b>", styles['TableCellBold'])],
        [Paragraph("Total Paid", styles['TableCellBold']), Paragraph("Original Receipts Required", styles['TableCell']), Paragraph("Receipt: Rs. 85,000 (Zero Balance)", styles['TableCell']), Paragraph("<b>100% RECONCILED</b>", styles['TableCellBold'])],
        [Paragraph("Bank Account", styles['TableCellBold']), Paragraph("Insured Aarav Mehta", styles['TableCell']), Paragraph("Aarav Mehta (Cheque layout)", styles['TableCell']), Paragraph("<b>IDENTITY VERIFIED</b>", styles['TableCellBold'])],
    ]
    t_xref = Table(xref_data, colWidths=[w_content * 0.20, w_content * 0.26, w_content * 0.32, w_content * 0.22])
    t_xref.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_xref)
    story.append(Spacer(1, 5))
    story.append(Paragraph(
        "<b>SYSTEM AUDIT ATTESTATION:</b> This claim submission bundle contains all required evidence. "
        "Every subdocument is verifiable and free of contradictions. The claim is ready for final adjudication by InsureMate.",
        styles['BodyP']
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"-> Generated Claim PDF: {output_path} (16 pages)")
    root_claim_pdf = ROOT_DIR / "InsureMate_Test_Health_Insurance_Claim_Documents.pdf"
    import shutil
    shutil.copyfile(output_path, root_claim_pdf)
    print(f"-> Synced Claim PDF to root: {root_claim_pdf}")


if __name__ == "__main__":
    print("Regenerating comprehensive test PDF documents...")
    generate_policy_pdf(POLICY_PDF)
    root_policy_pdf = ROOT_DIR / "InsureMate_Test_Health_Insurance_Policy.pdf"
    import shutil
    shutil.copyfile(POLICY_PDF, root_policy_pdf)
    generate_claim_pdf(CLAIM_PDF)
    print("Complete!")
