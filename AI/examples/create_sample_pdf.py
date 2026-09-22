"""
Helper script to generate a sample digital PDF for testing testWorking.py.
"""
import pymupdf as fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842) # A4

text = """APOLLO HOSPITALS LTD.
Plot No. 1A, Bhat GIDC, Gandhinagar, Gujarat - 382428
GSTIN: 24AAACA1234A1Z5 | Reg: HOSP-GJ-2019-8821

INVOICE / BILL OF SUPPLY
Invoice No: INV-2024-99812
Invoice Date: 15/03/2024
Admission Date: 10/03/2024
Discharge Date: 14/03/2024

PATIENT DETAILS:
Patient Name: Rajesh Kumar Patel
Age / Gender: 45 Y / Male
UHID / Patient ID: UHID-887210
Consulting Doctor: Dr. Anita Sharma (Reg: G-34912)

FINAL DIAGNOSIS:
Acute Appendicitis with localized peritonitis. Underwent Emergency Laparoscopic Appendectomy.

ITEMIZED CHARGES:
1. Room Rent & Nursing Charges (4 days) : Rs. 16,000.00
2. Surgeon Consultation & Operation Charges : Rs. 45,000.00
3. OT & Anesthesia Charges : Rs. 18,500.00
4. Pharmacy & Consumables : Rs. 12,300.00
5. Diagnostic & Lab Investigations : Rs. 8,200.00

SUMMARY:
Total Amount: Rs. 1,00,000.00
Discount: Rs. 0.00
Amount Paid: Rs. 1,00,000.00
"""

page.insert_text((50, 60), text, fontsize=11)
doc.save("sample_test_invoice.pdf")
doc.close()
print("Sample PDF 'sample_test_invoice.pdf' created successfully.")
