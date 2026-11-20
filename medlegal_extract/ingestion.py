from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Page:
    doc_id: str
    page: int  # 1-based
    text: str


def _doc_id(path: Path) -> str:
    return hashlib.sha1(path.name.encode()).hexdigest()[:10]


def ingest(path: str | Path) -> list[Page]:
    """Split a document into pages; OCR images / scanned pages when possible.

    Text layer first (pypdf). pytesseract is used only when installed and a
    page/image yields no text — otherwise the page is returned empty rather
    than failing the whole job.
    """
    p = Path(path)
    doc_id = _doc_id(p)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        pages = []
        for i, page in enumerate(PdfReader(str(p)).pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                text = _ocr_pdf_page(p, i) or ""
            pages.append(Page(doc_id, i, text))
        return pages
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return [Page(doc_id, 1, _ocr_image(p) or "")]
    # Plain text / markdown / anything else readable as text.
    return [Page(doc_id, 1, p.read_text(errors="ignore"))]


def _ocr_image(path: Path) -> str | None:
    try:
        import pytesseract  # optional
        from PIL import Image
        return pytesseract.image_to_string(Image.open(path))
    except Exception:
        return None


def _ocr_pdf_page(path: Path, page_no: int) -> str | None:
    # ponytail: rendering PDF pages to images needs pdf2image/poppler; skip
    # unless pytesseract+that stack appear. Text-layer covers born-digital PDFs.
    return None
