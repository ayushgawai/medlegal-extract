from __future__ import annotations
from pathlib import Path
from .extractors import HybridExtractor, get_provider
from .ingestion import ingest
from .schema import ExtractionResult
from .validation import validate


def run_file(path: str | Path, provider: str = "stub") -> ExtractionResult:
    pages = ingest(path)
    case = HybridExtractor(get_provider(provider)).extract(pages)
    return ExtractionResult(extraction=case, issues=validate(case),
                            pages=len(pages), doc_id=pages[0].doc_id if pages else "")
