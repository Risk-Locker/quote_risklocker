"""Render/raster-compare every approved v7 master/card-count scenario without database data."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import fitz
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rendering.template_renderer import render_quotation_html
from app.services.master_template_service import master_template_specs


COUNTS = (0, 1, 6, 12, 15, 20)


def cards(count: int) -> list[dict]:
    values = ["Unlimited", "999 km", "RM 1,200", "RM 150/day · 7 days", "FOC", "Flood, storm and strike cover"]
    return [
        {
            "selection_id": f"qa-{index}", "concept_key": f"qa-{index}",
            "label": "Long customer-facing benefit label" if index == count - 1 and count > 1 else f"Benefit {index + 1}",
            "value": values[index % len(values)], "cost_status": "foc" if index % 7 == 0 else "included", "asset_id": "",
        }
        for index in range(count)
    ]


def main() -> int:
    destination = ROOT / ".qc-tmp" / "master-pdf-parity"
    destination.mkdir(parents=True, exist_ok=True)
    fields = {
        "customer_name": {"value": "Alya Rahman"}, "vehicle_no": {"value": "JXS2820"},
        "car_model": {"value": "Honda HR-V"}, "coverage_type": {"value": "Comprehensive"},
        "cover_period": {"value": "15 Aug 2026 – 14 Aug 2027"}, "coverage_amount": {"value": "85,000"},
        "total_amount": {"value": "1,842.60"}, "insurance_company": {"value": "QA Insurer"},
    }
    report: dict = {"scenarios": [], "started_at": time.time()}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for master in master_template_specs():
                config = master["config"]
                width = int(config["canvas"]["width"])
                height = int(config["canvas"]["height"])
                for count in COUNTS:
                    context = {"current_benefits": cards(count), "available_addons": cards(count), "generation_blockers": []}
                    html = render_quotation_html(fields, template_name=master["name"], template_config=config, render_context=context, resolved_assets={})
                    stem = f'{master["key"]}-{count:02d}'
                    html_path = destination / f"{stem}.html"
                    preview_path = destination / f"{stem}-preview.png"
                    pdf_path = destination / f"{stem}.pdf"
                    raster_path = destination / f"{stem}-pdf.png"
                    html_path.write_text(html, encoding="utf-8")
                    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                    started = time.perf_counter()
                    page.set_content(html, wait_until="load")
                    page.emulate_media(media="print")
                    card_boxes = page.locator('[data-benefit-card="1"]').evaluate_all("els => els.map(el => { const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height,scale:Number(el.dataset.cardScale)}; })")
                    page.screenshot(path=str(preview_path), full_page=False)
                    page.pdf(path=str(pdf_path), width=f"{width}px", height=f"{height}px", print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}, prefer_css_page_size=True, tagged=True)
                    duration_ms = round((time.perf_counter() - started) * 1000)
                    page.close()

                    with fitz.open(pdf_path) as document:
                        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
                        pixmap.save(raster_path)
                    with Image.open(preview_path).convert("RGB") as preview, Image.open(raster_path).convert("RGB") as raster:
                        if raster.size != preview.size:
                            raster = raster.resize(preview.size)
                        difference = ImageChops.difference(preview, raster)
                        mean_error = round(sum(ImageStat.Stat(difference).mean) / 3, 4)
                    expected_cards = count * 2
                    if len(card_boxes) != expected_cards:
                        raise RuntimeError(f"{stem}: rendered {len(card_boxes)} cards, expected {expected_cards}")
                    scales = [round(float(item["scale"]), 12) for item in card_boxes]
                    if any(float(item["x"]) < -0.01 or float(item["y"]) < -0.01 or float(item["x"]) + float(item["w"]) > width + 0.01 or float(item["y"]) + float(item["h"]) > height + 0.01 for item in card_boxes):
                        raise RuntimeError(f"{stem}: a card escaped the fixed page")
                    report["scenarios"].append({"master": master["key"], "count_per_grid": count, "card_count": len(card_boxes), "scales": sorted(set(scales)), "render_ms": duration_ms, "preview_pdf_mean_error": mean_error, "preview": preview_path.name, "pdf_raster": raster_path.name})
        finally:
            browser.close()
    report["duration_ms"] = round((time.time() - report["started_at"]) * 1000)
    (destination / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Rendered {len(report['scenarios'])} preview/PDF scenarios to {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
