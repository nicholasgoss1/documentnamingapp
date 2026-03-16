"""
Debug script: check what PyMuPDF extracts from IDR-related PDFs.
Run from the project root:  python debug_idr.py "C:\path\to\J Curtis IDR.pdf"
"""
import sys
import re
import fitz  # PyMuPDF


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_idr.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"=== Analysing: {pdf_path} ===\n")

    doc = fitz.open(pdf_path)
    page = doc[0]
    width = page.rect.width
    height = page.rect.height

    top_cutoff = height * 0.25
    mid_x = width * 0.5

    print(f"Page size: {width:.0f} x {height:.0f}")
    print(f"Top cutoff (25%): y < {top_cutoff:.0f}")
    print(f"Mid X (50%): x < {mid_x:.0f}")
    print()

    # Show ALL blocks including images
    blocks = page.get_text("blocks")
    print("=== ALL BLOCKS (including images) ===")
    for i, block in enumerate(blocks):
        x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
        block_type = block[6]  # 0=text, 1=image
        mid_bx = (x0 + x1) / 2
        mid_by = (y0 + y1) / 2

        if mid_by < top_cutoff:
            region = "TOP-LEFT" if mid_bx < mid_x else "TOP-RIGHT"
        elif mid_by > height * 0.75:
            region = "BOTTOM"
        else:
            region = "BODY"

        if block_type == 1:
            print(f"  Block {i}: IMAGE at ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f}) -> {region}")
        else:
            text = block[4].strip()[:80]
            print(f"  Block {i}: TEXT at ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f}) -> {region}")
            print(f"            {text!r}")
    print()

    # Show spatial regions (text only, as the app does)
    top_left_parts = []
    top_right_parts = []
    for block in blocks:
        if block[6] != 0:
            continue
        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
        text = text.strip()
        if not text:
            continue
        mid_by = (y0 + y1) / 2
        mid_bx = (x0 + x1) / 2
        if mid_by < top_cutoff:
            if mid_bx < mid_x:
                top_left_parts.append(text)
            else:
                top_right_parts.append(text)

    print("=== TOP-LEFT region (text blocks) ===")
    print(repr("\n".join(top_left_parts)))
    print()
    print("=== TOP-RIGHT region (text blocks) ===")
    print(repr("\n".join(top_right_parts)))
    print()

    # Full page 1 text
    page1_text = page.get_text("text")
    page1_lower = page1_text.lower()
    page1_normalized = re.sub(r'\s+', ' ', page1_lower)

    print("=== Page 1 text (first 600 chars, raw) ===")
    print(repr(page1_lower[:600]))
    print()
    print("=== Page 1 text (first 600 chars, normalized) ===")
    print(repr(page1_normalized[:600]))
    print()

    # Check phrases
    phrases = ["on behalf of our mutual client", "claims made easy", "claimsco"]
    print("=== Phrase checks ===")
    for phrase in phrases:
        in_raw = phrase in page1_lower
        in_norm = phrase in page1_normalized
        print(f"  {phrase!r}:")
        print(f"    in raw page1:        {in_raw}")
        print(f"    in normalized page1: {in_norm}")
    print()

    doc.close()


if __name__ == "__main__":
    main()
