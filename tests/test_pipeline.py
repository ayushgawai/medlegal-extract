from medlegal_extract.ingestion import Page
from medlegal_extract.extractors import HybridExtractor
from medlegal_extract.validation import validate
from medlegal_extract.synthetic import generate

TEXT = """MEDICAL RECORD
Patient: Jane Doe
DOB: 01/15/1980
Provider: City General Hospital
Date of Service: 2024-03-01
Diagnosis: S13.4XXA - Cervical strain
Procedure: CPT 99213 - Office visit
Charges: $250.00
Total: $250.00
The defendant rear-ended the patient's vehicle at a stoplight.
"""


def extract(text=TEXT):
    return HybridExtractor().extract([Page("d1", 1, text)])


def test_core_fields_and_citations():
    c = extract()
    assert c.patient.name == "Jane Doe"
    assert str(c.patient.dob) == "1980-01-15"
    assert c.diagnoses[0].code == "S13.4XXA"
    assert c.procedures[0].code == "99213"
    assert c.total_charges == 250.00 and c.stated_total == 250.00
    assert c.liability_facts and "rear-ended" in c.liability_facts[0].text
    assert c.diagnoses[0].citations[0].page == 1  # every field is cited
    assert c.patient.field_citations["name"].page == 1
    assert validate(c) == []


def test_total_mismatch_and_treatment_gap():
    text = TEXT.replace("Total: $250.00", "Total: $999.00") + (
        "\nProvider: City General Hospital\nDate of Service: 2024-06-15\n"
        "Diagnosis: S13.4XXA - Cervical strain\nCharges: $100.00\n")
    c = extract(text)
    codes = [i.code for i in validate(c)]
    assert "total_mismatch" in codes
    assert c.treatment_gaps and c.treatment_gaps[0].days > 30


def test_synthetic_corpus_size():
    docs = generate(200)
    assert len(docs) == 200 and all(d["labels"]["patient"] for d in docs)


def test_eval_small_runs():
    from medlegal_extract.eval import run_eval
    r = run_eval(20)
    assert r["documents"] == 20 and 0 <= r["macro_f1"] <= 1
