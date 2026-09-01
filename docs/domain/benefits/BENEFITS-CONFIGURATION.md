# Benefits & Add-on Configuration Matrix

**Canonical source of truth for how every insurer structures benefits.** Read this before configuring or seeding any company catalog. It mirrors exactly what is seeded today (`commands/seed-demo.py`), covering all 7 underwriting insurers, 51 standardized global benefit concepts, 6 vehicle categories, and 3 coverage types (Comprehensive, TPFT, TPO) with deterministic pricing.

---

## Status Legend

| Mark | Meaning |
| --- | --- |
| ✅ seeded | Configuration is applied to the database and active |
| ⏳ draft | Config exists in seed scripts but is **not** applied / superseded |
| ⬜ pending | Not configured — fill this row to extend coverage |

---

## 1. Global Benefit Library (51 Standardized Concepts)

The standardized master library across all Malaysian motor underwriters. Every concept has a clean, informative description and maps directly to an active `BusinessAsset`.

### 1. Default & Included Base Family (14 Concepts)
1. `own-damage` — Comprehensive Accidental Own Damage
2. `fire-theft` — Accidental Fire & Theft Indemnity
3. `third-party-bi` — Unlimited Third-Party Bodily Injury & Death
4. `third-party-property` — Third-Party Property Damage (RM 3,000,000)
5. `towing` — 24/7 Roadside Towing Assistance
6. `roadside-assistance` — 24/7 Minor Roadside Repairs & Jumpstart
7. `repair-workmanship-warranty` — Panel Workshop Repair Workmanship Warranty
8. `all-drivers` — All Drivers / Unnamed Driver Excess Waiver
9. `betterment-protection` — Waiver of Betterment Contribution (New Replacement Parts)
10. `total-loss-theft-allowance` — Total Loss / Theft Lump-Sum Compassionate Allowance
11. `key-replacement` — Key & Transmitter Lock Replacement Reimbursement
12. `flood-relief-allowance` — Compassionate Flood & Inundation Cash Relief
13. `personal-belongings-theft` — Personal Belongings & Vehicle Break-in Theft
14. `ambulance-fees` — Emergency Ambulance Transport Reimbursement

### 2. Standard Riders & Add-ons (20 Concepts)
15. `windscreen` — Windscreen, Window & Sunroof Glass Damage
16. `special-perils` — Full Convulsion of Nature (Flood, Landslide, Typhoon, Storm)
17. `first-loss-flood` — First-Loss Flood Special Perils
18. `strike-riot-civil-commotion` — Strike, Riot & Civil Commotion (SRCC)
19. `legal-liability-to-passengers` — Legal Liability to Passengers (LLTP)
20. `legal-liability-of-passengers` — Legal Liability of Passengers (LLOP)
21. `legal-liability-to-pillion` — Legal Liability to Pillion Rider (LLTR)
22. `legal-costs-defense` — Legal Defense & Representation Costs
23. `medical-expenses` — Accidental Medical Expenses Reimbursement
24. `hospital-income` — Daily Hospital Income Allowance
25. `bereavement-allowance` — Compassionate Bereavement Funeral Allowance
26. `replacement-car` — Temporary Replacement Rental Vehicle
27. `repair-allowance` — Compensation for Assessed Repair Time (CART)
28. `repaint-spray-paint` — Whole Vehicle Respray / Spray Paint
29. `side-mirror-protection` — Side Mirror & Exterior Glass Cover
30. `child-car-seat` — Child Car Safety Seat Replacement
31. `vehicle-accessories` — Vehicle Accessories & Multimedia Gear Endorsement
32. `e-hailing-extension` — E-Hailing Passenger & Liability Extension
33. `agreed-value-market-value` — Agreed Value Sum Insured Settlement
34. `cashback-no-claim` — No-Claim Cashback / Surplus Sharing

### 3. Commercial, EV & Specialty Protection (17 Concepts)
35. `personal-accident` — Driver & Passenger Personal Accident (PA)
36. `driver-passenger-protector` — Packaged Driver & Passenger Protector PA
37. `out-of-pocket-allowance` — Inconvenience & Out-of-Pocket Expense Allowance
38. `car-detailing-cleanup` — Post-Repair Interior Detailing & Sanitisation
39. `brand-new-spare-parts` — Brand-New OEM Spare Parts Guarantee
40. `compassionate-allowance` — Compassionate Accidental Cash Grant
41. `document-replacement` — Official Vehicle Document & Registration Replacement
42. `hotel-accommodation` — Outstation Breakdown Hotel Accommodation
43. `daily-hospital-income` — Intensive Care Hospital Income
44. `tyre-rim-protection` — Accidental Tyre & Wheel Rim Cover
45. `sunroof-glass-protection` — Panoramic Glass & Sunroof Replacement
46. `valet-theft-protection` — Valet Parking & Third-Party Service Theft
47. `overturning` — Commercial Overturning & Loading Accident Damage
48. `boom-damage` — Hydraulic Crane Boom & Mechanism Damage
49. `tool-of-trade` — Commercial Tool of Trade Liability
50. `authorized-attendants` — Legal Liability to Authorised Attendants & Loaders
51. `ev-wall-charger` — EV Home Wallbox & Charging Cable Damage Protection

---

## 2. 7 Active Underwriter Catalogs Across 3 Coverage Types

All 7 insurers are ✅ seeded across 6 product lines $\times$ 3 coverage types (Comprehensive, TPFT, TPO):

1. **AmAssurance (Liberty General Insurance Berhad)**
   - Bundles: `auto365 Comprehensive Plus` (RM 118), `auto365 Comprehensive Premier` (RM 198)
   - Add-ons: Windscreen (15%), Special Perils (0.20%), CART (RM 58.30-150), All Drivers (RM 20), LLTP, LLOP.
2. **Berjaya Sompo Insurance Berhad**
   - Bundles: `SOMPO Motor N-hancer Pack 1` (RM 97.52), `SOMPO Motor N-hancer Pack 2` (RM 147.34), `SOMPO Motor Ultima Care` (RM 248.00)
   - Add-ons: Windscreen (15%), Special Perils (0.20%), Full Body Spray (RM 350), E-Hailing, LLTP, LLOP.
3. **Etiqa General Insurance / Takaful Berhad**
   - Bundles: `Cash Care PA Rider (Bronze)` (RM 65.00), `Cash Care PA Rider (Silver)` (RM 120.00), `Cash Care PA Rider (Gold)` (RM 195.00), `MyRider Motor PA (Plan 1-3)`
   - Add-ons: Windscreen (15%), Special Perils (0.25%), Compensation for Loss of Use (RM 100/day), Respray (RM 280), LLTP, LLOP.
4. **Lonpac Insurance Berhad**
   - Bundles: `Smart Driver DPA Plan A` (RM 70.00), `Plan B` (RM 120.00), `Plan C` (RM 180.00), `Plan D` (RM 260.00), `Lonpac EV Smart Pack` (RM 160.00)
   - Add-ons: Windscreen (15%), Special Perils (0.20%), CART (RM 60/day), All Drivers (RM 20), LLTP, LLOP.
5. **QBE Insurance (Malaysia) Berhad**
   - Bundles: `Driver Passenger Protector Plan A` (RM 70.00), `Plan B` (RM 120.00), `Plan C` (RM 175.00), `Plan D` (RM 260.00)
   - Add-ons: Windscreen (15%), Special Perils (0.25%), First-Loss Flood (RM 30), Out-of-Pocket (RM 90), Car Detailing (RM 35), LLTP, LLOP.
6. **Syarikat Takaful Malaysia Am Berhad (STMB)**
   - Bundles: `Driver & Passenger Protection (DPP)` (RM 75.00), `Motor PA Plus Plan 1` (RM 60.00), `Plan 2` (RM 110.00), `Bike PA Plus Plan 1-2`
   - Add-ons: Windscreen (15%), Special Perils (0.20%), CART Allowance (RM 100/day), 15% No-Claim Cash Back, LLTP, LLOP.
7. **Tune Protect Malaysia Berhad**
   - Bundles: `Autobuddy Plan A` (RM 58.30), `Autobuddy Plan B` (RM 98.00), `MotorShield PA Package` (RM 135.00)
   - Add-ons: Windscreen (15%), Special Perils (0.25%), Key Care (RM 35), Spray Paint (RM 250), LLTP, LLOP.

---

## 3. Seed Execution

The database is seeded idempotently via:
```bash
python commands/seed-demo.py --apply
```
This script handles the PostgreSQL immutable published revision lifecycle cleanly and provisions all dimensions, offerings, and bundle ladders.

---

## 4. Company Overview Matrix, Word/Excel Export & AI Seed Sync

Located in `frontend/src/app/builder/benefits/page.tsx` via the **"Company Overview Matrix"** view switcher:

- **Matrix Aggregation**: Backed by `backend/app/services/matrix_service.py:get_company_matrix_data`, plotting every scenario (Comprehensive, TPFT, TPO across Private, Company, Motorcycle, Commercial) with its included defaults (Cost: 0 RM), optional add-ons (base cost / rate), and bundled plan packages.
- **Word (.docx) & Markdown (.md) Catalogs**: Available at `GET /business/companies/{id}/export-matrix?format=docx` and stored canonical markdown specifications in `fix/company/*.md` with companion master catalog in `fix/company/GLOBAL_BENEFITS_CATALOG.md`.
- **Excel (.xlsx) Export**: Available at `GET /business/companies/{id}/export-matrix?format=xlsx`. Emits a multi-sheet workbook (`Scenarios Overview` and `Detailed Offerings`) with auto-sized columns and dark header styling.
- **AI Seed & Sync Protocol**:
  - The matrix view provides copyable Markdown tables formatted for Claude / ChatGPT / Gemini.
  - Non-destructive delta sync via `POST /business/companies/{id}/diff-matrix` allows AI agents to inspect incoming brochures and return only new/modified rows without re-seeding or overwriting existing catalogs.

