"""Static frontend regression contract for the persistent v7 session workspace."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "frontend/src/components/session-workspace/review-phase.tsx"
PREVIEW = ROOT / "frontend/src/components/session-workspace/preview-phase.tsx"
LAYOUT = ROOT / "frontend/src/app/sessions/[id]/layout.tsx"
PROVIDER = ROOT / "frontend/src/components/session-workspace/provider.tsx"


def test_workspace_provider_is_mounted_once_above_review_and_preview():
    layout = LAYOUT.read_text(encoding="utf-8")
    provider = PROVIDER.read_text(encoding="utf-8")
    assert "SessionWorkspaceProvider" in layout
    assert "dirtyPaths" in provider
    assert "operationsRef" in provider
    assert "base_revision" in provider
    assert "beforeunload" in provider
    assert "saveQueueRef" in provider


def test_workspace_save_keeps_operations_added_while_request_is_in_flight():
    provider = PROVIDER.read_text(encoding="utf-8")
    assert "operationVersionsRef" in provider
    assert "sentVersions" in provider
    assert "if (operationVersionsRef.current.get(path) === version)" in provider
    assert "applyPendingOperations" in provider


def test_review_is_one_mouse_pass_with_inline_values_and_benefit_boxes():
    source = REVIEW.read_text(encoding="utf-8")
    for label in ("Extracted values", "Next: Preview", "Included", "Add-ons", "Add paid", "Add FOC", "Hide PDF"):
        assert label in source
    assert "useWorkspaceData" in source
    assert "useWorkspaceActions" in source
    assert "decideField" in source
    assert "uploaded-files" in source
    assert 'op: "select_catalog_offering"' in source
    assert 'op: "create_custom_benefit"' in source
    assert 'op: "pin_catalog"' in source
    assert "/business/dictionaries/learn" in source
    assert "/generate" not in source
    assert "Generate PDF" not in source
    assert "score" not in source
    assert "source_method" not in source
    assert "findMatchingTemplate" not in source
    assert "available_templates" not in source
    assert "Keep Check Needed" not in source


def test_preview_is_staff_safe_session_override_only_and_generation_is_explicit():
    source = PREVIEW.read_text(encoding="utf-8")
    assert "useWorkspaceData" in source
    assert "Generate PDF" in source
    assert "Download latest PDF" in source
    assert "Save as template" not in source
    assert "/admin/" not in source
    assert "Our Specials" not in source
    assert "addSpecial" not in source
    assert "addElement" not in source
    assert '"Idempotency-Key"' in source
    assert "/jobs/${jobId}" in source
    assert "/preview-render" in source
    assert "Final rendered preview" in source
