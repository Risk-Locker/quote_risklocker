# Complete Serial Chronicle & Idea Specification (`idea.md`)

> **Document Purpose:** An exact, unfiltered, and unmanipulated serial record of all requirements, problems, questions, architectures, analogies, numbers, and operational critiques provided by the user from Message #1 through Message #20.
> **Date:** 2026-11-13
> **Project:** Risklocker Motor Quotation Platform (`quote.risklocker.com`)

---

## 1. Chronological Timeline of User Requests & Discussions

---

### Step 1: The Template Builder Dilemma & Design 2 Reality (Messages #1 & #2)

#### The Problem Stated by the User:
- The drag-and-drop block designer / template builder is over-complicated, clunky, and unnecessary.
- There are two worlds in the platform:
  1. The legacy template builder / block designer.
  2. The new **Design 2 (Modern 4-Column Grid)** template, which the user confirmed is **99.9% perfect, looks awesome, and is accepted by the company**.
- **User Question:** *"Do we really need the quotation designer or builder or not? It is complicating things more. Rather, what if we use a fixed template of coding where we can automatically generate code and the template changes accordingly? How was Design 2 set up so perfectly, and how are the benefits and add-ons set inside Design 2?"*

---

### Step 2: Unifying Bilingual Agency Motor & "Template as the Builder" (Message #3)

#### The Problem Stated by the User:
- In the system, there are 3 separate legacy Bilingual Agency templates:
  1. `Bilingual Agency Motor v4` (Itemized extras)
  2. `Bilingual Agency Motor v4 (No Extras)` (Extras completely hidden)
  3. `Bilingual Agency Motor v4 (Lump Sum Extras)` (Single lump-sum extras line)
- **User Core Idea:** *"Instead of having 3 separate database templates for Bilingual Agency, is it possible to have ONE single template, but on the motor quotation page we have an option directly of what to hide or what to do?"*
- *"Think like the template itself is the builder. On the quotation page we do things directly."*
- **Benefits Assignment Question:** *"Is the system perfectly assigning accurate benefits or is it feeding whatever it got? Each insurance company has their own list of benefits, so that must be maintained."*
- **Design 2 Primacy:** Design 2 is confirmed as the primary standard accepted by the company. Minor logo issues will be cleaned up, but the structure is the gold standard. In the future, if the company asks to add or hide a line, there must be a clean way to adjust without breaking things.

---

### Step 3: Company Rules, Fixed 24 Matrix, Dynamic Towing & Betterment Math (Messages #4 & #5)

#### 1. Hybrid Model: Company-Specific Rules + Smart Normalization
- Each underwriter has unique benefit names and packages. The system must maintain accurate underwriter-specific benefits, not generic guesses.

#### 2. Bilingual Agency Template Naming
- Stop calling it `v4`. Either keep it as a secondary template (`Bilingual Agency Motor (Design 1)`) or mark legacy rows as stale/deprecated. Keep things simple.

#### 3. Design 2 Constraints & Fixed 24 Benefits Boundary
- Design 2 is the default across the application.
- Design 2 has a **fixed 24 benefit cards matrix** (A4 page boundary: 6 rows × 4 columns).
- Insurance catalogs must be curated so each company fits cleanly within these 24 cards on Page 1.

#### 4. The Towing Variable Phenomenon (Most Critical & Confusing Feature)
- Towing is the single most important, scrutinized feature for every customer, from poor to super rich:
  - By default, comprehensive motor insurance provides basic emergency towing (e.g. up to RM 200 or 50 km).
  - In Design 2, this sits in the Top-Right "Free Added Coverage" card:
    - **Default:** `EMERGENCY TOWING ASSISTANCE` — *"24/7 towing service to the nearest approved repairer up to RM 200"*.
  - When a customer purchases a paid rider/add-on (e.g. Etiqa `OTO 360`, Takaful `Motor PA Plus Plan 4`, `DPP/N4`):
    - The Top-Right card must dynamically **upgrade in-place**:
      - Title becomes: **`UNLIMITED TOWING ASSISTANCE`**
      - Description becomes: *"24/7 accidental towing to nearest approved repairer with unlimited mileage (Upgraded via OTO 360)"*.
    - If `Motor PA Plus Plan 3` is selected, it updates to extended towing (e.g. 300 km or RM 500).
    - **Crucial deduplication rule:** In the bottom 24-card matrix, the paid rider (`OTO 360` / `Motor PA Plus Plan 4`) gets a green checkmark `[✔]`, while the redundant generic unselected `Unlimited Towing` card must be **suppressed completely** so there are never two conflicting towing cards confusing the customer.

#### 5. Betterment of Waiver (Exact Calendar Age Math)
- The user pointed out that calculating vehicle age by simple year subtraction (`2026 - 2016 = 10 years`) is blatantly wrong.
- **Exact Case:** A vehicle registered on `2016-06-15` with quotation inception on `2026-06-14` is **9 years, 11 months, and 29 days old**.
- In Malaysian motor insurance (PIAM tariff / Endorsement 113), this vehicle is strictly **9 completed years** (35% scale), NOT 10 years (40% scale). The system must calculate exact completed calendar years using true date math.

#### 6. System Context & Learning Memory
- How does the system remember and learn underwriting terminology over time?
- Einstein formula analogy: *"For Einstein, he might have notes where formulas are written every day, but that doesn't mean without the note his mind is empty. If his note gave E=mc, after a few months his mind gave E=mc²."*
- When the system scans PDF quotations from different underwriters and sees abbreviations (like `EVBA 200` for EV Battery Appliance, or `Driver PA` vs `Driver Passenger Accident`), it should map and retain these associations rather than being permanently dumb.

---

### Step 4: Google AI Studio Reality, Quota Limits & Account Ban Risk (Messages #6 to #9)

#### The Real Setup Stated by the User:
- **10 Separate Google Accounts:** The user carefully created 10 separate Google accounts, generating **exactly 1 API key per account**.
- Currently, 2 of these API keys are entered into `quote.risklocker.com`.
- **Zero Key Mixing:** Never generate multiple API keys under the same project or reuse the same key across different apps.

#### The Real Models & Google AI Studio Free Tier Caps:
As verified on the user's Google AI Studio dashboard (`gen-lang-client-0587737993`):

| Model | Category | RPM (Requests/Min) | TPM (Tokens/Min) | RPD (Requests/Day) |
| :--- | :--- | :--- | :--- | :--- |
| **Gemini 3.1 Flash Lite** | Text-out | 15 RPM | 250,000 TPM | 500 RPD |
| **Gemini 3.5 Flash Lite** | Text-out | 15 RPM | 250,000 TPM | 500 RPD |
| *Other Models (e.g. Gemini 3.8 Flash)* | Text-out | 5 RPM | 250,000 TPM | **20 RPD only** (DANGEROUS) |

#### The Hard Account Ban Danger:
- **If 16 requests hit a model in 1 minute, or if requests exceed 500 in a day, Google permanently bans the entire Google account.** There is no recovery.
- `gemini-3.8-flash` has a lethal limit of only **20 requests per day**. Calling it even a few times can exhaust the quota and ban the account. It must be completely purged from production.
- **The Safe Production Cap per Slot:**
  - **13 RPM** (keeping 2 requests as safety buffer below 15)
  - **200,000 TPM** (keeping 50,000 tokens safety buffer below 250k)
  - **480 RPD** (keeping 20 requests safety buffer below 500)

#### The Slot Architecture:
- 1 API Key = 1 Google Account = **2 Independent Model Slots** (`gemini-3.1-flash-lite` + `gemini-3.5-flash-lite`).
- If 2 API keys are configured, the system has **4 parallel model slots** (Total capacity: $4 \times 13 = 52\text{ RPM}$, $4 \times 480 = 1,920\text{ RPD}$).
- If 4 API keys are configured, the system has **8 parallel model slots**.

---

### Step 5: The Wheat Mill Analogy & Strict Mesh Equilibrium Dispatcher (Messages #9, #10, #11)

#### The Wheat Mill Analogy:
> *"Think of it like a machine of flour distribution using wheat. The system has 2 wheat mills. Each wheat mill has 2 wheat machines from which exactly 12 kg of wheat can be purchased from each machine (2 machines = 24 kg). Now we have a village mentor who assigns the villagers tickets:*
> *4 tickets for machine 1, 2 tickets for machine 2, 3 tickets for machine 3, 1 ticket for machine 4, and each ticket is stapled in a serialized manner. They cannot just go and dump them all together. They have to follow strict serialization."*

#### Strict Serialized Round-Robin Distribution:
- When PDFs or requests arrive, the system must NOT dump requests into one API key while leaving another key at 0.
- Requests must be packaged as standalone units: **`[ Request ] -> Slot i = (Key k, Model m)`**.
- For 4 API keys (8 slots) and 20 PDFs:
  - 1st PDF $\rightarrow$ Account 1, Slot 1 (`gemini-3.1-flash-lite`)
  - 2nd PDF $\rightarrow$ Account 1, Slot 2 (`gemini-3.5-flash-lite`)
  - 3rd PDF $\rightarrow$ Account 2, Slot 1 (`gemini-3.1-flash-lite`)
  - 4th PDF $\rightarrow$ Account 2, Slot 2 (`gemini-3.5-flash-lite`)
  - 5th PDF $\rightarrow$ Account 3, Slot 1
  - 6th PDF $\rightarrow$ Account 3, Slot 2
  - 7th PDF $\rightarrow$ Account 4, Slot 1
  - 8th PDF $\rightarrow$ Account 4, Slot 2
  - 9th PDF $\rightarrow$ Cycles back to Account 1, Slot 1, and so on ($i \pmod S$).
- If 130 requests occur over 5 days across 4 slots, each slot must have ~30 to 35 requests. Perfect equilibrium.

---

### Step 6: The "Living Eye" (Person Standing in Between) (Messages #12 & #13)

#### The Concept:
> *"I need someone to stand in between and look at it. How to put an eye — an actual eye? Why is it just rigid math? Why not something like you put a person there who checks every second, thinks, and decides? Why send 13 requests? Why not 11? Why not 10? If there are 52 PDFs, why dump all of them together? Put less. I need an eye — a real one."*

- The pacer cannot be a static, dumb mathematical formula.
- It must act like an attentive sentinel standing between the incoming queue and Google's servers:
  - If Google's response latency slows down (>4.0s), the sentinel backs off and adds breathing time between calls.
  - It checks token weights and spacing every second before letting a request through.

---

### Step 7: Staging Workflows, Token Weighing & Fleet Meter (Message #14)

#### Two Real-World Staff Upload Scenarios:
1. **Interactive Rush:** Staff opens the app, uploads 5 quick quotations, waits for results immediately.
2. **The "KFC Lunch Batch":**
   - Staff keeps the staging area open while doing quotation work across tabs for 30–40 minutes.
   - Staff downloads official quotes in batches of 3–6, staging them into the app.
   - Over 3 hours, 2 to 4 staff members stage 40, 60, or 80 PDFs each (e.g. 3 staff $\times$ 80 = **240 staged PDFs**).
   - Right before lunch hour, staff hits upload and goes out for KFC or McDonald's for an hour.
   - **There is zero rush in this scenario.** The system can take 15–20 minutes to pace the batch smoothly without choking or hitting rate limits.

#### Token Weighing & Disqualification Rule:
- 1-page quotation PDF costs ~10k to 30k tokens.
- Safe limit per slot is 200,000 TPM (cap is 250k).
- **The Staging Token Weigher:** While files sit staged in the browser, the system must calculate token weights.
- **The Disqualification Rule:** If a file is a 150-page policy manual (~240k tokens), it must be **disqualified immediately** before dispatching to Google, with a clear warning: *"File exceeds 200,000 token limit. Cannot be processed."*
- **Live Fleet Meter:** A visible meter showing total staged files, combined estimated token weight, and active quota headroom.

#### Google AI Studio Rate Limit UI Parity:
- Dashboard at `/settings/ai-engine` mirroring `https://aistudio.google.com/rate-limit?timeRange=last-1-day&project=gen-lang-client-0587737993`:
  - Columns: `Model`, `Category`, `RPM (Peak / Limit)`, `TPM (Peak / Limit)`, `RPD (Used / Limit)`, `Status`.
  - Filters: `Today`, `Last 1 Day`, `Last 7 Days`, `Last 28 Days`.
  - Display strictly for `Gemini 3.1 Flash Lite` and `Gemini 3.5 Flash Lite`.
- **Operational Switch (Pause / Rest Account):** A button to put an account/key to rest temporarily when approaching quota limits, without deleting or editing the stored key strings.

---

### Step 8: The Comprehensive Audit & Discovered Shortcomings (Messages #15 to #19)

When the implementation plan and codebase were audited in Message #17, the audit revealed 5 critical engineering defects in the earlier work:

1. **Browser vs Backend Token Discrepancy (P0):**
   - The backend used PyMuPDF character/page parsing.
   - The frontend used a crude byte heuristic (`file.size / 65,000` for pages).
   - A standard 2-page scanned 300 DPI quotation is 4–6 MB $\rightarrow$ the frontend estimated it as **70+ pages and 680k tokens**, falsely disqualifying legitimate customer quotations!
2. **The "Phantom Pacer":**
   - `PacerSentinel` was written and unit-tested in isolation, but `calculate_delay()` was **never called** in the actual extraction worker loop. No `time.sleep` or async delay was ever executed.
   - In-memory `threading.RLock` meant running multiple Uvicorn workers would bypass the 13 RPM cap and cause account suspensions.
3. **Hardcoding & Dual-Truth Invariants Broken:**
   - Towing upgrade rules for 6 insurers were hardcoded in Python `if/elif` branches and duplicated verbatim across 120 lines of TypeScript in `unified-addon-engine.ts`.
4. **Orphaned Betterment Engine:**
   - `betterment_engine.py` was created with `relativedelta`, but `ncd_evaluator.py` and live quotations still used the old year subtraction (`quote_y - veh_yom`).
5. **Database Memory Bomb:**
   - 28-day analytics loaded all rows into Python memory with `.all()` and ran $O(N^2)$ nested loops instead of using SQL `date_trunc('minute', created_at)`.

---

## 2. Summary of Core Operating Principles from the User

1. **Zero Google Account Bans:** Enforce strict 13 RPM, 200k TPM, 480 RPD caps. Lock strictly to `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`. Never call `gemini-3.8-flash` or preview models.
2. **Equal Mesh Equilibrium:** Distribute requests round-robin across all $S = 2N$ slots ($i \pmod S$).
3. **Real "Living Eye" Pacing:** Apply actual breathing delays between calls in the real extraction worker.
4. **Accurate PDF Token Weighing:** Never use naive file byte size to disqualify scanned PDFs.
5. **Single Template as Builder:** Consolidate Bilingual Agency to 1 template with an interactive `[ Itemized | Lump Sum | None ]` toggle on the quotation page.
6. **Design 2 Primacy:** Fixed 24 cards; dynamic in-place Towing upgrade; suppress duplicate towing card in the bottom matrix.
7. **Actuarial Betterment:** Completed calendar years (`relativedelta.years`), where 9y 11m 29d = 9 completed years at 35% scale.
8. **No Dual-Truth / No Hardcoding:** Business rules belong in database configs, not parallel Python and TypeScript `if/elif` blocks.
9. **Authentic Verification:** Never rely on mocked unit tests alone; verify the real running worker and live UI.

