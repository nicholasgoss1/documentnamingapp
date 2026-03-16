"""
Tests for duplicate detection.
"""
import unittest
from src.core.models import DocumentRecord, DuplicateStatus
from src.services.duplicate_detector import detect_duplicates, resolve_name_collisions


class TestDuplicateDetection(unittest.TestCase):

    def test_exact_duplicate_first_keeps_name(self):
        r1 = DocumentRecord(
            file_hash="abc123", content_hash="x1",
            proposed_filename="FF - 01.01.2024 - Report.pdf"
        )
        r2 = DocumentRecord(
            file_hash="abc123", content_hash="x1",
            proposed_filename="FF - 01.01.2024 - Report.pdf"
        )
        records = detect_duplicates([r1, r2])
        self.assertEqual(records[0].duplicate_status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertEqual(records[1].duplicate_status, DuplicateStatus.EXACT_DUPLICATE)
        # First keeps its name, second gets DUPLICATE
        self.assertEqual(records[0].proposed_filename, "FF - 01.01.2024 - Report.pdf")
        self.assertIn("DUPLICATE", records[1].proposed_filename)

    def test_exact_duplicate_three_files(self):
        r1 = DocumentRecord(file_hash="abc", content_hash="x1", proposed_filename="Report.pdf")
        r2 = DocumentRecord(file_hash="abc", content_hash="x1", proposed_filename="Report.pdf")
        r3 = DocumentRecord(file_hash="abc", content_hash="x1", proposed_filename="Report.pdf")
        records = detect_duplicates([r1, r2, r3])
        self.assertNotIn("DUPLICATE", records[0].proposed_filename)
        self.assertIn("DUPLICATE", records[1].proposed_filename)
        self.assertIn("DUPLICATE", records[2].proposed_filename)

    def test_content_duplicate(self):
        r1 = DocumentRecord(file_hash="aaa", content_hash="same", proposed_filename="A.pdf")
        r2 = DocumentRecord(file_hash="bbb", content_hash="same", proposed_filename="B.pdf")
        records = detect_duplicates([r1, r2])
        self.assertEqual(records[0].duplicate_status, DuplicateStatus.LIKELY_DUPLICATE)
        self.assertEqual(records[1].duplicate_status, DuplicateStatus.LIKELY_DUPLICATE)
        self.assertNotIn("DUPLICATE", records[0].proposed_filename)
        self.assertIn("DUPLICATE", records[1].proposed_filename)

    def test_non_duplicate_unchanged(self):
        r1 = DocumentRecord(file_hash="a1", content_hash="c1", proposed_filename="Report.pdf")
        r2 = DocumentRecord(file_hash="a2", content_hash="c2", proposed_filename="Other.pdf")
        records = detect_duplicates([r1, r2])
        self.assertEqual(records[0].duplicate_status, DuplicateStatus.NONE)
        self.assertEqual(records[1].duplicate_status, DuplicateStatus.NONE)
        self.assertNotIn("DUPLICATE", records[0].proposed_filename)
        self.assertNotIn("DUPLICATE", records[1].proposed_filename)

    def test_duplicate_filename_format(self):
        r1 = DocumentRecord(file_hash="a1", content_hash="c1",
                            proposed_filename="FF - 01.01.2024 - Site Report.pdf")
        r2 = DocumentRecord(file_hash="a1", content_hash="c1",
                            proposed_filename="FF - 01.01.2024 - Site Report.pdf")
        records = detect_duplicates([r1, r2])
        self.assertEqual(
            records[1].proposed_filename,
            "FF - 01.01.2024 - Site Report - DUPLICATE.pdf"
        )


class TestNameCollisionResolution(unittest.TestCase):

    def test_resolve_remaining_collisions(self):
        r1 = DocumentRecord(proposed_filename="Report.pdf")
        r2 = DocumentRecord(proposed_filename="Report.pdf")
        r3 = DocumentRecord(proposed_filename="Other.pdf")
        records = resolve_name_collisions([r1, r2, r3])
        self.assertEqual(records[0].proposed_filename, "Report.pdf")
        self.assertEqual(records[1].proposed_filename, "Report (2).pdf")
        self.assertEqual(records[2].proposed_filename, "Other.pdf")


if __name__ == "__main__":
    unittest.main()
