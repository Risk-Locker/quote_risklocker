# Active Insurer Motor Benefits Profile Catalog (Snapshot Date: 12/09/2026)

> **Snapshot Profile Version**: `12/09/2026`  
> **Status**: Active Baseline Profile Template (Canonical 63 Benefits)  
> **Coverage Scope**: All 7 Malaysian Motor Underwriters (QBE, STMB / Takaful Malaysia, Etiqa, Lonpac, Berjaya Sompo, Tune Protect, AmAssurance / Liberty).  
> **System Role**: Standardized reference profile for the insurer profile versioning engine (allowing admins to configure, version, and clone company-specific active benefit profiles).

---

## Policy Tier Packaging Principle (MANDATORY INVARIANT)

> [!IMPORTANT]
> **COMPREHENSIVE DEFAULTS INVARIANT**:
> In all Comprehensive motor policies, **Own Damage**, **Third Party Bodily Injury & Death**, and **Third Party Property Damage (TPPD)** are statutory tariff baselines inherent to Comprehensive cover by law and policy definition.
> 
> - **TPFT (Third Party, Fire & Theft) & TPO (Third Party Only)**: In these lower tiers, **ONLY** these 3 statutory baseline benefits exist in Defaults (Included at RM 0):
>   1. **Own Damage** (Restricted to Fire & Theft for TPFT; excluded for TPO)
>   2. **Third Party Bodily Injury & Death**
>   3. **Third Party Property Damage (TPPD)**
> - **Comprehensive Policies**: In Comprehensive policies, these 3 benefits are **STRICTLY OMITTED from the Defaults list** to eliminate redundant clutter. Defaults in Comprehensive profiles exclusively represent the insurer's non-tariff, bundled, or value-added inclusions (e.g. Free Towing, Betterment Waiver, Legal Defense, Key Replacement, All Drivers Excess Waiver, Workmanship Warranty, Non-Claim Cashback, etc.).

---

## 1. QBE Insurance (`qbe`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **All Driver Excess Waiver (`all-drivers`)** — Waives RM400 compulsory excess for unnamed licensed drivers/riders.
2. **Betterment Waiver (`betterment-protection`)** — Waives betterment cost-sharing on older vehicles repaired with parts.
3. **Compassionate Allowance on Total Loss / Theft (`total-loss-theft-allowance`)** — Immediate emergency cash payout (RM1,000-RM3,000) upon vehicle flood / total loss.
4. **Key Care and Replacement (`key-replacement`)** — Reimburses replacement and reprogramming of lost or stolen keys.
5. **Legal Defence Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.
6. **Towing (`towing`)** — 24/7 accidental Towing service to nearest approved repairer upto RM500.

### Add-ons (Optional Riders):
1. **Compensation for Assessed Repair Time / CART (`repair-allowance`)** — RM50/day for 14 days or RM100/day for 14 days.
2. **Cleaning Cost (`car-detailing-cleanup`)** — Water damage interior car cleaning reimbursement after flood.
3. **Inclusion of Special Perils (`special-perils`)** — Full cover for flood, storm, landslide & natural convulsions.
4. **Legal Liability of Passengers / LLOP (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
5. **Legal Liability to Passengers / LLTP (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury/death caused to passengers.
6. **NCD Protector (`ncd-relief`)** — Protects accumulated No Claim Discount from loss following an own-damage claim.
7. **Out of Pocket Allowance (`out-of-pocket-allowance`)** — Daily cash allowance for transit and expenses during repairs.
8. **Special Peril First Loss (`first-loss-flood`)** — Standalone first loss flood/disaster cover (5k/10k).
9. **Strike Riot & Civil Commotion / SRCC (`strike-riot-civil-commotion`)** — Covers damage directly caused by strikes, riots, or civil commotion.
10. **Tuition Purpose (`tuition`)** — Extends coverage while vehicle is used for driving tuition or instruction.
11. **Vehicle Accessories (`vehicle-accessories`)** — Covers fitted aftermarket accessories, multimedia, dashcams, and rims.
12. **Windscreen Damage (`windscreen`)** — Covers windscreen, window glass & sunroof repair without affecting NCD.
13. **Driver & Passenger Personal Accident / Plan 1 to 4 (`personal-accident`)** — Driver & passenger PA for death, disability & hospital.

---

## 2. STMB / Takaful Malaysia (`takaful-malaysia`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Agreed Value Settlement (`agreed-value-market-value`)** — Settles total loss or theft on agreed value without depreciation disputes.
2. **All Drivers (`all-drivers`)** — Waives RM400 compulsory excess penalty for all authorized licensed drivers.
3. **Betterment Waiver (`betterment-protection`)** — Waives betterment deductions on new original parts for vehicles up to 12 years.
4. **Complimentary Personal Accident PA (`personal-accident`)** — Complimentary accidental death cover for participant with bereavement allowance.
5. **Legal Defense (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.
6. **Non-Claim Cashback 15% (`cashback-no-claim`)** — 15% surplus cashback return if no claims are incurred during the year.
7. **Roadside Towing (`towing`)** — 24/7 breakdown and accident towing assistance up to 100 km round trip.

### Add-ons (Optional Riders):
1. **Motor PA PLUS Plan 1-4 (`motor-pa-plus`)** — Motor PA PLUS (Plans 1, 2, 3, and 4) personal accident rider for driver and passengers.
2. **Inclusion of Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake & fallen trees.
3. **Breakage of Glass in Windscreen (`windscreen`)** — Covers windscreen, window glass & tint repair without affecting NCD.
4. **Legal Liability of Passenger / LLOP (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
5. **Passenger Liability Cover / LLTP (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury/death caused to passengers.

---

## 3. Etiqa Insurance & Takaful (`etiqa`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Emergency Towing Assistance (`towing`)** — 24/7 accidental Towing service to nearest approved repairer upto RM200.
2. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.

### Add-ons (Optional Riders):
1. **Drive Less Save More FREE (`drive-less-save-more`)** — Drive-Less Save-More cash rebate up to 30% of base premium for low mileage.
2. **Windscreen (`windscreen`)** — Covers windscreen, window glass & tint repair without affecting NCD.
3. **All Driver (`all-drivers`)** — Waives RM400 compulsory excess penalty for unnamed authorized drivers.
4. **Inclusion of Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake & fallen trees.
5. **Legal Liability to Passenger / LLTP (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury/death caused to passengers.
6. **Legal Liability of Passengers for Negligent Acts / LLOP (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
7. **Strike, Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Covers damage directly caused by strikes, riots, or civil commotion.
8. **Vehicle Accessories (`vehicle-accessories`)** — Covers fitted aftermarket accessories, multimedia, dashcams, and rims.
9. **Gas Conversion Kit and Tank (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
10. **NCD Relief (`ncd-relief`)** — 15% of NCD Value / (10 days x 50) (10 days x 100) (10 days x 150) (10 days x 200).
11. **New Spare Part Replacement Cover (`betterment-protection`)** — Waives betterment deduction on new replacement parts for vehicles up to 10 yrs.
12. **Smart Key Replacement / Key Care Cover (`key-replacement`)** — Reimburses car key and lock replacement up to RM1,000 following loss or theft.
13. **Child Car Safety Seat (`child-safety-seat`)** — Reimburses replacement or repair of child safety seats damaged in a crash.
14. **Car Re-Spray Cover (`vehicle-respray`)** — Reimburses full exterior vehicle spray painting after an accident repair (limit up to RM1,000).
15. **Compensation for Assessed Repair Time (`repair-allowance`)** — Daily cash allowance for workshop repair days assessed by loss adjuster (7 days x RM50).

---

## 4. Lonpac Insurance (`lonpac`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Emergency Towing Assistance (`towing`)** — 24/7 accidental Towing service to nearest approved repairer upto RM200.
2. **Inconvenience & Out-of-Pocket Expense Allowance / Transport Allowance (`out-of-pocket-allowance`)** — PC Privilege 1 lump-sum transportation allowance of RM75 per own damage claim.

### Add-ons (Optional Riders):
1. **Accessories (`vehicle-accessories`)** — Covers fitted aftermarket accessories, multimedia, dashcams, and rims.
2. **Betterment Buyback (`betterment-protection`)** — Waives betterment cost-sharing on new original parts for cars aged 5-10 yrs.
3. **CART (`repair-allowance`)** — Daily cash allowance for workshop repair days assessed by loss adjuster.
4. **Cleaning Cost of Vehicle (`car-detailing-cleanup`)** — Professional car interior cleaning up to RM5,000 after a flood.
5. **Current Year NCD Relief (`ncd-relief`)** — Compensates for lost No Claim Discount (NCD) after an own-damage claim.
6. **E-Hailing (`e-hailing`)** — Comprehensive motor insurance coverage during commercial e-hailing work.
7. **Enhanced Inclusion of Special Peril (`special-perils`)** — Full cover for flood, storm, landslide, earthquake & fallen trees.
8. **Full Vehicle Body Painting (`vehicle-respray`)** — Reimburses complete exterior vehicle spray painting up to RM2,000 after repair.
9. **Gas Conversion (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
10. **LLP for Negligent Acts / LLOP (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
11. **Legal Liability to Passengers / LLP (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury/death caused to passengers.
12. **Replacement Cost of Car Key (`key-replacement`)** — Reimburses key and lock replacement up to RM2,000 due to theft or break-in.
13. **Strike Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Covers damage directly caused by strikes, riots, or civil commotion.
14. **Windscreen (`windscreen`)** — Covers windscreen, window glass & tint repair without affecting NCD.
15. **E-Assist Smart Driver / Personal Accident (`personal-accident`)** — Plan 1 (Limited Towing) & Plan 2 (Unlimited Towing) driver & passenger PA.

---

## 5. Berjaya Sompo Insurance (`berjaya-sompo`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Agreed Value Settlement Protection (`agreed-value-market-value`)** — Settles total loss or theft on agreed value for car models up to 3 years old.
2. **All Drivers / Unnamed Driver Excess Waiver (`all-drivers`)** — Waives RM400 compulsory excess for all authorized licensed drivers aged 21+.
3. **Emergency Towing Assistance (`towing`)** — 24/7 unlimited distance towing to panel workshops and minor roadside repairs.
4. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.
5. **Panel Repair Workmanship Warranty (`repair-warranty`)** — 12-month warranty on repair workmanship and replacement parts from panel shops.
6. **Personal Accident: Accidental Death (`personal-accident`)** — Lump-sum cash benefit paid to beneficiaries upon accidental road death.
7. **Special Perils (`special-perils`)** — Built-in full protection against flood, typhoon, storm, and natural disasters.

### Add-ons (Optional Riders):
1. **Accidental Boom Damage (Mobile Cranes)** — Endorsement 38A covering accidental and unforeseen structural damage to mobile crane booms, jibs, outriggers, and hydraulic apparatus during work operations.
2. **Attached Trailers & Towing Units Cover** — Endorsement 54 extending third-party liability and comprehensive damage cover to unspecified attached trailers, boat haulers, or commercial couplings.
3. **Betterment Waiver / New Spare Parts Buyback** — Waives standard tariff betterment contribution percentages (deductible) when older vehicles aged 5 to 15 years are repaired with new original replacement parts.
4. **Compensation for Assessed Repair Time (CART)** — Endorsement 112 daily cash payout for the workshop repair period assessed by the insurance claims loss adjuster (e.g. 7, 14, or 21 days at RM50 to RM200 per day).
5. **Comprehensive Driver & Passenger PA Bundle (DPP / DPA)** — Pre-packaged multi-plan personal accident rider protecting driver and passengers across tiered coverage schedules.
6. **E-Hailing / Private Hire Vehicle Endorsement** — Endorsement A008 permitting comprehensive motor insurance coverage during commercial ride-hailing and e-hailing app operations (e.g. Grab).
7. **Extended & Unlimited Towing Upgrade** — Optional upgrade rider extending towing assistance distance or providing unlimited nationwide breakdown and accident towing service.
8. **Legal Liability of Passengers (LLOP)** — Endorsement 72 protecting the vehicle owner against third-party liability claims resulting from negligent acts committed by vehicle passengers (e.g. opening a car door into oncoming traffic).
9. **Legal Liability to Passengers / Pillion (LLP)** — Endorsement 100/108 protecting the insured driver/rider against legal liability lawsuits for death or bodily injury caused to authorized passengers in passenger cars or pillion riders on motorcycles.
10. **Motorcycle PA & Rider Protection Bundle** — Pre-packaged personal accident rider with roadside towing tailored specifically for motorcycle riders and pillion passengers.
11. **NCD Relief (Current Year NCD Protection)** — Endorsement 111 reimbursing or preserving the financial value of the forfeited No Claim Discount (NCD) percentage following an own-damage accident claim.
12. **SOMPO Motor N-hancer Multi-Pack** — Berjaya Sompo proprietary multi-benefit bundle combining e-hailing CART, passenger liability, and enhanced personal accident.
13. **Special Perils (Flood & Natural Disasters)** — Full comprehensive indemnity (Endorsement 57) covering loss or damage caused by flood, flash flood, typhoon, storm, landslide, earthquake, fallen trees, and convulsions of nature up to full vehicle sum insured.
14. **Strike, Riot & Civil Commotion (SRCC)** — Endorsement 25 protection against physical loss or damage directly caused by strikers, locked-out workers, public civil unrest, or malicious riots.
15. **Tool of Trade / Mobile Plant Working Risks** — Endorsement 41/42 extending third-party bodily injury and property liability while excavators, loaders, or mobile machinery operate as working tools of trade.
16. **Windscreen & Window Glass Coverage** — Repair and replacement coverage for broken windscreen, front, rear, side window glass, and solar tint film without penalty or forfeiture of accumulated No Claim Discount (NCD).

---

## 6. Tune Protect (`tune-protect`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Drive-Less Save-More (`drive-less-save-more`)** — Pay-As-You-Drive cash rebate up to 30% of premium for low annual mileage.
2. **Emergency Towing Assistance (`towing`)** — 24/7 emergency accident towing assistance to nearest workshop up to RM200.
3. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.

### Add-ons (Optional Riders):
1. **All Drivers (`all-drivers`)** — Waives RM400 compulsory excess penalty for unnamed authorized drivers.
2. **Windscreen Damage (`windscreen`)** — Covers windscreen, window glass & tint repair without affecting NCD.
3. **Inclusion of Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake & fallen trees.
4. **Legal Liability to Passenger / LLP (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury/death caused to passengers.
5. **Legal Liability to Third Party caused by Passenger / LLOP (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
6. **Value of Accessories (`vehicle-accessories`)** — Covers fitted aftermarket accessories, multimedia, dashcams, and rims.
7. **Damage to Gas Conversion Kit and Tank (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
8. **Damage to Luggage and/or Caravan Trailers (`trailers`)** — Extends damage and liability coverage to attached luggage or caravan trailers.
9. **Compensation for Assessed Repair Time / CART (`repair-allowance`)** — Daily cash allowance for workshop repair days assessed by loss adjuster.
10. **Ferry Transit to and / or from Sabah and Labuan (`ferry-transit`)** — Covers loss or damage while vehicle is transported by ferry or vessel.
11. **Strike Riot and Civil Commotions / SRCC (`strike-riot-civil-commotion`)** — Covers damage directly caused by strikes, riots, or civil commotion.
12. **Extension to Thailand (`cross-border`)** — Extends comprehensive insurance coverage into Thailand.
13. **Extension to Kalimantan and Indonesia (`cross-border`)** — Extends comprehensive insurance coverage into Kalimantan and Indonesia.
14. **Tune Drive Protect (`tune-drive-protect`)** — Personal accident, medical, and hospital income protection bundle.
15. **Waiver of Betterment (`betterment-protection`)** — Waives betterment cost-sharing on new replacement parts for cars up to 10 yrs.
16. **MotorShield Multi-in-1 Comprehensive Bundle (`motor-shield`)** — Bundles personal accident, excess waiver, side mirror, keys, and towing.

---

## 7. AmAssurance / Liberty Insurance (`amassurance`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Betterment Scale / Tariff Deductible (`betterment-protection`)** — Tariff-mandated partial cost-sharing scale applied when repairing damaged components with brand-new original items.
2. **Emergency Towing Assistance (`towing`)** — Built-in 24/7 emergency accident towing assistance to nearest approved repairer up to policy limit.
3. **Legal Defense Costs (`legal-costs-defense`)** — Reimbursement of court legal defense representation costs up to RM2,000 limit.
4. **Panel Repair Workmanship Warranty (`repair-warranty`)** — Guaranteed warranty covering repair workmanship and genuine replacement parts from panel workshops.

### Add-ons (Optional Riders):
1. **Private Hire Car / E-Hailing (`e-hailing`)** — Permits comprehensive motor insurance coverage during commercial ride-hailing operations.
2. **Compensation for Assessed Repair Time / CART (`repair-allowance`)** — Daily cash payout for the workshop repair period assessed by loss adjuster.
3. **Current Year NCD Relief (`ncd-relief`)** — Preserves the financial value of forfeited No Claim Discount (NCD) after an own-damage claim.
4. **Inclusion of Special Perils / Convulsions of Nature (`special-perils`)** — Full cover for flood, storm, landslide, earthquake & convulsions of nature.
5. **Legal Liability of Passengers / LLOP (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
6. **Legal Liability to Passengers / LLP (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury/death caused to passengers.
7. **NGV Gas (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
8. **Strike, Riot and Civil Commotion / SRCC (`strike-riot-civil-commotion`)** — Covers physical loss or damage directly caused by strikes, riots, or civil commotion.
9. **Waiver of Betterment (`betterment-protection`)** — Waives betterment contribution on new original parts for vehicles 5+ years old.
10. **Windscreen Damage (Tempered/Laminated Glass Inclusive Labour Cost) (`windscreen`)** — Repair and replacement of windscreen and glass without affecting NCD.
11. **Windscreen Damage (Tinting Film Inclusive Labour Cost) (`windscreen-tint`)** — Repair and replacement of solar tint film inclusive of labour cost.
12. **Private Car Plans 1 to 4 System / Driver & Passenger PA Bundle (`personal-accident`)** — Multi-plan personal accident rider protecting driver and passengers across tiered schedules.

---


