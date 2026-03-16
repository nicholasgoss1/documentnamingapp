"""
Tests for the normalisation engine.
"""
import unittest
from src.core.settings import Settings
from src.services.normalizer import (
    normalize_entity, normalize_what, normalize_who,
    normalize_full_filename, clean_filename, fix_not_date,
    normalize_date_in_string
)


class TestNormalizeEntity(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()

    def test_alias_resolution(self):
        self.assertEqual(
            normalize_entity("Campbell Construction", self.settings),
            "Campbell Constructions"
        )
        self.assertEqual(
            normalize_entity("CCC", self.settings),
            "Campbell Constructions"
        )
        self.assertEqual(
            normalize_entity("Morse Building Consultant", self.settings),
            "Morse Building Consultants"
        )

    def test_case_normalization(self):
        self.assertEqual(
            normalize_entity("sedgwick", self.settings),
            "Sedgwick"
        )

    def test_passthrough(self):
        self.assertEqual(
            normalize_entity("Unknown Corp", self.settings),
            "Unknown Corp"
        )


class TestNormalizeWho(unittest.TestCase):

    def test_normalize(self):
        self.assertEqual(normalize_who("ff"), "FF")
        self.assertEqual(normalize_who("complainant"), "Complainant")
        self.assertEqual(normalize_who("AFCA"), "AFCA")


class TestCleanFilename(unittest.TestCase):

    def test_strip_invalid_chars(self):
        self.assertNotIn(":", clean_filename("File: Name"))
        self.assertNotIn("?", clean_filename("File? Name"))

    def test_strip_duplicate_spaces(self):
        self.assertNotIn("  ", clean_filename("File  Name"))

    def test_strip_repeated_separators(self):
        result = clean_filename("FF - - Site Report")
        self.assertNotIn("- -", result)

    def test_preserve_content(self):
        result = clean_filename("FF - 11.04.2024 - Campbell Constructions - Site Report")
        self.assertIn("FF", result)
        self.assertIn("Site Report", result)


class TestFixNotDate(unittest.TestCase):

    def test_fix(self):
        self.assertEqual(fix_not_date("NOT DATE"), "NO DATE")
        self.assertEqual(fix_not_date("not date"), "NO DATE")
        self.assertEqual(fix_not_date("NO DATE"), "NO DATE")


class TestNormalizeDateInString(unittest.TestCase):

    def test_fix_single_digit_month(self):
        self.assertEqual(normalize_date_in_string("08.1.2025"), "08.01.2025")

    def test_already_correct(self):
        self.assertEqual(normalize_date_in_string("08.01.2025"), "08.01.2025")


class TestFullFilename(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()

    def test_full_filename(self):
        result = normalize_full_filename(
            "FF", "11.04.2024", "Campbell Constructions", "Site Report",
            False, self.settings
        )
        self.assertEqual(result, "FF - 11.04.2024 - Campbell Constructions - Site Report.pdf")

    def test_no_date(self):
        result = normalize_full_filename(
            "FF", "NO DATE", "Campbell Constructions", "Photo Schedule",
            True, self.settings
        )
        self.assertEqual(
            result,
            "FF - NO DATE - Campbell Constructions - Photo Schedule - UNSURE.pdf"
        )

    def test_no_entity(self):
        result = normalize_full_filename(
            "AFCA", "03.06.2025", "", "Request for Information",
            False, self.settings
        )
        self.assertEqual(result, "AFCA - 03.06.2025 - Request for Information.pdf")


if __name__ == "__main__":
    unittest.main()
