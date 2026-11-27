# Motor Insurance Benefits Catalog & Design 2 Asset Audit Report (`v31.2`)

> **Verification Date:** 2026-11-24 (`v31.2`)  
> **Live DB Schema Version:** `091` (`schema_migrations` verified clean)  
> **Scope:** `10` insurance companies, `175` active/published `benefit_catalogs`, `11` active `company_benefit_bundles`, `64` active `benefit_concepts` (`100%` Design 2 flat vector icons), Builder UI ([page.tsx](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/benefits/page.tsx), [benefits-step-navigator.tsx](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/benefits/components/benefits-step-navigator.tsx), [benefit-conditions-tab.tsx](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/app/builder/benefits/components/benefit-conditions-tab.tsx)), Rendering & Matrix Engines ([render_context.py](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/render_context.py), [unified_addon_engine.py](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/unified_addon_engine.py), [unified-addon-engine.ts](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/lib/unified-addon-engine.ts)), and Reference Petrol Session `44ede2fd-8632-4eff-9080-60a0f3616a09`.

---

## 1. Subsystem Verification Checklist

| # | Subsystem / Invariant | Status | Verified Result (`v31.2`) |
| :--- | :--- | :--- | :--- |
| 1 | **Catalog as Single Source of Truth (100% Control)** | `[VERIFIED OK]` | `CatalogOffering.description_override` takes precedence over `CompanyBenefitConfig.baseline_description` -> `BenefitConcept.description`; `_offering()` (`catalog_lifecycle_service.py`), `save_catalog_offering`, `cleanCoverageValue`, and `updateOfferingValueInline` preserve custom non-numeric strings end-to-end. |
| 2 | **Builder vs Engine Revision Parity** | `[VERIFIED OK]` | `CATALOGS_WITH_DRAFT_ABOVE_PUB = 0` (`max_rev == max_pub_rev` on all `175` published catalogs); `/builder/benefits`, Overview Matrix (`matrix_service.py`), and Quotation Engine all read the exact same published revision. |
| 3 | **Zero Static Prices / Demo Amounts** | `[VERIFIED OK]` | `real_static_prices = 0`, `baseline_costs = 0`, `real_six_months = 0`. Only Base **Towing** limits and **Waiver of Betterment** year caps (`Up to 15 Years` / `Up to 10 Years`) hold static `display_value` + matching `description_override`; all other premiums/coverage sums come strictly from uploaded PDFs or staff manual entry. |
| 4 | **LLTP / LLOP & Motor Pillion Separation** | `[VERIFIED OK]` | `0` LLOP/LLTP items in Box 1 (`base/included`) across non-MMIP catalogs; `legal-liability-to-pillion` active (`sort_order = 27`) and placed in Motorcycle Box 2 (`added_moto_pillion: 53 + 4`); no duplicate offerings within any catalog. |
| 5 | **EV vs ICE Powertrain Isolation** | `[VERIFIED OK]` | `ev_in_ice = 0`, `ngv_in_ev = 0`. `is_ev_vehicle` / `isEVVehicle` splits CamelCase/acronyms (`EVSaloonCar` -> `EV Saloon Car`) and uses word boundaries (`\b(ev\|electric\|zev\|bev\|tesla\|...)\b`, `\b\d+\s*kw\b`), eliminating false substring matches (`seven`, `chevrolet`). `fillToSlots = 0` prevents unconfigured EV/ICE filler cards. |
| 6 | **TPO (`Third Party`) <-> MMIP Exclusive** | `[VERIFIED OK]` | `non_mmip_tpo = 0` (`89` non-MMIP TPO catalogs archived); MMIP has `1` active published catalog (`MMIP Third Party Only`); Builder navigator locks MMIP to `Third Party` and hides `Third Party` for all other insurers. |
| 7 | **Private Segment != Lorry** | `[VERIFIED OK]` | `priv_lorry = 0`, `null_seg_non_mmip = 0`. All Lorry catalogs live under `Company / Commercial` (`commercial`), and Builder UI blocks `Lorry` when `Private` segment is active. |
| 8 | **Kurnia & Liberty 1:1 AmAssurance Parity** | `[VERIFIED OK]` | Clean `AmAssurance` (`22` published catalogs including all `6` `auto365` ICE/EV tiers, products, tiers, configs, and `Private Car 365` bundle) cloned 1:1 to `Kurnia` (`22` catalogs) and `Liberty` (`22` catalogs) with proper brand naming. All `18` `auto365` tiers (`Lite 50 km`, `Plus 100 km`, `Premier 365 km` ICE & EV) match 1:1 between `display_value` and `description_override`. |
| 9 | **Tune Protect & Bundled Benefits (`CompanyBenefitBundle`)** | `[VERIFIED OK]` | `11` active bundles across all insurers, including `3` active Tune Protect bundles (`MotorShield Multi-Pack`, `AutoBuddy` [Plans A–E], `Motor Easy Bundle`). `38` dead legacy `company_benefit_conditions` deleted; legacy rules panel hidden when empty. |
| 10 | **Design 2 Flat Vector Icons (`#1D1D1B` + `#E52320`)** | `[VERIFIED OK]` | `Design 2 Vector Icons` global visual profile active (`64` unique `512x512` transparent `image/png` icons mapped 1:1 across all `64` active `benefit_concepts`, synced in [design2_icons.py](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/design2_icons.py) and [design2-icons.tsx](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/template-canvas/design2-icons.tsx)); `63` legacy 3D/isometric assets archived; `bg-white` tile badge preserves crisp icon contrast. |

---

## 2. SDLC Data-Control Architecture (How Catalogs -> Quotation Workspace -> PDF Work)

1. **Benefit Text & Value Resolution Precedence (100% Staff Control):**
   - **Title:** `CatalogOffering.label_override` -> `BenefitConcept.label`
   - **Description:** `CatalogOffering.description_override` *(highest precedence on a tier/catalog)* -> `CompanyBenefitConfig.baseline_description` *(insurer baseline)* -> `BenefitConcept.description` *(global default)*
   - **Coverage Limit (`display_value`):** Extracted PDF value / staff manual workspace override -> `CatalogOffering.display_value` *(only populated for Base Towing km/RM limit and Waiver of Betterment year cap; any custom non-numeric string typed in `/builder/benefits` is preserved verbatim)* -> otherwise blank (no fabricated demo amounts).
   - **Price (`optional_price`):** Strictly extracted from the uploaded source PDF or entered manually by staff in the Quotation Workspace. Catalog rows and `company_benefit_configs.baseline_cost` store `None`.
2. **Builder UI (`/builder/benefits`) Mechanics Fixed:**
   - Visible tile counts (`activeDefaultCount`, `activeAddonCount`) count only non-retired, company-enabled concepts, eliminating stale `7 / 11` / `23` hardcoded denominators.
   - Multi-catalog packages display accurate `Tier X of Y` (`Tier 1 of 3`, `Tier 2 of 3`, `Tier 3 of 3`).
   - All 8 inline value/price `<input>` controls carry offering/value-scoped React `key`s so switching tiers (e.g., `Premier 365 km` -> `Plus 100 km` -> `Lite 50 km`) never leaves uncontrolled stale DOM values stuck.
3. **Reference Session Check (`44ede2fd-8632-4eff-9080-60a0f3616a09`, Draft `2bce1532-636b-4d59-a721-3e470fd8d998`):**
   - Resolved via `_workspace_benefit_cards` + `build_unified_matrix_cards`: `6` current benefits, `11` available add-ons, `14` unified matrix cards, **`0` EV leaks**, **`0` fake demo default values**.

---

## 3. Per-Insurer Published Catalog & Bundle Summary (`10` Insurers, `175` Catalogs, `11` Bundles)

| Insurer (`slug`) | Published Catalogs | Private Car Comp Towing & Betterment | Active Bundled Benefits (`company_benefit_bundles`) |
| :--- | :---: | :--- | :--- |
| **AmAssurance** (`amassurance`) | `22` | `auto365` Lite `50 km` / Plus `100 km` / Premier `365 km` (ICE & EV); Betterment `Up to 10 Years` (Box 2); 6 non-offered add-ons excluded (`migrations/100_etiqa_dpp_bundles_and_amgen_box2_exclusions.sql`) | `Private Car 365` (4 plan tiers) |
| **Kurnia** (`kurnia`) | `22` | 1:1 clone of cleaned AmAssurance (ICE & EV tiers, commercial, motorcycle); Betterment `Up to 10 Years` (Box 2); 6 non-offered add-ons excluded (`migrations/100_etiqa_dpp_bundles_and_amgen_box2_exclusions.sql`) | `Private Car 365` (4 plan tiers) |
| **Liberty** (`liberty`) | `22` | 1:1 clone of cleaned AmAssurance (ICE & EV tiers, commercial, motorcycle); Betterment `Up to 10 Years` (Box 2); 6 non-offered add-ons excluded (`migrations/100_etiqa_dpp_bundles_and_amgen_box2_exclusions.sql`) | `Private Car 365` (4 plan tiers) |
| **Berjaya Sompo** (`berjaya-sompo`) | `18` | `Unlimited` towing + `Special Perils` in Box 1; Betterment `Up to 15 Years` (Box 2) | `SOMPO Motor N-hancer` (Pack 1–2) |
| **Etiqa** (`etiqa`) | `18` | `200 km` towing in Box 1; Betterment `Up to 10 Years` (Box 2) | `Driver Passenger Protection` (Plans 1–3 bilingual EN/ZH, Unlimited Towing; replaced `OTO 360` in `migrations/100_etiqa_dpp_bundles_and_amgen_box2_exclusions.sql`) |
| **Lonpac Insurance** (`lonpac`) | `18` | `RM 200` towing in Box 1; `Windscreen`/`Special Perils`/`CART` moved cleanly to Box 2; Betterment `Up to 10 Years` (Box 2) | `E-Assist Smart Driver` (3 plan tiers) |
| **QBE** (`qbe`) | `18` | `RM 500` towing + Betterment `Up to 10 Years` in Box 1 (`0% betterment deduction`); Lorry LLOP moved to Box 2 | `Driver & Passenger Protector (N4)` (1 tier) |
| **Takaful Malaysia** (`takaful-malaysia`) | `18` | `50 km` towing in Box 1; Betterment `Up to 10 Years` (Box 2) | `Motor PA Plus` (Plan 1–4) |
| **Tune Protect** (`tune-protect`) | `18` | `RM 300` towing + `Drive-Less Save-More` in Box 1; Betterment `Up to 15 Years` (Box 2) | `MotorShield Multi-Pack` (Included), `AutoBuddy` (Plan A–E), `Motor Easy Bundle` (Included) |
| **MMIP** (`mmip`) | `1` | `MMIP Third Party Only` (exclusive Third Party insurer) | None (TPO only) |

---

## 4. Complete Design 2 Flat Vector Icon Inventory (`64 / 64` Active Concepts)

Every active `benefit_concept` points to a unique `512x512` transparent `image/png` (`has_transparency = True`, dual-tone `#1D1D1B` charcoal + `#E52320` red) in Supabase Storage under the active `Design 2 Vector Icons` `GlobalBenefitProfile`:

| Order | Concept Key | Label | Builder Group | Asset Key (`512x512` PNG) |
| :---: | :--- | :--- | :--- | :--- |
| 0 | `smart-driver-pa` | Smart Driver PA | `addon` | `design2-vector:smart-driver-pa` |
| 2 | `own-damage` | Comprehensive Own Damage | `default` | `design2-vector:own-damage` |
| 3 | `legal-costs-defense` | Legal Defense Costs | `default` | `design2-vector:legal-costs-defense` |
| 7 | `third-party-bi` | Third Party Bodily Injury | `default` | `design2-vector:third-party-bi` |
| 8 | `third-party-property` | Third Party Property Damage | `default` | `design2-vector:third-party-property` |
| 11 | `towing` | Emergency Towing Assistance | `default` | `design2-vector:towing` |
| 13 | `agreed-value-market-value` | Agreed Value Settlement | `default` | `design2-vector:agreed-value-market-value` |
| 14 | `all-drivers` | All Drivers Excess Waiver | `default` | `design2-vector:all-drivers` |
| 16 | `betterment-protection` | Betterment Waiver | `default` | `design2-vector:betterment-protection` |
| 17 | `repair-allowance` | CART | `addon` | `design2-vector:repair-allowance` |
| 18 | `cross-border` | Cross-Border Extension | `addon` | `design2-vector:cross-border` |
| 20 | `ferry-transit` | Ferry Transit Cover | `addon` | `design2-vector:ferry-transit` |
| 21 | `first-loss-flood` | First Loss Special Perils | `addon` | `design2-vector:first-loss-flood` |
| 22 | `car-detailing-cleanup` | Car Detailing & Cleaning | `addon` | `design2-vector:car-detailing-cleanup` |
| 23 | `out-of-pocket-allowance` | Out of Pocket Allowance | `default` | `design2-vector:out-of-pocket-allowance` |
| 24 | `increased-tppd` | Increased Third Party Property | `addon` | `design2-vector:increased-tppd` |
| 25 | `key-replacement` | Key Care Replacement | `default` | `design2-vector:key-replacement` |
| 26 | `legal-liability-of-passengers` | Legal Liability of Passengers | `addon` | `design2-vector:legal-liability-of-passengers` |
| 27 | `legal-liability-to-passengers` | Legal Liability to Passengers | `addon` | `design2-vector:legal-liability-to-passengers` |
| 27 | `legal-liability-to-pillion` | Legal Liability to Pillion | `addon` | `design2-vector:legal-liability-to-pillion` |
| 28 | `ncd-relief` | NCD Relief | `addon` | `design2-vector:ncd-relief` |
| 29 | `vehicle-accessories` | Vehicle Accessories Cover | `addon` | `design2-vector:vehicle-accessories` |
| 30 | `special-perils` | Special Perils | `default` | `design2-vector:special-perils` |
| 31 | `strike-riot-civil-commotion` | Strike, Riot & Civil Commotion | `addon` | `design2-vector:strike-riot-civil-commotion` |
| 32 | `repaint-spray-paint` | Vehicle Respray Cover | `addon` | `design2-vector:repaint-spray-paint` |
| 33 | `motor-pa-plus` | Motor PA Plus | `addon` | `design2-vector:motor-pa-plus` |
| 33 | `windscreen` | Windscreen Coverage | `addon` | `design2-vector:windscreen` |
| 34 | `oto-360` | OTO 360 | `addon` | `design2-vector:oto-360` |
| 35 | `boom-damage` | Accidental Boom Damage | `addon` | `design2-vector:boom-damage` |
| 36 | `overturning` | Accidental Overturning | `addon` | `design2-vector:overturning` |
| 37 | `attached-trailers` | Attached Trailers Cover | `addon` | `design2-vector:attached-trailers` |
| 38 | `cargo-protection` | Cargo & Goods in Transit Liability | `addon` | `design2-vector:cargo-protection` |
| 39 | `gas-conversion-kit` | Gas Conversion Kit Cover | `addon` | `design2-vector:gas-conversion-kit` |
| 40 | `authorized-attendants` | Legal Liability to Authorized Attendants | `addon` | `design2-vector:authorized-attendants` |
| 42 | `tool-of-trade` | Tool of Trade Risks | `addon` | `design2-vector:tool-of-trade` |
| 43 | `total-loss-theft-allowance` | Compassionate Allowance | `default` | `design2-vector:total-loss-theft-allowance` |
| 44 | `flood-relief-allowance` | Compassionate Flood Relief Allowance | `addon` | `design2-vector:flood-relief-allowance` |
| 46 | `accidental-death` | Personal Accident Cover | `default` | `design2-vector:accidental-death` |
| 49 | `daily-hospital-income` | Daily Hospital Income | `addon` | `design2-vector:daily-hospital-income` |
| 50 | `double-indemnity` | PA: Double Indemnity Payout | `addon` | `design2-vector:double-indemnity` |
| 56 | `medical-expenses` | Accidental Medical Expenses | `addon` | `design2-vector:medical-expenses` |
| 57 | `permanent-disablement` | PA: Permanent Disablement | `addon` | `design2-vector:permanent-disablement` |
| 59 | `personal-belongings-theft` | Snatch and Theft Property Cover | `addon` | `design2-vector:personal-belongings-theft` |
| 60 | `ev-battery-depletion-towing` | EV Battery Towing | `addon` | `design2-vector:ev-battery-depletion-towing` |
| 61 | `ev-charging-bodily-injury` | EV Charging - Bodily Injury | `addon` | `design2-vector:ev-charging-bodily-injury` |
| 62 | `ev-home-content-fire` | EV Home Fire Damage | `addon` | `design2-vector:ev-home-content-fire` |
| 63 | `ev-home-charger-liability` | EV Charger Liability | `addon` | `design2-vector:ev-home-charger-liability` |
| 64 | `ev-wall-charger` | EV Wall Charger Cover | `addon` | `design2-vector:ev-wall-charger` |
| 65 | `child-car-seat` | Child Car Safety Seat | `addon` | `design2-vector:child-car-seat` |
| 66 | `payd-telematics` | Drive-Less Save-More | `default` | `design2-vector:payd-telematics` |
| 67 | `e-hailing-extension` | E-Hailing Cover | `addon` | `design2-vector:e-hailing-extension` |
| 68 | `natural-falling-objects` | Natural Falling Objects Cover | `default` | `design2-vector:natural-falling-objects` |
| 69 | `cashback-no-claim` | Non-Claim Cashback | `default` | `design2-vector:cashback-no-claim` |
| 70 | `repair-workmanship-warranty` | Panel Workmanship Warranty | `default` | `design2-vector:repair-workmanship-warranty` |
| 71 | `side-mirror-protection` | Side Mirror Damage Cover | `addon` | `design2-vector:side-mirror-protection` |
| 72 | `document-replacement` | Document Replacement Cover | `default` | `design2-vector:document-replacement` |
| 73 | `private-car-365` | Private Car 365 | `addon` | `design2-vector:private-car-365` |
| 74 | `commercial-driver-crew-pa` | Driver & Crew PA Bundle | `addon` | `design2-vector:commercial-driver-crew-pa` |
| 75 | `driver-passenger-protector` | Driver Passenger Protector | `addon` | `design2-vector:driver-passenger-protector` |
| 76 | `lonpac-ev-smart-pack` | Lonpac EV Smart Pack | `addon` | `design2-vector:lonpac-ev-smart-pack` |
| 77 | `motorshield-bundle` | MotorShield Multi-Pack | `addon` | `design2-vector:motorshield-bundle` |
| 79 | `sompo-motor-nhancer` | SOMPO Motor N-hancer | `addon` | `design2-vector:sompo-motor-nhancer` |
| 91 | `auto-buddy-malaysia` | AutoBuddy | `default` | `design2-vector:auto-buddy-malaysia` |
| 92 | `motor-easy` | Motor Easy | `default` | `design2-vector:motor-easy` |

---

## 5. Verification Suite Results (`v31.2`)

- **Idempotent Data & Icon Standardization Script:** `.venv/Scripts/python.exe commands/standardize-v31-2-catalogs-and-icons.py --apply` -> exit code `0` (`COMMITTED SUCCESSFULLY.`).
- **Backend Verification Suite:** `.venv/Scripts/python.exe -m pytest -q` -> **`1284 passed, 3 skipped`** (`0` failures).
- **Frontend Verification Suite:** `npx tsc --noEmit`, `npm run lint`, and `npm run build` -> all exited with code **`0`**.
