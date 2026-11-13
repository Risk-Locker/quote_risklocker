import pytest
from app.extraction.candidate_finder import score_document_type, detect_is_covernote

def test_single_page_quotation_classification():
    text = """
    TAKAFUL MALAYSIA AM BERHAD
    SEBUTHARGA TAKAFUL MOTOR
    THIS IS A QUOTATION ONLY
    VALID FOR 14 DAYS
    Vehicle No: JVS3663
    Total Payable: RM 1,234.50
    """
    doc_type, score, breakdown = score_document_type(
        text=text,
        filename="20261102_JVS3663_Quotation_STMB.pdf",
        page_count=1,
    )
    assert doc_type == "quotation"
    assert breakdown.get("page_count_quotation") == -25.0
    assert detect_is_covernote(text, "20261102_JVS3663_Quotation_STMB.pdf", page_count=1) is False

def test_multi_page_cover_note_classification():
    text = """
    ALLIANZ GENERAL INSURANCE COMPANY (MALAYSIA) BERHAD
    CERTIFICATE OF INSURANCE / OFFICIAL COVER NOTE
    POLICY SCHEDULE
    Policy No: 26VEC0012345
    Period of Insurance: 01/10/2026 to 30/09/2027
    Vehicle No: JYL7732
    """
    doc_type, score, breakdown = score_document_type(
        text=text,
        filename="20261102_JYL7732_CoverNote_Allianz.pdf",
        page_count=6,
    )
    assert doc_type == "covernote"
    assert breakdown.get("page_count_covernote") == 35.0
    assert breakdown.get("filename_covernote") == 60.0
    assert detect_is_covernote(text, "20261102_JYL7732_CoverNote_Allianz.pdf", page_count=6) is True

def test_filename_inversion_protection():
    # If a quote has a passing mention of 'certificate of insurance' in terms,
    # but has quote filename and 2 pages, it remains a quotation!
    text = """
    LIBERTY GENERAL INSURANCE BERHAD
    QUOTATION SCHEDULE
    Proposal Form Ref: Q123456
    Please refer to certificate of insurance upon policy binding.
    VALID FOR 30 DAYS
    """
    doc_type, score, _ = score_document_type(
        text=text,
        filename="20260930_JQM2682_Quotation_Amgen.pdf",
        page_count=2,
    )
    assert doc_type == "quotation"

