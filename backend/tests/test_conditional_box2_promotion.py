"""Tests for database-driven conditional Box 1 -> Box 2 promotion and Design 2 rendering."""

from types import SimpleNamespace

from app.rendering.render_context import resolve_benefit_cards
from app.rendering.template_renderer_design2 import render_design2_html
from app.rendering.unified_addon_engine import (
    build_unified_matrix_cards,
    extract_free_coverage_items,
    format_addon_value,
)
from app.services.workspace_patch_service import _reset_conditional_targets_for_trigger


def _make_concept(cid: str, key: str, label: str, desc: str = ""):
    return SimpleNamespace(
        id=cid,
        concept_key=key,
        label=label,
        description=desc,
        status="active",
        default_asset_id=None,
        display_overrides={},
    )


def _make_offering(oid: str, cid: str, key: str, kind: str, role: str, display_value: str = "", desc: str = "", sort_order: int = 10):
    return SimpleNamespace(
        id=oid,
        concept_id=cid,
        offering_key=key,
        offering_kind=kind,
        role=role,
        label_override=None,
        description_override=desc,
        display_value=display_value,
        typed_value={"type": "custom", "display_text": display_value} if display_value else None,
        optional_price=None,
        presentation_facet_ids=[],
        status="active",
        sort_order=sort_order,
    )


def _make_selection(sid: str, cid: str, oid: str, state: str, cost_status: str = "included", display_text: str | None = None, price=None):
    return SimpleNamespace(
        id=sid,
        concept_id=cid,
        catalog_offering_id=oid,
        selection_key=f"sel:{sid}",
        item_kind="catalog",
        state=state,
        cost_status=cost_status,
        price=price,
        label_override=None,
        description_override=None,
        coverage_limit=display_text,
        typed_value_override={"type": "custom", "display_text": display_text} if display_text is not None else None,
        evidence_snapshot={},
        package_plan_id=None,
        sort_order=10,
    )


def _make_condition(
    cond_id: str,
    trig_cid: str,
    target_cid: str,
    *,
    plan_filter: str | None,
    title: str,
    value: str,
    desc: str,
    action_type: str = "promote_to_addon",
):
    return SimpleNamespace(
        id=cond_id,
        trigger_concept_id=trig_cid,
        trigger_plan_filter=plan_filter,
        target_concept_id=target_cid,
        action_type=action_type,
        replacement_title=title,
        replacement_value=value,
        replacement_description=desc,
        is_active=True,
    )


def _stmb_fixtures(motor_pa_state: str, motor_pa_plan: str | None):
    c_towing = _make_concept("c-towing", "towing", "Towing", "Standard towing")
    c_pa = _make_concept("c-pa", "motor-pa-plus", "Motor PA Plus", "Driver & passenger PA")
    o_towing = _make_offering("o-towing", "c-towing", "stmb-towing", "base", "included", "50 km", "24/7 towing up to 50 km.", 10)
    o_pa = _make_offering("o-pa", "c-pa", "stmb-motor-pa", "optional", "addon_option", "1-4", "Motor PA Plus Plans 1-4.", 20)

    sel_towing = _make_selection("s-towing", "c-towing", "o-towing", "current", "included")
    sel_pa = _make_selection(
        "s-pa",
        "c-pa",
        "o-pa",
        motor_pa_state,
        "paid" if motor_pa_state == "current" else "optional",
        display_text=motor_pa_plan,
        price={"amount": "65.00", "currency": "MYR"} if motor_pa_state == "current" else None,
    )

    conditions = [
        _make_condition("cond-1", "c-pa", "c-towing", plan_filter="Plan 1", title="Towing", value="100 km", desc="24/7 towing up to 100 km."),
        _make_condition("cond-2", "c-pa", "c-towing", plan_filter="Plan 2", title="Towing", value="200 km", desc="24/7 towing up to 200 km."),
        _make_condition("cond-3", "c-pa", "c-towing", plan_filter="Plan 3", title="Towing", value="300 km", desc="24/7 towing up to 300 km."),
        _make_condition("cond-4", "c-pa", "c-towing", plan_filter="Plan 4", title="Unlimited Towing", value="", desc="24/7 unlimited towing."),
    ]
    return resolve_benefit_cards(
        selections=[sel_towing, sel_pa],
        offerings=[o_towing, o_pa],
        concepts=[c_towing, c_pa],
        relations=[],
        facets=[],
        company_conditions=conditions,
    )


def test_unselected_trigger_keeps_towing_in_box1_and_hides_from_box2():
    res = _stmb_fixtures("available_addon", None)
    free_items = extract_free_coverage_items(res["current_benefits"], insurer_name="STMB")
    matrix = build_unified_matrix_cards(res["current_benefits"], res["available_addons"], fill_to_slots=8, insurer_name="STMB")

    assert any("50 km" in fi["title"] for fi in free_items)
    assert not any(c["id"] == "towing" for c in matrix)
    pa_card = next(c for c in matrix if c["concept_key"] == "motor-pa-plus")
    assert pa_card["is_selected"] is False
    assert pa_card["value"] == "1-4"


def test_unpicked_range_1_to_4_does_not_false_match_plan_1():
    res = _stmb_fixtures("current", "1-4")
    free_items = extract_free_coverage_items(res["current_benefits"], insurer_name="STMB")
    assert any("50 km" in fi["title"] for fi in free_items)


def test_promoted_plans_1_through_4_hide_box1_and_populate_box2():
    for plan_input, expected_title, expected_val in [
        ("1", "Towing", "100 km"),
        ("Plan 2", "Towing", "200 km"),
        ("3", "Towing", "300 km"),
        ("Plan 4", "Unlimited Towing", ""),
    ]:
        res = _stmb_fixtures("current", plan_input)
        free_items = extract_free_coverage_items(res["current_benefits"], insurer_name="STMB")
        matrix = build_unified_matrix_cards(res["current_benefits"], res["available_addons"], fill_to_slots=8, insurer_name="STMB")

        assert not any("towing" in fi["title"].lower() for fi in free_items), f"Box 1 should hide Towing for {plan_input}"
        towing_card = next(c for c in matrix if c["id"] == "towing")
        assert towing_card["is_selected"] is True
        assert towing_card["title"] == expected_title
        assert towing_card["value"] == expected_val


def test_format_addon_value_preserves_plan_numbers_and_qualified_unlimited():
    assert format_addon_value("1") == "1"
    assert format_addon_value("4") == "4"
    assert format_addon_value("1-4") == "1-4"
    assert format_addon_value("Unlimited - Plan 1") == "Unlimited - Plan 1"
    assert format_addon_value("Unlimited - Driver Plan 1") == "Unlimited - Driver Plan 1"
    assert format_addon_value("1000") == "RM 1,000.00"


def test_reset_conditional_targets_clears_temp_overrides():
    sel_towing = _make_selection("s-towing", "c-towing", "o-towing", "removed", "included", display_text="Custom Edit")
    sel_towing.label_override = "Edited Towing"
    cond = _make_condition("cond-1", "c-pa", "c-towing", plan_filter="Plan 1", title="Towing", value="100 km", desc="100 km")

    class _FakeScalarResult:
        def all(self):
            return [cond]

    class _FakeDb:
        def scalars(self, _stmt):
            return _FakeScalarResult()

    draft = SimpleNamespace(id="d1", company_id="comp1")
    # Patch _draft_selections_with_pending via monkeypatch-free inline swap
    import app.services.workspace_patch_service as wps

    orig_fn = wps._draft_selections_with_pending
    wps._draft_selections_with_pending = lambda _db, _did: [sel_towing]
    try:
        _reset_conditional_targets_for_trigger(_FakeDb(), draft, "c-pa")
    finally:
        wps._draft_selections_with_pending = orig_fn

    assert sel_towing.label_override is None
    assert sel_towing.typed_value_override is None
    assert sel_towing.state == "current"


def test_design2_renders_option_a_tick_and_larger_box2_fonts():
    res = _stmb_fixtures("current", "1")
    html = render_design2_html(
        draft_fields={"insurance_company": "TAKAFUL MALAYSIA", "vehicle_type": "Car"},
        template_config={},
        render_context={"current_benefits": res["current_benefits"], "available_addons": res["available_addons"], "fill_to_slots": 8},
    )
    assert 'width="20" height="20" viewBox="0 0 22 22"' in html
    assert "skewX(-6deg)" in html
    assert "font-size: 11.8px; font-weight: 700;" in html
    assert "font-size: 11.0px; font-weight: 700;" in html
    assert "font-size: 10.0px; font-weight: 500;" in html


def test_render_context_and_unified_engine_suppress_cost_leaked_as_coverage():
    """Legacy selections with premium leaked into typed_value_override must suppress fake Coverage while keeping Windscreen/Towing/Betterment."""
    c_llop = _make_concept("c-llop", "legal-liability-of-passengers", "Legal Liability of Passengers")
    c_pc365 = _make_concept("c-pc365", "private-car-365", "Private Car 365 - Plan 2")
    c_ws = _make_concept("c-ws", "windscreen", "Windscreen Coverage")
    c_bet = _make_concept("c-bet", "betterment-protection", "Waiver of Betterment")

    o_llop = _make_offering("o-llop", "c-llop", "llop-opt", "optional", "addon_option", "", "", 10)
    o_llop.optional_price = {"amount": 15.0, "currency": "MYR"}  # Different from selection.price to test reversed-check regression!
    o_pc365 = _make_offering("o-pc365", "c-pc365", "pc365-opt", "optional", "addon_option", "", "", 20)
    o_ws = _make_offering("o-ws", "c-ws", "ws-opt", "optional", "addon_option", "", "", 30)
    o_bet = _make_offering("o-bet", "c-bet", "bet-opt", "optional", "addon_option", "Up to 10 Years", "", 40)

    sel_llop = _make_selection("s-llop", "c-llop", "o-llop", "current", "paid", display_text="RM 7.50", price={"amount": 7.50, "currency": "MYR"})
    sel_pc365 = _make_selection("s-pc365", "c-pc365", "o-pc365", "current", "paid", display_text="RM 130.00", price={"amount": 130.00, "currency": "MYR"})
    sel_ws = _make_selection("s-ws", "c-ws", "o-ws", "current", "paid", display_text="RM 15,000.00", price={"amount": 2250.00, "currency": "MYR"})
    sel_bet = _make_selection("s-bet", "c-bet", "o-bet", "current", "paid", display_text="Up to 10 Years", price={"amount": 100.00, "currency": "MYR"})

    resolved = resolve_benefit_cards(
        selections=[sel_llop, sel_pc365, sel_ws, sel_bet],
        offerings=[o_llop, o_pc365, o_ws, o_bet],
        concepts=[c_llop, c_pc365, c_ws, c_bet],
        relations=[],
        facets=[],
    )
    by_key = {c["concept_key"]: c for c in resolved["current_benefits"]}
    assert by_key["legal-liability-of-passengers"]["value"] == ""
    assert by_key["private-car-365"]["value"] == ""
    assert "15,000" in by_key["windscreen"]["value"]
    assert by_key["betterment-protection"]["value"] == "Up to 10 Years"

    matrix = build_unified_matrix_cards(resolved["current_benefits"], resolved["available_addons"], fill_to_slots=8, insurer_name="AmAssurance")
    m_by_id = {c["id"]: c for c in matrix}
    assert m_by_id["llop"]["value"] == ""
    assert m_by_id["private_car_365"]["value"] == ""
    assert "15,000" in m_by_id["windscreen"]["value"]
    assert m_by_id["betterment"]["value"] == "Up to 10 Years"


def test_comparison_syncs_updated_company_name_without_duplicates():
    """Updating a session's detected_company from Kurnia -> Liberty must update the entry in place without creating 2 columns."""
    from datetime import datetime, timezone
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.models.tables import Base, Batch, InsuranceCompany, InsuranceTenure, QuotationDraft, Session as QuotationSession, TenureComparisonEntry, TrackedVehicle, UploadedFile, new_id
    from app.services.marketing_comparison_service import get_marketing_comparison

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    u_id, b_id, kur_id, lib_id, tv_id, t_id = new_id(), new_id(), new_id(), new_id(), new_id(), new_id()
    uf1_id, d1_id, s1_id, e1_id = new_id(), new_id(), new_id(), new_id()
    uf2_id, d2_id, s2_id = new_id(), new_id(), new_id()
    with Session(engine) as db:
        batch = Batch(id=b_id, owner_id=u_id, name="Test Batch", status="ready")
        comp_kur = InsuranceCompany(id=kur_id, name="Kurnia", slug="kurnia", status="active")
        comp_lib = InsuranceCompany(id=lib_id, name="Liberty", slug="liberty", status="active")
        tv = TrackedVehicle(id=tv_id, vehicle_no="V1234")
        tenure = InsuranceTenure(
            id=t_id,
            tracked_vehicle_id=tv_id,
            vehicle_no="V1234",
            customer_name="TEST CLIENT",
            coverage_start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            coverage_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            expiry_month="2026-12",
            road_tax=90.0,
            runner_fee=20.0,
        )
        uf1 = UploadedFile(
            id=uf1_id, batch_id=b_id, owner_id=u_id, original_filename="liberty_quote.pdf", content_type="application/pdf",
            storage_path="p1", storage_provider="local", storage_status="available", storage_sha256="sha1", size_bytes=100, status="ready",
        )
        d1 = QuotationDraft(
            id=d1_id, revision=1, uploaded_file_id=uf1_id, owner_id=u_id, status="ready",
            company_id=lib_id,
            fields={"coverage_amount": {"value": "100000.00"}, "premium": {"value": "1500.00"}},
            scalar_decisions={}, warnings=[],
        )
        s1 = QuotationSession(
            id=s1_id, owner_id=u_id, uploaded_file_id=uf1_id, draft_id=d1_id, quotation_ref="RL2600001",
            status="active", tenure_id=t_id, is_tenure_active=True, detected_company="Liberty",
        )
        # Stale comparison entry created earlier as Kurnia before re-detect fixed s1 to Liberty
        stale_entry = TenureComparisonEntry(
            id=e1_id, tenure_id=t_id, session_id=s1_id, company_name="Kurnia", company_id=kur_id,
            sum_insured=100000.0, motor_premium=1500.0, road_tax=90.0, runner_fee=20.0, total_payable=1610.0,
            manual_overrides=[],
        )
        # In-flight preparing session must NOT create a premature column
        uf2 = UploadedFile(
            id=uf2_id, batch_id=b_id, owner_id=u_id, original_filename="pending_upload.pdf", content_type="application/pdf",
            storage_path="p2", storage_provider="local", storage_status="available", storage_sha256="sha2", size_bytes=100, status="preparing",
        )
        d2 = QuotationDraft(
            id=d2_id, revision=1, uploaded_file_id=uf2_id, owner_id=u_id, status="preparing",
            fields={}, scalar_decisions={}, warnings=[],
        )
        s2 = QuotationSession(
            id=s2_id, owner_id=u_id, uploaded_file_id=uf2_id, draft_id=d2_id, quotation_ref="RL2600002",
            status="active", tenure_id=t_id, is_tenure_active=True, detected_company=None,
        )
        db.add_all([batch, comp_kur, comp_lib, tv, tenure, uf1, d1, s1, stale_entry, uf2, d2, s2])
        db.commit()

        result = get_marketing_comparison(db, t_id, allow_commit=True)
        entries = list(db.scalars(select(TenureComparisonEntry).where(TenureComparisonEntry.tenure_id == t_id)).all())
        assert len(entries) == 1
        assert entries[0].company_name == "Liberty"
        assert entries[0].company_id == lib_id
        assert len(result["entries"]) == 1
        assert result["entries"][0]["company_name"] == "Liberty"


def test_betterment_10yr_cap_qbe_and_other_insurers():
    """Verify QBE vs non-QBE 10-year betterment caps, motorcycle/TPFT exclusion, and >10yr manual override preservation."""
    from types import SimpleNamespace
    from app.domain.betterment_engine import evaluate_betterment_catalog_eligibility
    from app.services.marketing_comparison.ncd_evaluator import evaluate_betterment_rules

    qbe = SimpleNamespace(slug="qbe", name="QBE", policy_rules={
        "betterment": {"auto_waive_without_peril": True, "allow_addon_purchase": False, "free_exemption_years": 10, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 10 Years"}
    })
    allianz = SimpleNamespace(slug="allianz", name="Allianz", policy_rules={
        "betterment": {"auto_waive_without_peril": False, "allow_addon_purchase": True, "free_exemption_years": 5, "max_waiver_years": 10, "default_display": "Up to 10 Years", "free_display": "Up to 5 Years"}
    })

    # QBE: free Box 1 up to age 10, never Box 2, hidden at age 11+
    assert evaluate_betterment_catalog_eligibility(0, company_obj=qbe, coverage_type="Comprehensive")["placement"] == "box1_free"
    qbe_10 = evaluate_betterment_catalog_eligibility(10, company_obj=qbe, coverage_type="Comprehensive")
    assert qbe_10["placement"] == "box1_free" and qbe_10["display_value"] == "Up to 10 Years"
    assert evaluate_betterment_catalog_eligibility(11, company_obj=qbe, coverage_type="Comprehensive")["placement"] == "hidden"

    # Non-QBE: 0-4 => box1_free ("Up to 5 Years"); 5-10 => box2_optional ("Up to 10 Years"); 11+ => hidden
    b4 = evaluate_betterment_catalog_eligibility(4, company_obj=allianz, coverage_type="Comprehensive")
    assert b4["placement"] == "box1_free" and b4["display_value"] == "Up to 5 Years"
    b5 = evaluate_betterment_catalog_eligibility(5, company_obj=allianz, coverage_type="Comprehensive")
    assert b5["placement"] == "box2_optional" and b5["display_value"] == "Up to 10 Years"
    b10 = evaluate_betterment_catalog_eligibility(10, company_obj=allianz, coverage_type="Comprehensive")
    assert b10["placement"] == "box2_optional" and b10["display_value"] == "Up to 10 Years"
    assert evaluate_betterment_catalog_eligibility(11, company_obj=allianz, coverage_type="Comprehensive")["placement"] == "hidden"

    # Box 1 included betterment must NOT be duplicated into Box 2 via fill_to_slots
    c_bet_box1 = _make_concept("c-bet-box1", "betterment-protection", "Waiver of Betterment")
    o_bet_box1 = _make_offering("o-bet-b1", "c-bet-box1", "bet-b1", "base", "included", "Up to 5 Years", "", 10)
    sel_bet_box1 = _make_selection("s-bet-b1", "c-bet-box1", "o-bet-b1", "current", "included", display_text="Up to 5 Years")
    res_box1 = resolve_benefit_cards(
        selections=[sel_bet_box1],
        offerings=[o_bet_box1],
        concepts=[c_bet_box1],
        relations=[],
        facets=[],
        betterment_policy_context=b4,
    )
    box2_matrix = build_unified_matrix_cards(res_box1["current_benefits"], [], fill_to_slots=8, insurer_name="Allianz")
    assert all(c["id"] != "betterment" for c in box2_matrix)

    # Excluded from motorcycle/commercial & TPFT/TPO
    assert evaluate_betterment_catalog_eligibility(3, company_obj=allianz, coverage_type="Comprehensive", is_commercial_or_moto=True)["placement"] == "hidden"
    assert evaluate_betterment_catalog_eligibility(3, company_obj=allianz, coverage_type="TPFT")["placement"] == "hidden"

    # Comparison evaluator cutoff: QBE age 10 (yom 2016 @ 2026) Yes(0%), age 11 No(40%); Allianz age 10 w/o waiver No(40%), w/ waiver Yes(0%), age 11 w/o manual No(40%)
    assert evaluate_betterment_rules(2016, 2026, "QBE", False, company_obj=qbe)[2] == "Yes (0%)"
    assert evaluate_betterment_rules(2015, 2026, "QBE", False, company_obj=qbe)[2] == "No (40%)"
    assert evaluate_betterment_rules(2016, 2026, "Allianz", False, company_obj=allianz)[2] == "No (40%)"
    assert evaluate_betterment_rules(2016, 2026, "Allianz", True, company_obj=allianz)[2] == "Yes (0%)"
    assert evaluate_betterment_rules(2015, 2026, "Allianz", False, company_obj=allianz)[2] == "No (40%)"

    # >10yo car hides default Box1/Box2 betterment in render_context, unless staff manually selects/overrides it
    c_bet = _make_concept("c-bet", "betterment-protection", "Waiver of Betterment")
    o_bet_inc = _make_offering("o-bet-1", "c-bet", "bet-inc", "base", "included", "Up to 10 Years", "", 10)
    ctx_hidden = {"placement": "hidden", "veh_age": 14, "eligible": False}

    res_auto = resolve_benefit_cards(
        selections=[],
        offerings=[o_bet_inc],
        concepts=[c_bet],
        relations=[],
        facets=[],
        betterment_policy_context=ctx_hidden,
    )
    assert all(c["concept_key"] != "betterment-protection" for c in res_auto["current_benefits"] + res_auto["available_addons"])

    sel_manual = _make_selection("s-bet-m", "c-bet", "o-bet-1", "current", "paid", display_text="Up to 10 Years")
    sel_manual.evidence_snapshot = {"source": "manual", "manually_edited": True}
    res_manual = resolve_benefit_cards(
        selections=[sel_manual],
        offerings=[o_bet_inc],
        concepts=[c_bet],
        relations=[],
        facets=[],
        betterment_policy_context=ctx_hidden,
    )
    assert any(c["concept_key"] == "betterment-protection" for c in res_manual["current_benefits"])


def test_catalog_lifecycle_fixes_and_betterment_policy_rule_endpoint():
    """Verify cascade delete of plan items, formula->expression normalization, clear_value, role exclusion, and partial policy-rules updates."""
    from types import SimpleNamespace
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.models.enums import Role
    from app.models.tables import (
        Base, BenefitCatalog, BenefitCatalogRevision, BenefitConcept,
        BenefitPackage, BenefitPackagePlan, BenefitPackagePlanItem,
        CatalogOffering, InsuranceCompany, InsuranceProduct, new_id,
    )
    from app.services.catalog_lifecycle_service import remove_catalog_offering, save_catalog_offering
    from app.services.company_setup_service import update_company_betterment_rule

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    admin = SimpleNamespace(id=new_id(), role=Role.ADMIN.value)

    with Session(engine) as db:
        comp = InsuranceCompany(id=new_id(), name="Allianz", slug="allianz", status="active", policy_rules={})
        prod = InsuranceProduct(id=new_id(), company_id=comp.id, product_key="motor-comp", name="Motor Comprehensive", status="active")
        concept = BenefitConcept(id=new_id(), concept_key="windscreen", label="Windscreen Cover", sort_order=1, status="active")
        cat = BenefitCatalog(id=new_id(), company_id=comp.id, product_id=prod.id, name="Test Cat", revision=1, status="draft")
        rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="draft", source_document_ids=[], content_hash="")
        pkg = BenefitPackage(id=new_id(), catalog_revision_id=rev.id, package_key="bundle", name="Bundle", package_kind="addon_bundle", status="active")
        plan = BenefitPackagePlan(id=new_id(), package_id=pkg.id, plan_key="plan-1", name="Plan 1", status="active")
        db.add_all([comp, prod, concept, cat, rev, pkg, plan])
        db.commit()

        # Save with formula->expression normalization
        saved = save_catalog_offering(db, admin, cat.id, {
            "base_revision": 1,
            "offering_key": "ws-test",
            "concept_id": concept.id,
            "offering_kind": "optional",
            "applies_to_type": "product",
            "applies_to_id": prod.id,
            "role": "addon_option",
            "display_value": "RM 1,000",
            "typed_value": {"type": "custom", "display_text": "RM 1,000"},
            "optional_price": {"type": "formula", "formula": "15% of Sum Covered", "display_text": "15% of Sum Covered"},
        })
        assert saved["optional_price"]["expression"] == "15% of Sum Covered"

        # 1-role-per-concept mutual exclusion when moving/adding same concept as included
        saved_inc = save_catalog_offering(db, admin, cat.id, {
            "base_revision": 2,
            "offering_key": "ws-test-inc",
            "concept_id": concept.id,
            "offering_kind": "base",
            "applies_to_type": "product",
            "applies_to_id": prod.id,
            "role": "included",
            "display_value": "RM 1,000",
        })
        remaining = list(db.scalars(select(CatalogOffering).where(CatalogOffering.catalog_revision_id == rev.id, CatalogOffering.concept_id == concept.id)).all())
        assert len(remaining) == 1 and remaining[0].id == saved_inc["id"]

        # clear_value clears both display_value & typed_value
        cleared = save_catalog_offering(db, admin, cat.id, {"id": saved_inc["id"], "base_revision": 3, "applies_to_type": "product", "applies_to_id": prod.id, "clear_value": True})
        assert cleared["display_value"] is None and cleared["typed_value"] is None

        # Deleting offering referenced by BenefitPackagePlanItem must not fail FK RESTRICT
        item = BenefitPackagePlanItem(id=new_id(), plan_id=plan.id, offering_id=cleared["id"], sort_order=1)
        db.add(item)
        db.commit()
        remove_catalog_offering(db, admin, cat.id, cleared["id"])
        assert db.get(CatalogOffering, cleared["id"]) is None

        # Partial policy_rules update preserves omitted fields
        res1 = update_company_betterment_rule(db, admin, comp.id, {"free_exemption_years": 6})
        assert res1["betterment_rule"]["free_exemption_years"] == 6
        assert res1["betterment_rule"]["max_waiver_years"] == 10
        assert res1["betterment_rule"]["allow_addon_purchase"] is True


def test_workspace_manual_edit_discrepancy_and_brn_guards():
    """Verify insurer BRN exclusion, punctuation-insensitive name match, and discrepancy dismiss without customer."""
    from types import SimpleNamespace
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.api.routers.sessions import post_resolve_customer_discrepancy
    from app.models.enums import Role
    from app.models.tables import Base, Batch, QuotationDraft, Session as QuotationSession, UploadedFile, new_id
    from app.services.customer_account_service import resolve_or_create_customer
    from app.services.identity_normalization_service import normalize_government_id
    from app.services.workspace_patch_service import _apply_select_catalog_offering
    from app.models.tables import BenefitCatalog, BenefitCatalogRevision, BenefitConcept, CatalogOffering, InsuranceCompany

    assert normalize_government_id("197801007153") == ("", "unknown")
    assert normalize_government_id("44191-P") == ("", "unknown")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    u_id = new_id()
    user = SimpleNamespace(id=u_id, role=Role.ADMIN.value)

    with Session(engine) as db:
        c1, disc1 = resolve_or_create_customer(db, "CSH BAKERY & CONFECTIONERY SDN BHD", "202001001234")
        c2, disc2 = resolve_or_create_customer(db, "CSH BAKERY CONFECTIONERY SDN. BHD.", "202001001234")
        assert c1 is not None and c2 is not None and c1.id == c2.id
        assert disc2 == []

        batch = Batch(id=new_id(), owner_id=u_id, name="B", status="ready")
        uf = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=u_id, original_filename="q.pdf", content_type="application/pdf", storage_path="p", storage_provider="local", storage_status="available", storage_sha256="s", size_bytes=1, status="ready")
        draft = QuotationDraft(id=new_id(), revision=1, uploaded_file_id=uf.id, owner_id=u_id, status="ready", fields={}, scalar_decisions={}, warnings=[], display_options={"customer_discrepancies": [{"field": "name", "current": "A", "detected": "B", "message": "diff"}]})
        sess = QuotationSession(id=new_id(), owner_id=u_id, uploaded_file_id=uf.id, draft_id=draft.id, quotation_ref="RL1", status="active")
        comp = InsuranceCompany(id=new_id(), name="Allianz", slug="allianz", status="active")
        concept = BenefitConcept(id=new_id(), concept_key="windscreen", label="Windscreen", sort_order=1, status="active")
        cat = BenefitCatalog(id=new_id(), company_id=comp.id, name="C", revision=1, status="draft")
        rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", source_document_ids=[], content_hash="")
        off = CatalogOffering(id=new_id(), catalog_revision_id=rev.id, offering_key="ws", concept_id=concept.id, offering_kind="optional", role="addon_option", status="active")
        db.add_all([batch, uf, draft, sess, comp, concept, cat, rev, off])
        db.commit()

        # Dismiss without session.customer succeeds and persists
        res = post_resolve_customer_discrepancy(sess.id, {"action": "dismiss", "field": "name"}, db=db, user=user)
        assert res["resolved"] is True and res["discrepancies_remaining"] == 0
        assert db.get(QuotationDraft, draft.id).display_options["customer_discrepancies"] == []

        # _apply_select_catalog_offering with overrides & description clear
        draft.catalog_revision_id = rev.id
        path = _apply_select_catalog_offering(db, draft, user, {
            "op": "select_catalog_offering",
            "offering_id": off.id,
            "state": "available_addon",
            "label": "Custom WS",
            "description": "Initial desc",
        })
        assert path.startswith("benefits.")
        _apply_select_catalog_offering(db, draft, user, {
            "op": "select_catalog_offering",
            "offering_id": off.id,
            "state": "available_addon",
            "description": "",
        })
        db.commit()


def test_tiered_bundle_display_title_and_description_switch_and_promote_unlimited_towing():
    """Verify universal per-tier display_title/display_description persistence, tier switching, and Box 1 -> Box 2 towing promotion."""
    from types import SimpleNamespace
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models.enums import Role
    from app.models.tables import (
        Base,
        Batch,
        BenefitCatalog,
        BenefitCatalogRevision,
        BenefitConcept,
        BenefitProfile,
        CatalogOffering,
        CompanyBenefitBundle,
        DraftBenefitSelection,
        InsuranceCompany,
        QuotationDraft,
        UploadedFile,
        new_id,
    )
    from app.services.company_benefit_bundle_service import load_active_company_bundles, save_company_bundle
    from app.services.workspace_patch_service import _apply_bundle_tier_fields

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    u_id = new_id()
    user = SimpleNamespace(id=u_id, role=Role.ADMIN.value)

    with Session(engine) as db:
        prof = BenefitProfile(id=new_id(), name="Active Profile", is_active=True, status="active")
        comp = InsuranceCompany(id=new_id(), name="Etiqa", slug="etiqa", status="active")
        c_tow = BenefitConcept(id=new_id(), concept_key="towing", label="Emergency Towing Assistance", sort_order=10, status="active")
        c_dpp = BenefitConcept(id=new_id(), concept_key="driver-passenger-protector", label="Driver Passenger Protector", sort_order=20, status="active")
        cat = BenefitCatalog(id=new_id(), company_id=comp.id, name="Comprehensive Private Car Insurance / Takaful", revision=1, status="published")
        rev = BenefitCatalogRevision(id=new_id(), catalog_id=cat.id, revision_number=1, state="published", source_document_ids=[], content_hash="")
        o_tow = CatalogOffering(id=new_id(), catalog_revision_id=rev.id, offering_key="towing", concept_id=c_tow.id, offering_kind="base", role="included", display_value="200 km", description_override="200 km towing.", sort_order=10, status="active")
        o_dpp = CatalogOffering(id=new_id(), catalog_revision_id=rev.id, offering_key="driver-passenger-protector", concept_id=c_dpp.id, offering_kind="optional", role="addon_option", sort_order=20, status="active")
        batch = Batch(id=new_id(), owner_id=u_id, name="B", status="ready")
        uf = UploadedFile(id=new_id(), batch_id=batch.id, owner_id=u_id, original_filename="etiqa.pdf", content_type="application/pdf", storage_path="p", storage_provider="local", storage_status="available", storage_sha256="s", size_bytes=1, status="ready")
        draft = QuotationDraft(id=new_id(), revision=1, uploaded_file_id=uf.id, owner_id=u_id, company_id=comp.id, catalog_revision_id=rev.id, status="ready", fields={}, scalar_decisions={}, warnings=[])
        db.add_all([prof, comp, c_tow, c_dpp, cat, rev, o_tow, o_dpp, batch, uf, draft])
        db.commit()

        saved = save_company_bundle(
            db,
            user,
            comp.id,
            {
                "bundle_key": "etiqa-driver-passenger-protection",
                "name": "Driver Passenger Protection",
                "primary_concept_id": c_dpp.id,
                "trigger_concept_ids": [c_dpp.id],
                "match_aliases": ["driver passenger protection", "dpp"],
                "force_box2": True,
                "has_plan_tiers": True,
                "is_active": True,
                "tiers": [
                    {
                        "tier_key": "plan_1",
                        "label": "Plan 1",
                        "display_title": "Driver Passenger Protection Plan 1\n意外保险-计划1",
                        "display_description": "Death and Disability - RM 15,000 / Passenger\n死亡/永久性残疾-RM 15,000/每位乘客",
                        "match_tokens": ["plan 1", "p1"],
                        "is_default_fallback": True,
                        "effects": [
                            {
                                "target_concept_id": c_tow.id,
                                "effect_type": "upgrade_to_box2",
                                "display_title": "Unlimited Towing Assistance",
                                "display_value": "",
                                "display_description": "24/7 emergency unlimited towing assistance.",
                                "icon_hint": "unlimited_towing",
                                "comparison_value": "Unlimited",
                            }
                        ],
                    },
                    {
                        "tier_key": "plan_2",
                        "label": "Plan 2",
                        "display_title": "Driver Passenger Protection Plan 2\n意外保险-计划2",
                        "display_description": "Death and Disability - RM 30,000 / Passenger\n死亡/永久性残疾-RM 30,000/每位乘客",
                        "match_tokens": ["plan 2", "p2"],
                        "is_default_fallback": False,
                        "effects": [
                            {
                                "target_concept_id": c_tow.id,
                                "effect_type": "upgrade_to_box2",
                                "display_title": "Unlimited Towing Assistance",
                                "display_value": "",
                                "display_description": "24/7 emergency unlimited towing assistance.",
                                "icon_hint": "unlimited_towing",
                                "comparison_value": "Unlimited",
                            }
                        ],
                    },
                ],
            },
            profile_id=prof.id,
        )
        assert len(saved["tiers"]) == 2
        assert saved["tiers"][0]["display_title"] == "Driver Passenger Protection Plan 1\n意外保险-计划1"
        assert saved["tiers"][1]["display_description"] == "Death and Disability - RM 30,000 / Passenger\n死亡/永久性残疾-RM 30,000/每位乘客"

        bundles = load_active_company_bundles(db, comp.id, profile_id=prof.id)
        sel_tow = DraftBenefitSelection(
            id=new_id(), draft_id=draft.id, selection_key="catalog:towing", catalog_offering_id=o_tow.id,
            concept_id=c_tow.id, item_kind="catalog", state="current", cost_status="included", sort_order=10,
        )
        sel_dpp = DraftBenefitSelection(
            id=new_id(), draft_id=draft.id, selection_key="catalog:dpp", catalog_offering_id=o_dpp.id,
            concept_id=c_dpp.id, item_kind="catalog", state="current", cost_status="paid",
            label_override="Driver Passenger Protection (Plan 1)",
            evidence_snapshot={"source": "comparison_sync"},
            bundle_tier_id=saved["tiers"][0]["id"], sort_order=20,
        )
        db.add_all([sel_tow, sel_dpp])
        db.commit()

        # Switch to Plan 2 via workspace_patch_service -> stale comparison_sync label_override must clear
        changed = _apply_bundle_tier_fields(
            db, draft, sel_dpp, {"op": "benefit_update", "selection_id": sel_dpp.id, "bundle_tier_id": saved["tiers"][1]["id"]}, offering=o_dpp,
        )
        assert changed is True
        assert sel_dpp.label_override is None

        resolved = resolve_benefit_cards(
            selections=[sel_tow, sel_dpp],
            offerings=[o_tow, o_dpp],
            concepts=[c_tow, c_dpp],
            relations=[],
            facets=[],
            company_bundles=bundles,
            catalog_name=cat.name,
        )
        free_items = extract_free_coverage_items(resolved["current_benefits"], insurer_name="Etiqa")
        matrix = build_unified_matrix_cards(resolved["current_benefits"], resolved["available_addons"], insurer_name="Etiqa")

        assert not any("towing" in fi["title"].lower() for fi in free_items)
        towing_card = next(c for c in matrix if c["id"] == "towing")
        dpp_card = next(c for c in matrix if c["concept_key"] == "driver-passenger-protector")
        assert towing_card["is_selected"] is True and towing_card["title"] == "Unlimited Towing Assistance"
        assert dpp_card["is_selected"] is True
        assert dpp_card["title"] == "Driver Passenger Protection Plan 2\n意外保险-计划2"
        assert "RM 30,000" in dpp_card["description"]

        html = render_design2_html(
            draft_fields={"insurance_company": "ETIQA GENERAL INSURANCE BERHAD", "vehicle_type": "Car"},
            template_config={},
            render_context={"current_benefits": resolved["current_benefits"], "available_addons": resolved["available_addons"]},
        )
        assert "Driver Passenger Protection Plan 2\n意外保险-计划2" in html
        assert "white-space: pre-line;" in html



