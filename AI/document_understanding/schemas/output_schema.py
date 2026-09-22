"""
Output schema representing the structured result of Phase 2 (Document Understanding).
This defines the version 1.0 contract consumed by Phase 3 (Medical Insurance Requirement Extraction).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from .common import FieldStatus, ConfidenceLevel, Provenance, BoundingBox, FieldValue


class DocumentTypeHint(BaseModel):
    """Explainable document type hint with supporting signals."""
    model_config = ConfigDict(extra="ignore")

    candidate_type: str = Field(
        ..., 
        description="Candidate type: medical_bill, hospital_invoice, discharge_summary, prescription, diagnostic_report, admission_document, insurance_form, incident_document, unknown"
    )
    confidence: ConfidenceLevel = Field(..., description="Categorical confidence")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Explainable rule score between 0.0 and 1.0")
    supporting_signals: List[str] = Field(
        default_factory=list, 
        description="List of detected keywords, headings, or structural patterns supporting this hint"
    )


class PageUnderstanding(BaseModel):
    """Page-level understanding information."""
    model_config = ConfigDict(extra="ignore")

    page_number: int = Field(..., ge=1)
    extracted_text: str = Field(..., description="Normalized text on this page")
    is_scanned: bool = Field(default=False)
    unreadable_char_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    tables_count: int = Field(default=0, ge=0)
    key_values_count: int = Field(default=0, ge=0)


class DocumentSection(BaseModel):
    """A detected semantic section/heading within the document."""
    model_config = ConfigDict(extra="ignore")

    heading: str = Field(..., description="Section title or heading")
    normalized_heading: str = Field(..., description="Standardized heading identifier (e.g. clinical_summary, diagnosis)")
    content: str = Field(..., description="Text content within this section")
    page_number: int = Field(..., ge=1)
    provenance: Provenance = Field(..., description="Source location of section")


class TableCell(BaseModel):
    """Individual cell in an extracted table."""
    text: str
    normalized_value: Optional[Any] = None
    column_index: int
    row_index: int


class TableRow(BaseModel):
    """Row in an extracted table."""
    cells: List[TableCell] = Field(default_factory=list)
    raw_row_text: Optional[str] = None


class ExtractedTable(BaseModel):
    """Structured table extracted from document."""
    model_config = ConfigDict(extra="ignore")

    table_id: str = Field(..., description="Unique table identifier within document")
    page_number: int = Field(..., ge=1)
    headers: List[str] = Field(default_factory=list, description="Extracted column headers")
    rows: List[TableRow] = Field(default_factory=list, description="List of rows")
    row_count: int = Field(default=0, ge=0)
    col_count: int = Field(default=0, ge=0)
    raw_table_text: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    extraction_method: str = Field(default="layout_or_text_grid")
    quality_notes: Optional[str] = None


class KeyValueField(BaseModel):
    """Extracted label-value pair."""
    model_config = ConfigDict(extra="ignore")

    field_id: str = Field(..., description="Unique field identifier")
    label: str = Field(..., description="Original verbatim label text (e.g. 'Patient Name:', 'DOA:')")
    normalized_key: str = Field(..., description="Standardized key (e.g. 'patient_name', 'admission_date')")
    value: Optional[str] = Field(default=None, description="Extracted value string")
    status: FieldStatus = Field(default=FieldStatus.EXTRACTED)
    provenance: Optional[Provenance] = None


# Entity-specific submodels preserving status, value, and provenance

class PatientEntities(BaseModel):
    """Patient demographic and identification entities."""
    name: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    patient_id: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    age: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    gender: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))


class HospitalEntities(BaseModel):
    """Hospital, clinic, or medical provider entities."""
    name: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    address: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    registration_number: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    doctor_name: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    department: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))


class EncounterEntities(BaseModel):
    """Medical encounter dates, documented diagnosis, and procedures."""
    admission_date: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    discharge_date: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    procedure_date: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    visit_date: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    diagnosis_text: FieldValue = Field(
        default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND),
        description="Diagnosis text strictly as documented in the source. NOT a verified medical diagnosis."
    )
    procedure_text: FieldValue = Field(
        default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND),
        description="Procedure or treatment text strictly as documented."
    )


class ItemizedCharge(BaseModel):
    """Individual line-item in medical bill or invoice."""
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    provenance: Optional[Provenance] = None


class FinancialEntities(BaseModel):
    """Billing and financial information."""
    invoice_number: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    bill_date: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    total_amount: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    paid_amount: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    balance_amount: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    currency: FieldValue = Field(default_factory=lambda: FieldValue(status=FieldStatus.NOT_FOUND))
    itemized_charges: List[ItemizedCharge] = Field(default_factory=list)


class ExtractedEntities(BaseModel):
    """Categorized medical, administrative, and financial entities."""
    patient: PatientEntities = Field(default_factory=PatientEntities)
    hospital: HospitalEntities = Field(default_factory=HospitalEntities)
    encounter: EncounterEntities = Field(default_factory=EncounterEntities)
    financial: FinancialEntities = Field(default_factory=FinancialEntities)


class QualityIssue(BaseModel):
    """Specific quality issue or warning identified during understanding."""
    code: str = Field(..., description="Machine-readable code (e.g. OCR_GARBLE, ARITHMETIC_MISMATCH, MISSING_CRITICAL_FIELD)")
    severity: str = Field(..., description="Severity level: info, warning, error")
    description: str = Field(..., description="Clear human-readable description of the issue")
    page_number: Optional[int] = Field(default=None, description="Page where issue occurs")
    field_reference: Optional[str] = Field(default=None, description="Related field or section name")


class ArithmeticReconciliation(BaseModel):
    """Reconciliation check between itemized line items and stated total amount."""
    checked: bool = False
    itemized_sum: Optional[float] = None
    stated_total: Optional[float] = None
    discrepancy: Optional[float] = None
    matches: Optional[bool] = None
    notes: Optional[str] = None


class DocumentQualityReport(BaseModel):
    """Overall quality and completeness evaluation of the document understanding."""
    model_config = ConfigDict(extra="ignore")

    overall_quality: str = Field(default="good", description="Categorical rating: excellent, good, degraded, poor, unreadable")
    unreadable_char_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    ocr_confidence_avg: Optional[float] = Field(default=None, description="Average OCR confidence score if available")
    is_scanned_or_image_based: bool = Field(default=False)
    has_conflicting_dates: bool = Field(default=False)
    arithmetic_reconciliation: ArithmeticReconciliation = Field(default_factory=ArithmeticReconciliation)
    missing_critical_fields: List[str] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """Document-level metadata."""
    source_type: str = Field(default="pdf")
    page_count: int = Field(..., ge=0)
    detected_language: str = Field(default="en")
    is_scanned: bool = Field(default=False)
    filename: Optional[str] = None


class DocumentUnderstandingResult(BaseModel):
    """
    The master structured result of Phase 2: Document Understanding.
    Schema Version 1.0.
    """
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="1.0", description="Schema version identifier")
    document_id: str = Field(..., description="Unique document ID")
    status: str = Field(default="completed", description="Overall processing status: completed, partial, failed")
    document_metadata: DocumentMetadata
    document_type_hints: List[DocumentTypeHint] = Field(default_factory=list)
    pages: List[PageUnderstanding] = Field(default_factory=list)
    sections: List[DocumentSection] = Field(default_factory=list)
    tables: List[ExtractedTable] = Field(default_factory=list)
    key_value_fields: List[KeyValueField] = Field(default_factory=list)
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    quality: DocumentQualityReport = Field(default_factory=DocumentQualityReport)
    issues: List[QualityIssue] = Field(default_factory=list)
