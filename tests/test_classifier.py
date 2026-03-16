"""
Tests for the document classifier.
"""
import unittest
from src.core.settings import Settings
from src.services.classifier import (
    detect_annexure, infer_who, infer_entity, infer_what,
    should_include_entity, extract_quote_amount, normalize_what_label
)


class TestAnnexure(unittest.TestCase):

    def test_detect_annexure(self):
        self.assertEqual(detect_annexure("Annexure 1"), (True, "1"))
        self.assertEqual(detect_annexure("Annexure 13"), (True, "13"))
        self.assertEqual(detect_annexure("Site Report.pdf"), (False, ""))

    def test_annex_variant(self):
        self.assertEqual(detect_annexure("Annex 3"), (True, "3"))


class TestWhoInference(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()

    def test_ff_from_sedgwick(self):
        who, conf = infer_who(
            "Sedgwick Assessment Report", "", "sedgwick_report.pdf",
            "Sedgwick", self.settings
        )
        self.assertEqual(who, "FF")

    def test_complainant_from_acb(self):
        who, conf = infer_who(
            "ACB Building Report", "", "acb_report.pdf",
            "ACB", self.settings
        )
        self.assertEqual(who, "Complainant")

    def test_afca_from_text(self):
        who, conf = infer_who(
            "AFCA Request for Information", "", "rfi.pdf",
            "AFCA", self.settings
        )
        self.assertEqual(who, "AFCA")

    def test_default_ff(self):
        who, conf = infer_who(
            "Some unknown report", "", "report.pdf",
            "", self.settings
        )
        self.assertEqual(who, "FF")


class TestEntityInference(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()

    def test_find_campbell(self):
        entity, conf = infer_entity(
            "Campbell Constructions Site Report", "", "campbell_report.pdf",
            self.settings
        )
        self.assertEqual(entity, "Campbell Constructions")

    def test_find_morse(self):
        entity, conf = infer_entity(
            "Morse Building Consultants Roof Report", "", "morse.pdf",
            self.settings
        )
        self.assertEqual(entity, "Morse Building Consultants")

    def test_alias_resolution(self):
        entity, conf = infer_entity(
            "CCC Site Report", "", "ccc_report.pdf",
            self.settings
        )
        self.assertEqual(entity, "Campbell Constructions")


class TestWhatInference(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()

    def test_site_report(self):
        what, conf = infer_what(
            "Site Report\n\nDate: 11 April 2024", "", "report.pdf",
            self.settings
        )
        self.assertEqual(what, "Site Report")

    def test_photo_schedule(self):
        what, conf = infer_what(
            "Photo Schedule\n\nPhotographs attached", "", "photos.pdf",
            self.settings
        )
        self.assertEqual(what, "Photo Schedule")

    def test_notice_of_response_qbe(self):
        what, conf = infer_what(
            "Notice of Response\nFrom QBE Insurance", "", "nor_qbe.pdf",
            self.settings
        )
        self.assertEqual(what, "Notice of Response from QBE")


class TestQuoteAmount(unittest.TestCase):

    def test_extract_amount(self):
        amount = extract_quote_amount("Total: $57,987.80")
        self.assertEqual(amount, "$57,987.80")

    def test_no_amount(self):
        amount = extract_quote_amount("No price shown here")
        self.assertEqual(amount, "")


class TestEntityInclude(unittest.TestCase):

    def setUp(self):
        self.settings = Settings()

    def test_site_report_includes_entity(self):
        self.assertTrue(should_include_entity("Site Report", "Campbell Constructions", self.settings))

    def test_afca_submission_excludes_entity(self):
        self.assertFalse(should_include_entity("AFCA Submission", "AFCA", self.settings))


class TestNormalizeWhat(unittest.TestCase):

    def test_title_case(self):
        labels = ["Site Report", "AFCA Submission"]
        self.assertEqual(normalize_what_label("site report", labels), "Site Report")
        self.assertEqual(normalize_what_label("afca submission", labels), "AFCA Submission")


if __name__ == "__main__":
    unittest.main()
