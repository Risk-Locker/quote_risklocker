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
    assert 'width="16" height="16" viewBox="0 0 20 20"' in html
    assert "font-size: 11.0px; font-weight: 700;" in html
    assert "font-size: 10.2px; font-weight: 700;" in html
    assert "font-size: 9.5px; font-weight: 400;" in html
