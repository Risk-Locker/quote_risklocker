"""Static frontend contract for fixed-page immutable template publication."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "frontend/src/app/builder/templates/[id]/builder/page.tsx"
TEMPLATE_LIST = ROOT / "frontend/src/app/builder/templates/page.tsx"
REVIEW = ROOT / "frontend/src/components/session-workspace/review-phase.tsx"
PROVIDER = ROOT / "frontend/src/components/session-workspace/provider.tsx"
CANVAS = ROOT / "frontend/src/components/template-canvas/shared.tsx"


def test_builder_publishes_an_immutable_revision_and_edits_dynamic_grids():
    source = BUILDER.read_text(encoding="utf-8")
    assert "/business/templates/${id}/publish" in source
    assert "base_revision" in source
    assert 'type: "benefit-grid"' in source
    assert '"current_benefits"' in source
    assert '"available_addons"' in source
    assert "page_profile" in source
    assert "Scenario count" in source
    for count in ("0", "1", "6", "12", "15", "20"):
        assert f'value="{count}"' in source
    for stress_count in ("100", "1000"):
        assert f'<option value="{stress_count}">{stress_count}</option>' not in source
    assert "/admin/our-specials" not in source
    assert "buildSpecialElement" not in source


def test_canvas_has_a_local_non_persisted_dynamic_grid_scenario():
    source = CANVAS.read_text(encoding="utf-8")
    assert "scenarioCount" in source
    assert "Dynamic benefit grid" in source
    assert "gridKind" in source


def test_check_values_uses_published_revision_options_and_confirmed_impact():
    source = REVIEW.read_text(encoding="utf-8")
    provider = PROVIDER.read_text(encoding="utf-8")
    assert "/business/templates/published" in source
    assert "/template-selection-impact" in source
    assert 'op: "template_selection"' in source
    assert 'operation.op === "template_selection"' in provider
    assert "confirmed: true" in source


def test_new_templates_are_insurer_independent():
    source = TEMPLATE_LIST.read_text(encoding="utf-8")
    create_body = source[source.index("async function createTemplate"):source.index("async function cloneTemplate")]
    assert "insurance_company_id" not in create_body
    assert "newCompanyId" not in source


def test_builder_gestures_capture_pointer_commit_pre_gesture_history_and_clamp_bounds():
    source = BUILDER.read_text(encoding="utf-8")
    pointer_move = source[source.index("function pointerMove"):source.index("function canvasPointerDown")]
    pointer_up = source[source.index("function pointerUp"):source.index("async function copyLocked")]
    assert "setPointerCapture(event.pointerId)" in source
    assert "historySnapshot" in source
    assert "drag.historySnapshot" in pointer_up
    assert "drag?.changed" in pointer_up
    assert "setFuture([])" in pointer_up
    assert "onPointerCancel" in source
    assert "onLostPointerCapture" in source
    assert "clone(current)" not in pointer_move
    assert "canvasW - bounds.w" in pointer_move
    assert "canvasH - bounds.h" in pointer_move
