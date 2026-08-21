# Benefits & Add-on Configuration Matrix

**Canonical source of truth for how every insurer structures benefits.** Read this before configuring or seeding any company catalog. It mirrors exactly what is seeded today (`commands/seed-demo.py`), what exists only as a draft (`commands/seed-docx-draft.py`), and what is still missing — so nothing is ever added silently and no row is left ambiguous.

This document is the refill sheet: **you** correct/extend values here, and a future data-driven seed script turns it into idempotent upserts (creates the missing rows, amends existing ones).

## Status Legend

| Mark | Meaning |
| --- | --- |
| ✅ seeded | Configuration is applied to the database today |
| ⏳ draft | Config exists in seed scripts but is **not** applied / superseded |
| ⬜ pending | Not configured — fill this row to extend coverage |

---

## 1. Global Benefit Library (all 34 concepts)

The stable benefit facility. `category` = `default` (base/included family) or `addon` (available as an optional extra). `variants` = named plan variants offered by some insurers (e.g. Driver Passenger Protector Plan A–D); single-insurer concepts are still global but named after their home insurer.

### Defaults (11)

| # | concept_key | Label | Notes |
| --- | --- | --- | --- |
| 1 | `towing` | Towing | 24/7 emergency towing |
| 2 | `roadside-assistance` | Roadside Assistance | 24h on-site / jumpstart / minor assist |
| 3 | `repair-workmanship-warranty` | Workmanship Warranty | Panel workshop body/paint warranty |
| 4 | `all-drivers` | All Drivers | Named-driver waiver / any authorised driver |
| 5 | `personal-accident` | Personal Accident | Includes AD / TPD |
| 6 | `betterment-protection` | Betterment / New Parts Protection | Waiver of betterment |
| 7 | `total-loss-theft-allowance` | Total Loss / Theft Allowance | Lump-sum compassionate allowance |
| 8 | `key-replacement` | Key Replacement | Smart/transmitter key reimburse |
| 9 | `flood-relief-allowance` | Flood Relief Allowance | Immediate cash relief |
| 10 | `personal-belongings-theft` | Personal Belongings Theft | Smash & grab / snatch theft |
| 11 | `ambulance-fees` | Ambulance Fees | Emergency transport reimburse |

### Add-ons (23)

| # | concept_key | Label | Variants |
| --- | --- | --- | --- |
| 12 | `windscreen` | Windscreen | — |
| 13 | `special-perils` | Special Perils | — |
| 14 | `strike-riot-civil-commotion` | Strike, Riot & Civil Commotion | — |
| 15 | `legal-liability-to-passengers` | Legal Liability to Passengers | — |
| 16 | `legal-liability-of-passengers` | Legal Liability of Passengers | — |
| 17 | `legal-liability-to-pillion` | Legal Liability to Pillion | — |
| 18 | `medical-expenses` | Medical Expenses | — |
| 19 | `hospital-income` | Hospital Income | — |
| 20 | `bereavement-allowance` | Bereavement Allowance | — |
| 21 | `replacement-car` | Replacement Car | — |
| 22 | `repaint-spray-paint` | Repaint / Spray Paint | — |
| 23 | `side-mirror-protection` | Side Mirror Protection | — |
| 24 | `child-car-seat` | Child Car Seat | — |
| 25 | `replacement-cost` | Replacement Cost | — |
| 26 | `vehicle-accessories` | Vehicle Accessories | — |
| 27 | `e-hailing-extension` | E-Hailing / Private Hire Extension | — |
| 28 | `agreed-value-market-value` | Agreed Value / Market Value | — |
| 29 | `cashback-no-claim` | Cashback / No-Claim Cashback | — |
| 30 | `out-of-pocket-allowance` | Out-of-Pocket Allowance | — |
| 31 | `driver-passenger-protector` | Driver Passenger Protector | A, B, C, D |
| 32 | `private-car-365` | Private Car 365 Plan | 1, 2, 3, 4, Ezy |
| 33 | `motor-pa-plus` | Motor PA Plus | 1, 2, 3 |
| 34 | `oto-360` | OTO 360 | 1, 2, 3 |

> Draft-only concept keys that are **not** in the 34 must be resolved before seeding `repair-allowance` — see [Lonpac caveat](#lonpac).

---

## 2. Dimensions

| Dimension | Values |
| --- | --- |
| Coverage type | `comprehensive` · `third_party_fire_theft` (Fire & Theft) · `third_party` (Third Party) — all 3 exist in DB; only `comprehensive` is configured today |
| Vehicle category | `car` · `motorcycle` · `commercial_vehicle` (sub: lorry/truck, van, bus) |
| Segment | `private` · `company_commercial` |
| Add-on system | `single` (one flat default set + one add-on list) · `package` (named tier chain, each tier = own defaults + add-ons) |

**Rule:** every company row below exists for every coverage type × vehicle category it must support. A row marked ⬜ means "configure later".

---

## 3. Per-Company Configuration

### QBE

| Coverage type | Vehicle | Add-on system | Status |
| --- | --- | --- | --- |
| Comprehensive | Car | `single` | ✅ seeded |
| Comprehensive | Motorcycle | `single` | ⬜ pending |
| Fire & Theft | Car | — | ⬜ pending |
| Third Party | Car | — | ⬜ pending |

**Product:** `qbe-private-car-protector` — "Private Car Protector" (car × comprehensive)

- **Defaults (base / included):**
  - `towing` — "As per policy"
  - `roadside-assistance` — "RM500"
  - `betterment-protection` — "Up to 10 years old vehicle age"
  - `total-loss-theft-allowance` — "5% or up to RM5,000 coverage, whichever is lower"
  - `key-replacement` — "Up to RM500"
- **Add-ons (available):** `windscreen` · `special-perils` · `strike-riot-civil-commotion` · `legal-liability-to-passengers` · `vehicle-accessories` · `out-of-pocket-allowance` · `driver-passenger-protector` · `flood-relief-allowance`

---

### AmAssurance

| Coverage type | Vehicle | Add-on system | Status |
| --- | --- | --- | --- |
| Comprehensive | Car | `package` (4 tiers) | ✅ seeded |
| Comprehensive | Motorcycle | `package` | ⬜ pending |
| Fire & Theft | Car | — | ⬜ pending |
| Third Party | Car | — | ⬜ pending |

**Product:** `amassurance-private-car-comprehensive` — "Private Car Comprehensive". Tier ladder Lite → Plus → Premier → All-Inclusive; each higher tier upgrades defaults in place and trims add-ons.

**Tier 1 — `lite` "auto365 Comprehensive Lite"**
- Defaults: `towing` · `roadside-assistance` · `repair-workmanship-warranty`
- Add-ons (15): `all-drivers` · `personal-accident` · `betterment-protection` · `total-loss-theft-allowance` · `key-replacement` · `flood-relief-allowance` · `personal-belongings-theft` · `ambulance-fees` · `windscreen` · `special-perils` · `legal-liability-to-passengers` · `legal-liability-of-passengers` · `strike-riot-civil-commotion` · `e-hailing-extension` · `private-car-365`

**Tier 2 — `plus` "auto365 Comprehensive Plus"**
- Defaults (8): `towing` · `roadside-assistance` · `repair-workmanship-warranty` · `all-drivers` · `flood-relief-allowance` · `key-replacement` · `personal-belongings-theft` · `ambulance-fees`
- Add-ons (10): `personal-accident` · `betterment-protection` · `total-loss-theft-allowance` · `windscreen` · `special-perils` · `legal-liability-to-passengers` · `legal-liability-of-passengers` · `strike-riot-civil-commotion` · `e-hailing-extension` · `private-car-365`

**Tier 3 — `premier` "auto365 Comprehensive Premier"**
- Defaults (10): `towing` · `roadside-assistance` · `repair-workmanship-warranty` · `all-drivers` · `flood-relief-allowance` · `key-replacement` · `personal-belongings-theft` · `ambulance-fees` · `total-loss-theft-allowance` · `betterment-protection`
- Add-ons (8): `personal-accident` · `windscreen` · `special-perils` · `legal-liability-to-passengers` · `legal-liability-of-passengers` · `strike-riot-civil-commotion` · `e-hailing-extension` · `private-car-365`

**Tier 4 — `all-inclusive` "Comprehensive All-Inclusive"**
- Defaults (11, all): `towing` · `roadside-assistance` · `repair-workmanship-warranty` · `all-drivers` · `personal-accident` · `betterment-protection` · `total-loss-theft-allowance` · `key-replacement` · `flood-relief-allowance` · `personal-belongings-theft` · `ambulance-fees`
- Add-ons: none

---

### Takaful Malaysia

| Coverage type | Vehicle | Add-on system | Status |
| --- | --- | --- | --- |
| Comprehensive | Car | `single` × 2 products | ✅ seeded |
| Comprehensive | Motorcycle | — | ⬜ pending |
| Fire & Theft | Car | — | ⬜ pending |
| Third Party | Car | — | ⬜ pending |

**Product 1:** `takaful-mymotor-private-motor` — "Takaful myMotor - Private Motor"

- Defaults:
  - `personal-accident` (label "Accidental Death / Total Permanent Disability") — "RM15,000 per life"
  - `towing` — "RM200"
  - `roadside-assistance` — "24/7"
- Add-ons (8): `windscreen` · `special-perils` · `legal-liability-to-passengers` · `legal-liability-of-passengers` · `strike-riot-civil-commotion` · `cashback-no-claim` · `motor-pa-plus` · `betterment-protection` (label "Waiver of Betterment")

**Product 2:** `myclick-takaful-car` — "myClick Takaful Car"

- Defaults: `personal-accident` · `all-drivers` · `towing` · `roadside-assistance` · `repair-workmanship-warranty`
- Add-ons (12): `windscreen` · `special-perils` · `flood-relief-allowance` · `repair-allowance-cart` · `key-replacement` · `legal-liability-to-passengers` · `legal-liability-of-passengers` · `strike-riot-civil-commotion` · `betterment-protection` · `agreed-value-market-value` · `cashback-no-claim` · `motor-pa-plus`

> **Collision caveat:** `commands/seed-docx-draft.py` holds earlier myMotor/myClick drafts with different keys (`takaful-mymotor-private-car`, `myclick` packages). These are ⏳ draft and superseded — the applied config above wins. Delete the stale drafts before reseeding to avoid duplicate products.

---

### Etiqa

| Coverage type | Vehicle | Add-on system | Status |
| --- | --- | --- | --- |
| Comprehensive | Car | `single` | ✅ seeded |
| Comprehensive | Motorcycle | — | ⬜ pending |
| Fire & Theft | Car | — | ⬜ pending |
| Third Party | Car | — | ⬜ pending |

**Product:** `etiqa-comprehensive-private-car` — "Comprehensive Private Car Insurance / Takaful"

- Defaults:
  - `towing` — "Up to 200 km"
  - `roadside-assistance` — "24/7"
  - `all-drivers` — "Any Authorised Driver"
- Add-ons (10): `windscreen` · `special-perils` · `repair-allowance-cart` ("Repair Allowance / Cash Assistance") · `oto-360` · `child-car-seat` · `repaint-spray-paint` · `replacement-cost` · `betterment-protection` · `strike-riot-civil-commotion` · `cashback-no-claim`

---

### Lonpac

| Coverage type | Vehicle | Add-on system | Status |
| --- | --- | --- | --- |
| Comprehensive | Car | `package` (1 tier) | ⏳ draft |

**Product (draft):** `lonpac-private-car-secure` — "Lonpac Private Car Secure"

**Package — "Private Car Secure"**
- Defaults (base / included):
  - `repair-allowance` — "RM 75" daily allowance (⚠️ concept **not in the 34** — needs a new concept)
  - `all-drivers` — "Included"
  - `roadside-assistance` — "Included"
- Add-ons (available): `windscreen` — "RM 1,000" · `special-perils` — "RM 50,000"

> ⚠️ **Lonpac concept fix required before seeding:** the draft uses `repair-allowance` (daily repair allowance) which is not one of the 34 concepts. Either add `repair-allowance` to the global library or remap it to an existing concept.

---

### Tune Protect

| Coverage type | Vehicle | Add-on system | Status |
| --- | --- | --- | --- |
| Comprehensive | Car | `package` (2 tiers) | ⏳ draft |

**Product (draft):** `tune-protect-motor-easy` — "Tune Protect Motor Easy"

**Tier 1 — "Motor Easy"**
- Defaults: `roadside-assistance` — "24/7" · `repair-workmanship-warranty` — "6 months"
- Add-ons: `windscreen` — "RM 1,000" · `special-perils` — "RM 50,000"

**Tier 2 — "Motor Easy + Motor Bundle"**
- Defaults add: `all-drivers` — "Included" · `key-replacement` — "RM 1,000" · `total-loss-theft-allowance` — "RM 10,000"
- Add-ons: `windscreen` — "RM 1,000" · `special-perils` — "RM 50,000"

---

### Berjaya Sompo

| Coverage type | Vehicle | Add-on system | Status |
| --- | --- | --- | --- |
| Comprehensive | Car | `package` (1 tier) | ⏳ draft |

**Product (draft):** `sompo-motor-comprehensive` — "SOMPO Motor Comprehensive"

**Package — "SOMPO Motor Base"**
- Defaults: `roadside-assistance` — "24/7" · `repair-workmanship-warranty` — "12 months" · `towing` — "RM 300"
- Add-ons: `all-drivers` — "Included" · `windscreen` — "RM 1,000" · `special-perils` — "RM 50,000" · `key-replacement` — "RM 1,000"

---

## 4. Gap Checklist (everything pending)

Tick off as you refill this document.

**Vehicle coverage gaps (car exists everywhere, motorcycles/commercial nowhere):**
- [ ] QBE — motorcycle comprehensive
- [ ] AmAssurance — motorcycle comprehensive
- [ ] Etiqa / Takaful Malaysia — motorcycle comprehensive
- [ ] Lonpac / Tune Protect / Berjaya Sompo — motorcycle + commercial rows
- [ ] All companies — commercial vehicle (lorry/van/bus) comprehensive where applicable

**Coverage-type gaps (only `comprehensive` configured for every company):**
- [ ] Fire & Theft (`third_party_fire_theft`) rows for all 7 companies
- [ ] Third Party (`third_party`) rows for all 7 companies

**Non-applied drafts (⏳ → ✅):**
- [ ] Lonpac — apply (after resolving the `repair-allowance` concept)
- [ ] Tune Protect — apply 2-tier Motor Easy
- [ ] Berjaya Sompo — apply SOMPO Motor Base
- [ ] Takaful Malaysia — purge stale myMotor/myClick drafts

**Global library extensions:**
- [ ] Standalone `repair-allowance` concept (Lonpac needs it)

**Reliability ideas (decide later):**
- [ ] Whether unique premium/limit values (e.g. QBE "RM500", Etiqa "200 km") should be typed values (`money`/`distance`) instead of free-text display strings, so they stay comparable across companies.

---

## 5. Seed Mechanics

When you have refilled this document, the following workflow turns it into database truth:

1. Convert the tables in §3 into a machine-readable source (JSON) that mirrors the structure `company → coverage_type → vehicle_category → addon_system → defaults/addons/packages`.
2. A data-driven seed command reads it and **upserts** idempotently:
   - Missing rows → create product → catalog (revision) → packages → offerings (base/optional).
   - Existing rows → amend values in place (never duplicate; never orphan).
3. Re-run `commands/seed-companies.py` + `commands/seed-demo.py` unaffected; new script reported in `docs/STRUCTURE.md` and the code map.

**Source references (keep in sync when you edit):** `commands/seed-demo.py` (`BENEFIT_CONCEPTS_DATA` L52-366, `seed_company_package_chains` L690-1128) · `commands/seed-docx-draft.py` (`NEW_GLOBAL_BENEFITS` L43-296, `DRAFT_CONFIGURATIONS` L298-440) · `migrations/033_benefits_package_hierarchy.sql` (dimension seeds).
