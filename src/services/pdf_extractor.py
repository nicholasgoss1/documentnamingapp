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


def extract_page1_spatial(file_path: str) -> dict:
    """
    Extract text from page 1 grouped by spatial region.

    Divides page 1 into regions based on letter layout conventions:
      - top_right:  upper quarter, right half  → typically the "from" / letterhead
      - top_left:   upper quarter, left half   → typically the "to" / addressee
      - top:        full-width upper quarter    → all header text combined
      - body:       middle 50% of the page      → main letter content
      - bottom:     lower quarter               → signature / sign-off area

    Returns a dict with keys: top_left, top_right, top, body, bottom.
    Each value is a string of the text blocks in that region.
    """
    regions = {"top_left": "", "top_right": "", "top": "", "body": "", "bottom": ""}
    try:
        doc = fitz.open(file_path)
        if len(doc) == 0:
            doc.close()
            return regions
        page = doc[0]
        width = page.rect.width
        height = page.rect.height

        # Region boundaries
        top_cutoff = height * 0.25
        bottom_cutoff = height * 0.75
        mid_x = width * 0.5

        blocks = page.get_text("blocks")  # list of (x0, y0, x1, y1, text, block_no, block_type)
        doc.close()

        top_left_parts = []
        top_right_parts = []
        top_parts = []
        body_parts = []
        bottom_parts = []

        for block in blocks:
            if block[6] != 0:  # skip image blocks
                continue
            x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
            text = text.strip()
            if not text:
                continue

            block_mid_y = (y0 + y1) / 2
            block_mid_x = (x0 + x1) / 2

            if block_mid_y < top_cutoff:
                top_parts.append(text)
                if block_mid_x < mid_x:
                    top_left_parts.append(text)
                else:
                    top_right_parts.append(text)
            elif block_mid_y > bottom_cutoff:
                bottom_parts.append(text)
            else:
                body_parts.append(text)

        regions["top_left"] = "\n".join(top_left_parts)
        regions["top_right"] = "\n".join(top_right_parts)
        regions["top"] = "\n".join(top_parts)
        regions["body"] = "\n".join(body_parts)
        regions["bottom"] = "\n".join(bottom_parts)
    except Exception:
        pass
    return regions


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
