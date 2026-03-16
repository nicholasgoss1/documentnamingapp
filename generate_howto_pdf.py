"""Generate HOW_TO_USE.pdf from structured content using PyMuPDF."""
import fitz  # PyMuPDF
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "HOW_TO_USE.pdf")

# Page setup
WIDTH, HEIGHT = fitz.paper_size("A4")
MARGIN = 54  # 0.75 inch
USABLE = WIDTH - 2 * MARGIN

# Fonts
FONT_TITLE = "helvetica-bold"
FONT_H1 = "helvetica-bold"
FONT_H2 = "helvetica-bold"
FONT_BODY = "helvetica"
FONT_BOLD = "helvetica-bold"
FONT_MONO = "courier"

# Sizes
SIZE_TITLE = 20
SIZE_H1 = 14
SIZE_H2 = 11.5
SIZE_BODY = 10
SIZE_SMALL = 9
SIZE_MONO = 8.5

# Colors
BLUE = (0.13, 0.35, 0.67)
DARK = (0.15, 0.15, 0.15)
GREY = (0.35, 0.35, 0.35)
CODE_BG = (0.94, 0.94, 0.96)
TABLE_HEADER_BG = (0.13, 0.35, 0.67)
TABLE_STRIPE = (0.95, 0.95, 0.97)
WHITE = (1, 1, 1)
DIVIDER = (0.8, 0.8, 0.8)


class PDFWriter:
    def __init__(self):
        self.doc = fitz.open()
        self.page = None
        self.y = 0
        self.new_page()

    def new_page(self):
        self.page = self.doc.new_page(width=WIDTH, height=HEIGHT)
        self.y = MARGIN

    def check_space(self, needed):
        if self.y + needed > HEIGHT - MARGIN:
            self.new_page()

    def title(self, text):
        self.check_space(40)
        self.page.insert_text((MARGIN, self.y + SIZE_TITLE), text,
                              fontname=FONT_TITLE, fontsize=SIZE_TITLE, color=DARK)
        self.y += SIZE_TITLE + 8
        # underline
        self.page.draw_line((MARGIN, self.y), (WIDTH - MARGIN, self.y),
                            color=BLUE, width=2)
        self.y += 16

    def h1(self, text):
        self.check_space(35)
        self.y += 10
        self.page.insert_text((MARGIN, self.y + SIZE_H1), text,
                              fontname=FONT_H1, fontsize=SIZE_H1, color=BLUE)
        self.y += SIZE_H1 + 4
        self.page.draw_line((MARGIN, self.y), (WIDTH - MARGIN, self.y),
                            color=DIVIDER, width=0.5)
        self.y += 8

    def h2(self, text):
        self.check_space(25)
        self.y += 6
        self.page.insert_text((MARGIN, self.y + SIZE_H2), text,
                              fontname=FONT_H2, fontsize=SIZE_H2, color=DARK)
        self.y += SIZE_H2 + 6

    def body(self, text, indent=0):
        """Write wrapped body text."""
        x = MARGIN + indent
        max_w = USABLE - indent
        lines = self._wrap(text, FONT_BODY, SIZE_BODY, max_w)
        for line in lines:
            self.check_space(SIZE_BODY + 4)
            self.page.insert_text((x, self.y + SIZE_BODY), line,
                                  fontname=FONT_BODY, fontsize=SIZE_BODY, color=DARK)
            self.y += SIZE_BODY + 4
        self.y += 2

    def bold_body(self, label, text, indent=0):
        """Write a line with bold label followed by normal text."""
        self.check_space(SIZE_BODY + 4)
        x = MARGIN + indent
        tw = fitz.get_text_length(label, fontname=FONT_BOLD, fontsize=SIZE_BODY)
        self.page.insert_text((x, self.y + SIZE_BODY), label,
                              fontname=FONT_BOLD, fontsize=SIZE_BODY, color=DARK)
        # wrap remaining text
        remaining_w = USABLE - indent - tw
        lines = self._wrap(text, FONT_BODY, SIZE_BODY, remaining_w)
        if lines:
            self.page.insert_text((x + tw, self.y + SIZE_BODY), lines[0],
                                  fontname=FONT_BODY, fontsize=SIZE_BODY, color=DARK)
            self.y += SIZE_BODY + 4
            for line in lines[1:]:
                self.check_space(SIZE_BODY + 4)
                self.page.insert_text((x, self.y + SIZE_BODY), line,
                                      fontname=FONT_BODY, fontsize=SIZE_BODY, color=DARK)
                self.y += SIZE_BODY + 4
        else:
            self.y += SIZE_BODY + 4
        self.y += 2

    def bullet(self, text, indent=0):
        x = MARGIN + indent
        self.check_space(SIZE_BODY + 4)
        self.page.insert_text((x, self.y + SIZE_BODY), "\u2022",
                              fontname=FONT_BODY, fontsize=SIZE_BODY, color=BLUE)
        max_w = USABLE - indent - 14
        lines = self._wrap(text, FONT_BODY, SIZE_BODY, max_w)
        for i, line in enumerate(lines):
            self.check_space(SIZE_BODY + 4)
            self.page.insert_text((x + 14, self.y + SIZE_BODY), line,
                                  fontname=FONT_BODY, fontsize=SIZE_BODY, color=DARK)
            self.y += SIZE_BODY + 4

    def code_block(self, lines_text):
        lines = lines_text.split("\n")
        block_h = len(lines) * (SIZE_MONO + 3) + 10
        self.check_space(block_h)
        # background
        rect = fitz.Rect(MARGIN, self.y, WIDTH - MARGIN, self.y + block_h)
        self.page.draw_rect(rect, color=None, fill=CODE_BG)
        self.y += 6
        for line in lines:
            self.check_space(SIZE_MONO + 3)
            self.page.insert_text((MARGIN + 8, self.y + SIZE_MONO), line,
                                  fontname=FONT_MONO, fontsize=SIZE_MONO, color=DARK)
            self.y += SIZE_MONO + 3
        self.y += 8

    def table(self, headers, rows, col_widths=None):
        """Draw a simple table."""
        n = len(headers)
        if col_widths is None:
            col_widths = [USABLE / n] * n
        row_h = SIZE_SMALL + 10

        # header
        self.check_space(row_h * (len(rows) + 1) if len(rows) < 5 else row_h * 2)
        x = MARGIN
        rect = fitz.Rect(x, self.y, x + USABLE, self.y + row_h)
        self.page.draw_rect(rect, color=None, fill=TABLE_HEADER_BG)
        cx = x
        for i, h in enumerate(headers):
            self.page.insert_text((cx + 4, self.y + SIZE_SMALL + 3), h,
                                  fontname=FONT_BOLD, fontsize=SIZE_SMALL, color=WHITE)
            cx += col_widths[i]
        self.y += row_h

        # rows
        for ri, row in enumerate(rows):
            self.check_space(row_h)
            cx = x
            if ri % 2 == 0:
                rect = fitz.Rect(x, self.y, x + USABLE, self.y + row_h)
                self.page.draw_rect(rect, color=None, fill=TABLE_STRIPE)
            for i, cell in enumerate(row):
                # truncate if too long
                text = str(cell)
                max_chars = int(col_widths[i] / (SIZE_SMALL * 0.45))
                if len(text) > max_chars:
                    text = text[:max_chars - 2] + ".."
                self.page.insert_text((cx + 4, self.y + SIZE_SMALL + 3), text,
                                      fontname=FONT_BODY, fontsize=SIZE_SMALL, color=DARK)
                cx += col_widths[i]
            self.y += row_h
        self.y += 6

    def spacer(self, h=6):
        self.y += h

    def _wrap(self, text, font, size, max_w):
        words = text.split()
        lines = []
        current = ""
        for w in words:
            test = f"{current} {w}".strip()
            tw = fitz.get_text_length(test, fontname=font, fontsize=size)
            if tw > max_w and current:
                lines.append(current)
                current = w
            else:
                current = test
        if current:
            lines.append(current)
        return lines if lines else [""]

    def save(self, path):
        self.doc.save(path)
        self.doc.close()


def build():
    p = PDFWriter()

    # === TITLE ===
    p.title("Claim File Renamer — Team How-To Guide")
    p.body("Claim File Renamer is a local desktop application (Windows) that bulk-renames insurance claim "
           "and AFCA PDF documents into a standardised format:")
    p.code_block("WHO - DATE - ENTITY - WHAT.pdf")
    p.body("Examples:")
    p.code_block(
        "FF - 11.04.2024 - Campbell Constructions - Site Report.pdf\n"
        "Complainant - 23.02.2024 - ACB - Letter of Engagement.pdf\n"
        "AFCA - 03.06.2025 - Request for Information.pdf\n"
        "FF - NO DATE - Sedgwick - Assessment Report.pdf"
    )
    p.body("Everything runs locally on your machine \u2014 no files are uploaded anywhere.")

    # === 1. GETTING THE APP ===
    p.h1("1. Getting the App")

    p.h2("Option A \u2014 Use the Built Executable (Recommended)")
    p.bullet("Download the ZIP of the project from GitHub:")
    p.body("Go to https://github.com/nicholasgoss1/documentnamingapp", indent=18)
    p.body("Switch to the branch claude/generate-runnable-project-HDg4G", indent=18)
    p.body("Click the green Code button \u2192 Download ZIP", indent=18)
    p.bullet("Extract the ZIP to a folder on your PC (e.g. C:\\ClaimFileRenamer)")
    p.bullet("Open a Command Prompt in that folder and run:")
    p.code_block("packaging\\build_windows.bat")
    p.body("This creates dist\\ClaimFileRenamer\\ClaimFileRenamer.exe.", indent=18)
    p.bullet("Double-click ClaimFileRenamer.exe to launch.")

    p.h2("Option B \u2014 Run from Source (Developer)")
    p.bullet("Install Python 3.12+ from python.org")
    p.bullet("Download or clone the repo as above")
    p.bullet("Open a Command Prompt in the project folder and run:")
    p.code_block(
        "python -m venv venv\n"
        "venv\\Scripts\\activate\n"
        "pip install -r requirements.txt\n"
        "python main.py"
    )

    # === 2. PREPARE FILES ===
    p.h1("2. Prepare Your Files")
    p.bullet("Gather the PDF files you want to rename into a folder on your PC.")
    p.bullet("Only .pdf files are supported.")
    p.bullet("The app works best with text-based PDFs. Scanned image PDFs will have limited "
             "metadata extraction (no OCR).")

    # === 3. LOAD FILES ===
    p.h1("3. Load Files into the App")
    p.body("You have two options:")
    p.bullet("Drag and drop \u2014 Drag PDF files or an entire folder onto the app window.")
    p.bullet("File menu \u2014 Click File \u2192 Open Files (Ctrl+O) and select your PDFs.")
    p.spacer()
    p.body("A progress bar will appear as the app processes each file.")

    # === 4. AUTOMATIC PROCESSING ===
    p.h1("4. What the App Does Automatically")
    p.body("For each PDF, the app extracts and infers:")
    p.table(
        ["Field", "What It Means", "Example Values"],
        [
            ["WHO", "Who the document is from", "FF, Complainant, AFCA, UNKNOWN"],
            ["DATE", "Document date", "11.04.2024, mm.yyyy, NO DATE"],
            ["ENTITY", "Company or person name", "Sedgwick, QBE, ACB"],
            ["WHAT", "Document type", "Site Report, Assessment Report, Quote"],
        ],
        [100, 200, USABLE - 300]
    )
    p.body("It also calculates:")
    p.bullet("Confidence score (0\u2013100) \u2014 how certain the app is about its guesses.")
    p.bullet("Duplicate status \u2014 flags exact duplicates, likely duplicates, and name collisions.")
    p.spacer()
    p.body("The app then generates a Proposed Filename in the format WHO - DATE - ENTITY - WHAT.pdf.")

    # === 5. REVIEW AND EDIT ===
    p.h1("5. Review and Edit")

    p.h2("Check Confidence")
    p.bullet("Green = high confidence, likely correct.")
    p.bullet("Amber = low confidence (below 60%), review carefully.")
    p.bullet("The Confidence Reason column tells you why confidence is low.")

    p.h2("Edit Fields")
    p.bullet("Double-click any cell in the WHO, DATE, ENTITY, or WHAT columns to edit it.")
    p.bullet("The Proposed Filename updates automatically when you change a field.")

    p.h2("Bulk Editing (for multiple files)")
    p.body("Select multiple rows (Ctrl+Click or Shift+Click), then use the toolbar buttons:")
    p.table(
        ["Button", "What It Does"],
        [
            ["Set WHO", "Set WHO for all selected rows"],
            ["Set Entity", "Set ENTITY for all selected rows"],
            ["Set WHAT", "Set document type for all selected rows"],
            ["Set Date", "Set DATE for all selected rows"],
            ["No Date", "Mark all selected as \"NO DATE\""],
            ["Find/Replace", "Find and replace text across fields"],
        ],
        [120, USABLE - 120]
    )

    p.h2("Filter Problem Files")
    p.body("Use the filter checkboxes at the top to quickly find files that need attention:")
    p.table(
        ["Filter", "Shows"],
        [
            ["Low Conf", "Confidence below 60%"],
            ["NO DATE", "Missing date"],
            ["No WHO", "Missing WHO field"],
            ["No WHAT", "Missing document type"],
            ["Duplicates", "Flagged as duplicate"],
            ["Annexure", "Detected annexure wrapper"],
        ],
        [120, USABLE - 120]
    )

    p.h2("Preview PDFs")
    p.body("Click any row to see a preview of the PDF in the right-hand pane.")

    # === 6. APPROVE AND RENAME ===
    p.h1("6. Approve and Rename")

    p.h2("Step 1: Approve")
    p.bullet("Select the rows you're happy with and click Approve Selected (Ctrl+A).")
    p.bullet("Or click Approve All to approve everything visible.")
    p.body("The Status column changes from PENDING \u2192 APPROVED.")

    p.h2("Step 2: Rename")
    p.bullet("Click Rename Approved.")
    p.bullet("The app validates all approved files (checks for duplicate names, invalid characters, path length).")
    p.bullet("If valid, files are renamed in place in their original folder.")
    p.body("The Status column changes from APPROVED \u2192 RENAMED (shown in green).")

    p.h2("If Something Goes Wrong")
    p.bullet("Undo Last Batch (Ctrl+Z or the Undo button) \u2014 reverts all files from the last rename "
             "back to their original names.")
    p.bullet("The app saves a rollback manifest automatically, so you can always undo.")

    # === 7. EXPORT ===
    p.h1("7. Export Results")
    p.bullet("File \u2192 Export CSV (Ctrl+E) \u2014 saves a spreadsheet of all files with their "
             "original names, proposed names, confidence scores, and rename status.")
    p.bullet("Exports are saved to %LOCALAPPDATA%\\ClaimFileRenamer\\exports\\")

    # === 8. DUPLICATES ===
    p.h1("8. Handling Duplicates")
    p.body("The app automatically detects:")
    p.bullet("Exact Duplicates \u2014 identical files (same content). The second copy gets "
             "\" - DUPLICATE\" appended to its proposed filename.")
    p.bullet("Likely Duplicates \u2014 same text content but different file hash (e.g. re-saved PDF).")
    p.bullet("Name Collisions \u2014 different files that would end up with the same proposed filename.")
    p.spacer()
    p.body("Use the Duplicates filter checkbox to review all flagged files before renaming.")

    # === 9. SETTINGS ===
    p.h1("9. Settings")
    p.body("Access via Edit \u2192 Settings or the gear icon.")
    p.table(
        ["Setting", "What It Controls"],
        [
            ["Dark Mode", "Toggle dark/light theme"],
            ["Confidence Threshold", "Below this score, files marked UNSURE (default: 60)"],
            ["Strip Annexure Prefix", "Auto-remove \"Annexure X\" wrappers"],
            ["Entity Aliases", "Map variations to standard name"],
            ["Preferred Entities", "Your common entity names for quick selection"],
            ["Preferred Doc Labels", "Your standard document type labels"],
        ],
        [150, USABLE - 150]
    )
    p.body("Settings persist between sessions in %LOCALAPPDATA%\\ClaimFileRenamer\\settings.json.")

    # === QUICK REFERENCE ===
    p.h1("Quick Reference \u2014 Keyboard Shortcuts")
    p.table(
        ["Action", "Shortcut"],
        [
            ["Open files", "Ctrl+O"],
            ["Approve selected", "Ctrl+A"],
            ["Undo last rename", "Ctrl+Z"],
            ["Export CSV", "Ctrl+E"],
            ["Toggle dark mode", "View \u2192 Toggle Dark Mode"],
        ],
        [200, USABLE - 200]
    )

    # === TROUBLESHOOTING ===
    p.h1("Troubleshooting")
    p.table(
        ["Problem", "Solution"],
        [
            ["App won't start", "Make sure Python 3.12+ is installed, or use the built .exe"],
            ["\"No text extracted\"", "The PDF is a scanned image \u2014 edit fields manually"],
            ["Confidence is low", "Check Settings \u2192 entity aliases and doc type keywords"],
            ["Rename fails", "Check error \u2014 file may be open or path too long"],
            ["Need to undo", "Edit \u2192 Undo Last Batch (Ctrl+Z)"],
        ],
        [140, USABLE - 140]
    )

    # === FILE LOCATIONS ===
    p.h1("File Locations")
    p.table(
        ["Location", "Contents"],
        [
            ["%LOCALAPPDATA%\\ClaimFileRenamer\\settings.json", "Your saved settings"],
            ["%LOCALAPPDATA%\\ClaimFileRenamer\\logs\\", "Rename operation logs"],
            ["%LOCALAPPDATA%\\ClaimFileRenamer\\rollback\\", "Undo manifests"],
            ["%LOCALAPPDATA%\\ClaimFileRenamer\\exports\\", "CSV exports"],
        ],
        [280, USABLE - 280]
    )

    p.save(OUTPUT)
    print(f"PDF saved to: {OUTPUT}")


if __name__ == "__main__":
    build()
