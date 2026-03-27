"""
Generate sample test PDF files for testing the renaming app.
Uses PyMuPDF to create simple PDFs with realistic content.

Usage: python tests/create_test_pdfs.py
"""
import os
import sys

import fitz  # PyMuPDF


TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pdfs")


def create_pdf(filename: str, pages: list):
    """Create a simple PDF with text content on each page."""
    os.makedirs(TEST_DIR, exist_ok=True)
    doc = fitz.open()
    for page_text in pages:
        page = doc.new_page(width=595, height=842)  # A4
        text_point = fitz.Point(50, 50)
        page.insert_text(text_point, page_text, fontsize=11, fontname="helv")
    filepath = os.path.join(TEST_DIR, filename)
    doc.save(filepath)
    doc.close()
    print(f"  Created: {filename}")
    return filepath


def main():
    print("Creating test PDFs...")
    print(f"Output directory: {TEST_DIR}")
    print()

    # 1. Campbell Constructions Site Report
    create_pdf("Annexure 1.pdf", [
        "Campbell Constructions Pty Ltd\n\n"
        "SITE REPORT\n\n"
        "Date: 11 April 2024\n\n"
        "Site Address: 123 Example Street, Melbourne VIC 3000\n\n"
        "Inspection conducted by: John Builder\n"
        "Job Reference: CC-2024-0456\n\n"
        "Summary of Findings:\n"
        "The site inspection was conducted on the above date.\n"
        "Damage consistent with storm activity observed on roof and guttering.\n"
        "Refer to attached photo schedule for photographic evidence.",
    ])

    # 2. Campbell Constructions Photo Schedule
    create_pdf("Annexure 2.pdf", [
        "Campbell Constructions Pty Ltd\n\n"
        "PHOTO SCHEDULE\n\n"
        "Job Reference: CC-2024-0456\n\n"
        "Photo 1: Front elevation showing roof damage\n"
        "Photo 2: Close-up of cracked ridge cap\n"
        "Photo 3: Internal water staining - bedroom ceiling\n"
        "Photo 4: Guttering displacement - north side",
    ])

    # 3. Sedgwick Assessment Report
    create_pdf("Sedgwick_Assessment_14032024.pdf", [
        "Sedgwick\n"
        "Claim Assessment Report\n\n"
        "Date: 14 March 2024\n"
        "Claim Number: QBE-2024-12345\n"
        "Insured: Jane Smith\n"
        "Site: 123 Example Street, Melbourne VIC 3000\n\n"
        "Assessment Report\n\n"
        "Event: Storm - 5 March 2024\n"
        "Our assessment of the claimed damage is as follows...",
    ])

    # 4. Sedgwick Progress Report 1
    create_pdf("Progress_Rpt_1.pdf", [
        "Sedgwick\n"
        "Progress Report #1\n\n"
        "Date: 11 April 2024\n"
        "Claim Number: QBE-2024-12345\n\n"
        "Progress update on claim assessment.\n"
        "Repairs have commenced per approved scope.",
    ])

    # 5. Sedgwick Progress Report 2
    create_pdf("Progress_Update_2.pdf", [
        "Sedgwick\n"
        "Progress Report #2\n\n"
        "Date: 19 June 2024\n"
        "Claim Number: QBE-2024-12345\n\n"
        "Second progress update.\n"
        "Roof repairs completed. Internal works in progress.",
    ])

    # 6. Morse Building Consultants Roof Report
    create_pdf("Morse_Roof_Rpt.pdf", [
        "Morse Building Consultants\n\n"
        "ROOF REPORT\n\n"
        "Date: 10 June 2024\n"
        "Client: QBE Insurance\n"
        "Property: 123 Example Street, Melbourne VIC 3000\n\n"
        "Independent assessment of roof condition and storm damage.\n"
        "Findings indicate pre-existing maintenance issues\n"
        "combined with recent storm impact.",
    ])

    # 7. QBE IDR FDL
    create_pdf("QBE_Decision_25062024.pdf", [
        "QBE Insurance (Australia) Limited\n\n"
        "INTERNAL DISPUTE RESOLUTION\n"
        "FINAL DECISION LETTER\n\n"
        "Date: 25 June 2024\n\n"
        "Dear Ms Smith,\n\n"
        "We refer to your complaint regarding Claim QBE-2024-12345.\n"
        "After review, our final decision is...",
    ])

    # 8. AFCA Request for Information
    create_pdf("AFCA_RFI_03062025.pdf", [
        "Australian Financial Complaints Authority\n\n"
        "REQUEST FOR INFORMATION\n\n"
        "Date: 3 June 2025\n"
        "Complaint Reference: AFCA-2025-000123\n\n"
        "Dear QBE Insurance,\n\n"
        "AFCA requires the following information in relation\n"
        "to the above complaint...",
    ])

    # 9. AFCA Written Preliminary Assessment
    create_pdf("AFCA_WPA.pdf", [
        "Australian Financial Complaints Authority\n\n"
        "WRITTEN PRELIMINARY ASSESSMENT\n\n"
        "Date: 23 July 2025\n"
        "Complaint Reference: AFCA-2025-000123\n\n"
        "Having considered the submissions of both parties,\n"
        "AFCA's preliminary view is...",
    ])

    # 10. ACB Building Report
    create_pdf("ACB_Report_Final.pdf", [
        "ACB Building Consultants\n\n"
        "BUILDING REPORT\n\n"
        "Date: 6 February 2024\n"
        "Our Reference: ACB-2024-789\n"
        "Client: Jane Smith (via ClaimsCo)\n\n"
        "Independent building inspection report.\n"
        "Comprehensive assessment of storm damage and remediation requirements.",
    ])

    # 11. ACB Supplementary Report
    create_pdf("ACB_Supp_Report.pdf", [
        "ACB Building Consultants\n\n"
        "SUPPLEMENTARY REPORT\n\n"
        "Date: 18 December 2025\n"
        "Our Reference: ACB-2024-789-S1\n"
        "Client: Jane Smith (via ClaimsCo)\n\n"
        "Supplementary report addressing points raised in\n"
        "the insurer's assessment.",
    ])

    # 12. Letter of Engagement
    create_pdf("LOE_signed.pdf", [
        "ClaimsCo Pty Ltd\n\n"
        "LETTER OF ENGAGEMENT\n\n"
        "Date: 1 February 2024\n\n"
        "Dear Ms Smith,\n\n"
        "Thank you for engaging our services.\n"
        "Please sign below to confirm your instructions.\n\n\n"
        "Client Signature: [signed]\n"
        "Date signed: 23 February 2024",
    ])

    # 13. Certificate of Insurance
    create_pdf("COI_2023.pdf", [
        "QBE Insurance\n\n"
        "CERTIFICATE OF INSURANCE\n\n"
        "Policy Number: HOM-2023-56789\n"
        "Insured: Jane Smith\n"
        "Property: 123 Example Street, Melbourne VIC 3000\n\n"
        "Period of Insurance:\n"
        "Inception date: 15 November 2023\n"
        "Expiry date: 15 November 2024\n\n"
        "Print date: 20 November 2023",
    ])

    # 14. Policy Schedule
    create_pdf("Policy_Schedule_2023.pdf", [
        "QBE Insurance\n\n"
        "POLICY SCHEDULE\n\n"
        "Policy Number: HOM-2023-56789\n"
        "Inception date: 15 November 2023\n"
        "Expiry: 15 November 2024\n"
        "Insured: Jane Smith\n"
        "Property: 123 Example Street, Melbourne VIC 3000\n\n"
        "Building Sum Insured: $850,000\n"
        "Contents Sum Insured: $150,000",
    ])

    # 15. PDS
    create_pdf("QBE_PDS_QM486-0323.pdf", [
        "QBE Insurance\n\n"
        "PRODUCT DISCLOSURE STATEMENT\n\n"
        "Home Insurance\n"
        "Preparation date: March 2023\n"
        "Wording code: QM486-0323\n\n"
        "This PDS contains important information about\n"
        "your home insurance policy.",
    ])

    # 16. ACB Quote
    create_pdf("ACB_Quote_2024.pdf", [
        "ACB Building Consultants\n\n"
        "QUOTATION\n\n"
        "Date: [not shown]\n"
        "Reference: ACB-Q-2024-001\n"
        "Prepared for: Jane Smith\n\n"
        "Scope of Works: Storm damage remediation\n\n"
        "Total (incl. GST): $57,987.80\n\n"
        "This quote is valid for 30 days.",
    ])

    # 17. Complainant AFCA Submission
    create_pdf("Our_AFCA_Submission.pdf", [
        "ClaimsCo Pty Ltd\n"
        "Authorised Representative of Jane Smith\n\n"
        "SUBMISSION TO AFCA\n\n"
        "Date: 4 December 2024\n"
        "Complaint Reference: AFCA-2025-000123\n\n"
        "Dear AFCA,\n\n"
        "We submit the following on behalf of the complainant...",
    ])

    # 18. Notice of Response (Complainant side)
    create_pdf("Complainant_NOR.pdf", [
        "ClaimsCo Pty Ltd\n"
        "Authorised Representative of Jane Smith\n\n"
        "NOTICE OF RESPONSE\n\n"
        "Date: 17 June 2025\n"
        "Complaint Reference: AFCA-2025-000123\n\n"
        "We respond to QBE's notice of response as follows...",
    ])

    # 19. Notice of Response from QBE
    create_pdf("QBE_NOR_23122024.pdf", [
        "QBE Insurance (Australia) Limited\n\n"
        "NOTICE OF RESPONSE\n\n"
        "Date: 23 December 2024\n"
        "Complaint Reference: AFCA-2025-000123\n\n"
        "From QBE Insurance\n\n"
        "Dear AFCA,\n\n"
        "QBE responds to the complaint as follows...",
    ])

    # 20. AAF to be signed
    create_pdf("AAF_blank.pdf", [
        "ClaimsCo Pty Ltd\n\n"
        "AUTHORITY AND ACCESS FORM\n\n"
        "Please complete and return this form.\n\n"
        "I, _____________, authorise ClaimsCo to act\n"
        "on my behalf in relation to my insurance claim.\n\n"
        "Signature: _______________\n"
        "Date: _______________",
    ])

    # 21. Supplementary Technical Assessment Report
    create_pdf("ACB_STAR.pdf", [
        "ACB Building Consultants\n\n"
        "SUPPLEMENTARY TECHNICAL ASSESSMENT REPORT\n\n"
        "Date: 17 June 2025\n"
        "Reference: ACB-2024-789-T1\n"
        "Client: Jane Smith (via ClaimsCo)\n\n"
        "Technical assessment responding to points raised\n"
        "in the Morse Building Consultants roof report.",
    ])

    # 22. Claim Lodgement Email
    create_pdf("claim_email_printout.pdf", [
        "From: jane.smith@email.com\n"
        "To: claims@qbe.com.au\n"
        "Date: 6 March 2024\n"
        "Subject: New Claim - Storm Damage 5 March 2024\n\n"
        "Claim Lodgement Email\n\n"
        "Dear QBE Claims,\n\n"
        "I wish to lodge a claim for storm damage to my property\n"
        "at 123 Example Street, Melbourne.",
    ])

    print()
    print(f"Created {len(os.listdir(TEST_DIR))} test PDFs in {TEST_DIR}")
    print()
    print("Expected rename results:")
    print("  Annexure 1.pdf -> FF - 11.04.2024 - Campbell Constructions - Site Report.pdf")
    print("  Annexure 2.pdf -> FF - NO DATE - Campbell Constructions - Photo Schedule.pdf")
    print("  Sedgwick_Assessment_14032024.pdf -> FF - 14.03.2024 - Sedgwick - Assessment Report.pdf")
    print("  Progress_Rpt_1.pdf -> FF - 11.04.2024 - Sedgwick - Progress Report 1.pdf")
    print("  Progress_Update_2.pdf -> FF - 19.06.2024 - Sedgwick - Progress Report 2.pdf")
    print("  Morse_Roof_Rpt.pdf -> FF - 10.06.2024 - Morse Building Consultants - Roof Report.pdf")
    print("  QBE_Decision_25062024.pdf -> FF - 25.06.2024 - QBE - IDR FDL.pdf")
    print("  AFCA_RFI_03062025.pdf -> AFCA - 03.06.2025 - Request for Information.pdf")
    print("  AFCA_WPA.pdf -> AFCA - 23.07.2025 - Written Preliminary Assessment.pdf")
    print("  ACB_Report_Final.pdf -> Complainant - 06.02.2024 - ACB - Building Report.pdf")
    print("  ACB_Supp_Report.pdf -> Complainant - 18.12.2025 - ACB - Supplementary Report.pdf")
    print("  LOE_signed.pdf -> Complainant - 23.02.2024 - Letter of Engagement.pdf")
    print("  COI_2023.pdf -> Complainant - 15.11.2023 - COI - Certificate of Insurance.pdf")
    print("  Policy_Schedule_2023.pdf -> FF - 15.11.2023 - Policy Schedule.pdf")
    print("  QBE_PDS_QM486-0323.pdf -> FF - 03.2023 - PDS - QM486-0323.pdf")
    print("  ACB_Quote_2024.pdf -> Complainant - NO DATE - ACB - Quote - $57,987.80.pdf")
    print("  Our_AFCA_Submission.pdf -> Complainant - 04.12.2024 - AFCA Submission.pdf")
    print("  Complainant_NOR.pdf -> Complainant - 17.06.2025 - Notice of Response.pdf")
    print("  QBE_NOR_23122024.pdf -> FF - 23.12.2024 - Notice of Response from QBE.pdf")
    print("  AAF_blank.pdf -> Complainant - NO DATE - AAF to be signed.pdf")
    print("  ACB_STAR.pdf -> Complainant - 17.06.2025 - Supplementary Technical Assessment Report.pdf")
    print("  claim_email_printout.pdf -> Complainant - 06.03.2024 - Claim Lodgement Email.pdf")


if __name__ == "__main__":
    main()
