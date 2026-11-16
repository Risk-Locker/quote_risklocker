# Commercial Vehicle (Lorry / Truck) vs. Private Car Benefits Catalog Comparison

> **Canonical Ground-Truth Audit**: Authoritative comparison between the system presentation catalog and live underwriter agent portals across all 7 Malaysian motor insurers (AmAssurance, Berjaya Sompo, Etiqa, Lonpac, QBE, STMB / Takaful Malaysia, and Tune Protect).

---

## 1. Executive Summary & Ground-Truth Invariant

### The Commercial Vehicle Invariant
> **NON-NEGOTIABLE RULE**: **For Commercial Vehicles (Lorries, Rigid Trucks, Prime Movers, Trailers, Commercial Haulage), TOWING DOES NOT EXIST.**
> 
> In actual Malaysian insurance agent portals:
> - There is **NO towing option** whatsoever for commercial vehicles.
> - It is **NOT free**, and it is **NOT a paid add-on**.
> - Tow trucks cannot tow commercial lorries, and underwriters do not offer towing coverage for commercial goods vehicles in their portals.
> - Any presentation showing "Emergency Towing Assistance", "Unlimited Towing", or "Heavy Towing" on a commercial vehicle quotation is **100% false and invalid**.

### Previous Flaws in the Codebase
1. **Blind Towing Insertion**: The top-right "Free Added Coverage" card in `extract_free_coverage_items()` unconditionally injected `Emergency Towing Assistance (RM 200.00)` on every quotation, including lorries.
2. **Passenger Car Fallbacks**: The engine appended consumer passenger car perks (`Child Car Safety Seat` and `Drive-Less Save-More`) to fill empty slots on commercial lorry quotes.
3. **Fluff / Padding**: Superficial items like *"24/7 commercial claims hotline"* dilute the professionalism of the quote. Every underwriter has a phone hotline; listing a helpline as a benefit looks like a cheap placeholder.
4. **Static 24-Card Add-on Matrix Leakage**: The bottom 24-card matrix displayed consumer EV items (`EV Wall Charger`, `EV Battery Out of Charge Towing`, `EV Charger Liability`), `Private Hire Car (E-Hailing)`, and `Key Care Replacement` on commercial lorry comparisons.

---

## 2. Core Differences Across Insurers (Private Car vs. Commercial Lorry)

| # | Benefit | Private Car (ICE & EV) Reality | Commercial Lorry (C-Permit & A-Permit) Reality |
| :-: | :--- | :--- | :--- |
| **1** | **Towing Assistance** | Standard 24/7 emergency accident and breakdown towing (RM 200–RM 300, or 50 km to Unlimited). | **DOES NOT EXIST.** Zero towing in defaults, zero towing in add-ons. Neither paid nor unpaid. |
| **2** | **Waiver of Betterment** | 0% betterment waiver available or included up to 10–15 years of vehicle age. | **Tariff Betterment Scale applies strictly** (0% for <5 yrs up to 40% for 10+ yrs). Waiver of betterment does not exist for commercial lorries. |
| **3** | **Driver Excess Waiver / All Drivers** | RM 400 unnamed driver excess penalty is either waived for all licensed drivers aged 21+, or purchasable as "All Drivers" rider. | Policy covers authorized corporate drivers holding valid **GDL (Goods Driving License)** or **E Heavy License**. All Drivers GDL waiver (Endorsement 101) is an optional add-on. |
| **4** | **Key Care / Key Replacement** | Reimburses smart key fob replacement and reprogramming up to RM 1,000–RM 2,000. | **DOES NOT EXIST.** Commercial lorries do not have smart key replacement riders. |
| **5** | **Legal Defense Costs** | Reimburses court legal representation and defense expenses up to RM 2,000 under Road Transport Act 1987. | **Fully Included (RM 2,000).** Standard across **all 7 insurers** in commercial vehicle comprehensive policies. |
| **6** | **Workmanship Warranty** | 12-month to 3-year repair warranty from approved panel repairers. | **12-month repair workmanship warranty** provided by insurers with commercial panel networks (e.g. AmAssurance, Berjaya Sompo). |

---

## 3. Insurer-by-Insurer Comparison (Live Portal Reality)

### 1. Etiqa Insurance & Takaful
- **Private Car**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Emergency Towing Assistance (RM 200), 24/7 Roadside Assistance, Legal Defense Costs (RM 2,000). Add-ons: Windscreen, Special Perils, SRCC, LLP, LLOP, CART, Child Seat, EV Wall Charger, Cash Care DPA Bundles.
- **Commercial Lorry**:
  - **Defaults (RM 0)**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Legal Defense Costs (RM 2,000), Loading & Unloading Third Party Liability.
  - **Towing**: **NONE. DOES NOT EXIST.**
  - **Add-ons**: Commercial Cabin Windscreen (End 89), Special Perils (End 57), SRCC (End 25), Passenger Risk / Cabin Attendant Liability (End 19/100), Commercial CART (End 112), Tailgate & Accessories (End 97), Commercial PA (Driver & Attendant), Ferry Transit (End 109).

### 2. Berjaya Sompo Insurance
- **Private Car**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), SOMPO Roadside Assist (Emergency towing up to RM 300), Legal Defense (RM 2,000), 12-Month Repair Warranty. Add-ons: Windscreen, Special Perils, LLP, LLOP, CART, SOMPO Motor N-hancer.
- **Commercial Lorry**:
  - **Defaults (RM 0)**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Legal Defense Costs (RM 2,000), 12-Month Panel Repair Workmanship Warranty.
  - **Towing**: **NONE. DOES NOT EXIST.**
  - **Add-ons**: Commercial Heavy Windscreen (End 89A), Special Perils (End 57), SRCC (End 25), Passenger Risk / LLP (End 19/100), Commercial CART (End 112), Attached Trailers Cover (End 54), Accidental Boom Damage (End 38A), Mobile Plant Working Risks (End 42).

### 3. Lonpac Insurance
- **Private Car**: Comprehensive Own Damage, TPBI, TPPD (RM 3M), Emergency Towing (RM 200), All Drivers Excess Waiver (21+), Legal Defense (RM 2,000), PC Privilege (Falling Objects, Document Replacement, Inconvenience Allowance).
- **Commercial Lorry**:
  - **Defaults (RM 0)**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Legal Defense Costs (RM 2,000), Commercial Tariff Betterment Scale.
  - **Towing**: **NONE. DOES NOT EXIST.**
  - **Add-ons**: Commercial Windscreen (End 89), Special Perils (End 57), SRCC (End 25), Overturning (End 38), LLOP (End 72), Passenger Risk / Attendants (End 19/100), Increased TPPD (End 105), Crane Boom Damage (End 38A), Tool of Trade (End 41/42).

### 4. AmAssurance / Liberty General Insurance
- **Private Car**: Comprehensive Own Damage, TPBI, TPPD (RM 3M), Emergency Towing (RM 200), 24/7 Roadside Assistance, Legal Defense (RM 2,000), 12-Month Panel Repair Warranty.
- **Commercial Lorry**:
  - **Defaults (RM 0)**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Legal Defense Costs (RM 2,000), 12-Month Panel Repair Workmanship Warranty.
  - **Towing**: **NONE. DOES NOT EXIST.**
  - **Add-ons**: Commercial Windscreen (End 89), Special Perils (End 57), SRCC (End 25), CART (End 112), Authorized Attendants / Employees (End 19i/100), LLOP (End 72), Increased TPPD (End 105), Overturning (End 38), Boom Damage (End 38a), Mobile Plant Tool of Trade (End 41/42).

### 5. QBE Insurance
- **Private Car**: Comprehensive Own Damage, TPBI, TPPD (RM 3M), 24/7 QBE Auto Assist (towing up to RM 300), Legal Defense (RM 2,000), 0% Betterment Waiver (0–10 yrs).
- **Commercial Lorry**:
  - **Defaults (RM 0)**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Legal Defense Costs (RM 2,000), Commercial Tariff Betterment Scale.
  - **Towing**: **NONE. DOES NOT EXIST.**
  - **Add-ons**: Commercial Windscreen, Special Perils, SRCC, Overturning, LLOP, Authorized Attendants / Employees (End 19i/100), Increased TPPD, Boom Damage, Tool of Trade.

### 6. STMB (Syarikat Takaful Malaysia Berhad)
- **Private Car**: Comprehensive Own Damage, TPBI, TPPD (RM 3M), 24/7 Tele Bantuan (towing up to RM 300), Legal Defense (RM 2,000), No Claim Cashback (Hibah surplus).
- **Commercial Lorry**:
  - **Defaults (RM 0)**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Legal Defense Costs (RM 2,000), No Claim Cashback (Distributable surplus via Hibah), Authorized GDL Drivers Coverage, Commercial Tariff Betterment Scale.
  - **Towing**: **NONE. DOES NOT EXIST.**
  - **Add-ons**: Commercial Windscreen, Special Perils, SRCC, LLP (End 100), LLOP (End 72), Cargo Protection / Carrier Liability, Increased TPPD.

### 7. Tune Protect Insurance
- **Private Car**: Comprehensive Own Damage, TPBI, TPPD (RM 3M), Emergency Towing (RM 200), Legal Defense (RM 2,000).
- **Commercial Lorry**:
  - **Defaults (RM 0)**: Comprehensive Own Damage, Third Party BI, TPPD (RM 3M), Legal Defense Costs (RM 2,000), Commercial Tariff Betterment Scale.
  - **Towing**: **NONE. DOES NOT EXIST.**
  - **Add-ons**: Commercial Heavy Windscreen, Special Perils, SRCC, Authorized Attendants / Loaders (End 19i/100), All Drivers GDL (End 101), Increased TPPD, Thailand Extension, Boom Damage (End 38A), Tool of Trade (End 41/42), Motorist PA Commercial (Plans B, C, D, E).

---

## 4. Top-Right "Free Added Coverage" Rules

### Commercial Lorry (Own Goods C-Permit / General Haulage A-Permit / Rigid Truck / Prime Mover)

```text
GROUND-TRUTH TOP-RIGHT CARD:
[✓] Legal Defense Costs (RM 2,000.00)        - Court legal representation & defense reimbursement under RTA 1987
[✓] Panel Repair Workmanship Warranty        - 12-month repair quality warranty from approved repairers (where applicable)
[✓] No Claim Cashback (Distributable Surplus)- Islamic surplus sharing via Hibah if no claims (STMB only)
[✓] Genuine Extracted Quotation FOC Perks    - Any specific free perk extracted directly from the uploaded quotation

STRICTLY BANNED / EXCLUDED FOR COMMERCIAL VEHICLES:
[X] Emergency Towing Assistance              - DOES NOT EXIST in agent portals
[X] Unlimited Towing                         - DOES NOT EXIST in agent portals
[X] Drive-Less Save-More                     - Passenger car telematics perk only
[X] Child Car Safety Seat                    - Passenger car perk only
[X] Key Care Replacement                    - Passenger car perk only
[X] 24/7 Commercial Claims Hotline           - Generic padding / fluff rejected
```

---

## 5. Bottom 24-Card Add-on Matrix: Strict Vehicle Separation

### Private Car Matrix
- Retains private passenger & EV items: `Windscreen`, `Unlimited Towing`, `LLOP`, `LLP`, `Special Perils`, `All Drivers`, `Motor PA Plus`, `Betterment Waiver`, `SRCC`, `Respray`, `CART`, `Accessories`, `NCD Protector`, `Key Care`, `International Towing`, `EV Wall Charger`, `EV Out of Charge Towing`, `EV Charger Liability`, `E-Hailing`, `Inconvenience Allowance`, `Flood Cleaning`, `Natural Falling Objects`, `Gas Conversion`, `Child Seat`.
- Hides commercial crane/goods endorsements (`Boom Damage`, `Overturning`, `Third Party Working Risk`, `Non-Fare Paying Passenger`).

### Commercial Vehicle Matrix
- **Completely removes all Towing & Consumer EV/E-Hailing cards**:
  - NO `towing`
  - NO `international_towing`
  - NO `ev_wall_charger`
  - NO `ev_out_of_charge`
  - NO `ev_charger_liability`
  - NO `ehailing`
  - NO `key_care`
  - NO `child_seat`
- **Displays genuine commercial endorsements**:
  1. Commercial Heavy Windscreen (End 89)
  2. Special Perils / Flood (End 57)
  3. Strike, Riot & Civil Commotion (SRCC - End 25)
  4. Legal Liability to Non-Fare Paying Passengers / Cabin Attendants (End 100 / End 19)
  5. Legal Liability of Passengers (End 72)
  6. Commercial CART / Vehicle Downtime (End 112)
  7. Commercial All-Authorized Drivers GDL (End 101)
  8. Commercial Driver & Crew PA (Motorist PA Commercial)
  9. Hydraulic Tailgate & Accessories (End 97)
  10. Increased TPPD Limit (End 105)
  11. Crane Boom Damage (End 38A)
  12. Mobile Plant Tool of Trade & Working Risks (End 41 / End 42)
  13. Damage by Overturning (End 38)
  14. Attached Trailers & Haulage Units (End 54)
  15. Marine Ferry Transit (End 109)
  16. Cross-Border Haulage Extension (Thailand / Kalimantan)
  17. Goods in Transit / Carrier Cargo Liability
  18. Gas Conversion Kit & Tank Cover (NGV Commercial)
  19. Accidental Collision Downtime Cash Allowance
  20. Loading & Unloading Working Operations Liability
  21. Un-named Cabin Loader PA Endorsement
  22. Commercial Replacement Vehicle Hire Allowance
  23. Current Year NCD Relief (Commercial Fleet End 111)
  24. Commercial Legal Defense Extension
