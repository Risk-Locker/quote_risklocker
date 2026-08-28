# Business Rules

## Non-Negotiable Constraints

- Use Supabase/Postgres only for application data; SQLite and local persistent data fallbacks are prohibited.
- Persist source and generated PDFs only in private Supabase Storage. Do not persist PDFs in the repository or application-server directories.
- Never expose service-role keys, backend credentials, storage keys, or provider URLs to the browser.
- Never silently guess an uncertain extracted value. Mark it `Check Needed` for review.
- Generate final PDFs deterministically from reviewed draft data and saved template configuration. Do not use AI-generated layout for final PDFs.
- Do not hardcode fees, roadtax, premium, commission, totals, or other business formulas.
- Preserve Upload -> Check Values -> Generate PDF.
- Accept exactly one PDF for every new upload. Legacy batches remain readable but cannot be created or bulk-generated.
- Companies, brands, products, catalogs, benefits, add-ons, packages, aliases, upgrades, and extraction rules are database data; no insurer count or catalog choice may be hardcoded.
- `coverage_type` is informational and never forces benefits.

## Review and Extraction

- Native PDF extraction uses text and layout data; enhanced reading is optional staff-facing OCR behavior.
- Store full extraction detail separately from the editable draft. Staff sees concise fields, source text, and friendly hints rather than parser internals.
- Clear values can be populated automatically. Missing, conflicting, or ambiguous required values stay `Check Needed`.
- Extracted Final Price (`total_amount`) is the source quotation's Total Payable / Total Contribution (which already includes base premium, taxes, stamp duty, and quotation optional covers). Insurance Premium (`premium`) is the net base insurance premium (`Final Price - Extracted Extras`). When add-ons or extras are added/removed, only the Final Price reactively updates while Insurance Premium remains stable. Road tax is automatically calculated from engine CC and vehicle type (Malaysian JPJ rates) when absent from the quotation PDF, and is included in the Total Payable. Runner fees are populated when explicitly configured or entered by staff.
- Benefit grid cards render a strict 4-tier hierarchy: (1) Title, (2) Coverage amount, (3) Short description, (4) Price or costing (`Cost : MYR XX.XX`). Pure default benefits omit the costing badge, while add-ons always display costing. The extras and coverage table sections dynamically expand their heights to prevent any clipping of extras, road tax, or totals.
- Quotation and source benefit lines are suggestions until reviewed. Narrative, PDS, illustrative, not-included, and unmapped lines never become selected benefits automatically.
- Staff-facing copy uses `Review / Edit`, `Please check this value.`, `Enhanced reading`, `PDF Expired`, and the statuses `Ready`, `Check Needed`, `Cannot Read`, and `Generated`.
- Never show OCR, parser, regex, confidence, coordinates, storage keys, provider URLs, or technical stack traces to Staff.

## Catalog Benefit Semantics

- A benefit concept is the stable facility (for example towing or windscreen); `base`, `upgrade`, and `optional` describe how a pinned company/product/tier offers that concept.
- Every new quotation starts from the pinned published catalog's base package even when the insurer PDF does not repeat every included facility.
- An explicit reviewed quotation value overrides the catalog value exactly. Arbitrary typed values such as `999 km`, `1,200 km`, and true `Unlimited` remain exact and are never rounded to a catalog variant.
- A selected upgrade replaces the current value for the same concept. A selected optional new facility adds that concept. Neither path may create duplicate current-benefit cards.
- Removing or customizing a benefit changes only that quotation. The published catalog remains unchanged.
- A company/product/tier with no base offering for a concept does not receive that current benefit. An optional offer appears only in Available Add-ons when a verified catalog defines it.
- Missing or unverified catalog information remains empty. Artwork and filenames never establish coverage by themselves.

## Benefit Packs (Bundled Add-on Plans)

- A benefit pack is an `addon_bundle` package with plan levels (A/B/C/D); each higher plan is an upgrade of the previous one. Packs are add-ons only and are never auto-added on catalog pin.
- Staff may add any plan level directly (no forced ladder climb). Adding a higher/lower plan of the same pack replaces the previous level in place — it never creates a duplicate grid of cards.
- A plan member upgrades an untouched catalog default in place (e.g. Towing 50 km -> 200 km -> Unlimited); the upgraded card moves inside the pack's group border. A staff- or AI-customized value is preserved and only adopted into the group.
- One current selection per concept is enforced; a benefit already present cannot be added again.
- In the final template, pack members render as normal grid cards wrapped in a red border with a corner badge showing the plan name. The grid never paginates or clips.
- Removing a pack removes its members and restores the superseded defaults.
- Packs carry no price of their own. Pricing comes from the quotation PDF; per-plan description changes are carried via the member's typed-value `display_text`.
- AI extraction detects purchased packs from cost-summary lines (e.g. "DPA pack A -> 288.05 RM") with tolerant description matching; confident detections auto-apply with a detection marker, uncertain ones stay `Check Needed`.
- Staff-added custom add-ons may carry a price (optional RM). Priced extras appear in an Extras block above the Coverage Premium in the bilingual master template and are added to the Total Premium. PDF-embedded add-ons stay inside the coverage premium and are not listed as extras.

## Templates and Versions

- Templates are insurer-independent fixed-page revisions. A4 is the default; longer pages are separate explicit page profiles, never automatic canvas extension.
- Builder edits remain mutable drafts. Publishing validates the complete fixed-page config and creates an immutable, content-hashed revision; quotations select and pin only published revisions.
- Dynamic benefit grids recompute rows/columns and uniformly shrink all card content inside fixed bounds. They never clip, paginate, drop cards, or extend the page.
- A new template may contain at most one Current Benefits grid and one Available Add-ons grid. Scenario counts are editor-only and must never enter saved template JSON.
- Customer-facing Builder scenarios are 0, 1, 6, 12, 15, and 20 cards. Larger counts are internal renderer stress cases and are not selectable product scenarios.
- Legacy manual benefit sections/cards remain readable for compatibility but cannot be published as new v7 benefit content.
- The Benefits grid contains confirmed base benefits and selected paid/FOC add-ons. An explicit upgrade replaces its current concept value; Available Add-ons shows only explicit next/branch choices.
- Broad-cover marketing facets are allowed only when the pinned verified source supports them; facets do not create extra entitlements.
- Missing required benefit variables and unknown add-on costs remain `Check Needed` and block generation.
- Generated versions snapshot reviewed fields, typed benefits, catalog/template revisions, layout, assets, and renderer version; existing versions are never overwritten.

## Roles

- Staff share access to all quotation/customer records and approved business-domain setup, including companies, catalogs, assets, and templates.
- Admins add user/security/audit/IP/operational administration to Staff capabilities.
- Exactly one Primary Admin (`super_admin`) exclusively controls Admin promotion/demotion, ownership transfer, and emergency recovery.
- Production prohibits the `dev` role. Server-issued capabilities guide the UI; backend authorization remains authoritative.
- Enforce authorization in backend routes and services.

## Security and Retention

- Uploads are PDF-only, size-limited, validated, quarantined in the OS temporary directory, malware-scanned when required, extraction-limited, and always cleaned up after processing.
- Source and generated PDF binaries remain until explicit manual deletion.
- Trash remains until explicit, audited permanent purge. There is no automatic PDF expiry or automatic trash purge.
- Referenced legacy data/assets remain hidden and immutable until compatibility/reference checks prove physical deletion safe.
- SharePoint/OneDrive archive support is optional, backend-only, and requires Microsoft Entra credentials, checksum verification, and object metadata before activation.
