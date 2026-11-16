# Commercial Vehicle (Lorry / Truck) vs. Private Car Benefits Catalog Comparison

> **Canonical Ground-Truth Audit**: Side-by-side comparative analysis between the current system catalog (`CANONICAL_24_CATALOG` & `extract_free_coverage_items()`) and the extracted underwriter policy catalogs (`docs/benefits/expanded/*.md` and `docs/benefits/concise/all_benefits.md`) across all 7 Malaysian motor insurers.

---

## 1. Executive Summary & Root Cause Analysis

### The Problem Identified
In the current RiskLocker comparison and PDF rendering engine (`backend/app/rendering/unified_addon_engine.py` and `frontend/src/lib/unified-addon-engine.ts`), **Commercial Vehicles (Lorries, Rigid Trucks, Prime Movers, Trailers)** are processed through the identical default benefit rules and catalog as Private Passenger Cars:
1. **Blind Towing Insertion**: The top-right "Free Added Coverage" card unconditionally inserts `Emergency Towing Assistance (RM 200.00)` on every quotation, even though heavy commercial lorries cannot be towed by standard roadside breakdown tow trucks, and certain underwriters (e.g. QBE and STMB) **do not include any free towing** in their commercial base cover.
2. **Irrelevant Consumer Fallbacks**: When fewer than 4 free benefits are extracted, the engine appends consumer passenger car perks (`Child Car Safety Seat` and `Drive-Less Save-More`) to commercial lorry quotes.
3. **Fluff / Padding Words**: Superficial filler items such as *"24/7 commercial claims hotline"* dilute the professionalism of the quotation. In reality, every underwriter has a claims helpline; highlighting a phone number as an exclusive "free benefit" makes the quotation look deficient.
4. **Static 24-Card Add-on Matrix Leakage**: The bottom 24-card matrix mixes consumer EV items (`EV Wall Charger`, `EV Battery Out of Charge Towing`, `EV Charger Liability`) and `Private Hire Car (E-Hailing)` into commercial lorry comparisons, while showing commercial crane attachments (`Accidental Damage to Boom`, `Damage by Overturning`) on private cars.

---

## 2. The 6 Critical Differentiating Benefits (Private Car vs. Commercial Lorry)

The following 6 benefits are the **only ones that matter and differ** across Malaysian insurers. Everything else is either a standard statutory baseline (Own Damage, Third Party BI, Third Party Property Damage up to RM 3M) or an optional calculated endorsement.

| # | Benefit | Private Car (ICE & EV) Reality | Commercial Lorry (C-Permit & A-Permit) Reality | Insurer Variations & Invariants |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **Towing Assistance** | Standard 24/7 emergency accident and breakdown towing (RM 200 to RM 300, or 50 km to Unlimited). | **No free breakdown towing.** Only basic **accidental towing reimbursement up to RM 200** to nearest repairer is provided by 5 insurers (AmAssurance, Berjaya Sompo, Etiqa, Lonpac, Tune Protect). **QBE and STMB include NO default towing** (STMB requires an expensive RM 180–RM 220 Heavy Towing rider). | **Crucial Invariant**: Must NEVER show "Unlimited Breakdown Towing" on commercial lorries. For QBE & STMB, omit towing from default free benefits completely. |
| **2** | **Waiver of Betterment** | 0% betterment waiver available or included up to 10–15 years of vehicle age. | **Tariff Betterment Scale applies strictly** (0% for <5 yrs, 15% 5–6y, 20% 6–7y, 25% 7–8y, 30% 8–9y, 35% 9–10y, 40% 10+ yrs). Waiver of betterment is **not standard** for heavy commercial vehicles. | Must show standard commercial tariff scale or omit betterment waiver unless explicitly granted by underwriter. |
| **3** | **Driver Excess Waiver / All Drivers** | RM 400 unnamed driver excess penalty is either waived for all licensed drivers aged 21+, or purchasable as "All Drivers" rider. | Policy covers authorized corporate drivers holding valid **GDL (Goods Driving License)** or **E Full Heavy License**. Unnamed driver excess waiver (Endorsement 101) is an optional add-on (or built into corporate fleet wording). | STMB includes authorized GDL drivers in default wording. Tune Protect & AmAssurance sell Endorsement 101 All Drivers GDL as an add-on. |
| **4** | **Key Care / Key Replacement** | Reimburses smart key fob replacement and reprogramming up to RM 1,000–RM 2,000. | **Not applicable.** Commercial heavy vehicles use mechanical ignition or master fleet keys; key replacement riders do not apply. | Never show Key Care in Commercial Lorry default free benefits. |
| **5** | **Legal Defense Costs** | Reimburses court legal representation and defense expenses up to RM 2,000 under Road Transport Act 1987. | **Fully Included (RM 2,000).** Standard across **all 7 insurers** in commercial vehicle comprehensive policies. | Authentic, universal commercial policy default inclusion. |
| **6** | **Workmanship Warranty** | 12-month to 3-year repair warranty from approved panel repairers. | **12-month repair workmanship warranty** provided by insurers with commercial panel workshop networks (e.g. AmAssurance, Berjaya Sompo). | Authentic free perk where offered by the underwriter's commercial repairer network. |

---

## 3. Insurer-by-Insurer Side-by-Side Comparison

Below is the definitive side-by-side comparison synthesized directly from `docs/benefits/expanded/*.md` across all 7 Malaysian motor insurers:

### 1. Etiqa Insurance & Takaful
| Dimension | Private Car (12 Months) | Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit - 6 Months) |
| :--- | :--- | :--- |
| **Default Inclusions (RM 0)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• Emergency Towing Assistance (RM 200)<br>• 24/7 Roadside Assistance Service<br>• Legal Defense Costs (RM 2,000) | • Own Damage, TPBI, TPPD (RM 3M)<br>• **Transportation of Damaged Lorry (Towing Base up to RM 200)** (Roadside breakdown assistance *strictly excluded*)<br>• Legal Defense Costs (RM 2,000)<br>• Loading & Unloading Third Party Liability<br>• Towing Disabled Vehicle Extension |
| **Towing Scope** | RM 200 base towing; upgradeable to 24/7 Unlimited roadside breakdown towing. | Accidental towing reimbursement to nearest repairer/yard up to RM 200 only. No roadside assistance. |
| **Betterment** | New Spare Part Replacement Cover (Non-Tariff up to 15 years). | Commercial Tariff Betterment Scale (0% under 5y up to 40% 10y+). |
| **Driver Excess** | Standard private car excess. | Authorized drivers with valid GDL. |
| **Key Care** | Smart Key Replacement (up to RM 1,000). | None. |
| **Workmanship** | Panel repair network warranty. | Approved commercial repairer network. |
| **Relevant Add-ons** | Windscreen (End 89), Special Perils (End 57), SRCC (End 25), LLP (End 100), LLOP (End 72), CART (End 112), Child Safety Seat, EV Wall Charger, Cash Care DPA Bundles. | Commercial Cabin Windscreen (End 89), Special Perils (End 57), SRCC (End 25), Passenger Risk / Cabin Attendant Liability (End 19/100), Commercial CART (End 112), Tailgate & Accessories (End 97), Commercial PA (Driver & Attendant), Ferry Transit (End 109). |

---

### 2. Berjaya Sompo Insurance
| Dimension | Private Car (12 Months) | Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit - 6 Months) |
| :--- | :--- | :--- |
| **Default Inclusions (RM 0)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• SOMPO Roadside Assist (Emergency towing up to RM 300)<br>• Legal Defense Costs (RM 2,000)<br>• 12-Month Repair Workmanship Warranty | • Own Damage, TPBI, TPPD (RM 3M)<br>• **Commercial Standard Towing Allowance (Emergency accident towing up to RM 200)**<br>• Legal Defense Costs (RM 2,000)<br>• 12-Month Panel Repair Workmanship Warranty |
| **Towing Scope** | RM 300 roadside towing allowance. | Accidental towing reimbursement up to RM 200. Optional add-ons: Unlimited Towing BDM ≤ 7.5T (End A05 - RM 60) or BDM > 7.5T (End A05A - RM 90). |
| **Betterment** | SOMPO Motor N-hancer (0% betterment up to 15 years). | Standard commercial vehicle tariff betterment scale. |
| **Driver Excess** | All Drivers Excess Waiver (End 101) or standard excess. | Authorized drivers with valid GDL / commercial driving license. |
| **Key Care** | Included in bundled riders. | None. |
| **Workmanship** | 12-Month Panel Repair Warranty. | 12-Month Panel Repair Warranty. |
| **Relevant Add-ons** | Enhanced Windscreen (End 89A), Special Perils (End 57), LLP (End 100), LLOP (End 72), CART (End 112), SOMPO Motor N-hancer Pack 1. | Enhanced Commercial Windscreen (End 89A), Special Perils (End 57), SRCC (End 25), Passenger Risk / LLP (End 19/100 for 2 attendants), Commercial CART (End 112), Unlimited Commercial Towing (End A05/A05A), Attached Trailers Cover (End 54), Accidental Boom Damage (End 38A), Mobile Plant Working Risks (End 42). |

---

### 3. Lonpac Insurance
| Dimension | Private Car (12 Months) | Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit - 6 Months) |
| :--- | :--- | :--- |
| **Default Inclusions (RM 0)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• Emergency Towing Assistance (RM 200)<br>• All Drivers / Unnamed Driver Excess Waiver (21+)<br>• Legal Defense Costs (RM 2,000)<br>• PC Privilege: Falling Objects (25% SI), Document Replacement (RM 150), Inconvenience Cash (RM 75) | • Own Damage, TPBI, TPPD (RM 3M)<br>• **Towing Reimbursement (Accidental towing up to RM 200 to nearest repairer; roadside assistance excluded)**<br>• Legal Defense Costs (RM 2,000)<br>• Commercial Tariff Betterment Scale |
| **Towing Scope** | Emergency towing reimbursement up to RM 200. | Accidental towing reimbursement up to RM 200 only. No roadside assist. |
| **Betterment** | Betterment Waiver (Add-on up to 10 years). | Commercial tariff betterment contribution scale (0% under 5y to 40% 10y+). |
| **Driver Excess** | All Drivers Excess Waiver included by default for private cars. | Standard commercial excess terms. |
| **Key Care** | Key Replacement Cover (Add-on up to RM 2,000). | None. |
| **Workmanship** | Lonpac approved panel repairer guarantee. | Lonpac approved commercial repairer guarantee. |
| **Relevant Add-ons** | Windscreen (End 89), Special Perils (End 57), SRCC (End 25), CART (End 112), Key Replacement, Flood Interior Cleaning, Respray, Lonpac EV Smart Pack. | Commercial Windscreen (End 89), Special Perils (End 57), SRCC (End 25), Overturning (End 38), LLOP (End 72), Passenger Risk / Attendants (End 19/100), Increased TPPD (End 105), Crane Boom Damage (End 38A), Tool of Trade (End 41/42). |

---

### 4. AmAssurance / Liberty General Insurance
| Dimension | Private Car (12 Months) | Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit - 6 Months) |
| :--- | :--- | :--- |
| **Default Inclusions (RM 0)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• Emergency Towing Assistance (RM 200)<br>• 24/7 Roadside Assistance<br>• Legal Defense Costs (RM 2,000)<br>• 12-Month Panel Repair Workmanship Warranty | • Own Damage, TPBI, TPPD (RM 3M)<br>• **Emergency Towing (Accident towing assistance up to RM 200 to nearest approved repairer)**<br>• Legal Defense Costs (RM 2,000)<br>• 12-Month Panel Repair Workmanship Warranty |
| **Towing Scope** | RM 200 base towing; upgradeable in Auto365 packs. | Accidental emergency towing reimbursement up to RM 200 only. |
| **Betterment** | Betterment Waiver (Add-on up to 15 years). | Commercial tariff betterment scale (0% under 5y to 40% 10y+). |
| **Driver Excess** | Auto365 excess waiver or standard excess. | Authorized drivers with valid GDL license. |
| **Key Care** | Key Care Replacement (Auto365 pack up to RM 1,000). | None. |
| **Workmanship** | 12-Month Panel Repair Warranty. | 12-Month Panel Repair Warranty. |
| **Relevant Add-ons** | Windscreen, Special Perils, SRCC, LLP, LLOP, CART, Respray, Auto365 Bundles, E-Hailing. | Commercial Windscreen, Special Perils, SRCC, CART, Authorized Attendants / Employees (End 19i/100), LLOP, Increased TPPD, Overturning, Boom Damage (End 38a), Mobile Plant Tool of Trade (End 41/42). |

---

### 5. QBE Insurance
| Dimension | Private Car (12 Months) | Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit - 6 Months) |
| :--- | :--- | :--- |
| **Default Inclusions (RM 0)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• 24/7 QBE Auto Assist (Breakdown & accident towing up to RM 300)<br>• Legal Defense Costs (RM 2,000)<br>• **Waiver of Betterment (0% betterment for vehicles 0–10 years old)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• Legal Defense Costs (RM 2,000)<br>• Commercial Tariff Betterment Scale<br>• *(ZERO default towing)* |
| **Towing Scope** | Standard RM 300 towing; upgrades to 24-Hour Unlimited Towing when DPP Plan A/B/C/D is selected. | **NO FREE TOWING IN BASE COVER.** |
| **Betterment** | 0% Betterment Waiver included by default for 0–10 years. | Standard commercial tariff scale. |
| **Driver Excess** | Standard private car excess. | Authorized drivers with valid GDL. |
| **Key Care** | Key Replacement (Add-on). | None. |
| **Workmanship** | QBE panel workshop network guarantee. | Approved commercial repairer network. |
| **Relevant Add-ons** | Windscreen, Special Perils, SRCC, LLOP, LLP, CART, Driver Passenger Protector (DPP Plans A/B/C/D). | Commercial Windscreen, Special Perils, SRCC, Overturning, LLOP, Authorized Attendants / Employees (End 19i/100), Increased TPPD, Boom Damage, Tool of Trade. |

---

### 6. STMB (Syarikat Takaful Malaysia Berhad)
| Dimension | Private Car (12 Months) | Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit - 6 Months) |
| :--- | :--- | :--- |
| **Default Inclusions (RM 0)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• 24/7 Tele Bantuan (Emergency towing up to RM 300 / 50 km)<br>• Legal Defense Costs (RM 2,000)<br>• **No Claim Cashback (Distributable surplus cashback via Hibah)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• Legal Defense Costs (RM 2,000)<br>• **No Claim Cashback (Distributable surplus cashback via Hibah)**<br>• Authorized GDL Drivers Coverage<br>• Commercial Tariff Betterment Scale<br>• *(ZERO default towing)* |
| **Towing Scope** | Tele Bantuan emergency towing up to RM 300. | **NO FREE TOWING IN BASE COVER.** Heavy Commercial Towing is a paid optional add-on (RM 180 for Own Goods / RM 220 for General Haulage). |
| **Betterment** | Betterment Waiver (Add-on up to 10 years). | Tariff commercial betterment scale. |
| **Driver Excess** | All Drivers (Lite Add-on) or standard excess. | Authorized drivers holding valid GDL / E heavy license. |
| **Key Care** | Key Care (Add-on). | None. |
| **Workmanship** | Takaful Malaysia panel workshop network guarantee. | Approved commercial repairer network. |
| **Relevant Add-ons** | Windscreen, Special Perils, SRCC, LLP, LLOP, CART, Motor PA Plus (Plans 1–4). | Commercial Windscreen, Special Perils, SRCC, LLP (End 100), LLOP (End 72), **Heavy Towing Rider (RM 180–RM 220)**, Cargo Protection / Carrier Liability, Increased TPPD. |

---

### 7. Tune Protect Insurance
| Dimension | Private Car (12 Months) | Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit - 6 Months) |
| :--- | :--- | :--- |
| **Default Inclusions (RM 0)** | • Own Damage, TPBI, TPPD (RM 3M)<br>• Emergency Towing Assistance (Accident towing up to RM 200)<br>• Legal Defense Costs (RM 2,000) | • Own Damage, TPBI, TPPD (RM 3M)<br>• **Basic Towing (Accidental towing assistance up to RM 200 to nearest approved repairer)**<br>• Legal Defense Costs (RM 2,000)<br>• Commercial Tariff Betterment Scale |
| **Towing Scope** | RM 200 accident towing; upgrades to unlimited in MotorShield / AUTOBUDDY packs. | Accidental towing reimbursement up to RM 200 only. |
| **Betterment** | Betterment Waiver (Add-on up to 15 years). | Standard commercial vehicle tariff betterment scale. |
| **Driver Excess** | MotorShield excess waiver or standard excess. | Commercial All Drivers (Endorsement 101 for valid GDL - RM 15). |
| **Key Care** | MotorShield bundle inclusion. | None. |
| **Workmanship** | Tune Protect panel repair guarantee. | Approved commercial repairer network. |
| **Relevant Add-ons** | Windscreen, Special Perils, SRCC, LLP, LLOP, CART, Spray Paint, Side Mirror, AUTOBUDDY PA Bundles, PAYD Telematics. | Commercial Heavy Windscreen, Special Perils, SRCC, Authorized Attendants / Loaders (End 19i/100), All Drivers GDL (End 101), Increased TPPD, Thailand Extension, Boom Damage (End 38A), Tool of Trade (End 41/42), Motorist PA Commercial (Plans B, C, D, E). |

---

## 4. Current Flaws vs. Calibrated Top-Right "Free Added Coverage"

### Comparison Summary for Top-Right Box (Commercial Lorry)

```text
CURRENT ENGINE OUTPUT (BUGGY):
[X] 01. Emergency Towing Assistance (RM 200.00)  <-- Falsely added for QBE & STMB
[X] 02. Legal Defense Costs                      <-- Genuine
[X] 03. Drive-Less Save-More                     <-- COMPLETELY WRONG FOR LORRIES
[X] 04. Child Car Safety Seat                    <-- COMPLETELY WRONG FOR LORRIES

CALIBRATED GROUND-TRUTH OUTPUT (ZERO FLUFF, 100% AUTHENTIC):
For AmAssurance, Berjaya Sompo, Etiqa, Lonpac, Tune Protect:
[✓] 01. Accidental Towing Allowance (RM 200.00)  (Accidental towing to nearest approved repairer; roadside breakdown excluded)
[✓] 02. Legal Defense Costs (RM 2,000.00)        (Court legal defense reimbursement under Road Transport Act 1987)
[✓] 03. Panel Repair Workmanship Warranty        (12-month repair quality warranty from approved commercial repairers)

For QBE:
[✓] 01. Legal Defense Costs (RM 2,000.00)        (Court legal defense reimbursement under Road Transport Act 1987)
[✓] 02. Commercial Panel Repair Guarantee        (Approved commercial repairer network quality assurance)
(Towing is strictly excluded because QBE Commercial has zero free towing)

For STMB (Takaful Malaysia):
[✓] 01. Legal Defense Costs (RM 2,000.00)        (Court legal defense reimbursement under Road Transport Act 1987)
[✓] 02. No Claim Cashback (Distributable Surplus)(Islamic surplus profit-sharing distribution via Hibah if no claims)
[✓] 03. Authorized GDL Drivers Protection        (Comprehensive coverage for licensed corporate drivers with valid GDL)
(Towing is strictly excluded because STMB Commercial Towing is a RM 180-220 paid rider)
```

---

## 5. Bottom 24-Card Add-on Matrix: Separation of Catalogs

To achieve complete mathematical and visual integrity, the 24-card add-on matrix must be divided cleanly by vehicle category:

### A. Private Car 24-Card Catalog (ICE & EV)
1. Windscreen & Window Glass (End 89)
2. Unlimited Towing & Roadside Assist
3. Legal Liability of Passengers (End 72)
4. Legal Liability to Passengers (End 100)
5. Special Perils (Flood & Storm - End 57)
6. All Drivers Excess Waiver (End 101)
7. Driver & Passenger Personal Accident (DPA / PA Plus)
8. Waiver of Betterment (Up to 15 Years)
9. Strike, Riot & Civil Commotion (SRCC - End 25)
10. Vehicle Respray Cover (Spray Paint)
11. Compensation for Assessed Repair Time (CART - End 112)
12. Vehicle Accessories Cover (End 97)
13. Current Year NCD Protector (End 111)
14. Key Care Replacement
15. International / Cross-Border Towing
16. EV Wall Charger / Wallbox Damage Cover
17. EV Battery Depletion Emergency Towing
18. EV Charger Third-Party Liability
19. Private Hire Car (E-Hailing Endorsement)
20. Inconvenience & Out-of-Pocket Allowance
21. Flood & Water Damage Interior Cleaning
22. Natural Falling Objects Cover
23. Gas Conversion Kit (NGV)
24. Child Car Safety Seat Replacement

### B. Commercial Vehicle 24-Card Catalog (Lorry / Truck / Heavy Goods)
1. Commercial Heavy Windscreen & Cabin Glass (End 89)
2. Special Perils (Flood, Tempest & Landslide - End 57)
3. Strike, Riot & Civil Commotion (SRCC - End 25)
4. Legal Liability to Non-Fare Paying Passengers / Cabin Attendants (End 19 / End 100)
5. Legal Liability of Passengers (End 72)
6. Commercial CART / Vehicle Downtime (End 112)
7. Commercial All-Authorized Drivers (GDL Extension - End 101)
8. Commercial Driver & Crew PA Bundle (Motorist PA Commercial)
9. Hydraulic Tailgate & Commercial Accessories (End 97)
10. Increased Third Party Property Damage (TPPD Limit - End 105)
11. Accidental Damage to Crane Boom (End 38A)
12. Mobile Plant Tool of Trade & Working Risks (End 41 / End 42)
13. Accidental Damage by Overturning (End 38)
14. Heavy Commercial Vehicle Towing Rider (Winched Towing Package)
15. Attached Trailers & Haulage Units (End 54)
16. Marine Ferry Transit (Sabah, Labuan & Island Ports - End 109)
17. Cross-Border Haulage Extension (Thailand / Kalimantan)
18. Goods in Transit / Carrier Cargo Liability
19. Gas Conversion Kit & Tank Cover (NGV Commercial)
20. Accidental Collision Downtime Cash Allowance
21. Loading & Unloading Working Operations Liability
22. Un-named Cabin Loader PA Endorsement
23. Commercial Replacement Vehicle Hire Allowance
24. Current Year NCD Relief (Commercial Fleet End 111)

---

## 6. Implementation Plan for Next Step

1. **Update `extract_free_coverage_items()` in `backend/app/rendering/unified_addon_engine.py` & `frontend/src/lib/unified-addon-engine.ts`**:
   - Detect vehicle classification (`is_commercial` / `is_lorry`): checks `vehicle_type` against `{"Lorry", "Truck", "Commercial", "Others"}` or registration carrying capacity (`KG`/`BDM`).
   - For commercial vehicles:
     - Suppress consumer passenger perks: `Drive-Less Save-More`, `Child Car Safety Seat`, `Key Care`.
     - Evaluate underwriter towing rules:
       - If insurer is **QBE** or **STMB / Takaful Malaysia**, **do NOT** inject default towing.
       - If insurer is **AmAssurance**, **Berjaya Sompo**, **Etiqa**, **Lonpac**, or **Tune Protect**, inject authentic `Accidental Towing Allowance (RM 200.00)` (specifically noting emergency accident towing only).
     - Populate authentic commercial inclusions:
       - `Legal Defense Costs (RM 2,000.00)` (All insurers)
       - `12-Month Panel Repair Workmanship Warranty` (AmAssurance, Berjaya Sompo)
       - `No Claim Cashback (Distributable Surplus)` (STMB)
       - `Authorized GDL Drivers Protection` (STMB)
       - Genuine extracted FOC items from the uploaded quotation.
2. **Synchronize 24 Matrix Add-ons**:
   - Provide vehicle-type aware catalog filtering so commercial lorry quotes prioritize commercial endorsements (Windscreen, Special Perils, End 100 Passenger Risk, Commercial PA, Overturning, Boom, CART, Tailgate, All Drivers GDL) instead of EV wall chargers and e-hailing.
3. **Verify 1:1 Parity**:
   - Ensure React live canvas (`design2-canvas.tsx`) and Playwright Chromium PDF generator (`template_renderer_design2.py`) render identical cards and descriptions.
