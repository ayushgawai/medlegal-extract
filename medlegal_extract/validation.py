from __future__ import annotations
from .schema import CaseExtraction, ValidationIssue


def validate(case: CaseExtraction) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not case.patient.name:
        issues.append(ValidationIssue(code="missing_patient", message="No patient name extracted"))
    if case.stated_total is not None and abs(case.stated_total - case.total_charges) > 0.01:
        issues.append(ValidationIssue(code="total_mismatch",
            message=f"Stated total {case.stated_total:.2f} != sum of charges {case.total_charges:.2f}"))
    dates = [v.date_of_service for v in case.visits if v.date_of_service]
    if dates != sorted(dates):
        issues.append(ValidationIssue(code="date_order", message="Visits are not in chronological order"))
    if case.patient.dob:
        for v in case.visits:
            if v.date_of_service and v.date_of_service < case.patient.dob:
                issues.append(ValidationIssue(code="dos_before_dob",
                    message=f"Visit {v.date_of_service} precedes patient DOB {case.patient.dob}"))
    for v in case.visits:
        if not v.date_of_service:
            issues.append(ValidationIssue(code="missing_dos", message=f"Visit at {v.provider or '?'} has no date of service"))
    for name, items in (("diagnosis", case.diagnoses), ("procedure", case.procedures)):
        for it in items:
            if not it.citations:
                issues.append(ValidationIssue(code="missing_citation", message=f"{name} {it.code} has no citation"))
    return issues
