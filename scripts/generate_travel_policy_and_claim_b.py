"""scripts/generate_travel_policy_and_claim_b.py
Generates real PDF test fixtures:
- policy_B.pdf (Overseas Travel Protection Policy)
- claim_B.pdf (Travel Baggage Loss Claim Document)
"""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

ROOT_DIR = Path(__file__).resolve().parent.parent


def generate_policy_b(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=colors.HexColor("#1E3A8A"),
        alignment=1,
        spaceAfter=8
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E293B")
    )
    bold_style = ParagraphStyle(
        'DocBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    story = [
        Paragraph("GLOBAL VOYAGE ASSURANCE COMPANY", title_style),
        Paragraph("Overseas Travel Protection Policy Certificate & Schedule", ParagraphStyle('Sub', parent=title_style, fontSize=11, textColor=colors.HexColor("#475569"))),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=8),
        Paragraph("<b>Policy Number:</b> TRAV-2026-9090 | <b>Plan Type:</b> Worldwide Platinum Travel Cover", bold_style),
        Paragraph("<b>Policy Holder Name:</b> Johnathan Edward Doe | <b>Proposer:</b> Johnathan Edward Doe", body_style),
        Paragraph("<b>Policy Period:</b> 01/01/2026 to 31/12/2026 | <b>Status:</b> ACTIVE & IN-FORCE", body_style),
        Paragraph("<b>Policy Inception Date:</b> 01/01/2026 | <b>Policy Expiry Date:</b> 31/12/2026", body_style),
        Paragraph("<b>Sum Insured:</b> USD 50,000 | <b>Geographical Scope:</b> Worldwide excluding sanctioned territories", body_style),
        Spacer(1, 10),
        Paragraph("<b>SECTION IV: CLAIMS PROCEDURE & MANDATORY SUPPORTING DOCUMENTS</b>", bold_style),
        Paragraph("For processing travel loss claims under Policy Number TRAV-2026-9090, the claimant must submit:", body_style),
        Spacer(1, 4),
        Paragraph("1. First Information Report (FIR): Loss of baggage requires Police First Information Report (FIR) filed with local airport or transit police within 24 hours of incident.", body_style),
        Spacer(1, 3),
        Paragraph("2. Boarding Pass and Airline Ticket: Original Boarding Pass and Airline Ticket must be submitted establishing passenger travel dates.", body_style),
        Spacer(1, 3),
        Paragraph("3. Property Irregularity Report (PIR): Official airline Property Irregularity Report issued by the baggage handling counter.", body_style),
        Spacer(1, 10),
        Paragraph("<b>TERMS, EXCLUSIONS & LIMITS</b>", bold_style),
        Paragraph("Baggage loss covered up to USD 2,500 subject to a USD 50 deductible. Delay of baggage covered up to USD 500 for emergency purchases. Pre-existing medical conditions excluded unless emergency life-saving stabilization.", body_style),
        Spacer(1, 12),
        Paragraph("Underwritten by Global Voyage Assurance Co. Ltd. | 24/7 International Emergency Assistance: +1-800-555-0199", body_style)
    ]

    doc.build(story)
    print(f"Generated policy_B.pdf -> {output_path}")


def generate_claim_b(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=colors.HexColor("#1E3A8A"),
        alignment=1,
        spaceAfter=8
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E293B")
    )
    bold_style = ParagraphStyle(
        'DocBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    story = [
        Paragraph("GLOBAL VOYAGE ASSURANCE - TRAVEL CLAIM DOSSIER", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=8),
        Paragraph("<b>Claimant Name:</b> Johnathan Edward Doe | <b>Passport No:</b> Z8849102", bold_style),
        Paragraph("<b>Policy Reference:</b> TRAV-2026-9090 | <b>Claim Tracking ID:</b> CLM-TRV-2026-0081", body_style),
        Paragraph("<b>Date of Incident:</b> 15/05/2026 | <b>Claim Submission Date:</b> 20/05/2026", body_style),
        Paragraph("<b>Flight Number:</b> AI-102 (BOM - LHR) | <b>PNR:</b> TRV88192 | <b>Seat:</b> 14B", body_style),
        Spacer(1, 8),
        Paragraph("<b>INCIDENT DOCUMENTATION & SUBMITTED EVIDENCE</b>", bold_style),
        Paragraph("<b>1. Police First Information Report (FIR):</b> Report No. FIR-LHR-2026-4410 filed at Metropolitan Airport Police Station on 15/05/2026 recording checked baggage disappearance from carousel 4.", body_style),
        Spacer(1, 4),
        Paragraph("<b>2. Travel Boarding Pass & E-Ticket:</b> Original Air India boarding pass issued for flight AI-102 dated 15/05/2026 for passenger Johnathan Edward Doe.", body_style),
        Spacer(1, 4),
        Paragraph("<b>3. Property Irregularity Report (PIR):</b> Air India Ground Services PIR reference LHR-AI-2026-9902 confirming luggage not located.", body_style),
        Spacer(1, 8),
        Paragraph("<b>Claimed Amount:</b> USD 1,850.00 (Total replacement expenses for checked baggage contents).", bold_style),
        Spacer(1, 12),
        Paragraph("I declare the above details to be true and complete. [Signed: Johnathan Edward Doe]", body_style)
    ]

    doc.build(story)
    print(f"Generated claim_B.pdf -> {output_path}")


if __name__ == "__main__":
    generate_policy_b(ROOT_DIR / "policy_B.pdf")
    generate_claim_b(ROOT_DIR / "claim_B.pdf")
