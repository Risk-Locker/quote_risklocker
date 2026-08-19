"""Static frontend contract for the Benefits workspace flow-only page (refactor Task 5 & R2-1)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "frontend/src/app/builder/benefits/page.tsx"


def test_workspace_navigates_the_database_driven_hierarchy():
    source = PAGE.read_text(encoding="utf-8")
    for endpoint in (
        "/business/segments?page=1&page_size=100",
        "/business/vehicle-categories?page=1&page_size=100",
        "/business/companies?page=1&page_size=100",
    ):
        assert endpoint in source


def test_workspace_path_flow_and_segment_tooltip():
    source = PAGE.read_text(encoding="utf-8")
    assert "Insurance companies" in source
    assert "Segment" in source and "Vehicle type" in source and "Product" in source
    # Segment explains Private vs Company / Commercial and defaults to Private.
    assert "Private" in source
    assert "Company / Commercial" in source
    assert 'item.key === "private"' in source
    # Coverage is implied Comprehensive for this phase.
    assert "Comprehensive" in source
    assert "coverage-types" not in source


def test_workspace_has_single_mode_and_package_mode():
    source = PAGE.read_text(encoding="utf-8")
    assert "Single mode" in source
    assert "Package mode" in source
    assert "package_kind: \"comprehensive\"" in source
    assert "package_kind: \"addon_bundle\"" in source
    # Products without named packages never get a fake "base" package.
    assert '"Single"' in source
    assert 'config.package ? config.package.name : "Single"' in source


def test_workspace_manages_packages_bundles_clone_and_revisions():
    source = PAGE.read_text(encoding="utf-8")
    assert "/packages/${sourcePackage.id}/clone" in source
    assert "Clone package" in source
    assert "New bundle" in source
    assert "/publish" in source and "/new-draft" in source
    assert "Revisions" in source
    # Revisions is its own tab; aliases live under Extraction & Aliases now.
    assert "aliases" not in source.lower().replace("aliases", "", 0) or "Aliases" not in source


def test_workspace_is_interactive_flow_without_list_toggle():
    source = PAGE.read_text(encoding="utf-8")
    # R2-1: Delete the list view and view toggle; the Benefits page IS the flow.
    assert "viewMode" not in source
    assert "List view" not in source


def test_workspace_never_uses_catalog_language_or_hardcodes_business_data():
    source = PAGE.read_text(encoding="utf-8")
    # API paths and type names may mention catalogs; user-facing copy must not.
    for label in ("No catalog", "New catalog", "catalog workspace", "catalogs for", "Catalog selected", "This catalog", "Select a catalog"):
        assert label not in source, f"User-facing copy must not say '{label}'"
    assert 'title="Add configuration"' in source or "Add configuration" in source
    for hardcoded in ("AmAssurance", "QBE", "Etiqa"):
        assert hardcoded not in source, f"{hardcoded} must not be hardcoded in the workspace"
    # Assignments are typed and role-driven.
    for role in ("\"included\"", "\"addon_option\"", "\"bundle_component\""):
        assert role in source


def test_workspace_uses_the_shared_api_client_only():
    source = PAGE.read_text(encoding="utf-8")
    assert "from \"@/lib/api\"" in source
    assert "fetch(" not in source
