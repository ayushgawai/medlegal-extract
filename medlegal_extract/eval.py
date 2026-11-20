from __future__ import annotations
import time
from .extractors import HybridExtractor
from .ingestion import Page
from .synthetic import generate

FIELDS = ["patient", "dob", "provider", "dos", "icd10", "cpt", "charges"]


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def run_eval(n: int = 200, seed: int = 42) -> dict:
    docs = generate(n, seed)
    ex = HybridExtractor()
    counts = {f: [0, 0, 0] for f in FIELDS}  # tp, fp, fn
    pages = 0; t0 = time.perf_counter()
    for doc in docs:
        labels = doc["labels"]
        case = ex.extract([Page(doc["id"], 1, doc["text"])]); pages += 1
        pred = {"patient": case.patient.name, "dob": case.patient.dob.isoformat() if case.patient.dob else None,
                "provider": case.visits[0].provider if case.visits else (case.providers[0].name if case.providers else None),
                "dos": case.visits[0].date_of_service.isoformat() if case.visits and case.visits[0].date_of_service else None,
                "icd10": [d.code for d in case.diagnoses], "cpt": [p.code for p in case.procedures],
                "charges": [round(c, 2) for v in case.visits for c in v.charges]}
        for f in FIELDS:
            gold, got = labels[f], pred[f]
            if isinstance(gold, list):
                for g in gold: counts[f][0 if g in got else 2] += 1
                for g in got:
                    if g not in gold: counts[f][1] += 1
            elif got == gold: counts[f][0] += 1
            else:
                counts[f][2] += 1
                if got: counts[f][1] += 1
    elapsed = time.perf_counter() - t0
    fields = {}
    for f in FIELDS:
        p, r, f1 = _prf(*counts[f]); fields[f] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}
    macro = round(sum(v["f1"] for v in fields.values()) / len(fields), 4)
    return {"documents": n, "pages": pages, "fields": fields, "macro_f1": macro,
            "pages_per_minute": round(pages / max(elapsed, 1e-9) * 60, 1),
            "seconds": round(elapsed, 2), "cost_per_document_usd": 0.0,
            "provider": "stub (offline, $0)"}
