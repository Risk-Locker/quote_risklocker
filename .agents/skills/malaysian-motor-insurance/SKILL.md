---
name: malaysian-motor-insurance
description: >-
  Enforce authoritative Malaysian motor insurance domain rules (JPJ ICE CC & 2026 ZEV EV road tax slabs, NCD tiers, betterment age caps, insurer towing/windscreen rules, and quotation vs covernote isolation). Use before touching pricing, tax, comparison, or tenure logic.
---

# Malaysian Motor Insurance Domain Playbook (`docs/domain/BUSINESS-RULES.md`)

Never invent Malaysian motor rules from memory or compute them in browser TypeScript. Backend `Decimal` services and Supabase catalog tables are the sole authority.

## 1. Road Tax Rules (ICE CC vs 2026 EV kW)

- **ICE Vehicles (CC):** Follow Peninsular vs Sabah/Sarawak/Labuan Saloon/Non-Saloon Private/Company JPJ tables stored in DB—never evaluate formulas via `eval()` and never allow downward bracket cliffs (`880 -> 842.50` bug). Check `road_tax_engine.py` vs frontend removal of stale `840`/`880` fallbacks.
- **EV Vehicles (ZEV effective 1 Jan 2026):** Measured in `kW` (normalize inputs `>= 1000 W` cleanly to `kW`). Identical Private & Company passenger car schedule (`RM 20` up to `RM 305` for `220 kW`, `RM 335` for `230 kW`, etc.; `50%` East Malaysia/Labuan discount above `100 kW`); Electric Motorcycles `RM 2`–`RM 42`.
- **Quotation Display:** Label as `Engine Capacity/发动机排量 : ` appending **strictly** `cc` OR `kW`, never both.

## 2. Insurer Benefit & Towing Invariants (7+ Underwriters)

- **STMB / Takaful Malaysia vs Etiqa vs Lonpac vs QBE vs AmAssurance vs Berjaya Sompo vs Tune Protect:**
  - **Towing Protection:** Never parse `"4" in text` (`towing_evaluator.py` defect) and never default unknown/unmentioned towing to `"Unlimited"` (`ncd_evaluator.py` defect). Match structured tokens (`unlimited`, explicit `km`, `200km`, etc.) cleanly and preserve exact reviewed overrides (`999 km`, `1,200 km`).
  - **Waiver of Betterment:** Private Car Comprehensive only (ICE & EV) — **excluded** from motorcycles & commercial vehicles. QBE offers it in Defaults (`0 RM`, up to 10 years); Tune/Sompo/AmAssurance/Etiqa offer it in Add-ons (up to 15 years); Lonpac/STMB offer it in Add-ons (up to 10 years).
  - **Coverage Type:** `coverage_type` is informational and never forces catalog entitlements silently.

## 3. Quotations vs Cover Notes & Calendar Renewals

- **Cover Note Isolation:** Filename/text cues (`cn`, `cover note`, `policy`, `polisi`, `schedule`) identify binding policies. **Never create `TenureComparisonEntry` columns from a Cover Note**—a Cover Note populates Current Policy details and advances stage cleanly.
- **Calendar Dates:** Always compute annual policy expiry / next renewal using exact calendar anniversary math (`dateutil.relativedelta(years=1)` minus 1 day / leap-safe), **never `+364` or `+365` days**.
- **Reference Numbers:** Format strictly as internal counter `RL{YY}{SEQ:07d}` (`Asia/Kuala_Lumpur` year)—never extracted from insurer PDFs.
- **Decimal Guard:** All premium, NCD, stamp duty (`RM 10.00`), SST (`8%` where applicable), and road tax sums use `Decimal` (`ROUND_HALF_UP`), never IEEE-754 floats.

## 4. Boundary Verification Matrix

| Scenario | Authoritative Rule |
| :--- | :--- |
| EV input supplied in Watts (`150000`) | Normalize `>= 1000` cleanly to `150 kW` before ZEV tariff lookup |
| East Malaysia EV `> 100 kW` | Apply statutory `50%` Sabah/Sarawak/Labuan EV road tax discount |
| Feb 29 leap-year inception | Anniversary via `relativedelta(years=1)` minus 1 day -> leap-safe |
| Commercial / Motorcycle policy | Exclude Private Car Betterment entitlements regardless of age |

See `references/road-tax-and-underwriter-matrix.md` for ICE/2026 EV slab safeguards and the 7-insurer betterment/towing decision table.

