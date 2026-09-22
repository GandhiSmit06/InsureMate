"""Pytest fixtures and sample policy texts for InsureMate Phase 3 tests."""

import pytest
from phase3.engine import RequirementExtractionEngine
from phase3.extractor.rule_extractor import RuleExtractor


@pytest.fixture
def engine():
    """Provides a RequirementExtractionEngine with RuleExtractor for deterministic tests."""
    return RequirementExtractionEngine(extractor=RuleExtractor())


# Sample 1: Standard Inpatient Hospitalization Policy
SAMPLE_HOSPITALIZATION_POLICY = """
MEDICLAIM PLUS POLICY - SECTION 5: CLAIMS PROCEDURE

5.1 Documents Required for Inpatient Hospitalization Claim:
The insured person shall submit the following documents to the company/TPA:
a. Duly completed and signed Claim Form Part A and Part B with hospital seal.
b. Original Hospital Discharge Summary mentioning diagnosis, admission date, discharge date, and treatment given.
c. Original itemized Final Hospital Bill with detailed breakup of room rent, nursing charges, and consultation.
d. Original Payment Receipts from the hospital with serial number and revenue stamp.
e. Doctor Prescriptions and Consultation Papers recommending hospitalization.
f. Diagnostic and Investigation Reports including pathology, biochemistry, and radiology reports.
g. Original Pharmacy Bills supported by doctor prescriptions.
"""

# Sample 2: Cashless Treatment Policy
SAMPLE_CASHLESS_POLICY = """
SECUREHEALTH POLICY - CLAUSE 7: CASHLESS FACILITY PROCEDURE

7.1 Network Hospital Requirement:
Cashless facility is available only at network hospitals empanelled with the TPA/Company.

7.2 Pre-Authorization Process:
For planned hospitalization, the cashless pre-authorization request form must be submitted at least 48 hours prior to admission.
In case of emergency hospitalization, notice of claim and cashless authorization request must be submitted within 24 hours of emergency admission.

7.3 Authorization Approval:
The insured must present the Cashless Pre-Authorization Approval letter issued by the TPA along with the hospital admission desk registration.
"""

# Sample 3: Reimbursement Policy
SAMPLE_REIMBURSEMENT_POLICY = """
NATIONAL HEALTH CARE POLICY - SECTION 8: REIMBURSEMENT CLAIMS

8.1 Submission of Claim Documents:
The insured person shall submit all original claim documents within 30 days of discharge from the hospital.

8.2 Required Documentation:
a. Original completed Claim Form.
b. Hospital Discharge Summary signed by attending physician.
c. Itemized hospital bill and original payment receipts.
d. Chemist bills and diagnostic test reports.
e. Treating doctor's certificate stating the history and etiology of the ailment.

8.3 Settlement Timeline:
Upon receipt of all complete claim papers, the company shall settle the claim within 30 days.
"""

# Sample 4: Accident Claim Policy
SAMPLE_ACCIDENT_POLICY = """
ACCIDENT CARE POLICY - CLAUSE 12: ACCIDENTAL INJURY & TRAUMA CLAIMS

12.1 Special Documentation for Accident Claims:
In case of accidental injury or road traffic accident (RTA), the following documents are mandatory:
a. First Information Report (Police FIR copy) or Panchnama registered with local police station.
b. Medico-Legal Certificate (MLC copy) issued by the admitting hospital casualty department.
c. Alcohol and Toxicology Screening Report stating blood alcohol content at time of accident.
d. Immediate notice of claim must be given to the insurer within 24 hours of accident.
e. In case of surgery, Operation Theatre notes and implant invoice and stickers are required.
"""

# Sample 5: Conditional Requirements Policy
SAMPLE_CONDITIONAL_POLICY = """
ELITE HEALTH SHIELD - SECTION 9: SPECIAL CONDITIONAL PROVISIONS

9.1 Intensive Care Unit (ICU):
If ICU stay exceeds 48 hours, treating intensivist clinical justification and indoor case papers (ICP) daily charts must be submitted.

9.2 Organ Donor Expenses:
In case of organ donor transplantation claim, donor screening certificate and medical fitness clearance of donor are required.

9.3 High-Value Claims KYC:
Mandatory KYC documents including PAN Card copy and cancelled cheque are required if claim amount exceeds INR 1,00,000.

9.4 Day Care Treatments:
Day care procedures as listed in Annexure 1 do not require continuous 24-hour hospitalization.
"""

# Sample 6: Deadlines Policy
SAMPLE_DEADLINES_POLICY = """
CHRONOHEALTH POLICY - CLAUSE 4: TIME LIMITS AND NOTICE PERIODS

4.1 Intimation Deadlines:
a. In case of emergency admission: Intimate within 24 hours of emergency hospitalization.
b. In case of planned admission: Intimate at least 48 hours prior to admission.

4.2 Document Submission Deadline:
All original bills and claim papers must be submitted within 15 days of discharge from hospital.

4.3 Response to Queries:
The insured must respond to queries within 15 days of receipt of query letter from the TPA.
"""

# Sample 7: Ambiguous and Discretionary Wording Policy
SAMPLE_AMBIGUOUS_POLICY = """
FLEXI-CARE HEALTH INSURANCE - CLAUSE 15: GENERAL CLAIM CONDITIONS

15.1 Discretionary Clause:
The company or TPA reserves the right to request such other documents as may be deemed necessary by the insurer for proper scrutiny of the claim.
Reasonable and customary documents and clinical records may be called for as deemed fit by the insurer.
"""

# Sample 8: Policy with Duplicate and Similar Clauses
SAMPLE_DUPLICATE_POLICY = """
OPTIMA HEALTH PLAN - CLAIM REQUIREMENTS

Page 1:
The insured must submit:
1. Final Hospital Bill.
2. Hospital Discharge Summary with diagnosis.
3. Payment Receipts.

Page 2:
Documents Required for Reimbursement:
1. Itemized Hospital Bill with detailed breakup of all charges.
2. Hospital Discharge Summary signed by treating doctor with admission and discharge dates.
3. Original Money Receipts with stamp.
"""

# Sample 9: Minimal Policy without Extra Documents (Anti-Hallucination)
SAMPLE_MINIMAL_POLICY = """
BASIC HOSPITAL CASH PLAN

Benefits are paid solely on proof of hospital admission.
Required Documents:
1. Duly signed Claim Form.
2. Hospital Discharge Card stating dates of admission and discharge.
"""
