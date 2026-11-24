# Motor Insurance Catalog Audit Report (Live DB Snapshot)

> **Audit Date:** 2026-11-24 (read-only snapshot; zero DB, migration, or code changes made)  
> **Scope Inspected:** `10` active `insurance_companies`, `269` non-archived `benefit_catalogs` (`256 published`, `3 active`, `10 draft`; `32 archived` excluded), latest non-archived revisions, `company_benefit_configs` (`Master Unified Profile (Active)`), `company_benefit_conditions` (`38` rows), `company_benefit_bundles` (`8` rows / `22` tiers), `benefit_packages`, and `benefit_concepts` (`95` rows).  
> **Reference Baselines:** [SKILL.md](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/.agents/skills/malaysian-motor-insurance/SKILL.md), [BENEFITS-CONFIGURATION.md](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/domain/benefits/BENEFITS-CONFIGURATION.md), [BerjayaSompo.md](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/benefits/expanded/BerjayaSompo.md), [Lonpac.md](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/benefits/expanded/Lonpac.md), and standard Malaysian motor tariff/non-tariff domain rules.

---

## Subsystem Audit Checklist

| # | Audited Subsystem | Status | Summary Finding |
| :--- | :--- | :--- | :--- |
| 1 | LLTP & LLOP Free vs Add-on Placement | `[DEFECT FOUND]` | Private Car Comp has none in Box 1, **but QBE Commercial Lorry puts LLOP in Box 1 (FREE)**; motorcycles carry Car LLTP/LLOP; Tune Protect bundle omits both; AmAssurance EV Lite duplicates LLOP; RM 7.50 / RM 0.00 / `'6 months'` pricing anomalies. |
| 2 | EV vs ICE Contamination & EV Parity | `[DEFECT FOUND]` | **Berjaya Sompo ICE puts 4 EV benefits in Box 2**; **17 EV catalogs include `gas-conversion-kit`**; EV TPO puts EV battery towing in Box 1 (FREE); EV catalogs lose Box 1 items vs ICE and leak Commercial/Car/Moto items across categories. |
| 3 | Paid Add-ons Mistakenly in Box 1 (Free/Base) | `[DEFECT FOUND]` | **Lonpac `Private Car Secure`** has Windscreen, Special Perils, CART (`RM 75`), and Out-of-Pocket in Box 1; **Berjaya Sompo** puts `special-perils` in Box 1 on EV TPFT/Lorry/Motorcycle; QBE puts LLOP in Box 1 on Lorry; EV TPO puts battery towing in Box 1. |
| 4 | Missing Core Catalogs & Insurer Gaps | `[DEFECT FOUND]` | **Kurnia & Liberty have 0 Private Car Comprehensive catalogs (ICE or EV)** and their EV catalogs are named `AmAssurance ... (EV)`. |
| 5 | TPO & TPFT Coverage Contamination | `[DEFECT FOUND]` | `windscreen` appears in **39 ICE TPFT** and **2 ICE Motorcycle TPO** catalogs; **72** Comprehensive-only offerings appear in EV TPFT (`special-perils`, `ncd-relief`, `agreed-value-market-value`, etc.). |
| 6 | Duplicate Catalogs, Status & Duplicate Offerings | `[DEFECT FOUND]` | `27` duplicate concepts inside single catalogs; duplicate active dimensions (AmAssurance, Berjaya Sompo, Takaful MY, Tune Protect); `3` `active` and `10` `draft` non-archived catalogs. |
| 7 | Retired & Duplicate Global Concepts | `[DEFECT FOUND]` | **85 active offerings** still reference `retired` concepts; active duplicates exist for `third-party-bi`/`third-party-bodily-injury` and `third-party-property`/`third-party-property-damage`. |
| 8 | Betterment Waiver, Towing, Bundles & Conditions | `[DEFECT FOUND]` | QBE Box 1 / others Box 2 matches domain rule, but Kurnia/Liberty & AmAssurance Premier ICE lack Betterment, Box 2 prices are `0.0`, Etiqa/STMB config text disagrees with year caps (`10`/`12` vs `15`/`10`), all `38` `company_benefit_conditions` are inactive, `14` active `benefit_packages` have `0` plans. |
| 9 | Data Hygiene (`display_value` & Price JSON) | `[DEFECT FOUND]` | Commercial add-ons carry scraped `display_value = '6 months'`; `optional_price` mixes 5 incompatible JSON shapes (`{type,value,currency}`, `{amount,currency}`, `{currency,rate}`, scalar `0.0`, `null`). |
| 10 | MMIP Catalog (`MMIP Third Party Only`) | `[VERIFIED OK]` | Contains TPBI & TPPD in Box 1 (`base/included`); only minor note is using `third-party-bodily-injury` / `third-party-property-damage` instead of the shorter `third-party-bi` / `third-party-property` keys. |

---

## 1. PRIORITY: LLTP & LLOP Audit — Free (Box 1) vs Add-on (Box 2)

> **Definitions:**
> - **Box 1 (`offering_kind='base'`, `role='included'`):** Included free in base policy.
> - **Box 2 (`offering_kind='optional'`, `role='addon_option'`):** Optional paid add-on.
> - **Bundle (`offering_kind='upgrade'`, `role='bundle_component'`):** Included as part of a paid upgrade pack.

### 1.1 Private Car Comprehensive Verdict (All 10 Companies)

**Verdict on Private Car Comprehensive:** **No insurer puts LLTP (`legal-liability-to-passengers`) or LLOP (`legal-liability-of-passengers`) in Box 1 (Free)** on Private Car Comprehensive (ICE or EV). Every Private Car Comprehensive catalog that lists them puts them in Box 2 (`optional/addon_option`), plus bundle upgrades (`upgrade/bundle_component`) where noted below:

| Insurer | Engine | Catalog Name | LLTP Placement & Price | LLOP Placement & Price | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| AmAssurance | EV | `auto365 Comprehensive Lite (EV)` | Box 2 (`None`) | **Box 2 x2 DUPLICATE** (`None`) | Duplicate LLOP row |
| AmAssurance | EV | `auto365 Comprehensive Plus (EV)` | Box 2 (`20.0 MYR`) | Box 2 (`7.5 MYR`) | OK |
| AmAssurance | EV | `auto365 Comprehensive Premier (EV)` | Box 2 (`None`) | Box 2 (`None`) | Price missing |
| AmAssurance | ICE | `auto365 Comprehensive Lite` | Box 2 (`None`) | Box 2 (`None`) | Price missing |
| AmAssurance | ICE | `auto365 Comprehensive Plus` | Box 2 (`RM 20.00`) | Box 2 (`RM 7.50`) | OK |
| AmAssurance | ICE | `auto365 Comprehensive Premier` | Box 2 (`None`) | Box 2 (`None`) | Price missing |
| Berjaya Sompo | EV | `Berjaya Sompo Private Car Comprehensive (EV)` | Box 2 (`7.5 MYR`) | Box 2 (`7.5 MYR`) | Suspicious LLTP price (`7.5` vs normal `>=20`) |
| Berjaya Sompo | ICE | `SOMPO Motor (Private Car Non-Tariff)` | Box 2 (`7.5 MYR`) + Bundle (`60.0`, `150.0`) | Box 2 (`7.5 MYR`) + Bundle (`150.0`) | Suspicious LLTP price (`7.5`) |
| Berjaya Sompo | ICE | `SOMPO Motor Comprehensive` | Box 2 (`None`) | Box 2 (`None`) | Price missing |
| Etiqa | EV | `Etiqa Private Car Comprehensive (EV)` | Box 2 (`7.5 MYR`) | Box 2 (`7.5 MYR`) | Suspicious LLTP price (`7.5`) |
| Etiqa | ICE | `Comprehensive Private Car Insurance / Takaful` | Box 2 (`7.5 MYR`) | Box 2 (`7.5 MYR`) | Suspicious LLTP price (`7.5`) |
| Kurnia | ICE/EV | *(MISSING)* | N/A | N/A | **No Private Car Comp catalog** |
| Liberty | ICE/EV | *(MISSING)* | N/A | N/A | **No Private Car Comp catalog** |
| Lonpac Insurance | EV | `Lonpac Insurance Private Car Comprehensive (EV)` | Box 2 (`20.0 MYR`) | Box 2 (`7.5 MYR`) | OK |
| Lonpac Insurance | ICE | `Private Car Secure` | Box 2 (`20.0 MYR`) | Box 2 (`7.5 MYR`) | OK |
| MMIP | ICE | *(Third Party Only)* | N/A | N/A | Only TPO exists |
| QBE | EV | `QBE Private Car Comprehensive (EV)` | Box 2 (`20.0 MYR`) | Box 2 (`7.5 MYR`) | OK |
| QBE | ICE | `Private Car Protector` | Box 2 (`None`) | Box 2 (`None`) | Price missing |
| Takaful Malaysia | EV | `Takaful Malaysia Private Car Comprehensive (EV)` | Box 2 (`30.0 MYR`) | Box 2 (`7.5 MYR`) | OK |
| Takaful Malaysia | ICE | `Takaful myMotor (Private Car)` | Box 2 (`None`) | Box 2 (`7.5 MYR`) | LLTP price missing (`30.00` in config) |
| Takaful Malaysia | ICE | `myClick Takaful Car` | Box 2 (`None`) | Box 2 (`None`) | Price missing |
| Tune Protect | EV | `Tune Protect Private Car Comprehensive (EV)` | Box 2 (`20.0 MYR`) | Box 2 (`7.5 MYR`) | OK |
| Tune Protect | ICE | `Motor Easy + Motor Bundle` | **MISSING** | **MISSING** | Neither LLTP nor LLOP present |
| Tune Protect | ICE | `Tune Protect Motor Easy` | Box 2 (`0.0 MYR`) | Box 2 (`0.0 MYR`) | **`0.0` price looks free** |
| Tune Protect | ICE | `Tune Protect Motor Easy (Private Car)` | Box 2 (`20.0 MYR`) + Bundle (`135.0`) | Box 2 (`7.5 MYR`) | OK |

### 1.2 Confirmed LLTP / LLOP Defects Across All Catalogs (6 Defects)

1. **QBE `Commercial Vehicle Protector` (Company/Commercial | Lorry | Comprehensive | ICE):**
   - `legal-liability-of-passengers` (LLOP) is stored in **Box 1 (`base/included` = FREE)** even though it carries `display_value = 'RM 7.50'` and `optional_price = {'type': 'money', 'value': 7.5, 'currency': 'MYR'}`. Must be moved to Box 2 (`optional/addon_option`).
2. **Tune Protect `Motor Easy + Motor Bundle` (Private Car Comprehensive ICE):**
   - Both LLTP and LLOP are **completely missing**.
3. **AmAssurance `auto365 Comprehensive Lite (EV)`:**
   - `legal-liability-of-passengers` is **duplicated twice** in Box 2 (`optional/addon_option`).
4. **Motorcycle Catalogs Carrying Car Passenger LLTP/LLOP Instead of Pillion (`legal-liability-to-pillion`):**
   - **All 9 insurers' EV Motorcycle catalogs** (Comprehensive, Third Party, TPFT) put Car `legal-liability-to-passengers` and `legal-liability-of-passengers` in Box 2.
   - **Kurnia & Liberty `Standard Motorcycle Comprehensive (Third Party)` (ICE)** put **duplicate x2** `legal-liability-to-passengers` and **duplicate x2** `legal-liability-of-passengers` at `RM 0.00`.
   - Meanwhile, `legal-liability-to-pillion` is marked **`retired`** in `benefit_concepts` and only exists in 1 QBE draft catalog (`Motorcycle Policy (Private)`, price `5.0 MYR`).
5. **`display_value = '6 months'` Scraped into Commercial LLOP/LLTP:**
   - Across Commercial Car and Commercial Lorry catalogs (`AmAssurance`, `Etiqa`, `Kurnia`, `Liberty`, `Lonpac Insurance`, `QBE`, `Takaful Malaysia`, `Tune Protect`), `display_value` is `'6 months'` instead of a coverage limit or price (prices are half-year rates `RM 3.75` for LLOP and `RM 10.00` or `RM 15.00` for LLTP).
6. **Suspicious LLTP Pricing & `baseline_cost` Inconsistencies:**
   - In `company_benefit_configs` (`Master Unified Profile (Active)`):
     - `Berjaya Sompo` and `Etiqa` store `baseline_cost = RM 7.50` for LLTP (as well as `7.5 MYR` in offerings). Note: `RM 7.50` is the standard Malaysian flat rate for **LLOP** (End. 72); **LLTP** (End. 100) is tariff-linked (~25% of Act premium, typically `RM 20.00`–`RM 30.00+` for Private Car, or ~`RM 5.00`/seat). Verify whether `RM 7.50` LLTP was copied from LLOP by mistake.
     - `AmAssurance`, `Kurnia`, `Liberty`, and `Tune Protect` have `baseline_cost = NULL` for LLTP.
     - `Tune Protect Motor Easy` (ICE) has `optional_price = 0.0 MYR` for both LLTP and LLOP.

---

## 2. PRIORITY: EV vs ICE Contamination & EV Catalog Quality

### 2.1 EV Benefits Inside ICE Box 2 Add-ons (Exact Issue Flagged)

- **`Berjaya Sompo | SOMPO Motor (Private Car Non-Tariff)` (Private | Car | Comprehensive | ICE `[published]`):**
  Contains **4 EV-only offerings** in Box 2 (`optional/addon_option`):
  1. `ev-battery-depletion-towing` (EV Battery Towing)
  2. `ev-wall-charger` (EV Wall Charger Cover)
  3. `ev-home-charger-liability` (EV Charger Liability) — **duplicated x2**

### 2.2 ICE-Only Benefit Inside EV Box 2 Add-ons

- **`gas-conversion-kit` (NGV / LPG Gas Conversion Kit)** appears in **17 published EV catalogs** across Car, Lorry, and Motorcycle (`AmAssurance` x4, `Etiqa` x3, `Kurnia` x2, `Liberty` x2, `Lonpac Insurance` x3, `Tune Protect` x3). EVs cannot have an NGV gas tank/kit.

### 2.3 EV Third Party Only (TPO) Free Unlimited Battery Towing Inversion

- On **all 9 insurers' `Private Car Third Party (EV)`** catalogs (`AmAssurance`, `Berjaya Sompo`, `Etiqa`, `Kurnia`, `Liberty`, `Lonpac Insurance`, `QBE`, `Takaful Malaysia`, `Tune Protect`), `ev-battery-depletion-towing` (`display_value = 'Unlimited'`) is placed in **Box 1 (`base/included` = FREE)** on a **Third Party Only** policy, even though EV Comprehensive catalogs put it in Box 2 as a paid add-on. (Note: `Kurnia` and `Liberty` EV TPO catalogs are also named `AmAssurance Private Car Third Party (EV)`.)

### 2.4 EV vs ICE Box 1 -> Box 2 Parity Drift & Missing Metadata

- **Segment Dimension Missing:** `Berjaya Sompo`, `Lonpac Insurance`, and `Tune Protect` EV Private Car Comprehensive catalogs have `segment = NULL` instead of `Private`. (All EV non-AmAssurance TPO/TPFT/Lorry/Motorcycle catalogs also have `segment = NULL`.)
- **Box 1 Demotions in EV vs ICE:**
  - **QBE EV** moved `all-drivers`, `key-replacement`, and `total-loss-theft-allowance` from Box 1 (in ICE `Private Car Protector`) into Box 2 (in `QBE Private Car Comprehensive (EV)`).
  - **Takaful Malaysia EV** moved `agreed-value-market-value`, `all-drivers`, `cashback-no-claim`, and `personal-accident` from Box 1 (in ICE `Takaful myMotor` / `myClick`) into Box 2 (in EV).
  - **Etiqa EV** moved `all-drivers` and `payd-telematics` from Box 1 (in ICE) into Box 2 (in EV).
- **Cross-Category Leakage Inside EV Catalogs:**
  - `Berjaya Sompo Private Car Comprehensive (EV)` contains **commercial-only** concepts (`boom-damage`, `tool-of-trade`, `attached-trailers`) and **`motorcycle-pa-bundle`** in Box 2.
  - **18** Private-Car concepts leaked into EV Lorry catalogs (`e-hailing-extension`, `child-car-seat`, `payd-telematics`, `sompo-motor-nhancer`).
  - **138** Car / EV-charger / Passenger concepts leaked into EV Motorcycle catalogs (`e-hailing-extension`, `repaint-spray-paint`, `payd-telematics`, `sompo-motor-nhancer`, `ev-wall-charger`, `ev-home-charger-liability`, `legal-liability-to-passengers`, `legal-liability-of-passengers`).

---

## 3. Critical Box 1 (Free / Included) Misclassifications

Across all `269` non-archived catalogs, **`21` Box 1 (`base/included`) offerings** belong to paid add-on concepts:

1. **Lonpac Insurance — `Private Car Secure` (Private | Car | Comprehensive | ICE `[published]`):**
   - `special-perils` (`base/included` AND duplicated in Box 2 `optional` at `RM 125.00`)
   - `windscreen` (`base/included` AND duplicated in Box 2 `optional` at `RM 150.00`, `RM 1,000`)
   - `repair-allowance` (`base/included`, `RM 75` AND duplicated in Box 2 `optional` at `RM 58.30`, `RM 50/day`)
   - `out-of-pocket-allowance` (`base/included`, `None`)
   - **Root Cause (per [Lonpac.md](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/benefits/expanded/Lonpac.md)):** Lonpac's built-in "PC Privileges 1–4" (`Transport Allowance RM 75`, `Natural Falling Objects`, `Document Replacement RM 150`, `Windscreen Auto-Reinstatement`) were mis-mapped onto paid add-on concepts (`repair-allowance`, `special-perils`, `out-of-pocket-allowance`, `windscreen`) in Box 1, creating free Windscreen & Special Perils claims.
2. **Berjaya Sompo — `special-perils` in Box 1 on Non-Private-Car-Comprehensive Catalogs (`6` EV catalogs + `1` ICE):**
   - Valid in Box 1 on `SOMPO Motor (Private Car Non-Tariff)` (ICE) and `Berjaya Sompo Private Car Comprehensive (EV)` per [BerjayaSompo.md](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/docs/benefits/expanded/BerjayaSompo.md) (built-in Special Perils for Sompo Motor Private Car Non-Tariff).
   - **SUSPICIOUS / INVALID in Box 1** on the other `5` Berjaya Sompo EV catalogs:
     - `Berjaya Sompo Private Car Third Party Fire & Theft (EV)` (`special-perils` in Box 1 on **TPFT**!)
     - `Berjaya Sompo Commercial Vehicle Comprehensive (EV)` (Lorry)
     - `Berjaya Sompo Commercial Vehicle Third Party Fire & Theft (EV)` (Lorry TPFT)
     - `Berjaya Sompo Motorcycle Comprehensive (EV)`
     - `Berjaya Sompo Motorcycle Third Party Fire & Theft (EV)` (Motorcycle TPFT)
3. **QBE — `Commercial Vehicle Protector` (Lorry | Comprehensive | ICE):**
   - `legal-liability-of-passengers` in Box 1 (`RM 7.50`).
4. **All 9 Insurers — `Private Car Third Party (EV)` (TPO):**
   - `ev-battery-depletion-towing` (`Unlimited`) in Box 1 on TPO.

---

## 4. Missing Core Catalogs & Per-Insurer Structural Defects

### 4.1 Missing Private Car Comprehensive Catalogs & Brand Mix-Up (Kurnia & Liberty)

- **Kurnia (`0` Private Car Comprehensive ICE, `0` Private Car Comprehensive EV):** Completely missing Private Car Comprehensive in both ICE and EV.
- **Liberty (`0` Private Car Comprehensive ICE, `0` Private Car Comprehensive EV):** Completely missing Private Car Comprehensive in both ICE and EV.
- **Misnamed EV Catalogs:** All `8` published EV catalogs for **Kurnia** and all `8` published EV catalogs for **Liberty** carry `AmAssurance ... (EV)` names (e.g., `AmAssurance Private Car Third Party (EV)`).
- **Corrupted Motorcycle TPO Catalog (Kurnia & Liberty ICE):** `Standard Motorcycle Comprehensive (Third Party)` has `11` offerings including **`windscreen` (on a Motorcycle TPO!)**, `legal-costs-defense` **x4**, `legal-liability-to-passengers` **x2**, `legal-liability-of-passengers` **x2**, and `strike-riot-civil-commotion` **x2**.

### 4.2 TPO & TPFT Coverage Contamination

- **Third Party Only (TPO):** `windscreen` appears in `2` Motorcycle TPO catalogs (`Kurnia`, `Liberty`). (Plus `ev-battery-depletion-towing` in Box 1 across all 9 EV Car TPO catalogs.)
- **Third Party Fire & Theft (TPFT):**
  - `windscreen` appears in **39 ICE TPFT catalogs** (Car & Lorry). TPFT only covers Third Party + Fire + Theft; Windscreen glass breakage is a Comprehensive endorsement (End. 89).
  - `first-loss-flood` appears in **1 ICE TPFT catalog**.
  - **71 Comprehensive-only offerings** appear in **EV TPFT catalogs** across insurers: `special-perils` (`3` Box 1 + `24` Box 2), `ncd-relief` (`21`), `agreed-value-market-value` (`6`), `out-of-pocket-allowance` (`6`), `payd-telematics` (`6`), `first-loss-flood` (`3`), `child-car-seat` (`2`).

### 4.3 Duplicate Catalogs, Overlapping Products & Status Anomalies

- **Exact Duplicate Catalogs:**
  - `AmAssurance`: `Auto365 Comprehensive Lite (Third Party)` x2 (both `published`); `Auto365 Comprehensive Lite (TPFT)` x2 (both `published`).
- **Overlapping Private Car Comprehensive (ICE) Products on Same Dimension Tuple (`Private | Car | Comprehensive | ICE`):**
  - `AmAssurance`: `auto365 Comprehensive Lite`, `Plus`, `Premier` (intentional tier split, **but `Premier` is missing `betterment-protection`**).
  - `Berjaya Sompo`: `SOMPO Motor (Private Car Non-Tariff)` vs `SOMPO Motor Comprehensive`.
  - `Takaful Malaysia`: `Takaful myMotor (Private Car)` vs `myClick Takaful Car`.
  - `Tune Protect`: `Tune Protect Motor Easy` vs `Tune Protect Motor Easy (Private Car)` vs `Motor Easy + Motor Bundle` (missing LLTP/LLOP and legal defense).
- **Catalog Status Anomalies (Non-Archived):**
  - `3` catalogs stuck in `status='active'` instead of `'published'`: `Berjaya Sompo` (`Private Car Comprehensive (Third Party)`, `Motorcycle Comprehensive (Third Party)`) and `Etiqa` (`Comprehensive Private Car Insurance / Takaful (Third Party)`).
  - `10` catalogs still in `status='draft'`: `QBE` (`8` catalogs covering Commercial Car Comp/TP/TPFT & Motorcycle Private/Commercial Comp/TP/TPFT), `Etiqa` (`Commercial Car Insurance (Company Car)`), `AmAssurance` (`Motorcycle365 (Private Motorcycle) (TPFT)`).
- **Duplicate Offerings Within Same Catalog (`27` cases):**
  - Includes `AmAssurance`/`Kurnia`/`Liberty` Commercial Car `towing` x2; `AmAssurance` EV Lite LLOP x2; `Berjaya Sompo` Non-Tariff `accidental-death` x2, `repair-allowance` x2, LLOP x2, LLTP x3, `ev-home-charger-liability` x2; `Lonpac` `repair-allowance`/`special-perils`/`windscreen` x2 (Box 1 + Box 2); `Tune Protect` `all-drivers`/`legal-liability-to-passengers` x2 (Box 2 + bundle). (Note: QBE `first-loss-flood` x2 for `5K` vs `10K` and `repair-allowance` x2 for `RM 50/day` vs `RM 100/day` are distinct tier variants sharing a concept key.)

---

## 5. Global Concepts, Betterment/Towing Rules, Bundles & Data Hygiene

### 5.1 Retired & Duplicate `benefit_concepts` (`95` rows)

- **85 Active Offerings Reference `retired` Concepts:**
  - `personal-accident` (retired): `38` (`36` EV optional + `2` ICE base)
  - `betterment-scale` (retired): `16` EV optional
  - `windscreen-auto-reinstatement` (retired): `10` EV optional
  - `auto-assistance` (retired): `7` (`4` EV optional + `3` ICE optional)
  - `motorcycle-pa-bundle` (retired): `6` EV optional
  - `fire-theft` (retired): `4` ICE base
  - `tuition-purpose` (retired): `3` (`2` EV optional + `1` ICE optional)
  - `legal-liability-to-pillion` (retired): `1` ICE optional (QBE draft)
- **Duplicate Active Concepts (Split Usage):**
  - `third-party-bi` (`x7`) vs `third-party-bodily-injury` (`x1`, MMIP)
  - `third-party-property` (`x7`) vs `third-party-property-damage` (`x1`, MMIP)
- **Retired Test Artifacts Left in Table:** `test-active-632fb0c9`, `test-retired-60679069`.

### 5.2 Betterment Waiver, Towing, Bundles & Conditions

- **Betterment Waiver (`betterment-protection`) Scope Check:**
  - Exists ONLY on Private Car Comprehensive (ICE & EV) — **no leakage into Motorcycles, Commercial/Lorry, TPO, or TPFT**.
  - **QBE:** Correctly in **Box 1 (`base/included`)** on both ICE (`Private Car Protector`) and EV (`QBE Private Car Comprehensive (EV)`).
  - **All other seeded insurers (`AmAssurance`, `Berjaya Sompo`, `Etiqa`, `Lonpac`, `Takaful Malaysia`, `Tune Protect`):** In **Box 2 (`optional/addon_option`)**, **EXCEPT**:
    1. `Kurnia` & `Liberty` lack Private Car Comprehensive catalogs altogether.
    2. `AmAssurance | auto365 Comprehensive Premier` (ICE) omits `betterment-protection` (present in `Lite` and `Plus`).
    3. All Box 2 `betterment-protection` rows store `optional_price = 0.0 MYR` (instead of a rated/percentage/tiered price or unset).
  - **Description Cap Mismatches in `company_benefit_configs`:**
    - `Etiqa` `baseline_description` says **`"up to 10 years"`** (domain rule in `SKILL.md`: up to **15 years**).
    - `Takaful Malaysia` `baseline_description` says **`"up to 12 years"`** (domain rule in `SKILL.md` & EV `display_value`: up to **10 years**).
- **Bundles (`company_benefit_bundles` — `8` active, `22` tiers/effects):** Cleanly configured across all 9 active insurers (AmAssurance, Kurnia, Liberty share `amassurance-private-car-365`; Berjaya Sompo intentionally omitted since Unlimited Towing is already Box 1).
- **Legacy Conditions (`company_benefit_conditions` — `38` rows):** All `is_active = False` (superseded by `company_benefit_bundles`).
- **Packages (`benefit_packages`):** `14` active packages on latest revisions, **all with `0` plans** (`plans=0`).

### 5.3 Data Hygiene (`display_value` & `optional_price` Schema Drift)

- **`display_value = '6 months'` Bug:** Commercial Car & Lorry offerings (`AmAssurance`, `Berjaya Sompo`, `Etiqa`, `Kurnia`, `Liberty`, `Lonpac`, `QBE`, `Takaful Malaysia`, `Tune Protect`) store `'6 months'` in `display_value` for `legal-liability-of-passengers`, `legal-liability-to-passengers`, `special-perils`, `strike-riot-civil-commotion`, `windscreen`, `repair-allowance`, `cross-border`, and `ferry-transit` (policy tenure leaked into benefit value).
- **5 Incompatible `optional_price` JSON Shapes:**
  - EV catalogs: `{"amount": ..., "currency": "MYR"}` (`397`), `{"currency": "MYR", "rate": ...}` (`72`), `{"type": "money", "value": ..., "currency": "MYR"}` (`11`), `{"display_text": ..., "formula": ..., "type": ...}` (`1`), `null` (`503`).
  - ICE catalogs: `{"type": "money", "value": ..., "currency": "MYR"}` (`505`), `{"currency": "MYR", "raw": ...}` (`2`), `{"display_text": ..., "formula": ..., "type": ...}` (`3`), bare scalar `0.0` (`2`), `null` (`283`).

---

## 6. Prioritized Remediation Checklist (For Future Fix Pass)

- **P0 — Immediate (Wrong Free Benefits / Missing Major Insurer Products):**
  1. Provision missing Private Car Comprehensive (ICE & EV) catalogs for **Kurnia** and **Liberty**, and rename their `AmAssurance ... (EV)` catalogs.
  2. Fix **Lonpac `Private Car Secure`**: move `windscreen`, `special-perils`, `repair-allowance` (`CART`), and `out-of-pocket-allowance` out of Box 1 (`base/included`), and map Lonpac PC Privileges 1–4 cleanly.
  3. Fix **Berjaya Sompo**: remove the 4 EV add-ons from ICE `SOMPO Motor (Private Car Non-Tariff)`; remove `special-perils` from Box 1 (`base/included`) on EV TPFT, EV Lorry, and EV Motorcycle.
  4. Fix **QBE `Commercial Vehicle Protector`**: move `legal-liability-of-passengers` from Box 1 (`base/included`) to Box 2 (`optional/addon_option`).
  5. Fix **all 9 insurers' `Private Car Third Party (EV)`**: remove free `Unlimited` `ev-battery-depletion-towing` from Box 1 on TPO.
- **P1 — High (Domain Accuracy Across Coverage Types & EV):**
  6. Remove `gas-conversion-kit` from all `17` EV catalogs; remove Commercial/Moto leakage from Berjaya Sompo EV Car and Private-Car/EV-charger leakage from EV Lorry (`18`) and EV Motorcycle (`138`); restore Box 1 parity on QBE/STMB/Etiqa EV; backfill `segment_id` on EV catalogs.
  7. Strip `windscreen` (`39` ICE TPFT + `2` Moto TPO) and Comprehensive-only items (`72` EV TPFT + `1` ICE TPFT) out of TPFT/TPO.
  8. Fix Kurnia/Liberty `Standard Motorcycle Comprehensive (Third Party)` (remove `windscreen`, 4x legal defense, 2x LLTP/LLOP/SRCC); replace Motorcycle Car LLTP/LLOP with `legal-liability-to-pillion` (un-retire concept).
  9. Fix LLTP `RM 7.50` (`Berjaya Sompo`, `Etiqa`) vs `RM 0.00` (`Tune Protect Motor Easy`), add LLTP/LLOP to `Motor Easy + Motor Bundle`, and strip `'6 months'` from Commercial `display_value`.
- **P2 — Hygiene & Normalization:**
  10. Deduplicate exact duplicate catalogs (`AmAssurance` Lite TP/TPFT) and `27` duplicate offering rows; add `betterment-protection` to `AmAssurance Premier` (ICE) and clarify overlapping Berjaya Sompo/STMB/Tune Protect Private Car Comp catalogs.
  11. Migrate `85` offerings off retired concepts (`personal-accident` -> `accidental-death`, etc.), consolidate `third-party-bi`/`third-party-bodily-injury` & `third-party-property`/`third-party-property-damage`, align Etiqa/STMB Betterment descriptions (`15 yr` / `10 yr`), review `active`/`draft` catalog states, and normalize `optional_price` JSON schema.
