# PLAN 2: Workspace UI Streamlining & The 3-Eye Multimodal AI Evaluation Model

> **UI Rationalization & 3-Eye Autonomous Quality Gate Blueprint**
> **Scope:** Clean up both workspaces (purge the 23 clutter fields from Quotation Workspace and redundant vehicle/customer fields from Comparison Modal), build the interactive Box 1 (Free) vs Box 2 (Paid) benefit switcher, enforce powertrain card filtering (no EV on petrol), and establish the full **3-Eye Multimodal AI Evaluation Consensus Architecture** for unattended overnight batch processing.

---

## 1. Marketing Comparison Modal Streamlining (`manual-quote-modal.tsx`)

### The Cleanup Mandate
- **Permanently Remove from "Edit Underwriter Quote" Modal:**
  - Customer Name, IC / Business Reg No., Customer Address
  - Chassis No., Engine No., Capacity / Unit
  - Road Tax and Runner Fee
  *(These live exclusively in the Customer & Vehicle Ledger at the top of the tenure page).*

### The Clean Underwriter Edit Form:
1. **Underwriter Identity:** Company Name, Insurer Quotation Reference No.
2. **Valuation & Sum:** Sum Insured (RM), Valuation Type (`Market Value` vs `Agreed Value`), Agreed Value toggle.
3. **Financials:** Net Motor Premium (RM), Policy Excess (RM).
   - *Total Payable is calculated automatically:* $\text{Net Premium} + \text{Road Tax} + \text{Runner Fee (RM 20.00)}$.
4. **Key Perils:** Towing Limit (e.g. `50 KM`, `200 KM`, `Unlimited`), Windscreen Coverage (RM), Special Perils / Flood, LLP / LLOP, Waiver of Betterment.
5. **Notes & Ranking:** Endorsement notes, deterministic ranking (Rank #1, #2, #3 based on price).

---

## 2. Quotation Workspace Streamlining (`policy-fields-card.tsx`)

### The Cleanup Mandate
- **Permanently Remove:**
  - 23 secondary technical clutter fields (raw layout tags, unmapped JSON, duplicated dates).
  - The fake subtraction math that deducted extras to fabricate `RM 1,589.00`.

### The Exact Streamlined Canonical Fields:
1. **Top Header & Identity:**
   - Quotation Ref: `RL260001131`
   - Vehicle No: `WFW8977`
   - Insurer Name: `QBE` (with official underwriter logo)

2. **Vehicle Information (车辆资料):**
   - Customer / 客户姓名: `YAU YEN CHEN`
   - Period Of Insurance / 保障期限: `08-11-2026 to 07-11-2027`
   - Coverage Type / 保障种类: `Third Party` / `Comprehensive`
   - Car Model / 车型: `HONDA CIVIC`
   - NCD / 无索偿折扣: `45.00%`
   - Valuation Type / 估价方式: `Market Value` / `Agreed Value`
   - Policy Excess / 自负额: `RM 0.00`
   - Vehicle Sum Insured / 车辆保额: `RM 0.00` (or agreed amount)

3. **Premium Summary (保费):**
   - Insurance Premium / 保费: `RM 335.00` (True net underwriter premium)
   - Roadtax and Runner Fee / 路税及服务费: `RM 298.80` (Road Tax `RM 278.80` + Runner Fee `RM 20.00`)
   - TOTAL PAYABLE 应付总额: `RM 633.80` ($\text{Net Premium} + \text{Tax} + \text{Runner}$)

4. **The Two Benefit Catalogs (Movement & Editability):**
   - **Box 1: Free Added Coverage (Included by Insurer):**
     Complimentary covers like Emergency Towing, Legal Defense, Drive-Less Save-More, Child Car Safety Seat.
   - **Box 2: Add-On Upgrades ++ (Purchased Add-Ons):**
     Paid covers like Windscreen, LLP, LLOP, All Drivers Waiver, Special Perils.
   - **Interactive Switcher:** Clicking a button moves an item cleanly between Box 1 (Free) and Box 2 (Paid), updating `DraftBenefitSelection.item_kind` and `cost_status`.
   - **Powertrain Card Filter:** If vehicle is `ICE` (Petrol/Diesel), suppress cards 07, 08, 09 (EV Wall Charger, EV Battery Towing, EV Liability) on the Design 2 canvas and replace with ICE perils.

---

## 3. The 3-Eye Multimodal AI Evaluation Consensus Architecture

This is the multi-level perception engine that guarantees **100% zero-defect, zero-touch overnight batch processing**:

```
                  ┌──────────────────────────────────────────────┐
                  │          Uploaded Source PDF(s)              │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │ EYE 1: Multimodal Source Intelligence AI      │
                 │ (Extracts true document intent, terms & sums) │
                 │ - Gemini Multimodal pool (No regex)           │
                 │ - Vehicle, Financials, All Riders, Deduplicated│
                 └───────────────────────┬───────────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │        Unified Single-Source Data Layer       │
                 │  (Canonical Vehicle, Coverage, Ledger & Perils)│
                 └──────────────┬─────────────────┬──────────────┘
                                │                 │
               ┌────────────────┘                 └────────────────┐
               ▼                                                   ▼
┌───────────────────────────────┐               ┌──────────────────────────────────┐
│  Comparison Matrix Workspace  │               │   Quotation Workspace (Design 2) │
│    (Rendered DOM / Table)     │               │     (Rendered A4 Canvas / PDF)   │
└──────────────┬────────────────┘               └──────────────────┬───────────────┘
               │                                                   │
               ▼                                                   ▼
     [ Snapshot Image 1 ]                                 [ Snapshot Image 2 ]
               │                                                   │
               └────────────────────────┬──────────────────────────┘
                                        │
                                        ▼
                 ┌───────────────────────────────────────────────┐
                 │ EYE 2 & EYE 3: AI Referee & Visual Auditor    │
                 │ 1. EYE 2: Source PDF vs Comparison Snapshot   │
                 │ 2. EYE 3: Comparison Winner vs Design 2 PDF   │
                 │ 3. 3-Way Strict Parity & Certification Gate   │
                 └───────────────────────┬───────────────────────┘
                                         │
                  ┌──────────────────────┴───────────────────────┐
                  ▼                                              ▼
          [ All 3 Match 100% ]                          [ Any Drift / Conflict ]
                  │                                              │
                  ▼                                              ▼
        ✅ GREEN LIGHT SEAL                              ⚠️ HARD STOP & FLAG
     (Ready for Instant Dispatch)                (Pinpoints exact drift; blocks
                                                  dispatch until corrected)
```

### The 3 Eyes in Detail:

#### EYE 1: Multimodal Source Intelligence (Input PDF $\rightarrow$ Structured Truth)
- **Role:** Extracts the complete truth directly from the source underwriter quotation PDF using Gemini Multimodal vision.
- **Coverage:**
  - Coverage tier (Comprehensive vs TPFT vs Third Party).
  - Own Damage Sum Insured (Strictly RM 0.00 for Third Party; isolates chassis/engine digits).
  - Net Motor Premium, NCD %, excess schedules, and all rider perils with their sub-limits and costs.
  - Vehicle identification (Plate, Make, Model, Year, CC, Chassis, Engine).
- **Rule:** **Zero procedural regex overrides.** Python code is never allowed to override what multimodal vision extracted.

#### EYE 2: Comparison Workspace Table Auditor (Source PDF vs Comparison Matrix)
- **Role:** Scans the live rendered Comparison Matrix against the Source Facts extracted by Eye 1.
- **Audit Checklist:**
  - Are underwriter cards displaying the exact net premiums from the source quotes?
  - Are vehicle names, plates, and years uniform across all columns?
  - Are fixed costs (Road Tax and Runner Fee = RM 20.00) uniform across every column?
  - Are ranks (1, 2, 3) mathematically ordered by total payable without duplicates?
  - Did any column suffer corruption or drift before winner selection occurs?

#### EYE 3: Quotation Workspace Visual Parity Auditor (Comparison Winner vs Design 2 PDF)
- **Role:** The final pre-flight delivery gate before client dispatch. Compares the generated Design 2 PDF against the original insurer quote and the Comparison Matrix selected winner.
- **Audit Checklist:**
  - **Premium & Totals:** Does the client PDF print the true Net Premium (`RM 335.00`), Road Tax + Runner (`RM 298.80`), and Total Payable (`RM 633.80`) with zero mathematical gap ($A + B = C$ to the exact cent)?
  - **Benefit Alignment:** Are all complimentary covers in **Box 1** and all purchased add-ons in **Box 2** matching the insurer quote?
  - **Powertrain Integrity:** Are EV wallbox / EV battery towing cards strictly suppressed on Petrol/Diesel vehicles?
  - **Visual Layout:** Is any text clipped, wrapped, or missing?
- **Decision:**
  - **100% Match:** Affixes `AuditSeal: PASS` and green-lights instant overnight client dispatch.
  - **Mismatch:** Halts dispatch, outputs the exact conflicting field and delta, and flags it for review.

---

## 4. Execution Tasks for Plan 2

- [x] **Task 2.1: Prune Comparison Modal (`manual-quote-modal.tsx`)**
  - Removed Customer Name, IC, Address, Chassis, Engine, CC from the modal (anchored strictly in Customer & Vehicle Ledger).
  - Simplified layout into Underwriter Identity, Valuation & Sum, Financials (Net Premium + Excess), and Key Perils.
- [x] **Task 2.2: Streamline Quotation Workspace (`policy-fields-card.tsx`)**
  - Removed 23 secondary clutter fields (`ADVANCED_POLICY_FIELDS` and `extraExtractedFields`).
  - Purged fake subtraction math in `draft_mapper.py` that deducted extras from underwriter total contribution.
  - Formatted 3 clean canonical sections: Top Header & Identity (3 fields), Vehicle Info (8 canonical fields + auxiliary), and Premium Summary (3 fields + total).
- [x] **Task 2.3: Build Box 1 vs Box 2 Benefit Switcher & Powertrain Filter**
  - Standardized Box 1 (`cost_status: "included"`) and Box 2 (`cost_status: "paid"`) with two-way switcher in `benefit-cards.tsx` and `workspace_patch_service.py`.
  - Enforced powertrain check across `unified_addon_engine.py` and `unified-addon-engine.ts` suppressing cards 07, 08, 09 (EV Wall Charger, EV Battery Towing, EV Liability) on Petrol/Diesel cars and filling 24-card matrix with canonical ICE perks.
- [x] **Task 2.4: Implement Eye 2 Comparison Auditor & Eye 3 Pre-Flight Referee**
  - Wired Eye 2 in `backend/app/extraction/referee.py` (`audit_comparison_matrix_consensus`) auditing road tax parity, universal RM 20 runner fee, mathematical validity, and duplicate rank prevention.
  - Wired Eye 3 in `backend/app/extraction/visual_referee.py` (`audit_pdf_visual_consensus`) auditing generated Design 2 PDF against winner quotation.
  - Implemented `verify_3_eye_consensus` executing Eye 1, Eye 2, and Eye 3 in series with `audit_seal: "PASS"` gating unattended overnight batch dispatch.
