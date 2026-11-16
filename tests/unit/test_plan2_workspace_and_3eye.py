"""Unit tests for PLAN 2: Workspace UI Streamlining & 3-Eye Multimodal Consensus Model.

Covers:
1. Task 2.1 & 2.2: Direct net premium mapping without fake subtraction in draft_mapper.
2. Task 2.3: Powertrain card filtering (EV cards suppressed on ICE, enabled on EV).
3. Task 2.4: Eye 2 Comparison Workspace Table Auditor.
4. Task 2.4: Eye 3 Quotation Workspace Visual Parity Auditor.
5. Task 2.4: Complete 3-Eye Consensus Gate releasing overnight batch processing.
"""

from decimal import Decimal
import pytest
from app.extraction.draft_mapper import build_draft
from app.extraction.referee import audit_comparison_matrix_consensus
from app.extraction.types import CandidateValue
from app.extraction.visual_referee import audit_pdf_visual_consensus, verify_3_eye_consensus
from app.rendering.unified_addon_engine import (
    build_unified_matrix_cards,
    is_ev_vehicle,
    ICE_EXCLUDED_MATRIX_IDS,
)


def test_task_2_2_draft_mapper_direct_net_premium_without_fake_subtraction():
    """Verify that draft_mapper extracts the true underwriter net contribution

    directly without subtracting optional extras to fabricate a false base premium.
    """
    candidates = {
        "vehicle_no": [CandidateValue(field="vehicle_no", value="WFW8977", source_method="ai", score=0.99, page=1, evidence="WFW8977")],
        "customer_name": [CandidateValue(field="customer_name", value="YAU YEN CHEN", source_method="ai", score=0.99, page=1, evidence="YAU YEN CHEN")],
        "insurance_company": [CandidateValue(field="insurance_company", value="QBE Insurance", source_method="ai", score=0.99, page=1, evidence="QBE")],
        "premium": [CandidateValue(field="premium", value="335.00", source_method="ai", score=0.99, page=1, evidence="335.00")],
        "total_amount": [CandidateValue(field="total_amount", value="335.00", source_method="ai", score=0.99, page=1, evidence="335.00")],
    }
    benefit_lines = [
        {"name": "Windscreen", "premium_cost": "150.00"},
        {"name": "Legal Liability to Passengers", "premium_cost": "30.00"},
    ]

    fields, warnings, status = build_draft(candidates, benefit_lines=benefit_lines)

    # Net premium must remain 335.00 (NOT 335.00 - 180.00 = 155.00)
    assert fields["premium"]["value"] == "335.00"
    # Total payable in draft is Net Premium + Road Tax + Runner Fee (auto_rt=0 here)
    # Runner fee defaults to 0 in candidate builder if not passed, but no fake math is added
    assert float(fields["premium"]["value"]) == 335.00


def test_task_2_3_powertrain_filter_suppresses_ev_cards_on_ice():
    """Verify that if a vehicle is ICE (Petrol / Diesel), EV wallbox and EV battery

    towing cards are strictly excluded from the 24 cards matrix.
    """
    # 1. Test ICE Car
    ice_cards = build_unified_matrix_cards(
        active_benefits=[],
        available_addons=[],
        fill_to_slots=24,
        vehicle_type="Car",
        car_model="HONDA CIVIC 1.5 TURBO",
    )
    ice_card_ids = {c["id"] for c in ice_cards}
    for ev_id in ICE_EXCLUDED_MATRIX_IDS:
        assert ev_id not in ice_card_ids, f"EV card '{ev_id}' must not appear in ICE vehicle matrix!"
    assert len(ice_cards) == 24

    # 2. Test EV Car (Tesla Model 3)
    ev_cards = build_unified_matrix_cards(
        active_benefits=[],
        available_addons=[],
        fill_to_slots=24,
        vehicle_type="EVSaloonCar",
        car_model="TESLA MODEL 3",
    )
    ev_card_ids = {c["id"] for c in ev_cards}
    assert "ev_wall_charger" in ev_card_ids or "ev_out_of_charge" in ev_card_ids
    assert len(ev_cards) == 24


def test_task_2_4_eye_2_comparison_matrix_auditor():
    """Verify Eye 2 audits comparison columns for uniform road tax, universal

    RM 20 runner fee, mathematical equation, and duplicate ranks.
    """
    clean_entries = [
        {
            "company_name": "QBE Insurance",
            "motor_premium": 335.00,
            "road_tax": 90.00,
            "runner_fee": 20.00,
            "total_amount": 445.00,
            "manual_rank": 1,
        },
        {
            "company_name": "Etiqa General",
            "motor_premium": 380.00,
            "road_tax": 90.00,
            "runner_fee": 20.00,
            "total_amount": 490.00,
            "manual_rank": 2,
        },
    ]

    result = audit_comparison_matrix_consensus(clean_entries, tenure_ledger={"road_tax": 90.00})
    assert result["is_consensus_reached"] is True
    assert result["audit_seal"] == "PASS"

    # Test discrepancy: Non-20 runner fee and duplicate rank
    flawed_entries = [
        {
            "company_name": "QBE Insurance",
            "motor_premium": 335.00,
            "road_tax": 90.00,
            "runner_fee": 10.00,  # Flawed runner fee
            "total_amount": 435.00,
            "manual_rank": 1,
        },
        {
            "company_name": "Etiqa General",
            "motor_premium": 380.00,
            "road_tax": 90.00,
            "runner_fee": 20.00,
            "total_amount": 490.00,
            "manual_rank": 1,  # Duplicate rank
        },
    ]

    flawed_result = audit_comparison_matrix_consensus(flawed_entries, tenure_ledger={"road_tax": 90.00})
    assert flawed_result["is_consensus_reached"] is False
    assert flawed_result["audit_seal"] == "REVIEW_NEEDED"
    assert any("Runner fee" in f for f in flawed_result["findings"])
    assert any("Duplicate rank" in f for f in flawed_result["findings"])


def test_task_2_4_eye_3_quotation_visual_parity_auditor():
    """Verify Eye 3 validates Design 2 PDF against selected winner quotation."""
    winner_entry = {
        "company_name": "QBE Insurance",
        "motor_premium": 335.00,
        "road_tax": 278.80,
        "runner_fee": 20.00,
        "total_amount": 633.80,
    }

    # 1. Clean Parity
    clean_pdf_fields = {
        "insurance_company": "QBE Insurance",
        "premium": "335.00",
        "roadtax": "278.80",
        "service_fee": "20.00",
        "total_amount": "633.80",
    }
    res = audit_pdf_visual_consensus(clean_pdf_fields, winner_entry, is_ev_vehicle=False)
    assert res["is_consensus_reached"] is True
    assert res["audit_seal"] == "PASS"

    # 2. Premium Drift
    drifted_fields = {
        **clean_pdf_fields,
        "premium": "385.00",  # Mismatch with winner
    }
    res_drift = audit_pdf_visual_consensus(drifted_fields, winner_entry, is_ev_vehicle=False)
    assert res_drift["is_consensus_reached"] is False
    assert any("Net Premium drift" in f for f in res_drift["findings"])

    # 3. Powertrain card violation on ICE car
    violating_pdf = {
        **clean_pdf_fields,
        "benefit_07": "EV Wall Charger Cover",
    }
    res_powertrain = audit_pdf_visual_consensus(violating_pdf, winner_entry, is_ev_vehicle=False)
    assert res_powertrain["is_consensus_reached"] is False
    assert any("Powertrain violation" in f for f in res_powertrain["findings"])


def test_task_2_4_complete_3_eye_consensus_gate():
    """Verify the 3-Eye consensus gate requires all 3 perception models to agree

    before giving the green light for unattended overnight dispatch.
    """
    source_extraction = {
        "vehicle_no": "WFW8977",
        "customer_name": "YAU YEN CHEN",
        "insurance_company": "QBE Insurance",
        "vehicle_type": "Car",
    }
    comparison_entries = [
        {
            "company_name": "QBE Insurance",
            "motor_premium": 335.00,
            "road_tax": 278.80,
            "runner_fee": 20.00,
            "total_amount": 633.80,
            "is_recommended": True,
            "manual_rank": 1,
        }
    ]
    pdf_render_context = {
        "draft_fields": {
            "insurance_company": "QBE Insurance",
            "premium": "335.00",
            "roadtax": "278.80",
            "service_fee": "20.00",
            "total_amount": "633.80",
        }
    }

    consensus = verify_3_eye_consensus(
        source_extraction=source_extraction,
        comparison_entries=comparison_entries,
        pdf_render_context=pdf_render_context,
        tenure_ledger={"road_tax": 278.80},
    )

    assert consensus["can_dispatch"] is True
    assert consensus["audit_seal"] == "PASS"
    assert "100% 3-Eye Multimodal AI Consensus Achieved" in consensus["summary"]
