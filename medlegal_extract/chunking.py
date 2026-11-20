from __future__ import annotations
import re
from dataclasses import dataclass
from .ingestion import Page


@dataclass
class Chunk:
    doc_id: str
    page: int
    text: str
    heading: str = ""


HEADING = re.compile(r"^(#{1,3}\s+|[A-Z][A-Z /&-]{3,}:?\s*$)")


def chunk_pages(pages: list[Page], max_chars: int = 1200) -> list[Chunk]:
    """Layout-aware: split on headings / blank lines, never across pages,
    so every chunk retains an exact page citation."""
    chunks: list[Chunk] = []
    for pg in pages:
        heading, buf = "", ""
        def flush():
            if buf.strip():
                chunks.append(Chunk(pg.doc_id, pg.page, buf.strip(), heading))
        for block in re.split(r"\n\s*\n", pg.text):
            block = block.strip()
            if not block:
                continue
            first = block.splitlines()[0]
            if HEADING.match(first):
                flush(); buf = ""; heading = first.strip(" #:")
            if len(buf) + len(block) > max_chars and buf:
                flush(); buf = block
            else:
                buf = f"{buf}\n\n{block}" if buf else block
        flush()
    return chunks
