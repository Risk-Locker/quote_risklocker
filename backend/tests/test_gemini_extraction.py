import pytest
from pathlib import Path
from app.extraction.orchestrator import ExtractionOrchestrator

# Ensure tests have access to the mock PDF paths
COMPANY_BASED_DIR = Path(__file__).parent.parent.parent / "company_based"

@pytest.mark.skipif(not COMPANY_BASED_DIR.exists(), reason="company_based dir not found")
def test_qbe_multimodal_extraction():
    """
    E2E extraction test that verifies Gemini 1.5 Flash multimodal alignment
    for detached layout pricing in QBE documents.
    """
    qbe_pdf = COMPANY_BASED_DIR / "QBE" / "20260311_JUM2709_Quotation_QBE_extras.pdf"
    if not qbe_pdf.exists():
        pytest.skip(f"Test file {qbe_pdf} not found")

    orchestrator = ExtractionOrchestrator()
    result = orchestrator.extract_file(
        file_path=qbe_pdf,
        enhanced_reading=False,
        db_aliases={},
        db_brands=[],
        db_models=[],
        db_companies=[],
        db_benefit_concepts=[],
        db_packs=[],
        db_corrections=[]
    )
    
    draft = result.get("draft", {})
    fields = draft.get("fields", {})
    
    # Verify core NCD / premium safeguards
    assert fields.get("premium", {}).get("value") == "1130.97", "Total premium mismatch"
    assert fields.get("ncd_amount", {}).get("value") == "345.49", "NCD amount mismatch or contains negative sign"
    assert fields.get("ncd_percent", {}).get("value") == "25.00", "NCD percent mismatch or contains % sign"
    
    # Verify client records extensions
    client_type = fields.get("client_type", {}).get("value")
    # For private clients, we expect "Private"
    assert client_type in ["Private", "Company", None], "Invalid client type"

    # Verify visual multimodal benefit extraction 
    benefits = result.get("full_record", {}).get("benefit_lines", [])
    assert len(benefits) > 0, "No benefits detected, multimodal alignment failed"
