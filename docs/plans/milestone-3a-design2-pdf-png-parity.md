# Milestone 3a: Design 2 PDF/PNG Parity, Logos, Footer & Inline PDF Viewer

**Status:** Verified & Complete (`v30.4`)

## Delivered Scope
1. **Pure Pillow Image Padding Trim & Horizontal Asset Parity (`benefit_schedule_renderer.py`):**
   - Replaced `import numpy as np` in `_trim_image_padding_data_uri()` with fast C-level `PIL.ImageChops` alpha/white bounding-box trimming so Docker (`requirements.txt` without `numpy`) crops padded square assets cleanly without shrinking the header wordmark.
   - Prioritized horizontal curated assets (`frontend/public/assets/brand/logo-horizontal-black.png` `2021x449` and `frontend/public/assets/companies/*`) ahead of 1:1 legacy icons so PDF and live canvas/PNG match identically.
2. **Official Footer Branding Restored (`benefit_schedule_renderer.py`, `template_renderer_design2.py`, `design2-canvas.tsx`):**
   - Restored default Design 2 footer agency identity to `RISKLOCKER SDN. BHD.` and `202301041962(1535879-U)` across live canvas, PDF Sheet 1, and continuation schedule pages.
3. **Backend Single-Source Total Parity (`generation_service.py`, `template_renderer_design2.py`, `useReviewWorkspaceState.ts`):**
   - Bumped `RENDERER_VERSION = "risklocker-v7.2"`, prioritized `total_premium_adjusted` unless user explicitly overrode `total_amount` (`decision == "edit"`), and zeroed disabled road tax / runner fee values identically on both live canvas `previewFields` and frozen PDF snapshots (`VRS7732` `RM 140,534.00` parity).
4. **Inline PDF New-Tab Viewer (`useQuotationExports.ts`):**
   - Replaced HTML `/previews/{id}/html` popup with synchronous popup placeholder + `ensureGeneratedPdfVersionId` polling `job.result.version_id` -> `GET /versions/{id}/pdf?download=false` (`application/pdf`, `Content-Disposition: inline`).

## Empirical Verification
- `tests/unit/test_design2_pdf_png_parity.py` (4/4 passing, including `numpy`-blocked crop tests & SQLite snapshot context parity)
- `.\.venv\Scripts\pytest.exe tests/ -q`: `1,171 passed, 3 skipped` (`tests/security/test_postgres_schema_contracts.py`)
- `cd frontend; npm run build`: exit 0 (`47/47` pages + ESLint)
- Playwright Chromium PDF render `.qc-tmp/shots/verify_vrs7732_m3a.pdf` (visual check: full horizontal RL & AmAssurance banners, `RM 140,534.00`, `RISKLOCKER SDN. BHD.` / `202301041962(1535879-U)` footer)
