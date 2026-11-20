from __future__ import annotations
import random
from datetime import date, timedelta

FIRST = ["Jane", "John", "Maria", "James", "Priya", "Robert", "Sarah", "David", "Anna", "Michael"]
LAST = ["Doe", "Smith", "Garcia", "Patel", "Johnson", "Brown", "Lee", "Wilson", "Sharma", "Davis"]
PROVIDERS = ["City General Hospital", "City General Hosp.", "Riverside Clinic",
             "Riverside Medical Clinic", "Northside Orthopedics"]
DIAGS = [("S13.4XXA", "Cervical strain"), ("M54.50", "Low back pain"),
         ("S06.0X0A", "Concussion"), ("M25.511", "Shoulder pain"), ("S83.91XA", "Knee sprain")]
PROCS = [("99213", "Office visit"), ("97110", "Therapeutic exercise"),
         ("72100", "Lumbar X-ray"), ("97530", "Therapeutic activities")]
LIABILITY = ["The defendant rear-ended the patient's vehicle at a stoplight.",
             "The other driver failed to yield and struck the patient's car.",
             "The defendant ran a red light and caused the collision."]


CANON = {"City General Hosp.": "City General Hospital",
         "Riverside Medical Clinic": "Riverside Clinic"}


def generate(n: int = 200, seed: int = 42) -> list[dict]:
    """Deterministic synthetic labeled corpus: {text, labels} per document."""
    rng = random.Random(seed)
    docs = []
    for i in range(n):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        dob = date(1970, 1, 1) + timedelta(days=rng.randint(0, 12000))
        provider = rng.choice(PROVIDERS)
        base = date(2024, 1, 5) + timedelta(days=rng.randint(0, 300))
        kind = ["medical", "bill", "legal"][i % 3]
        diag = rng.choice(DIAGS); proc = rng.choice(PROCS)
        charge = round(rng.uniform(75, 900), 2)
        labels = {"patient": name, "dob": dob.isoformat(), "provider": CANON.get(provider, provider),
                  "dos": base.isoformat(), "icd10": [diag[0]], "cpt": [proc[0]],
                  "charges": [charge], "total": charge}
        # Noise every 10th doc: a date format the rule parser does not cover.
        dos_text = base.strftime("%d-%b-%Y") if i % 10 == 5 else base.isoformat()
        if kind == "medical":
            text = (f"MEDICAL RECORD\nPatient: {name}\nDOB: {dob:%m/%d/%Y}\nProvider: {provider}\n"
                    f"Date of Service: {dos_text}\nDiagnosis: {diag[0]} - {diag[1]}\n"
                    f"Procedure: CPT {proc[0]} - {proc[1]}\nCharges: ${charge:.2f}\nTotal: ${charge:.2f}\n")
        elif kind == "bill":
            text = (f"MEDICAL BILL\nPatient: {name}\nDate of Birth: {dob:%m/%d/%Y}\nProvider: {provider}\n"
                    f"DOS: {dos_text}\n{diag[0]} - {diag[1]}\nCPT {proc[0]} - {proc[1]}\n"
                    f"Amount: ${charge:.2f}\nTotal Due: ${charge:.2f}\n")
            labels["charges"] = [charge]
        else:
            fact = rng.choice(LIABILITY); labels["liability"] = fact
            text = (f"LEGAL CASE SUMMARY\nPatient: {name}\nDOB: {dob:%m/%d/%Y}\nProvider: {provider}\n"
                    f"Visit Date: {dos_text}\nDiagnosis: {diag[0]} - {diag[1]}\n"
                    f"Procedure: CPT {proc[0]} - {proc[1]}\nCharges: ${charge:.2f}\nTotal: ${charge:.2f}\n{fact}\n")
        docs.append({"id": f"syn-{i:03d}", "kind": kind, "text": text, "labels": labels})
    return docs
