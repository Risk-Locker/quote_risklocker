# ENTERPRISE LEVEL Extraction - 2026-11-16 18:30

> **Master Architecture & Field Rationalization Plan**
> **Scope:** Cleanse, streamline, and permanently unify the **Marketing Comparison Workspace** and the **Quotation Workspace** into a single synchronized database core. Purge all clutter, redundant duplicate fields, and toxic overrides. Establish the 3-Tier Multi-Level AI Master validation loop.

---

## 1. The Core Problem & User Mandate

### The Current Disorder
1. **Clutter & Redundancy in "Edit Underwriter Quote" (Comparison Workspace):**
   - Inside each individual underwriter quote modal, the UI was displaying and duplicating:
     - Customer Name, IC / Business Reg No., Customer Address
     - Chassis No., Engine No., Capacity / Unit
     - Road Tax & Runner Fee calculations
   - **User Mandate:** Remove these from the underwriter quote modal completely. They belong solely to the **Customer & Vehicle Ledger** at the top of the page. Underwriter quotes should ONLY contain insurer-specific pricing, coverage terms, and benefits.

2. **Clutter & Over-Engineering in Quotation Workspace:**
   - The review workspace was rendering 18 primary fields + 23 secondary fields + dozens of unmapped extraction keys (41+ input boxes!).
   - In live testing, `draft_mapper.py` reverse-engineered fake premiums (`RM 1,589.00`) by subtracting extras, causing the client PDF to display $1,589 + 850.40 = 2,834.00$ (a mathematically impossible quotation).
   - Windscreen was detected twice (`RM 345.00` + `RM 345.00`), age loading (`RM 50.00`) was misclassified as an optional rider, and EV wallbox cards were printed on a petrol car.
   - **User Mandate:** Strip out the 23 secondary junk fields. Retain **only the exact essential fields** needed to control and verify the quotation.

3. **Single Database Core (Zero Separate Versions / Zero Drift):**
   - The vehicle specifications, customer identity, and shared fees live in **one canonical record**.
   - If an agent or AI edits the vehicle model, plate, or customer name in ANY quotation, it immediately updates across all other quotation options and the vehicle ledger simultaneously.
   - When an underwriter is picked as the winner in Comparison, the exact same ledger, pricing, and benefits feed directly into the Quotation Workspace and Design 2 canvas.

---

## 2. Definitive Field Pruning & Workspace Schemas

### A. Customer & Vehicle Ledger (Shared Single Source of Truth)
*Managed once at the top of the tenure. Linked to all quotes. Changing here updates ALL quotes.*

| Field | Description / Rules |
| :--- | :--- |
| **`customer_name`** | Policyholder name (e.g. `YAU YEN CHEN`) |
| **`ic_or_brn`** | NRIC or Company Business Reg No. (e.g. `860630-43-5720`) |
| **`vehicle_no`** | Normalized registration plate (e.g. `WFW8977`) |
| **`car_brand` & `car_model`** | Normalized vehicle make and model (e.g. `HONDA CIVIC`, no brand duplication) |
| **`vehicle_year`** | Year of manufacture (e.g. `1997`) |
| **`engine_cc`** | Engine capacity (e.g. `1797 CC`) |
| **`vehicle_type`** | Classification: `Car (Private Saloon)` / `Non-Saloon (SUV/MPV)` / `Commercial` |
| **`powertrain`** | `ICE` (Petrol/Diesel) vs `EV`. **Controls EV card suppression on Design 2.** |
| **`chassis_no`** | Chassis / VIN (e.g. `EJ7906208`). Isolated from financial extraction. |
| **`engine_no`** | Engine identification (e.g. `B18C1400290`) |
| **`coverage_period`** | Start Date to End Date (e.g. `08/11/2026 - 07/11/2027`) |
| **`road_tax`** | Authoritative JPJ calculation (e.g. `RM 278.80`) |
| **`runner_fee`** | **Universal Flat Fee: Strictly RM 20.00** across the entire platform |
| **`ncd_percentage`** | NCD entitlement (e.g. `45.00%`) |

---

### B. Marketing Comparison Workspace: Cleaned "Edit Underwriter Quote"
*Removed: Customer Name, IC, Address, Chassis, Engine, CC, Roadtax, Runner Fee.*
*Retained ONLY the fields unique to this underwriter:*

| Section | Clean Field Name | Input Type | Description |
| :--- | :--- | :--- | :--- |
| **Insurer Info** | `company_name` | Select / Text | e.g. `QBE`, `Takaful Malaysia`, `Etiqa` |
| | `source_quotation_no` | Text | Insurer quotation reference (e.g. `Q233260002196`) |
| **Valuation & Sum**| `sum_insured` | Money | Vehicle sum insured (Strictly `RM 0.00` for Third Party) |
| | `valuation_type` | Select | `Market Value` vs `Agreed Value` |
| | `agreed_value` | Checkbox | Quick toggle for Agreed Value endorsement |
| **Pricing** | `net_motor_premium` | Money | True net motor insurance premium payable to underwriter |
| | `excess` | Money | Policy excess (e.g. `RM 0.00`) |
| | `total_payable` | Display/Auto | Automatically: `net_motor_premium + road_tax + runner_fee` |
| **Key Perils** | `towing_limit` | Text / Select | e.g. `RM 500`, `50 KM`, `200 KM`, `Unlimited` |
| | `windscreen_sum` | Money | Windscreen coverage amount (e.g. `RM 1,500.00`) |
| | `special_perils` | Text / Select | `Included` or rate (e.g. `0.20%`) |
| | `llp_llop` | Text / Select | `Included` or amount |
| | `waiver_betterment`| Checkbox | Waiver of betterment endorsement |
| | `notes` | Text | Endorsement notes (e.g. `Workshop panel only`) |
| **Rank** | `rank` | Number / Badge | Deterministic order: **Rank #1, Rank #2, Rank #3** |

---

### C. Quotation Workspace: The Exact Streamlined Fields
*Removed: 23 secondary clutter fields, fake reverse-engineered math, unclosed layout keys.*
*Retained ONLY the exact fields that define the customer quotation:*

#### 1. Header & Identity
- **Quotation Ref**: `RL260001131` (Generated Risklocker official reference)
- **Vehicle No**: `WFW8977`
- **Insurer Name**: `QBE` (with insurer logo)

#### 2. Vehicle Information (车辆资料)
- **Customer / 客户姓名**: `YAU YEN CHEN`
- **Period Of Insurance / 保障期限**: `08-11-2026 to 07-11-2027`
- **Coverage Type / 保障种类**: `Third Party` / `Comprehensive`
- **Car Model / 车型**: `HONDA CIVIC`
- **NCD / 无索偿折扣**: `45.00%`
- **Valuation Type / 估价方式**: `Market Value` / `Agreed Value`
- **Policy Excess / 自负额**: `RM 0.00`
- **Vehicle Sum Insured / 车辆保额**: `RM 0.00` (or agreed amount)

#### 3. Premium Summary (保费)
- **Insurance Premium / 保费**: `RM 335.00` (Extracted true net underwriter premium)
- **Roadtax and Runner Fee / 路税及服务费**: `RM 298.80` (Road Tax `RM 278.80` + Runner Fee `RM 20.00`)
- **TOTAL PAYABLE 应付总额**: `RM 633.80` ($\text{Net Premium} + \text{Roadtax} + \text{Runner Fee}$)
*(Zero subtraction heuristics. Math balances $A + B = C$ to the exact cent.)*

#### 4. The Two Benefit Catalogs (Movement, Switchability & Editability)
- **Box 1: Free Added Coverage (Included by Insurer / Complimentary)**
  - Items that come free with the policy.
  - Examples: `Emergency Towing Assistance (RM 200.00)`, `Legal Defense Costs (RM 2,000.00)`, `Drive-Less Save-More`, `Child Car Safety Seat`.
  - Feature: One-click switchability to move items between Free (Box 1) and Paid Add-on (Box 2).
- **Box 2: Add-On Upgrades ++ (Purchased Optional Covers)**
  - Extra endorsements selected or purchased by the client.
  - Examples: `Windscreen (Sum RM 1,500 / Cost RM 225)`, `Legal Liability of Passengers`, `Legal Liability to Passengers (RM 41.85)`, `All Drivers Excess Waiver`.
  - Feature: Clear display of Limit / Sum Insured + Premium Cost. Deduplicated by concept code so duplicates (like double windscreen) can NEVER occur.

---

## 3. The 3-Tier Multi-Level AI Master Evaluation Architecture

To ensure zero human errors, unattended overnight batch dispatch, and 100% precision:

```
                  ┌──────────────────────────────────────────────┐
                  │          Uploaded Source PDF(s)              │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │ TIER 1: Multimodal Source Intelligence (AI)   │
                 │ - Sharded Gemini Pool (3 Keys x 2 Models)     │
                 │ - Direct 2D visual layout extraction          │
                 │ - Full breakdown: Vehicle, Policy, Deduplicated│
                 │   Riders, Financial Ledger                    │
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │ TIER 2: Actuarial Math & Integrity Gate (Code)│
                 │ - Gross = Basic - NCD + Sum(Riders)           │
                 │ - Total = Net Premium + Road Tax + Runner Fee │
                 │ - Third Party => Sum Insured == 0.00          │
                 │ - Powertrain Filter: Suppress EV cards on ICE │
                 │ - Cent-accuracy check: Halt & flag if delta>0 │
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │ TIER 3: Visual Parity Referee & Pre-Flight AI │
                 │ - Compares Source PDF vs Generated Design 2   │
                 │ - Line-by-line rider audit (Box 1 & Box 2)    │
                 │ - Visual layout audit (No clipped/hidden text)│
                 │ - 100% Match -> GREEN LIGHT DISPATCH SEAL     │
                 │ - Any Mismatch -> Auto-reconcile or Flag      │
                 └───────────────────────────────────────────────┘
```

### AI Master Roles:
1. **Tier 1 (The Reader - Gemini 3.5 Flash / Flash Lite Pool):**
   - Multimodal perception. Reads messy tables, multi-column layouts, and endorsements directly from PDF coordinate space.
   - Outputs strict typed Pydantic structure. Zero regex interference.
2. **Tier 2 (The Accountant - Deterministic Actuarial Engine):**
   - 100% mathematical precision. Checks that $\text{Net} + \text{Tax} + \text{Runner} = \text{Total}$ to the exact cent.
   - Isolates chassis and engine numbers. Enforces Third Party = RM 0.00.
   - Suppresses EV cards on ICE vehicles.
3. **Tier 3 (The Auditor & Referee - Multimodal Visual Pre-Flight):**
   - Inspects the rendered Design 2 PDF against the original insurer PDF.
   - Acts as the final quality gate: if an add-on was dropped, a cost is missing, or a number is misaligned, Tier 3 halts dispatch and flags the exact line.
   - If 100% verified, affixes `AuditSeal: PASS` for automatic batch dispatch.

---

## 4. Execution Sequence for Implementation (Fresh Chat Ready)

### Phase 1: Shared Core & Fee Unification
1. Lock global `RUNNER_FEE = Decimal("20.00")` across backend and frontend.
2. Remove Customer Name, IC, Address, Chassis, Engine, CC from `manual-quote-modal.tsx`.
3. Implement `sync_tenure_vehicle_data` so editing vehicle info updates all attached quotes simultaneously.

### Phase 2: Quotation Workspace Streamlining & Math Restoration
1. Purge the 23 secondary junk fields in `policy-fields-card.tsx`.
2. Delete the fake subtraction math in `draft_mapper.py` and `sessions.py`.
3. Enforce the exact 3 sections: Vehicle Information, Premium Summary, and the 2 Benefit Boxes.

### Phase 3: Benefit Deduplication & Powertrain Card Filtering
1. Implement strict rider deduplication by concept key (preventing duplicate windscreen).
2. Separate age loadings/surcharges from optional add-ons.
3. Implement powertrain check on Design 2 canvas to hide EV cards (07, 08, 09) on Petrol/Diesel cars.

### Phase 4: Actuarial Balance Gate & Tier 3 Visual Referee
1. Add `validate_actuarial_balance` in Python backend.
2. Add `VisualParityReferee` service utilizing Gemini multimodal vision to audit the rendered PDF.
3. Wire the automated batch runner with green-light seal for overnight dispatch.
