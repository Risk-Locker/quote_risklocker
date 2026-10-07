"""Static frontend contract for fixed-page immutable template publication."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "frontend/src/app/builder/templates/[id]/builder/page.tsx"
TEMPLATE_LIST = ROOT / "frontend/src/app/builder/templates/quotation-templates/page.tsx"
REVIEW = ROOT / "frontend/src/components/session-workspace/review-phase.tsx"
PROVIDER = ROOT / "frontend/src/components/session-workspace/provider.tsx"
CANVAS = ROOT / "frontend/src/components/template-canvas/shared.tsx"


def test_builder_publishes_an_immutable_revision_and_edits_dynamic_grids():
    source = BUILDER.read_text(encoding="utf-8")
    assert "/publish" in source
    assert "base_revision" in source
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
    # RL-DISABLED legacy pixel dragging replaced by 4-Column Box Model Container Studio — disabled 2026-10-06; restore if pixel dragging returns
    pass
