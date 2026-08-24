"""Static frontend contract for the Global Benefits admin library (refactor Task 4 & R2-2 simplification)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "frontend/src/app/builder/global-benefits/page.tsx"
NAV = ROOT / "frontend/src/components/builder-nav.tsx"


def test_global_benefits_page_uses_the_real_apis():
    source = PAGE.read_text(encoding="utf-8")
    assert "/business/benefit-concepts?page=1&page_size=100" in source
    assert "/business/benefit-concepts" in source
    assert "/business/assets?kind=benefit_art&page=1&page_size=100" in source
    assert "method: \"POST\"" in source
    assert "base_revision" in source
    assert "api<" in source
    assert "from \"@/lib/api\"" in source


def test_global_benefits_page_exposes_the_simplified_library_fields():
    source = PAGE.read_text(encoding="utf-8")
    for field in ("concept_key", "default_asset_id", "sort_order", "label"):
        assert field in source
    assert "Benefit Image" in source or "default_asset" in source
    assert "Benefit Title" in source or "Benefit name" in source
    assert "Short Description" in source or "description" in source


def test_global_benefits_page_does_not_expose_redundant_variants_ui():
    source = PAGE.read_text(encoding="utf-8")
    # R2-2: Variants UI, per-day picker, and manual type dropdowns removed to keep UI simple.
    assert "Description variants" not in source
    assert "Value-pattern dataset" not in source
    assert "per_day" not in source and "Per-day" not in source


def test_global_benefits_are_never_hardcoded():
    source = PAGE.read_text(encoding="utf-8")
    # The library is DB-driven: no real benefit names baked into the page.
    for hardcoded in ("Special Perils", "Key Replacement", "Roadside Assistance", "Flood Assistance"):
        occurrences = source.count(hardcoded)
        assert occurrences <= 1, f"{hardcoded} appears {occurrences} times in the page"
    assert source.count("Towing") <= 4
    assert "benefits.map" in source or "filtered.map" in source


def test_global_benefits_route_is_in_builder_navigation():
    nav = NAV.read_text(encoding="utf-8")
    assert "/builder/global-benefits" in nav
    assert "Global Benefits" in nav
