# medlegal-extract

Structured entity extraction from medical records, medical bills and legal
case documents (PDFs and scans) for injury-case preparation — with a
page-level citation for every extracted field, a validation layer, and a
measured evaluation harness.

```
  PDFs / scans / text          hybrid extraction            checked output
 +------------------+      +-----------------------+      +------------------+
 | ingestion        |      | regex + rules         |      | validation       |
 |  pypdf text layer|----->|  dates, ICD-10, CPT,  |----->|  schema (Pydantic|
 |  pytesseract OCR |      |  currency, liability  |      |  totals reconcile|
 |  (when installed)|      |         +             |      |  date ordering   |
 +------------------+      | LLM provider (gap-    |      +------------------+
        |                  |  fill only): stub /   |             |
        v                  |  Anthropic / OpenAI   |             v
 +------------------+      +-----------------------+      +------------------+
 | layout-aware     |               |                     | FastAPI job queue|
 | chunking: split  |---------------+                     |  POST /jobs      |
 | on headings,     |      entity resolution:             |  GET  /jobs/{id} |
 | never cross page |      merge providers/visits         |  GET  .../result |
 +------------------+      across documents                | SQLite/Postgres  |
                                                          +------------------+
```

## Design

| Module | What it does | Key choice |
|---|---|---|
| `ingestion.py` | Splits PDFs into pages (pypdf text layer), OCRs images — and image-only pages — with pytesseract when installed | Text layer first; a page with no text layer degrades to empty rather than failing the job |
| `chunking.py` | Layout-aware chunks: split on headings/blank lines, never across a page | Every chunk keeps an exact page number, which is what makes citations possible |
| `extractors.py` | Hybrid: deterministic regex/rules for dates, ICD-10, CPT, currency and liability phrases; an `LLMProvider` (Anthropic/OpenAI, or a deterministic offline `stub`) fills only the fields rules missed | Rules first — they are free, reproducible and citable; the LLM is never the first resort |
| `schema.py` | Pydantic models: patient, provider, dates of service, diagnoses, procedures, charges, treatment gaps, liability facts | Every entity inherits `Cited` and carries `field_citations: {field: {doc_id, page, quote}}` |
| `resolution.py` | Merges provider spelling variants and duplicate visits across documents | Normalise names (strip punctuation/suffixes), de-dupe visits on `(provider, DOS)` |
| `validation.py` | Schema checks, totals reconciliation (stated total vs sum of line charges), chronological date ordering, DOS-before-DOB, missing-citation checks | Issues are returned alongside the extraction, never silently swallowed |
| `app.py` | FastAPI async job queue: submit → status → result, SQLAlchemy-backed | SQLite by default; set `DATABASE_URL=postgresql+psycopg://…` for PostgreSQL |
| `synthetic.py` + `eval.py` | Generates a labelled synthetic corpus (medical records, bills, legal summaries) and scores extraction against it | Deterministic (`seed=42`), includes noise such as abbreviated provider names evaluated against the canonical name |

## Run

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/medlegal run examples/sample_record.txt          # extract one document (JSON)
.venv/bin/medlegal run scan.pdf --provider anthropic        # LLM gap-fill (needs ANTHROPIC_API_KEY)
.venv/bin/medlegal serve --port 8000                        # API: POST /jobs, GET /jobs/{id}, GET /jobs/{id}/result
.venv/bin/medlegal eval --n 200                             # evaluation harness
```

(`medlegal` is installed into the venv; equivalently `python -m medlegal_extract.cli …`.)

## Test

```bash
.venv/bin/python -m pytest -q   # 6 passed
```

## Benchmark / evaluation results

`medlegal eval --n 200` over the synthetic labelled corpus (seed 42, offline
stub provider — no LLM calls, $0). Throughput is on single-page synthetic
text documents, not scanned PDFs, so treat pages/minute as a parser-speed
ceiling rather than an OCR figure.

| Field | Precision | Recall | F1 |
|---|---|---|---|
| patient | 1.000 | 1.000 | 1.000 |
| dob | 1.000 | 1.000 | 1.000 |
| provider | 0.630 | 0.630 | 0.630 |
| dos | 1.000 | 0.900 | 0.947 |
| icd10 | 1.000 | 1.000 | 1.000 |
| cpt | 1.000 | 1.000 | 1.000 |
| charges | 1.000 | 1.000 | 1.000 |
| **macro** | | | **0.940** |

| Metric | Value |
|---|---|
| Documents | 200 |
| Macro F1 | 0.9396 |
| Throughput | ~1.19M pages/min (synthetic text; machine-dependent) |
| Cost per document | $0.00 (stub provider) |

The two sub-1.0 rows are known, deliberate gaps in the corpus design:
provider abbreviations (`City General Hosp.`) are scored against the
canonical name and entity resolution does not yet expand abbreviations,
and 10% of documents use a `05-Mar-2024` date format the rule parser does
not cover. Both are visible in the output of the eval command itself.

## License

MIT — see [LICENSE](LICENSE).
