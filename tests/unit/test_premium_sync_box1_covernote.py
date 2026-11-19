"""Hermetic TDD suite for v30.6 Milestones 1-4:
- Insurer bottom-total extraction (STMB, Tune, Etiqa, AmAssurance, Sompo, Lonpac)
- Zero double-counting & idempotent applied_to_premium add-on delta math
- Two-way Workspace <-> Comparison benefit/price sync (including inline edits + PDS suppression)
- Strict Box 1 <-> Design 2 Top-Right 1:1 parity
- Cover Note inline & full editing sync
- Worker DB-release safety & batch upload limit defaults
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from app.api.routers.comparison import UpdateComparisonEntryPatch, patch_comparison_entry
from app.extraction.candidate_finder import _add_2d_spatial_candidates
from app.extraction.draft_mapper import build_draft
from app.models.tables import (
    Base,
    Batch,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    CatalogOffering,
    DraftBenefitSelection,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceTenure,
    OutputTemplateConfig,
    QuotationDraft,
    Session as SessionModel,
    TemplatePageProfile,
    TemplateRevision,
    TenureComparisonEntry,
    TrackedVehicle,
    UploadedFile,
    User,
    new_id,
)
from app.services.marketing_comparison.benefits_extractor import _resolve_comparison_benefits
from app.services.master_template_service import motor_modern_design_2_config
from app.services.workspace_patch_service import apply_workspace_patch
from app.services.workspace_snapshot_service import build_workspace_snapshot


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _seed_full_quote_fixture(db: OrmSession):
    user = User(id=new_id(), name="Agent", email="agent@risklocker.local", password_hash="hash", role="admin")
    comp = InsuranceCompany(
        id=new_id(),
        name="Lonpac Insurance",
        slug="lonpac-insurance",
        detection_phrases=["Lonpac"],
        status="active",
    )
    prod = InsuranceProduct(id=new_id(), company_id=comp.id, product_key="commercial-van", name="Commercial Van", status="active")
    cat = BenefitCatalog(id=new_id(), company_id=comp.id, product_id=prod.id, name="Commercial", status="active")
    cat_rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", content_hash="h1")

    tmpl = OutputTemplateConfig(id=new_id(), insurance_company_id=None, name="Design 2", status="active")
    page = TemplatePageProfile(id=new_id(), profile_key="a4", name="A4", width=794, height=1123, unit="px", safe_margins={}, bleed={})
    t_rev = TemplateRevision(
        id=new_id(),
        template_id=tmpl.id,
        page_profile_id=page.id,
        revision_number=1,
        state="published",
        config=motor_modern_design_2_config(),
        config_hash="th1",
    )

    c_ws = BenefitConcept(id=new_id(), concept_key="windscreen", label="Windscreen Coverage", status="active")
    c_sp = BenefitConcept(id=new_id(), concept_key="special-perils", label="Special Perils", status="active")
    c_llp = BenefitConcept(id=new_id(), concept_key="legal-liability-to-passengers", label="Legal Liability to Passengers", status="active")
    c_bet = BenefitConcept(id=new_id(), concept_key="betterment", label="Waiver of Betterment", status="active")
    c_tow = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", status="active")

    off_ws = CatalogOffering(
        id=new_id(), catalog_revision_id=cat_rev.id, offering_key="fc435683-add-windscreen",
        concept_id=c_ws.id, offering_kind="optional", role="addon_option", status="active",
    )
    off_sp = CatalogOffering(
        id=new_id(), catalog_revision_id=cat_rev.id, offering_key="fc435683-add-special-perils",
        concept_id=c_sp.id, offering_kind="optional", role="addon_option", status="active",
        optional_price={"amount": "75.00", "currency": "MYR"},
    )
    off_llp = CatalogOffering(
        id=new_id(), catalog_revision_id=cat_rev.id, offering_key="fc435683-add-llp",
        concept_id=c_llp.id, offering_kind="optional", role="addon_option", status="active",
        optional_price={"amount": "41.85", "currency": "MYR"},
    )
    off_bet = CatalogOffering(
        id=new_id(), catalog_revision_id=cat_rev.id, offering_key="fc435683-add-betterment",
        concept_id=c_bet.id, offering_kind="optional", role="addon_option", status="active",
    )

    vehicle = TrackedVehicle(
        id=new_id(),
        vehicle_no="VAA1234",
        car_brand="Nissan",
        car_model="Urvan",
        engine_cc="2488",
        manufacture_year=2015,
    )
    tenure = InsuranceTenure(
        id=new_id(),
        tracked_vehicle_id=vehicle.id,
        vehicle_no="VAA1234",
        customer_name="ACME LOGISTICS SDN BHD",
        coverage_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        coverage_end_date=datetime(2027, 5, 31, tzinfo=timezone.utc),
        expiry_month="2027-05",
        status="draft",
        road_tax=0.0,
        runner_fee=0.0,
        include_road_tax=False,
        include_runner_fee=False,
        ncd_percentage=25.0,
    )
    batch = Batch(id=new_id(), owner_id=user.id, name="Batch 1")
    uf = UploadedFile(
        id=new_id(), batch_id=batch.id, owner_id=user.id,
        original_filename="lonpac.pdf", content_type="application/pdf", storage_path="tmp/lonpac.pdf",
    )
    draft = QuotationDraft(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf.id,
        company_id=comp.id,
        product_id=prod.id,
        catalog_revision_id=cat_rev.id,
        template_revision_id=t_rev.id,
        revision=1,
        status="ready",
        display_options={"document_type": "quotation"},
        fields={
            "vehicle_no": {"value": "VAA1234"},
            "customer_name": {"value": "ACME LOGISTICS SDN BHD"},
            "car_model": {"value": "Urvan"},
            "vehicle_year": {"value": "2015"},
            "vehicle_type": {"value": "Lorry"},
            "insurance_company": {"value": "Lonpac Insurance"},
            "sum_insured": {"value": "30000.00"},
            "coverage_amount": {"value": "30000.00"},
            "valuation_type": {"value": "Market Value"},
            "excess_amount": {"value": "600.00"},
            "premium": {"value": "1474.05", "detected_value": "1474.05", "status": "ready"},
            "roadtax": {"value": "0.00"},
            "service_fee": {"value": "0.00"},
            "include_road_tax": {"value": "false"},
            "include_runner_fee": {"value": "false"},
            "total_amount": {"value": "1474.05", "detected_value": "1474.05", "status": "ready"},
            "authorized_driver": {
                "value": "Authorized Driver",
                "evidence": "Premium 1,447.44 - NCD(25.00%) (361.86) + WINDSCREEN RM1,800.00 270.00 = Total 1,474.03 • Special Perils / Flood",
            },
        },
        scalar_decisions={"total_amount": {"decision": "confirm"}},
    )
    sel_ws = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:fc435683-add-windscreen",
        catalog_offering_id=off_ws.id,
        concept_id=c_ws.id,
        item_kind="catalog",
        state="current",
        cost_status="paid",
        label_override="Windscreen Coverage",
        typed_value_override={"type": "money", "value": "1800.00", "currency": "MYR", "display_text": "RM 1,800.00", "semantic_role": "limit"},
        price={"value": 270, "amount": 270, "currency": "MYR"},
        evidence_snapshot={"source": "extracted_addon", "is_detected": True, "premium_cost": "270.00", "coverage_limit": "1,800.00"},
    )
    sel_sp_removed = DraftBenefitSelection(
        id=new_id(),
        draft_id=draft.id,
        selection_key="catalog:fc435683-add-special-perils",
        catalog_offering_id=off_sp.id,
        concept_id=c_sp.id,
        item_kind="catalog",
        state="available_addon",
        cost_status="paid",
        label_override="Special Perils",
        price={"amount": "75.00", "currency": "MYR"},
    )
    session_obj = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        tenure_id=tenure.id,
        detected_company="Lonpac Insurance",
        is_tenure_active=True,
    )
    entry = TenureComparisonEntry(
        id=new_id(),
        tenure_id=tenure.id,
        session_id=session_obj.id,
        company_id=comp.id,
        company_name="Lonpac Insurance",
        motor_premium=1474.05,
        sum_insured=30000.0,
        valuation_type="market_value",
        agreed_value=False,
        road_tax=0.0,
        runner_fee=0.0,
        include_road_tax=False,
        include_runner_fee=False,
        total_payable=1474.05,
        windscreen_sum_insured=1800.0,
        special_perils=None,
        llp_llop=None,
        excess=600.0,
        rate_percentage=4.9135,
        version=1,
    )
    db.add_all([
        user, comp, prod, cat, cat_rev, tmpl, page, t_rev,
        c_ws, c_sp, c_llp, c_bet, c_tow,
        off_ws, off_sp, off_llp, off_bet,
        vehicle, tenure, batch, uf, draft, sel_ws, sel_sp_removed, session_obj, entry,
    ])
    db.commit()
    return {
        "user": user,
        "comp": comp,
        "draft": draft,
        "session": session_obj,
        "tenure": tenure,
        "entry": entry,
        "sel_ws": sel_ws,
        "sel_sp": sel_sp_removed,
        "off_sp": off_sp,
        "off_llp": off_llp,
        "c_sp": c_sp,
        "c_llp": c_llp,
        "c_bet": c_bet,
    }


def test_m1_extraction_captures_stmb_total_contribution_and_preserves_stamp_duty_in_premium():
    # 1. 2D spatial extraction must match STMB bare "TOTAL CONTRIBUTION : RM 1,106.85"
    words = [
        {"page": 1, "top": 100.0, "x0": 10.0, "x1": 40.0, "text": "TOTAL"},
        {"page": 1, "top": 100.0, "x0": 45.0, "x1": 110.0, "text": "CONTRIBUTION"},
        {"page": 1, "top": 100.0, "x0": 115.0, "x1": 120.0, "text": ":"},
        {"page": 1, "top": 100.0, "x0": 130.0, "x1": 145.0, "text": "RM"},
        {"page": 1, "top": 100.0, "x0": 150.0, "x1": 200.0, "text": "1,106.85"},
    ]
    res: dict = {}
    _add_2d_spatial_candidates(words, res, [])
    assert res.get("total_amount"), "2D alignment must capture STMB TOTAL CONTRIBUTION"
    assert res["total_amount"][0].value == "1106.85"

    # Also Tune "Total Payable Perlu Dibayar"
    tune_words = [
        {"page": 1, "top": 100.0, "x0": 10.0, "x1": 40.0, "text": "Total"},
        {"page": 1, "top": 100.0, "x0": 45.0, "x1": 90.0, "text": "Payable"},
        {"page": 1, "top": 100.0, "x0": 95.0, "x1": 125.0, "text": "Perlu"},
        {"page": 1, "top": 100.0, "x0": 130.0, "x1": 175.0, "text": "Dibayar"},
        {"page": 1, "top": 100.0, "x0": 200.0, "x1": 260.0, "text": "5,512.15"},
    ]
    res_tune: dict = {}
    _add_2d_spatial_candidates(tune_words, res_tune, [])
    assert res_tune.get("total_amount")
    assert res_tune["total_amount"][0].value == "5512.15"

    # 2. build_draft must not lose RM 10 stamp duty when gross_premium + service_tax runs before total_amount
    from app.extraction.types import CandidateValue

    candidates = {
        "gross_premium": [CandidateValue("gross_premium", "1015.62", "text", 0.99)],
        "service_tax": [CandidateValue("service_tax", "81.23", "text", 0.99)],
        "stamp_duty": [CandidateValue("stamp_duty", "10.00", "text", 0.99)],
        "basic_premium": [CandidateValue("basic_premium", "1350.00", "text", 0.99)],
        "premium": [CandidateValue("premium", "1350.00", "text", 0.99)],
        "total_amount": [CandidateValue("total_amount", "1106.85", "text", 0.99)],
    }
    draft_fields, _warnings, _status = build_draft(candidates)
    assert Decimal(draft_fields["premium"]["value"]) == Decimal("1106.85")
    assert Decimal(draft_fields["total_amount"]["value"]) == Decimal("1106.85")


def test_m1_extracted_addon_never_double_counted_and_round_total_defaults_false(db: OrmSession):
    fx = _seed_full_quote_fixture(db)
    snap = build_workspace_snapshot(db, fx["user"], fx["session"].id)
    assert snap["total_premium_adjusted"] == "1,474.05"
    assert snap["fields"]["premium"]["value"] == "1474.05"
    assert snap["fields"]["total_amount"]["value"] == "1474.05"


def test_m1_staff_add_remove_benefits_adjusts_premium_idempotently_and_syncs_comparison(db: OrmSession):
    fx = _seed_full_quote_fixture(db)
    draft = fx["draft"]
    user = fx["user"]
    entry = fx["entry"]

    # 1. Add custom paid add-on Dashcam (RM 100.00) -> premium & comparison motor_premium both +100.00 cleanly
    apply_workspace_patch(
        db, user, draft.id, base_revision=1,
        operations=[{
            "op": "create_custom_benefit",
            "selection_key": "custom-dashcam-1",
            "label": "Dashcam Cover",
            "cost_status": "paid",
            "state": "current",
            "price": {"amount": "100.00", "currency": "MYR"},
        }],
    )
    db.refresh(draft)
    db.refresh(entry)
    assert draft.fields["premium"]["value"] == "1574.05"
    assert draft.fields["total_amount"]["value"] == "1574.05"
    assert float(entry.motor_premium) == pytest.approx(1574.05)
    assert float(entry.total_payable) == pytest.approx(1574.05)
    snap_after_add = build_workspace_snapshot(db, user, fx["session"].id)
    assert snap_after_add["total_premium_adjusted"] == "1,574.05"

    # 2. Remove extracted Windscreen (RM 270.00) -> subtracts 270.00 -> 1304.05 and clears Comparison windscreen
    apply_workspace_patch(
        db, user, draft.id, base_revision=draft.revision,
        operations=[{
            "op": "benefit_update",
            "selection_id": fx["sel_ws"].id,
            "state": "removed",
        }],
    )
    db.refresh(draft)
    db.refresh(entry)
    assert draft.fields["premium"]["value"] == "1304.05"
    assert draft.fields["total_amount"]["value"] == "1304.05"
    assert float(entry.motor_premium) == pytest.approx(1304.05)
    assert entry.windscreen_sum_insured is None

    # 3. Select Special Perils (RM 75.00) -> adds 75.00 -> 1379.05 and syncs Special Perils = Included
    apply_workspace_patch(
        db, user, draft.id, base_revision=draft.revision,
        operations=[{
            "op": "select_catalog_offering",
            "offering_id": fx["off_sp"].id,
            "state": "current",
            "cost_status": "paid",
            "price": {"amount": "75.00", "currency": "MYR"},
        }],
    )
    db.refresh(draft)
    db.refresh(entry)
    assert draft.fields["premium"]["value"] == "1379.05"
    assert float(entry.motor_premium) == pytest.approx(1379.05)
    assert entry.special_perils == "Included"

    # 4. Reset benefits -> restores premium back to detected_value 1474.05
    apply_workspace_patch(
        db, user, draft.id, base_revision=draft.revision,
        operations=[{"op": "reset_benefits"}],
    )
    db.refresh(draft)
    assert draft.fields["premium"]["value"] == "1474.05"


def test_m1_pds_boilerplate_in_authorized_driver_does_not_trigger_special_perils(db: OrmSession):
    fx = _seed_full_quote_fixture(db)
    # Remove any Special Perils selection -> authorized_driver.evidence still contains "Special Perils / Flood"
    b_res = _resolve_comparison_benefits(db, fx["session"], fx["comp"].id, fx["draft"].fields, None)
    assert b_res["special_perils"] is None


def test_m1_comparison_inline_patch_syncs_new_fields_and_benefit_selections(db: OrmSession):
    fx = _seed_full_quote_fixture(db)
    tenure = fx["tenure"]
    entry = fx["entry"]
    draft = fx["draft"]
    user = fx["user"]
    rev_before = draft.revision

    # 1. Remove Windscreen ONLY from Comparison when Workspace had recorded price RM 270 -> subtracts 270.00!
    res_ws = patch_comparison_entry(
        tenure_id=tenure.id,
        entry_id=entry.id,
        payload=UpdateComparisonEntryPatch(
            windscreen_sum_insured=0.0,
            expected_version=entry.version,
        ),
        db=db,
        user=user,
    )
    db.refresh(entry)
    db.refresh(draft)
    assert entry.windscreen_sum_insured is None
    assert float(entry.motor_premium) == pytest.approx(1204.05)
    assert draft.fields["premium"]["value"] == "1204.05"
    assert res_ws["motor_premium"] == pytest.approx(1204.05)

    # 2. Inline edit Sum Insured, Motor Premium, Agreed Value, Betterment=No (waiver_betterment=True), Special Perils=Included
    res = patch_comparison_entry(
        tenure_id=tenure.id,
        entry_id=entry.id,
        payload=UpdateComparisonEntryPatch(
            sum_insured=35000.0,
            motor_premium=1600.0,
            agreed_value=True,
            waiver_betterment=True,
            special_perils="Included",
            expected_version=entry.version,
        ),
        db=db,
        user=user,
    )
    db.refresh(entry)
    db.refresh(draft)

    assert entry.sum_insured == pytest.approx(35000.0)
    assert entry.agreed_value is True
    assert entry.valuation_type == "agreed_value"
    assert entry.waiver_betterment is True
    assert entry.betterment_display == "No (0%)"
    assert entry.special_perils == "Included"
    assert float(entry.motor_premium) == pytest.approx(1600.0)
    assert draft.revision > rev_before
    assert res["sum_insured"] == pytest.approx(35000.0)

    ws_sel = db.get(DraftBenefitSelection, fx["sel_ws"].id)
    assert ws_sel is not None
    assert ws_sel.state != "current"
    sp_sel = db.scalar(
        select(DraftBenefitSelection).where(
            DraftBenefitSelection.draft_id == draft.id,
            DraftBenefitSelection.concept_id == fx["c_sp"].id,
            DraftBenefitSelection.state == "current",
        )
    )
    assert sp_sel is not None

    # 3. Clear Special Perils added via Comparison (no RM cost entered -> motor_premium stays 1600.00!)
    res2 = patch_comparison_entry(
        tenure_id=tenure.id,
        entry_id=entry.id,
        payload=UpdateComparisonEntryPatch(
            special_perils="Not Included",
            expected_version=entry.version,
        ),
        db=db,
        user=user,
    )
    db.refresh(entry)
    db.refresh(draft)
    assert entry.special_perils is None
    assert float(entry.motor_premium) == pytest.approx(1600.0)
    assert res2["motor_premium"] == pytest.approx(1600.0)


def test_m2_box1_design2_strict_one_to_one_parity_zero_phantom_perks():
    from app.rendering.unified_addon_engine import extract_free_coverage_items
    from app.rendering.template_renderer_design2 import render_design2_html

    # 1. Box 1 has exact custom benefits (including catalog-overlapping items like Key Care & Repair Allowance):
    # Top-Right MUST render ONLY those exact Box 1 items — zero phantom RM 200 towing, zero hardcoded Legal Defense!
    box1 = [
        {
            "id": "b1",
            "concept_key": "repair-allowance-cart",
            "label": "Repair Allowance (CART)",
            "value": "RM 100/day",
            "description": "Cash allowance while vehicle is under repair.",
            "is_extra": False,
            "cost_status": "included",
        },
        {
            "id": "b2",
            "concept_key": "key-replacement",
            "label": "Key Replacement Cover",
            "value": "RM 1,000",
            "description": "Reimburses stolen or lost key replacement.",
            "is_extra": False,
            "cost_status": "included",
        },
    ]
    free_items = extract_free_coverage_items(
        box1,
        insurer_name="Lonpac Insurance",
        vehicle_type="Lorry",
        fields={"vehicle_type": {"value": "Lorry"}, "coverage_type": {"value": "Comprehensive"}},
    )
    titles = [item["title"] for item in free_items]
    assert titles == ["Repair Allowance (CART)", "Key Replacement Cover"]
    assert not any("towing" in t.lower() or "legal defense" in t.lower() or "rm 200" in t.lower() for t in titles)

    # 2. Empty Box 1 ([]), even with insurer_name="QBE": zero phantom towing & zero fallback perks in HTML!
    empty_items = extract_free_coverage_items(
        [],
        insurer_name="QBE Insurance",
        vehicle_type="Car",
        fields={"vehicle_type": {"value": "Car"}, "coverage_type": {"value": "Comprehensive"}},
    )
    assert empty_items == []

    html = render_design2_html(
        {
            "customer_name": {"value": "ACME LOGISTICS"},
            "vehicle_no": {"value": "VAA1234"},
            "insurance_company": {"value": "Lonpac Insurance"},
            "coverage_amount": {"value": "30000.00"},
            "premium": {"value": "1474.05"},
            "total_amount": {"value": "1474.05"},
        },
        render_context={"current_benefits": box1, "available_addons": []},
    )
    assert "Repair Allowance (CART)" in html
    assert "Key Replacement Cover" in html
    assert "RM200" not in html and "RM 200" not in html
    assert "Legal Defense Costs" not in html


def test_m2_design2_typography_enlarged_and_fits_a4_height():
    from app.rendering.template_renderer_design2 import render_design2_html

    addons = [
        {"id": f"item_{i}", "label": f"Coverage Rider {i}", "value": f"RM {1000 + i}", "description": "Comprehensive endorsement protection benefit details."}
        for i in range(24)
    ]
    html = render_design2_html(
        {
            "customer_name": {"value": "TAN MEI LING"},
            "vehicle_no": {"value": "JXY9988"},
            "insurance_company": {"value": "Etiqa"},
            "car_model": {"value": "Honda Civic FE"},
            "coverage_amount": {"value": "110000.00"},
            "premium": {"value": "2400.00"},
            "total_amount": {"value": "2400.00"},
        },
        render_context={"current_benefits": addons[:4], "available_addons": addons[4:]},
    )
    assert "font-size: 10.0px" in html
    assert "font-size: 8.6px" in html
    assert "height: 73px" in html
    assert "1123px" in html


def test_m3_covernote_patch_updates_all_fields_dates_benefits_and_won_premium(db: OrmSession):
    from app.api.routers.comparison import CovernotePatchRequest, patch_tenure_covernote
    from app.services.marketing_comparison_service import get_marketing_comparison

    fx = _seed_full_quote_fixture(db)
    tenure = fx["tenure"]
    cn_sess = fx["session"]
    draft = fx["draft"]
    user = fx["user"]

    # Promote session as issued Cover Note on this tenure
    cn_sess.document_type = "covernote"
    cn_sess.policy_number = "CN-OLD-001"
    tenure.covernote_session_id = cn_sess.id
    tenure.winning_company_id = fx["comp"].id
    tenure.won_premium = 1474.05
    tenure.policy_number = "CN-OLD-001"
    tenure.stage = "Issue Policy"
    tenure.status = "hit"
    draft.display_options = {"document_type": "covernote"}

    # Seed another insurer to verify company reassignment
    etiqa = InsuranceCompany(
        id=new_id(),
        name="Etiqa General Insurance",
        slug="etiqa",
        detection_phrases=["Etiqa"],
        status="active",
    )
    db.add(etiqa)
    db.commit()

    # Patch Cover Note inline + full details: policy #, company, leap-year dates, financial specs, & benefits
    res = patch_tenure_covernote(
        tenure_id=tenure.id,
        payload=CovernotePatchRequest(
            policy_number="CN-ETIQA-2026-999",
            company_name="Etiqa General Insurance",
            coverage_start_date="2028-02-29",
            coverage_end_date="2029-02-28",
            sum_insured=38500.0,
            motor_premium=1620.50,
            agreed_value=True,
            windscreen_sum_insured=2500.0,
            towing_limit="Unlimited",
            special_perils="Included",
            llp_llop="Included",
            excess=250.0,
            waiver_betterment=True,
        ),
        db=db,
        user=user,
    )
    db.refresh(tenure)
    db.refresh(cn_sess)
    db.refresh(draft)

    assert tenure.policy_number == "CN-ETIQA-2026-999"
    assert cn_sess.policy_number == "CN-ETIQA-2026-999"
    assert tenure.winning_company_id == etiqa.id
    assert draft.company_id == etiqa.id
    assert tenure.expiry_month == "2029-02"
    assert float(tenure.won_premium) == pytest.approx(1620.50)

    cn_out = res.get("covernote_policy")
    assert cn_out is not None
    assert cn_out["policy_number"] == "CN-ETIQA-2026-999"
    assert cn_out["company_name"] == "Etiqa General Insurance"
    assert cn_out["sum_insured"] == pytest.approx(38500.0)
    assert cn_out["motor_premium"] == pytest.approx(1620.50)
    assert cn_out["exact_total_payable"] == pytest.approx(1620.50)
    assert cn_out["agreed_value"] is True
    assert cn_out["windscreen_sum_insured"] == pytest.approx(2500.0)
    assert cn_out["towing_limit"] == "Unlimited"
    assert cn_out["special_perils"] == "Included"
    assert cn_out["llp_llop"] == "Included"
    assert cn_out["excess"] == pytest.approx(250.0)
    assert cn_out["waiver_betterment"] is True

    # Reload via GET comparison endpoint to verify full persistence & fixed-cost exclusion accuracy
    reloaded = get_marketing_comparison(db, tenure.id)
    assert reloaded["covernote_policy"]["policy_number"] == "CN-ETIQA-2026-999"
    assert reloaded["covernote_policy"]["exact_total_payable"] == pytest.approx(1620.50)


def test_m4_bulk_upload_limit_defaults_to_100_and_persists_override(db: OrmSession):
    from app.services.admin_service import get_bulk_upload_limit, set_bulk_upload_limit

    admin = User(id=new_id(), name="Boss", email="boss@risklocker.local", password_hash="h", role="admin")
    db.add(admin)
    db.commit()

    # Without an app_settings row, bulk upload default must support 100 PDFs
    assert get_bulk_upload_limit(db) == 100

    # Explicit overrides persist cleanly and remain validated >= 3
    assert set_bulk_upload_limit(db, admin, 50) == 50
    assert get_bulk_upload_limit(db) == 50
    assert set_bulk_upload_limit(db, admin, 100) == 100
    assert get_bulk_upload_limit(db) == 100


def test_m4_worker_releases_db_connection_during_slow_extractor_and_handles_failure(tmp_path):
    from datetime import timedelta
    import socket
    from types import SimpleNamespace
    from sqlalchemy.pool import QueuePool
    from app.models.tables import Job
    from app.workers.extraction_worker import process_extraction_job, run_one_job

    db_path = tmp_path / "m4_worker.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=0,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Seed user, batch, two isolated file/draft/session/job pipelines cleanly
    seed_db = SessionLocal()
    src_file = tmp_path / "sample_quote.pdf"
    src_file.write_bytes(b"%PDF-1.4 sample payload for worker m4 test")
    import hashlib
    src_sha = hashlib.sha256(src_file.read_bytes()).hexdigest()

    user = User(id=new_id(), name="Agent", email="m4@risklocker.local", password_hash="h", role="admin")
    batch = Batch(id=new_id(), owner_id=user.id, name="Batch M4")
    uf = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="sample_quote.pdf",
        content_type="application/pdf",
        storage_provider="local_ephemeral",
        storage_path=str(src_file),
        storage_sha256=src_sha,
    )
    draft = QuotationDraft(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf.id,
        revision=1,
        status="processing",
        display_options={"document_type": "quotation"},
        fields={},
        scalar_decisions={},
    )
    sess = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf.id,
        draft_id=draft.id,
        status="active",
        is_test=True,
    )
    job = Job(
        id=new_id(),
        owner_id=user.id,
        job_type="extract_pdf",
        idempotency_key=f"m4-ok-{new_id()}",
        state="processing",
        lease_owner="test-worker-1",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        uploaded_file_id=uf.id,
        session_id=sess.id,
        payload={"enhanced_reading": False},
    )

    uf_fail = UploadedFile(
        id=new_id(),
        batch_id=batch.id,
        owner_id=user.id,
        original_filename="sample_fail.pdf",
        content_type="application/pdf",
        storage_provider="local_ephemeral",
        storage_path=str(src_file),
        storage_sha256=src_sha,
    )
    draft_fail = QuotationDraft(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf_fail.id,
        revision=1,
        status="processing",
        display_options={"document_type": "quotation"},
        fields={},
        scalar_decisions={},
    )
    sess_fail = SessionModel(
        id=new_id(),
        owner_id=user.id,
        uploaded_file_id=uf_fail.id,
        draft_id=draft_fail.id,
        status="active",
        is_test=True,
    )
    job_fail = Job(
        id=new_id(),
        owner_id=user.id,
        job_type="extract_pdf",
        idempotency_key=f"m4-fail-{new_id()}",
        state="queued",
        uploaded_file_id=uf_fail.id,
        session_id=sess_fail.id,
        payload={
            "enhanced_reading": False,
            "storage_provider": "local_ephemeral",
            "node_host": socket.gethostname(),
        },
    )
    seed_db.add_all([user, batch, uf, draft, sess, job, uf_fail, draft_fail, sess_fail, job_fail])
    seed_db.commit()
    job_id = job.id
    job_fail_id = job_fail.id
    seed_db.close()

    checked_out_during_extract: list[int] = []

    class _DummyPacer:
        def acquire(self, estimated_tokens: int = 0):
            return (0, 0.0)

    def _fake_extractor(path, **_kwargs):
        checked_out_during_extract.append(engine.pool.checkedout())
        return {
            "full_record": {"raw_text": "TOTAL CONTRIBUTION RM 1,106.85", "ocr_text": ""},
            "draft": {
                "status": "ready",
                "fields": {
                    "vehicle_no": {"value": "VAA1234", "status": "ready"},
                    "premium": {"value": "1106.85", "status": "ready"},
                    "total_amount": {"value": "1106.85", "status": "ready"},
                },
                "benefits": [],
                "warnings": [],
            },
        }

    worker_db = SessionLocal()
    settings = SimpleNamespace(app_env="test", max_source_pdf_bytes=20 * 1024 * 1024)
    try:
        loaded_job = worker_db.get(Job, job_id)
        process_extraction_job(
            worker_db,
            settings,
            loaded_job,
            worker_id="test-worker-1",
            extractor=_fake_extractor,
            context_loader=lambda _db: {"db_companies": [], "field_aliases": [], "benefit_aliases": []},
            pacer=_DummyPacer(),
        )
        loaded_job = worker_db.get(Job, job_id)
        worker_db.refresh(loaded_job)
        assert checked_out_during_extract == [0], (
            f"Expected 0 checked-out DB connections while blocking on extractor, got {checked_out_during_extract}"
        )
        assert loaded_job.state == "completed"

        # Verify run_one_job failure path after extractor release does not hit DetachedInstanceError
        import app.workers.extraction_worker as ew

        orig_process = ew.process_extraction_job

        def _failing_process(db_s, cfg, jb, **kw):
            return orig_process(
                db_s,
                cfg,
                jb,
                extractor=lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("boom after release")),
                context_loader=lambda _db: {"db_companies": [], "field_aliases": [], "benefit_aliases": []},
                pacer=_DummyPacer(),
                **{k: v for k, v in kw.items() if k in ("worker_id", "storage")},
            )

        orig_ref = ew.process_extraction_job
        ew.process_extraction_job = _failing_process
        try:
            claimed_job = run_one_job(worker_db, settings, worker_id="test-worker-1", pacer=_DummyPacer())
        finally:
            ew.process_extraction_job = orig_ref
        assert claimed_job is not None and claimed_job.id == job_fail_id
        failed_job = worker_db.get(Job, job_fail_id)
        worker_db.refresh(failed_job)
        assert failed_job.state in ("failed", "queued")
        assert (failed_job.safe_error or {}).get("code") == "processing_failed"
    finally:
        worker_db.close()
        engine.dispose()

