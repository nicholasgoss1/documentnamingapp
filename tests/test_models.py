"""
Tests for data models.
"""
import unittest
from src.core.models import DocumentRecord, sanitize_filename


class TestSanitizeFilename(unittest.TestCase):

    def test_remove_invalid_chars(self):
        self.assertEqual(sanitize_filename('File<>:Name'), "FileName")

    def test_strip_spaces(self):
        self.assertEqual(sanitize_filename("  Name  "), "Name")

    def test_strip_pdf(self):
        self.assertEqual(sanitize_filename("Name.pdf"), "Name")

    def test_double_spaces(self):
        self.assertNotIn("  ", sanitize_filename("A  B  C"))


class TestDocumentRecord(unittest.TestCase):

    def test_build_proposed_filename(self):
        rec = DocumentRecord()
        rec.who = "FF"
        rec.date = "11.04.2024"
        rec.entity = "Campbell Constructions"
        rec.what = "Site Report"
        rec.is_unsure = False
        result = rec.build_proposed_filename()
        self.assertEqual(result, "FF - 11.04.2024 - Campbell Constructions - Site Report.pdf")

    def test_unsure_suffix(self):
        rec = DocumentRecord()
        rec.who = "FF"
        rec.date = "NO DATE"
        rec.entity = "Campbell Constructions"
        rec.what = "Photo Schedule"
        rec.is_unsure = True
        result = rec.build_proposed_filename()
        self.assertEqual(
            result,
            "FF - NO DATE - Campbell Constructions - Photo Schedule - UNSURE.pdf"
        )

    def test_no_entity(self):
        rec = DocumentRecord()
        rec.who = "AFCA"
        rec.date = "03.06.2025"
        rec.entity = ""
        rec.what = "Request for Information"
        result = rec.build_proposed_filename()
        self.assertEqual(result, "AFCA - 03.06.2025 - Request for Information.pdf")

    def test_partial_date(self):
        rec = DocumentRecord()
        rec.who = "FF"
        rec.date = "03.2023"
        rec.entity = ""
        rec.what = "PDS - QM486-0323"
        result = rec.build_proposed_filename()
        self.assertEqual(result, "FF - 03.2023 - PDS - QM486-0323.pdf")


if __name__ == "__main__":
    unittest.main()
