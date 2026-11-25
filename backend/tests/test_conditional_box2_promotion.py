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
    o_bet = _make_offering("o-bet", "c-bet", "bet-opt", "base", "included", "Up to 15 Years", "", 40)

    sel_llop = _make_selection("s-llop", "c-llop", "o-llop", "current", "paid", display_text="RM 7.50", price={"amount": 7.50, "currency": "MYR"})
    sel_pc365 = _make_selection("s-pc365", "c-pc365", "o-pc365", "current", "paid", display_text="RM 130.00", price={"amount": 130.00, "currency": "MYR"})
    sel_ws = _make_selection("s-ws", "c-ws", "o-ws", "current", "paid", display_text="RM 15,000.00", price={"amount": 2250.00, "currency": "MYR"})
    sel_bet = _make_selection("s-bet", "c-bet", "o-bet", "current", "included", display_text="Up to 15 Years")

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
    assert by_key["betterment-protection"]["value"] == "Up to 15 Years"

    matrix = build_unified_matrix_cards(resolved["current_benefits"], resolved["available_addons"], fill_to_slots=8, insurer_name="AmAssurance")
    m_by_id = {c["id"]: c for c in matrix}
    assert m_by_id["llop"]["value"] == ""
    assert m_by_id["private_car_365"]["value"] == ""
    assert "15,000" in m_by_id["windscreen"]["value"]
    assert m_by_id["betterment"]["value"] == "Up to 15 Years"


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

