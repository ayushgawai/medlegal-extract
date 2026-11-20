from __future__ import annotations
from datetime import date
from pydantic import BaseModel, Field


class Citation(BaseModel):
    doc_id: str
    page: int  # 1-based
    quote: str = ""


class Cited(BaseModel):
    """Every extracted entity carries page-level citations per field."""
    citations: list[Citation] = Field(default_factory=list)
    field_citations: dict[str, Citation] = Field(default_factory=dict)

    def cite(self, field: str, doc_id: str, page: int, quote: str = ""):
        c = Citation(doc_id=doc_id, page=page, quote=quote.strip()[:200])
        self.field_citations[field] = c
        if c not in self.citations:
            self.citations.append(c)


class Patient(Cited):
    name: str | None = None
    dob: date | None = None


class Provider(Cited):
    name: str
    normalized: str = ""


class Diagnosis(Cited):
    code: str  # ICD-10
    description: str = ""


class Procedure(Cited):
    code: str  # CPT
    description: str = ""


class Visit(Cited):
    provider: str = ""
    date_of_service: date | None = None
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    charges: list[float] = Field(default_factory=list)


class TreatmentGap(Cited):
    start: date
    end: date
    days: int


class LiabilityFact(Cited):
    text: str
    incident_date: date | None = None


class CaseExtraction(Cited):
    patient: Patient = Field(default_factory=Patient)
    providers: list[Provider] = Field(default_factory=list)
    visits: list[Visit] = Field(default_factory=list)
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    total_charges: float = 0.0
    stated_total: float | None = None
    treatment_gaps: list[TreatmentGap] = Field(default_factory=list)
    liability_facts: list[LiabilityFact] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: str = "warning"


class ExtractionResult(BaseModel):
    extraction: CaseExtraction
    issues: list[ValidationIssue] = Field(default_factory=list)
    pages: int = 0
    doc_id: str = ""
