# Benefits & Add-on Configuration Matrix

**Canonical source of truth for how every insurer structures benefits.** This document follows the RiskLocker hierarchy exactly. A benefit is a benefit. `Default` and `Add-on` are only two placement lists used inside a product/package; they do **not** define what a benefit fundamentally is.

A grouped option is **not** a benefit. It is a package/group that contains existing benefits. Examples include QBE Driver Passenger Protector, QBE Out-of-Pocket Allowance, AmAssurance Private Car 365, Etiqa OTO 360, Etiqa MyRider, Tune AUTOBUDDY and Tune Drive Protect.

---

## 1. System Hierarchy

```text
Company
└── Vehicle
    ├── Car
    ├── Motorcycle
    └── Commercial Vehicle
        ├── Lorry
        ├── Truck
        ├── Van
        └── Bus
        │
        └── Coverage
            ├── Comprehensive
            ├── Fire & Theft
            └── Third Party
                │
                └── Product / Insurance Plan
                    │
                    ├── SIMPLE MODE
                    │   ├── Default Benefits
                    │   ├── Individual Add-ons
                    │   └── Grouped Package Benefits
                    │       └── Group / Plan → Benefits
                    │
                    └── COMPLEX MODE
                        ├── Package / Plan 1
                        │   ├── Default Benefits
                        │   ├── Add-ons
                        │   └── Grouped Package Benefits
                        ├── Package / Plan 2
                        │   ├── Default Benefits
                        │   ├── Add-ons
                        │   └── Grouped Package Benefits
                        ├── Package / Plan 3
                        └── Package / Plan 4
```

### Core rules

1. **Company** is the insurer/company.
2. **Vehicle** is selected independently. Car, Motorcycle and Commercial Vehicle are never merged.
3. **Coverage** belongs to the selected vehicle.
4. A **Product / Insurance Plan** belongs to the selected company + vehicle + coverage.
5. **Simple mode** means one main insurance product with:
   - benefits included initially;
   - individual add-ons that can be purchased separately;
   - optional grouped package benefits that contain multiple existing benefits.
6. **Complex mode** means the insurer sells multiple main packages/plans. The customer selects the package/plan itself. Each package has its own included benefits and remaining add-ons.
7. A higher package can move benefits from the Add-on side into the included/default side. Once included in that selected package, the same benefit must **not remain available as an add-on for that package**.
8. A grouped package is **not a benefit** and must never receive a global benefit ID.
9. The benefits inside a grouped package reuse the same global benefit IDs.
10. A benefit may be included by default in one product/package and be purchasable as an add-on in another.
11. Do not infer a vehicle configuration from another vehicle.
12. If the source does not verify a configuration, mark it pending rather than inventing it.

---

## 2. Global Benefit Library

These are the actual benefits. They are the only objects that belong in the global benefit library.

### Benefits

| # | concept_key | Label |
| --- | --- | --- |
| 1 | `towing` | Towing |
| 2 | `roadside-assistance` | Roadside Assistance |
| 3 | `workmanship-warranty` | Workmanship Warranty |
| 4 | `all-drivers-riders` | All Drivers / Riders |
| 5 | `personal-accident` | Personal Accident |
| 6 | `medical-expenses` | Medical Expenses |
| 7 | `hospital-income` | Hospital Income |
| 8 | `ambulance-fees` | Ambulance Fees |
| 9 | `bereavement-allowance` | Bereavement Allowance |
| 10 | `double-indemnity` | Double Indemnity |
| 11 | `cart` | CART |
| 12 | `transportation-allowance` | Transportation Allowance |
| 13 | `inconvenience-allowance` | Inconvenience Allowance |
| 14 | `betterment-new-parts-protection` | Betterment / New Parts Protection |
| 15 | `flood-relief-allowance` | Flood Relief Allowance |
| 16 | `flood-cleaning-cost` | Flood Cleaning Cost |
| 17 | `total-loss-theft-allowance` | Total Loss / Theft Allowance |
| 18 | `key-replacement` | Key Replacement |
| 19 | `personal-belongings-theft` | Personal Belongings Theft |
| 20 | `falling-object-damage` | Falling Object Damage |
| 21 | `document-replacement` | Document Replacement |
| 22 | `replacement-car` | Replacement Car |
| 23 | `hotel-accommodation` | Hotel Accommodation |
| 24 | `repaint-spray-paint` | Repaint / Spray Paint |
| 25 | `side-mirror-protection` | Side Mirror Protection |
| 26 | `child-car-seat` | Child Car Seat |
| 27 | `replacement-cost` | Replacement Cost |
| 28 | `vehicle-accessories` | Vehicle Accessories |
| 29 | `agreed-value-market-value` | Agreed Value / Market Value |
| 30 | `current-year-ncd-relief` | Current Year NCD Relief |
| 31 | `cashback-no-claim` | Cashback / No-Claim Cashback |
| 32 | `personal-liability` | Personal Liability |
| 33 | `ev-home-wall-charger` | EV Home Wall Charger |
| 34 | `overturning-damage` | Overturning Damage |
| 35 | `tool-of-trade-liability` | Tool-of-Trade Liability |
| 36 | `boom-damage` | Boom Damage |
| 37 | `windscreen` | Windscreen |
| 38 | `special-perils` | Special Perils |
| 39 | `strike-riot-civil-commotion` | Strike, Riot & Civil Commotion |
| 40 | `legal-liability-to-passengers` | Legal Liability to Passengers |
| 41 | `legal-liability-of-passengers` | Legal Liability of Passengers |
| 42 | `legal-liability-to-pillion` | Legal Liability to Pillion |
| 43 | `e-hailing-private-hire-extension` | E-Hailing / Private Hire Extension |
| 44 | `out-of-pocket-allowance` | Out-of-Pocket Allowance |
| 45 | `repair-allowance` | Repair Allowance |

> `Default` and `Add-on` are placement states only. They are not permanent categories of the global benefit.

---

## 3. Dimensions

| Dimension | Values |
| --- | --- |
| Vehicle | `car` · `motorcycle` · `commercial_vehicle` |
| Commercial vehicle type | `lorry` · `truck` · `van` · `bus` |
| Coverage | `comprehensive` · `third_party_fire_theft` · `third_party` |
| System mode | `simple` · `complex` |
| Benefit placement | `default` · `addon` |
| Group type | `package_benefit_group` |

---

# 4. Company Configuration

## QBE

**System mode:** `simple`

**Structure:**

```text
QBE
└── Vehicle
    ├── Car
    │   └── Comprehensive
    │       └── Private Car Protector
    │           ├── Default Benefits
    │           ├── Add-ons
    │           └── Package Benefit Groups
    │               ├── Out-of-Pocket Allowance
    │               └── Driver Passenger Protector
    │
    ├── Motorcycle
    │   └── Comprehensive
    │       └── Motorcycle
    │           ├── Default Benefits
    │           ├── Add-ons
    │           └── Package Benefit Groups
    │               ├── Out-of-Pocket Allowance
    │               └── Driver Passenger Protector
    │
    └── Lorry
        └── Comprehensive
            └── Commercial Vehicle
                ├── Default Benefits
                ├── Add-ons
                └── Package Benefit Groups
                    ├── Out-of-Pocket Allowance
                    └── Driver Passenger Protector
```

### Car → Comprehensive → Private Car Protector

**Default Benefits**

- `towing` — QBE Auto Assist; accident, breakdown and roadside repair services share RM500 service limit
- `betterment-new-parts-protection` — 0% betterment for vehicles 0–10 years old
- `total-loss-theft-allowance` — 5% of Sum Insured, maximum RM5,000
- `key-replacement` — Up to RM500

**Individual Add-ons**

- `windscreen`
- `special-perils`
- `strike-riot-civil-commotion`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `vehicle-accessories`
- `all-drivers-riders`
- `cart`
- `flood-cleaning-cost`

**Package Benefit Groups**

### Driver Passenger Protector

| Plan | Benefits included |
| --- | --- |
| Plan A | `personal-accident` · `medical-expenses` · `hospital-income` · `ambulance-fees` · `bereavement-allowance` · `personal-belongings-theft` · `towing` · `roadside-assistance` |
| Plan B | `personal-accident` · `medical-expenses` · `hospital-income` · `ambulance-fees` · `bereavement-allowance` · `personal-belongings-theft` · `towing` · `roadside-assistance` |
| Plan C | `personal-accident` · `medical-expenses` · `hospital-income` · `ambulance-fees` · `bereavement-allowance` · `personal-belongings-theft` · `towing` · `roadside-assistance` |
| Plan D | `personal-accident` · `medical-expenses` · `hospital-income` · `ambulance-fees` · `bereavement-allowance` · `personal-belongings-theft` · `towing` · `roadside-assistance` |

### Out-of-Pocket Allowance

| Group | Benefits included |
| --- | --- |
| Out-of-Pocket Allowance | `replacement-car` · `hotel-accommodation` · `repaint-spray-paint` |

### Motorcycle → Comprehensive → Motorcycle

**Status:** ⬜ pending exact current product mapping.

### Lorry → Comprehensive → Commercial Vehicle

**Default Benefits**

- `roadside-assistance` — 24/7 QBE Auto Assist; shares RM500 combined service limit
- `betterment-new-parts-protection` — 0% betterment for vehicles 0–10 years old
- `total-loss-theft-allowance` — 5% of Sum Insured, maximum RM5,000
- `key-replacement` — Up to RM500

**Individual Add-ons**

- `windscreen`
- `special-perils`
- `strike-riot-civil-commotion`
- `vehicle-accessories`
- `all-drivers-riders`
- `cart`
- `flood-cleaning-cost`
- `overturning-damage`
- `tool-of-trade-liability`
- `boom-damage`

**Package Benefit Groups**

- `out-of-pocket-allowance`
- `driver-passenger-protector`

**Fire & Theft**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

**Third Party**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

---

## AmAssurance / Liberty

**System mode:** `complex`

The customer selects the main insurance package/plan. The selected package controls its included benefits and its remaining add-ons.

### Car → Comprehensive

| Main Package / Plan | Status |
| --- | --- |
| Private Car Comprehensive | ✅ |
| auto365 Comprehensive Lite | ✅ |
| auto365 Comprehensive Plus | ✅ |
| auto365 Comprehensive Premier | ✅ |

### Private Car Comprehensive

**Default Benefits**

- `towing`
- `roadside-assistance`
- `workmanship-warranty`

**Add-ons**

- `windscreen`
- `special-perils`
- `cart`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `strike-riot-civil-commotion`
- `e-hailing-private-hire-extension`

**Package Benefit Group**

- `private-car-365`

### auto365 Comprehensive Lite

**Default Benefits**

- `towing`
- `roadside-assistance`
- `workmanship-warranty`

**Add-ons**

- `towing` — breakdown enhancement up to 150km round trip
- `all-drivers-riders`
- `personal-accident` — up to RM10,000
- `windscreen`
- `special-perils`
- `cart`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `strike-riot-civil-commotion`
- `e-hailing-private-hire-extension`

**Package Benefit Group**

- `private-car-365`

### auto365 Comprehensive Plus

**Default Benefits**

- `towing`
- `roadside-assistance`
- `workmanship-warranty`
- `all-drivers-riders`
- `flood-relief-allowance` — RM1,500
- `key-replacement` — RM500
- `personal-belongings-theft` — RM500
- `ambulance-fees` — RM500

**Add-ons**

- `personal-accident`
- `windscreen`
- `special-perils`
- `cart`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `strike-riot-civil-commotion`
- `e-hailing-private-hire-extension`

**Package Benefit Group**

- `private-car-365`

### auto365 Comprehensive Premier

**Default Benefits**

- `towing` — up to 365km
- `roadside-assistance`
- `workmanship-warranty`
- `all-drivers-riders`
- `flood-relief-allowance` — RM3,000
- `key-replacement` — RM1,000
- `personal-belongings-theft` — RM1,000
- `ambulance-fees` — RM1,000
- `total-loss-theft-allowance` — 5% of Sum Insured, maximum RM5,000

**Add-ons**

- `windscreen`
- `special-perils`
- `cart`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `strike-riot-civil-commotion`
- `e-hailing-private-hire-extension`

**Package Benefit Group**

- `private-car-365`

### Private Car 365

This is a grouped package benefit. It is **not** a global benefit.

| Plan | Benefits included |
| --- | --- |
| Plan 1 | Personal Accident · Double Indemnity · Medical Expenses · Hospital / Recovery benefits · Towing / assistance benefits according to plan |
| Plan 2 | Personal Accident · Double Indemnity · Medical Expenses · Hospital / Recovery benefits · Towing / assistance benefits according to plan |
| Plan 3 | Personal Accident · Double Indemnity · Medical Expenses · Hospital / Recovery benefits · Towing / assistance benefits according to plan |
| Plan 4 | Personal Accident · Double Indemnity · Medical Expenses · Hospital / Recovery benefits · Towing / assistance benefits according to plan |
| Plan Ezy | Personal Accident · Medical Expenses · Towing / assistance benefits according to plan |

### Motorcycle → Comprehensive

| Main Package / Plan | Status |
| --- | --- |
| Motorcycle Comprehensive | ⏳ |
| motorcycle365 Comprehensive Plus | ⏳ |

**Motorcycle Comprehensive**

**Default Benefits**

- `towing` — accident up to RM50
- `all-drivers-riders`

**Add-ons**

- `legal-liability-to-pillion`
- `special-perils`
- `strike-riot-civil-commotion`

**motorcycle365 Comprehensive Plus**

**Default Benefits**

- `towing` — accident up to RM50; breakdown up to 75km round trip, maximum 3 events/year, motorcycles ≤250cc
- `personal-accident` — RM5,000 rider; RM1,500 pillion
- `double-indemnity` — up to RM10,000
- `hospital-income` — RM50/day up to 60 days
- `ambulance-fees` — up to RM200

**Add-ons**

- `all-drivers-riders`
- `legal-liability-to-pillion`
- `special-perils`
- `strike-riot-civil-commotion`

### Lorry → Comprehensive

| Main Package / Plan | Status |
| --- | --- |
| Commercial Vehicle Comprehensive | ⏳ |
| Commercial Vehicle 365 | ⏳ |

**Commercial Vehicle Comprehensive**

**Default Benefits**

- Base commercial comprehensive cover

**Add-ons**

- `windscreen`
- `special-perils`
- `cart`
- `strike-riot-civil-commotion`
- `commercial-vehicle-365`

**Commercial Vehicle 365**

- ⬜ package benefit details pending exact current commercial quotation/PDS

**Fire & Theft**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

**Third Party**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

---

## Takaful Malaysia / STMB

**System mode:** `simple`

### Car → Comprehensive → Takaful myMotor - Private Motor

**Default Benefits**

- `personal-accident` — RM15,000 per life
- `towing` — RM200
- `roadside-assistance` — 24/7

**Individual Add-ons**

- `windscreen`
- `special-perils`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `strike-riot-civil-commotion`
- `betterment-new-parts-protection`
- `cart`

**Package Benefit Groups**

- `motor-pa-plus`
- `cashback-no-claim`

### Car → Comprehensive → myClick Motor

**Default Benefits**

- `personal-accident` — RM15,000 per driver/passenger
- `all-drivers-riders`
- `towing`
- `roadside-assistance`
- `workmanship-warranty` — 6 months
- `cashback-no-claim`

**Individual Add-ons**

- `windscreen`
- `special-perils`
- `flood-cleaning-cost`
- `cart`
- `key-replacement`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `strike-riot-civil-commotion`
- `betterment-new-parts-protection`

**Package Benefit Groups**

- `motor-pa-plus`

### Motorcycle → Comprehensive → Takaful myMotor - Motorcycle

**Status:** ⏳ pending exact current configuration.

### Motorcycle → Comprehensive → myClick Motorcycle

**Status:** ⏳ pending exact current configuration.

### Lorry → Comprehensive

**Status:** ⬜ pending.

**Fire & Theft**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

**Third Party**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

---

## Etiqa

**System mode:** `simple` + grouped package benefits

### Car → Comprehensive → Comprehensive Private Car Insurance / Takaful

**Default Benefits**

- `towing` — first 200km free in Peninsular Malaysia
- `roadside-assistance` — 24/7
- `all-drivers-riders`
- `cashback-no-claim`

**Individual Add-ons**

- `windscreen`
- `special-perils`
- `cart`
- `child-car-seat`
- `repaint-spray-paint`
- `replacement-cost`
- `betterment-new-parts-protection`
- `strike-riot-civil-commotion`

**Package Benefit Groups**

### OTO 360

| Group | Benefits included |
| --- | --- |
| OTO 360 | `towing` — unlimited · `roadside-assistance` — 24-hour breakdown assistance · `personal-accident` — up to RM50,000 per person |

### Motorcycle → Comprehensive → Comprehensive Motorcycle

**Default Benefits**

- `all-drivers-riders`

**Package Benefit Groups**

- `myrider`
- `myrider-plus`

### MyRider

**Eligibility:** motorcycles up to 249cc

**Benefits included**

- `towing` — unlimited
- `personal-accident` — RM8,000
- `medical-expenses`
- `inconvenience-allowance`

### MyRider Plus

**Eligibility:** motorcycles 250cc and above

**Benefits included**

- `towing` — unlimited
- `personal-accident` — RM10,000
- `medical-expenses` — up to RM2,000
- `inconvenience-allowance`

### Lorry → Comprehensive → Commercial Vehicle

**Status:** ⏳ pending exact current package/add-on configuration.

**Fire & Theft**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

**Third Party**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

---

## Lonpac

**System mode:** `simple` + grouped package benefits

### Car → Comprehensive → Private Car Secure

**Default Benefits**

- `transportation-allowance` — RM75 per payable own-damage claim
- `falling-object-damage` — up to 25% of Policy Sum Insured
- `document-replacement` — RM150 during qualifying Smash & Grab
- `all-drivers-riders`
- `roadside-assistance`
- `towing` — RM400 service limit

**Individual Add-ons**

- `windscreen`
- `special-perils`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `repaint-spray-paint`
- `key-replacement`
- `cart`
- `strike-riot-civil-commotion`
- `current-year-ncd-relief`

**Package Benefit Groups**

- `e-assist-smart-driver`

### Car → Comprehensive → Motor ezSecure

**Default Benefits**

- `all-drivers-riders`
- `roadside-assistance`
- `towing`
- `workmanship-warranty`

**Add-ons**

- `windscreen`
- `special-perils`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `cart`

**Package Benefit Groups**

- `e-assist-smart-driver`

### Motorcycle → Comprehensive

- ⬜ pending exact current configuration

### Lorry → Comprehensive

- ⬜ pending exact current configuration

**Fire & Theft**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

**Third Party**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

---

## Tune Protect

**System mode:** `simple` + grouped package benefits

### Car → Comprehensive → Motor Easy

**Default Benefits**

- `roadside-assistance` — 24-hour Emergency Auto-assist
- `workmanship-warranty` — 6 months

**Individual Add-ons**

- `windscreen`
- `special-perils`
- `strike-riot-civil-commotion`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `cart`
- `personal-accident`

**Package Benefit Groups**

- `autobuddy`
- `tune-drive-protect`
- `motor-bundle`
- `motorshield`
- `pay-as-you-drive-refund`

### AUTOBUDDY

| Plan | Benefits included |
| --- | --- |
| A | `personal-accident` · `medical-expenses` · `bereavement-allowance` · `hospital-income` · `towing` · `roadside-assistance` · `flood-relief-allowance` |
| B | `personal-accident` · `medical-expenses` · `bereavement-allowance` · `hospital-income` · `towing` · `roadside-assistance` · `flood-relief-allowance` |
| C | `personal-accident` · `medical-expenses` · `bereavement-allowance` · `hospital-income` · `towing` · `roadside-assistance` · `flood-relief-allowance` |
| D | `personal-accident` · `medical-expenses` · `bereavement-allowance` · `hospital-income` · `towing` · `roadside-assistance` · `flood-relief-allowance` |
| E | `personal-accident` · `medical-expenses` · `bereavement-allowance` · `hospital-income` · `towing` · `roadside-assistance` · `flood-relief-allowance` |

### Tune Drive Protect

| Plan | Benefits included |
| --- | --- |
| 1 | `inconvenience-allowance` · `repaint-spray-paint` |
| 2 | `inconvenience-allowance` · `repaint-spray-paint` |
| 3 | `inconvenience-allowance` · `repaint-spray-paint` |
| 4 | `inconvenience-allowance` · `repaint-spray-paint` |

### Motor Bundle

| Group | Benefits included |
| --- | --- |
| Motor Bundle | `all-drivers-riders` · `total-loss-theft-allowance` · `side-mirror-protection` · `key-replacement` · `personal-accident` · `towing` · `roadside-assistance` · `flood-relief-allowance` |

### Motorcycle → Comprehensive → Motorcycle Comprehensive / Motor Bike Easy

**Default Benefits**

- `towing` — maximum towing cost RM50
- `roadside-assistance`
- `workmanship-warranty`

**Individual Add-ons**

- `special-perils`
- `strike-riot-civil-commotion`
- `cart`
- `current-year-ncd-relief`
- `personal-accident`

**Package Benefit Groups**

- `autobuddy`
- `tune-drive-protect`
- `motor-bundle`
- `motorshield`
- `pay-as-you-drive-refund`

### Lorry → Comprehensive → Commercial Vehicle Comprehensive

**Status:** ⏳ pending exact current configuration.

**Fire & Theft**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

**Third Party**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

---

## Berjaya Sompo

**System mode:** `simple` + grouped package benefits

### Car → Comprehensive → SOMPO Motor - Private Car Comprehensive

**Default Benefits**

- `all-drivers-riders`
- `roadside-assistance` — 24-hour Auto Assist
- `towing` — qualifying accident/breakdown towing
- `workmanship-warranty` — 12 months
- `special-perils`

**Individual Add-ons**

- `windscreen`
- `legal-liability-to-passengers`
- `legal-liability-of-passengers`
- `vehicle-accessories`
- `current-year-ncd-relief`
- `cart`
- `strike-riot-civil-commotion`
- `betterment-new-parts-protection`
- `e-hailing-private-hire-extension`
- `personal-accident`

**Grouped package benefits**

- ⬜ exact current grouped-package structure pending verification

### Motorcycle → Comprehensive

- ⬜ pending

### Lorry → Comprehensive

- ⬜ pending

**Fire & Theft**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

**Third Party**

- Car: ⬜ pending
- Motorcycle: ⬜ pending
- Lorry: ⬜ pending

---

# 5. Gap Checklist

## Vehicle gaps

- [ ] QBE Motorcycle
- [ ] QBE Lorry
- [ ] AmAssurance Motorcycle package configuration
- [ ] AmAssurance Lorry package configuration
- [ ] Takaful Malaysia Motorcycle
- [ ] Takaful Malaysia Lorry
- [ ] Etiqa Lorry
- [ ] Lonpac Motorcycle
- [ ] Lonpac Lorry
- [ ] Tune Protect Motorcycle package values
- [ ] Tune Protect Lorry
- [ ] Berjaya Sompo Motorcycle
- [ ] Berjaya Sompo Lorry

## Coverage gaps

- [ ] QBE Fire & Theft
- [ ] QBE Third Party
- [ ] AmAssurance Fire & Theft
- [ ] AmAssurance Third Party
- [ ] Takaful Malaysia Fire & Theft
- [ ] Takaful Malaysia Third Party
- [ ] Etiqa Fire & Theft
- [ ] Etiqa Third Party
- [ ] Lonpac Fire & Theft
- [ ] Lonpac Third Party
- [ ] Tune Protect Fire & Theft
- [ ] Tune Protect Third Party
- [ ] Berjaya Sompo Fire & Theft
- [ ] Berjaya Sompo Third Party

## Grouped package gaps

- [ ] QBE Driver Passenger Protector exact current plan values
- [ ] QBE Out-of-Pocket Allowance exact vehicle eligibility
- [ ] AmAssurance Private Car 365 exact plan benefits/values
- [ ] AmAssurance motorcycle365 package completion
- [ ] AmAssurance Commercial Vehicle 365 package completion
- [ ] Takaful Malaysia Motor PA Plus exact plan values
- [ ] Etiqa OTO 360 exact current package values
- [ ] Etiqa MyRider / MyRider Plus exact current package values
- [ ] Lonpac E-Assist Smart Driver exact plan values
- [ ] Tune AUTOBUDDY exact current plan values
- [ ] Tune Drive Protect exact current plan values
- [ ] Tune Motor Bundle exact current components
- [ ] Berjaya Sompo grouped package structure

---

# 6. Seed Schema

The database hierarchy must follow:

```text
company
  └── vehicle
       └── coverage
            └── product / insurance plan
                 ├── mode: simple
                 │    ├── default_benefits[]
                 │    ├── addon_benefits[]
                 │    └── package_benefit_groups[]
                 │         └── group
                 │              └── benefits[]
                 │
                 └── mode: complex
                      └── packages[]
                           ├── package
                           │    ├── default_benefits[]
                           │    ├── addon_benefits[]
                           │    └── package_benefit_groups[]
                           │         └── group
                           │              └── benefits[]
```

### Important seed rules

```text
Benefit
= actual customer coverage

Package / Plan
= main insurance product selection

Package Benefit Group
= optional group containing multiple existing benefits

Default / Add-on
= placement of a benefit inside the selected product/package

Global Benefit ID
= reused whenever the same underlying benefit appears again
```

### Example — QBE

```text
QBE
→ Car
→ Comprehensive
→ Private Car Protector
→ simple

default_benefits:
  - Towing
  - Betterment / New Parts Protection
  - Total Loss / Theft Allowance
  - Key Replacement

addon_benefits:
  - Windscreen
  - Special Perils
  - Legal Liability to Passengers
  - Legal Liability of Passengers
  - Vehicle Accessories
  - All Drivers / Riders
  - CART
  - Flood Cleaning Cost

package_benefit_groups:
  - Driver Passenger Protector
      → Plan A
          → Personal Accident
          → Medical Expenses
          → Hospital Income
          → Ambulance Fees
          → Bereavement Allowance
          → Personal Belongings Theft
          → Towing
          → Roadside Assistance
      → Plan B
      → Plan C
      → Plan D

  - Out-of-Pocket Allowance
      → Replacement Car
      → Hotel Accommodation
      → Repaint / Spray Paint
```

### Example — AmAssurance

```text
AmAssurance
→ Car
→ Comprehensive
→ complex

packages:

  Private Car Comprehensive
    default_benefits[]
    addon_benefits[]
    package_benefit_groups[]

  auto365 Comprehensive Lite
    default_benefits[]
    addon_benefits[]
    package_benefit_groups[]

  auto365 Comprehensive Plus
    default_benefits[]
    addon_benefits[]
    package_benefit_groups[]

  auto365 Comprehensive Premier
    default_benefits[]
    addon_benefits[]
    package_benefit_groups[]
```

**The selected AmAssurance package is the main purchase.** The system does not start with one package and then randomly add benefits from the other tiers.

**The selected package's included benefits are its defaults. Its remaining purchasable benefits are its add-ons.**

---

# 7. Final Non-Negotiable Rules

- Do not create `Enhancer Pack` as a global benefit.
- Do not create any package name as a global benefit.
- Do not create OTO 360 as a global benefit.
- Do not create Driver Passenger Protector as a benefit.
- Do not create AUTOBUDDY as a benefit.
- Do not create Motor PA Plus as a benefit.
- Do not create Tune Drive Protect as a benefit.
- Do not create Motor Bundle as a benefit.
- These are **groups/packages containing benefits**.

- Do not merge Car, Motorcycle and Lorry.
- Do not copy Car benefits into Motorcycle or Lorry.
- Do not assume every insurer uses the same purchase structure.
- QBE = simple mode example.
- AmAssurance = complex package mode example.
- A benefit can be default in one product and add-on in another.
- A package can contain many benefits.
- A package can also contain grouped package benefits.
- A grouped package references existing global benefits; it does not create new benefit types.
- When a selected package already includes a benefit, that benefit is not simultaneously offered as an add-on within that same selected package.
- If the source does not establish the value/configuration, leave it pending.
- Current quotation / policy schedule / PDS overrides this reference.
