"""
PDF text extraction and preview using PyMuPDF (fitz).
All processing is local. No network calls.
"""
import hashlib
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def extract_text(file_path: str, max_pages: int = 5) -> str:
    """Extract text from the first N pages of a PDF."""
    try:
        doc = fitz.open(file_path)
        text_parts = []
        for i in range(min(max_pages, len(doc))):
            page = doc[i]
            text_parts.append(page.get_text("text"))
        doc.close()
        return "\n".join(text_parts)
    except Exception:
        return ""


def extract_page1_text(file_path: str) -> str:
    """Extract text from page 1 only."""
    try:
        doc = fitz.open(file_path)
        if len(doc) > 0:
            text = doc[0].get_text("text")
        else:
            text = ""
        doc.close()
        return text
    except Exception:
        return ""


def get_page_count(file_path: str) -> int:
    """Return number of pages."""
    try:
        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def render_page_pixmap(file_path: str, page_num: int = 0,
                       zoom: float = 1.5) -> Optional[bytes]:
    """Render a page to PNG bytes for preview."""
    try:
        doc = fitz.open(file_path)
        if page_num >= len(doc):
            doc.close()
            return None
        page = doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception:
        return None


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of the file."""
    sha = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()
    except Exception:
        return ""


def compute_content_hash(text: str) -> str:
    """Compute a hash of extracted text for content-based duplicate detection."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
