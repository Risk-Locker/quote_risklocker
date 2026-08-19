"""Static frontend contract for the Extraction & Aliases section (replan step 3)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTION_NAV = ROOT / "frontend/src/components/extraction-nav.tsx"
SETTINGS_NAV = ROOT / "frontend/src/components/settings-nav.tsx"
APP_SHELL = ROOT / "frontend/src/components/app-shell.tsx"
BENEFIT_ALIASES = ROOT / "frontend/src/app/extraction/benefit-aliases/page.tsx"
MOVED = [
    ROOT / "frontend/src/app/extraction/company-detection/page.tsx",
    ROOT / "frontend/src/app/extraction/field-aliases/page.tsx",
    ROOT / "frontend/src/app/extraction/road-tax/page.tsx",
    ROOT / "frontend/src/app/extraction/vehicles/page.tsx",
]


def test_extraction_nav_lists_all_five_sections():
    source = EXTRACTION_NAV.read_text(encoding="utf-8")
    for route in (
        "/extraction/company-detection",
        "/extraction/field-aliases",
        "/extraction/benefit-aliases",
        "/extraction/vehicles",
        "/extraction/road-tax",
    ):
        assert route in source


def test_settings_nav_keeps_only_users_checks_storage():
    source = SETTINGS_NAV.read_text(encoding="utf-8")
    for route in ("/settings/users", "/settings/system-checks", "/settings/storage"):
        assert route in source
    assert "extraction" not in source


def test_app_shell_has_extraction_and_aliases_entry():
    source = APP_SHELL.read_text(encoding="utf-8")
    assert "/extraction/company-detection" in source
    assert "Extraction & Aliases" in source


def test_moved_pages_use_the_extraction_nav():
    for page in MOVED:
        source = page.read_text(encoding="utf-8")
        assert page.exists()
        assert "ExtractionNav" in source
        assert "SettingsNav" not in source


def test_old_settings_extraction_paths_redirect():
    for old in (
        ROOT / "frontend/src/app/settings/extraction/companies/page.tsx",
        ROOT / "frontend/src/app/settings/extraction/field-aliases/page.tsx",
        ROOT / "frontend/src/app/settings/extraction/road-tax/page.tsx",
        ROOT / "frontend/src/app/settings/extraction/vehicles/page.tsx",
    ):
        source = old.read_text(encoding="utf-8")
        assert "redirect(" in source


def test_benefit_aliases_page_manages_scoped_aliases():
    source = BENEFIT_ALIASES.read_text(encoding="utf-8")
    assert "/business/benefit-aliases?benefit_id=" in source
    assert "/business/benefit-aliases" in source
    for scope in ("global", "company", "product", "package"):
        assert scope in source
    assert "/business/companies?page=1&page_size=100" in source
    assert "/business/companies/${companyId}/workspace" in source
    assert "package_kind" in source
    for hardcoded in ("AmAssurance", "QBE", "Etiqa", "Windscreen"):
        assert hardcoded not in source, f"{hardcoded} must not be hardcoded in the aliases page"
    # One occurrence is allowed for a user-facing placeholder example.
    assert source.count("Towing") <= 1
