"""
Tests for duplicate detection.
"""
import unittest
from src.core.models import DocumentRecord, DuplicateStatus
from src.services.duplicate_detector import detect_duplicates, resolve_name_collisions


class TestDuplicateDetection(unittest.TestCase):

    def test_exact_duplicate(self):
        r1 = DocumentRecord(file_hash="abc123", content_hash="x1")
        r2 = DocumentRecord(file_hash="abc123", content_hash="x1")
        r3 = DocumentRecord(file_hash="def456", content_hash="x2")
        records = detect_duplicates([r1, r2, r3])
        self.assertEqual(records[0].duplicate_status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertEqual(records[1].duplicate_status, DuplicateStatus.EXACT_DUPLICATE)
        self.assertEqual(records[2].duplicate_status, DuplicateStatus.NONE)

    def test_content_duplicate(self):
        r1 = DocumentRecord(file_hash="aaa", content_hash="same")
        r2 = DocumentRecord(file_hash="bbb", content_hash="same")
        records = detect_duplicates([r1, r2])
        self.assertEqual(records[0].duplicate_status, DuplicateStatus.LIKELY_DUPLICATE)
        self.assertEqual(records[1].duplicate_status, DuplicateStatus.LIKELY_DUPLICATE)

    def test_name_collision(self):
        r1 = DocumentRecord(
            file_hash="a1", content_hash="c1",
            proposed_filename="Report.pdf"
        )
        r2 = DocumentRecord(
            file_hash="a2", content_hash="c2",
            proposed_filename="Report.pdf"
        )
        records = detect_duplicates([r1, r2])
        self.assertEqual(records[0].duplicate_status, DuplicateStatus.NAME_COLLISION)
        self.assertEqual(records[1].duplicate_status, DuplicateStatus.NAME_COLLISION)


class TestNameCollisionResolution(unittest.TestCase):

    def test_resolve(self):
        r1 = DocumentRecord(proposed_filename="Report.pdf")
        r2 = DocumentRecord(proposed_filename="Report.pdf")
        r3 = DocumentRecord(proposed_filename="Other.pdf")
        records = resolve_name_collisions([r1, r2, r3])
        self.assertEqual(records[0].proposed_filename, "Report.pdf")
        self.assertEqual(records[1].proposed_filename, "Report (2).pdf")
        self.assertEqual(records[2].proposed_filename, "Other.pdf")


if __name__ == "__main__":
    unittest.main()
