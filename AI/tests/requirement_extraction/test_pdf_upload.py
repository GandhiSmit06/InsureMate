"""Test Case 10: Policy PDF Ingestion and Page Traceability Test."""

import pytest
from AI.requirement_extraction.schema.models import Category
from AI.requirement_extraction.ingestion.pdf_reader import PDFReader


def create_test_pdf_bytes(page_texts):
    """Utility to generate a valid multi-page PDF document in memory."""
    objects = []

    def add_obj(content):
        objects.append(content)
        return len(objects)

    catalog_id = 1
    pages_id = 2
    objects.append(b"")
    objects.append(b"")

    page_refs = []
    font_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for text in page_texts:
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_content = f"BT /F1 12 Tf 50 750 Td ({escaped}) Tj ET".encode("latin1")
        stream_id = add_obj(
            f"<< /Length {len(stream_content)} >>\nstream\n".encode("latin1")
            + stream_content
            + b"\nendstream"
        )
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {stream_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode("latin1")
        )
        page_id = add_obj(page_obj)
        page_refs.append(f"{page_id} 0 R")

    kids = " ".join(page_refs)
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode("latin1")

    pdf = bytearray(b"%PDF-1.4\n")
    xref_offsets = [0]
    for i, obj in enumerate(objects):
        xref_offsets.append(len(pdf))
        pdf.extend(f"{i+1} 0 obj\n".encode("latin1") + obj + b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode("latin1"))
    for off in xref_offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin1"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode(
            "latin1"
        )
    )
    return bytes(pdf)


def test_pdf_reader_multipage():
    """Verify that PDFReader extracts multi-page text with accurate page numbers."""
    page_1_content = "Clause 1: Hospital Discharge Summary and Final Hospital Bill are required."
    page_2_content = "Clause 2: In case of accident, Police FIR and Medico-Legal Certificate are required."

    pdf_bytes = create_test_pdf_bytes([page_1_content, page_2_content])
    pages = PDFReader.extract_from_bytes(pdf_bytes)

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "Discharge Summary" in pages[0].text
    assert pages[1].page_number == 2
    assert "Police FIR" in pages[1].text


def test_pdf_end_to_end_requirement_extraction(engine):
    """Verify end-to-end extraction from PDF bytes with accurate source_page tracking."""
    page_1_content = "Hospitalization requires Hospital Discharge Summary and Hospital Final Bill."
    page_2_content = "Accident claims require Police FIR copy and Medico-Legal Certificate."

    pdf_bytes = create_test_pdf_bytes([page_1_content, page_2_content])

    response = engine.process(
        pdf_bytes=pdf_bytes,
        claim_type="hospitalization",
        policy_name="Multi-Page PDF Policy",
    )

    assert response.success is True
    assert len(response.requirements) >= 2

    # Check page 1 requirement
    discharge_req = next(
        (r for r in response.requirements if "Discharge Summary" in r.name),
        None,
    )
    assert discharge_req is not None
    assert discharge_req.source_page == 1

    # Check page 2 requirement
    fir_req = next(
        (r for r in response.requirements if "FIR" in r.name or "Medico-Legal" in r.name),
        None,
    )
    assert fir_req is not None
    assert fir_req.source_page == 2
