"""
Tests for the date inference engine.
"""
import unittest
from src.services.date_engine import (
    extract_all_dates, normalize_date, infer_date, find_page1_top_date,
    find_signed_date, find_policy_inception_date
)


class TestDateExtraction(unittest.TestCase):

    def test_dd_mm_yyyy(self):
        dates = extract_all_dates("Report dated 11.04.2024")
        self.assertEqual(len(dates), 1)
        self.assertEqual(dates[0][0], "11.04.2024")
        self.assertFalse(dates[0][1])  # not partial

    def test_dd_slash_mm_slash_yyyy(self):
        dates = extract_all_dates("Date: 14/03/2024")
        self.assertEqual(dates[0][0], "14.03.2024")

    def test_written_date(self):
        dates = extract_all_dates("Dated 11 April 2024")
        self.assertEqual(dates[0][0], "11.04.2024")

    def test_partial_date(self):
        dates = extract_all_dates("Edition 03.2023")
        self.assertTrue(any(d[1] for d in dates))  # has partial

    def test_iso_date(self):
        dates = extract_all_dates("Created 2024-06-10")
        self.assertEqual(dates[0][0], "10.06.2024")

    def test_normalize_date(self):
        self.assertEqual(normalize_date("11.04.2024"), "11.04.2024")
        self.assertEqual(normalize_date("NO DATE"), "NO DATE")
        self.assertEqual(normalize_date("NOT DATE"), "NO DATE")

    def test_find_page1_top_date(self):
        text = "Some Company\nReport\n\nDate: 25 June 2024\n\nContent..."
        date, partial = find_page1_top_date(text)
        self.assertEqual(date, "25.06.2024")
        self.assertFalse(partial)

    def test_two_digit_year(self):
        dates = extract_all_dates("Date: 28/06/24")
        self.assertEqual(len(dates), 1)
        self.assertEqual(dates[0][0], "28.06.2024")

    def test_two_digit_year_dot(self):
        dates = extract_all_dates("Signed 15.03.25")
        self.assertEqual(dates[0][0], "15.03.2025")

    def test_find_signed_date(self):
        text = "I agree to the terms.\n\nSigned: 23/02/2024\nName: John Smith"
        date = find_signed_date(text)
        self.assertEqual(date, "23.02.2024")

    def test_find_signed_date_two_digit_year(self):
        text = "I agree to the terms.\n\nSigned: 23/02/24\nName: John Smith"
        date = find_signed_date(text)
        self.assertEqual(date, "23.02.2024")

    def test_find_signed_date_standalone_label(self):
        """Standalone 'Date:' in signature block at end of document."""
        text = (
            "Scope of Claim content...\n" * 20
            + "Signature: [signed]\nPrint name: Leah Heron\nDate: 28/06/24\n"
        )
        date = find_signed_date(text)
        self.assertEqual(date, "28.06.2024")

    def test_signed_type_uses_last_date(self):
        """SIGNED_TYPES should prefer the last date (signature date near end)."""
        page1 = "Scope of Claim\nDate issued: 02/07/2024\n\nContent..."
        full = page1 + "\n" * 10 + "Signature\nDate: 28/06/24\n"
        date, conf = infer_date("Letter of Engagement", page1, full, "loe.pdf")
        self.assertEqual(date, "28.06.2024")

    def test_find_policy_inception(self):
        text = "Policy Schedule\nInception date: 15/11/2023\nExpiry: 15/11/2024"
        date = find_policy_inception_date(text)
        self.assertEqual(date, "15.11.2023")


class TestDateInference(unittest.TestCase):

    def test_letter_type(self):
        date, conf = infer_date(
            "Site Report",
            "Site Report\n\nDate: 11 April 2024\n\nInspection details...",
            "Full text here 11 April 2024",
            "site_report.pdf"
        )
        self.assertEqual(date, "11.04.2024")
        self.assertGreater(conf, 10)

    def test_no_date(self):
        date, conf = infer_date(
            "Photo Schedule",
            "Photos from inspection\nNo date visible",
            "Photos only content",
            "photos.pdf",
            photo_mode="conservative"
        )
        self.assertEqual(date, "NO DATE")

    def test_policy_schedule(self):
        date, conf = infer_date(
            "Policy Schedule",
            "Policy Schedule\nInception date: 15/11/2023",
            "Policy inception date: 15/11/2023\nExpiry: 15/11/2024",
            "policy.pdf"
        )
        self.assertEqual(date, "15.11.2023")


if __name__ == "__main__":
    unittest.main()
