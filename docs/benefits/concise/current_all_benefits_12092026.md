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
1. **All Drivers Excess Waiver (`all-drivers`)** — Waives RM400 compulsory excess for unnamed licensed drivers.
2. **Betterment Waiver (`betterment-protection`)** — Waives betterment cost-sharing on older vehicles repaired with parts.
3. **Compassionate Allowance (`total-loss-theft-allowance`)** — Emergency cash payout upon vehicle flood loss or total loss.
4. **Key Care and Replacement (`key-replacement`)** — Reimburses replacement and reprogramming of lost or stolen keys.
5. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.
6. **Emergency Towing Assistance (`towing`)** — 24/7 accidental towing assistance to nearest approved panel workshop.

### Add-ons (Optional Riders):
1. **Compensation for Assessed Repair Time (`repair-allowance`)** — Daily cash allowance during workshop accident repair days.
2. **Car Detailing and Cleaning Cost (`car-detailing-cleanup`)** — Interior water damage and sanitization cleaning after floods.
3. **Special Perils (`special-perils`)** — Full protection against flood, storm, landslide and natural disasters.
4. **Legal Liability of Passengers (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
5. **Legal Liability to Passengers (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury or death to passengers.
6. **NCD Relief (`ncd-relief`)** — Protects accumulated No Claim Discount from loss after an own-damage claim.
7. **Out of Pocket Allowance (`out-of-pocket-allowance`)** — Daily cash allowance for transit and daily expenses during repairs.
8. **First Loss Special Perils (`first-loss-flood`)** — Dedicated flood and natural storm damage cover up to selected limit.
9. **Strike, Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Covers physical loss or damage caused by strikes, riots or unrest.
10. **Tuition Purpose (`tuition-purpose`)** — Extends vehicle coverage while used for driving tuition or instruction.
11. **Vehicle Accessories (`vehicle-accessories`)** — Covers fitted aftermarket multimedia, dashcams and accessories.
12. **Windscreen Coverage (`windscreen`)** — Covers windscreen, window glass and solar tint without losing NCD.
13. **Driver & Passenger Personal Accident (`personal-accident`)** — Personal accident cash benefits for driver and passengers.
14. **EV Wall Charger Cover (`ev-wall-charger`)** — Covers accidental damage, fire or theft of home EV wallbox charger.
15. **EV Battery Towing (`ev-battery-depletion-towing`)** — Emergency flatbed towing to nearest public EV charging station.
16. **EV Charger Liability (`ev-home-charger-liability`)** — Third-party injury and property liability from home EV charger.

---

## 2. STMB / Takaful Malaysia (`takaful-malaysia`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Agreed Value Settlement (`agreed-value-market-value`)** — Settles total loss or theft on agreed value without disputes.
2. **All Drivers Excess Waiver (`all-drivers`)** — Waives RM400 compulsory excess penalty for all authorized drivers.
3. **Betterment Waiver (`betterment-protection`)** — Waives betterment deductions on new parts for vehicles up to 12 years.
4. **Personal Accident (`personal-accident`)** — Complimentary accidental death cover with compassionate cash grant.
5. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.
6. **Non-Claim Cashback (`cashback-no-claim`)** — 15% surplus cashback return if no claims are incurred during the year.
7. **Emergency Towing Assistance (`towing`)** — 24/7 breakdown and accident towing assistance up to 100 km round trip.

### Add-ons (Optional Riders):
1. **Motor PA Plus (`motor-pa-plus`)** — Tiered personal accident protection for driver and passengers.
2. **Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake and fallen trees.
3. **Windscreen Coverage (`windscreen`)** — Covers windscreen, window glass and tint repair without affecting NCD.
4. **Legal Liability of Passengers (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
5. **Legal Liability to Passengers (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury or death caused to passengers.
6. **EV Wall Charger Cover (`ev-wall-charger`)** — Covers accidental damage, fire or theft of home EV wallbox charger.
7. **EV Battery Towing (`ev-battery-depletion-towing`)** — Emergency flatbed towing to nearest public EV charging station.
8. **EV Charger Liability (`ev-home-charger-liability`)** — Third-party injury and property liability from home EV charger.

---

## 3. Etiqa Insurance & Takaful (`etiqa`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Emergency Towing Assistance (`towing`)** — 24/7 accidental towing service to nearest approved repairer up to RM200.
2. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.

### Add-ons (Optional Riders):
1. **Drive-Less Save-More (`drive-less-save-more`)** — Cash rebate up to 30% of base premium for low annual mileage.
2. **Windscreen Coverage (`windscreen`)** — Covers windscreen, window glass and tint repair without affecting NCD.
3. **All Drivers Excess Waiver (`all-drivers`)** — Waives RM400 compulsory excess penalty for unnamed authorized drivers.
4. **Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake and fallen trees.
5. **Legal Liability to Passengers (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury or death to passengers.
6. **Legal Liability of Passengers (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
7. **Strike, Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Covers physical damage caused by strikes, riots or public unrest.
8. **Vehicle Accessories (`vehicle-accessories`)** — Covers fitted aftermarket accessories, dashcams, multimedia and rims.
9. **Gas Conversion Kit and Tank (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
10. **NCD Relief (`ncd-relief`)** — Protects the financial value of your No Claim Discount after a claim.
11. **Betterment Waiver (`betterment-protection`)** — Waives betterment deduction on new replacement parts up to 10 years.
12. **Key Care Replacement (`key-replacement`)** — Reimburses key and lock replacement up to RM1,000 following theft or loss.
13. **Child Car Safety Seat (`child-safety-seat`)** — Reimburses replacement or repair of child safety seats in a crash.
14. **Vehicle Respray Cover (`vehicle-respray`)** — Reimburses full exterior vehicle spray painting up to RM1,000 after repairs.
15. **Compensation for Assessed Repair Time (`repair-allowance`)** — Daily cash allowance during workshop repairs assessed by claims adjuster.
16. **EV Wall Charger Cover (`ev-wall-charger`)** — Covers accidental damage, fire or theft of home EV wallbox charger.
17. **EV Battery Towing (`ev-battery-depletion-towing`)** — Emergency flatbed towing to nearest public EV charging station.
18. **EV Charger Liability (`ev-home-charger-liability`)** — Third-party injury and property liability from home EV charger.

---

## 4. Lonpac Insurance (`lonpac`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Emergency Towing Assistance (`towing`)** — 24/7 accidental towing service to nearest approved repairer up to RM200.
2. **Out of Pocket Allowance (`out-of-pocket-allowance`)** — Lump-sum transportation expense allowance of RM75 per own damage claim.

### Add-ons (Optional Riders):
1. **Vehicle Accessories (`vehicle-accessories`)** — Covers fitted aftermarket accessories, multimedia, dashcams and rims.
2. **Betterment Waiver (`betterment-protection`)** — Waives betterment cost-sharing on new original parts for cars aged 5-10 yrs.
3. **Compensation for Assessed Repair Time (`repair-allowance`)** — Daily cash allowance for workshop repair days assessed by claims adjuster.
4. **Car Detailing and Cleaning Cost (`car-detailing-cleanup`)** — Professional interior water damage cleaning up to RM5,000 after flood.
5. **NCD Relief (`ncd-relief`)** — Preserves the value of your No Claim Discount after an own-damage claim.
6. **E-Hailing (`e-hailing`)** — Comprehensive motor insurance coverage during commercial e-hailing driving.
7. **Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake and fallen trees.
8. **Vehicle Respray Cover (`vehicle-respray`)** — Reimburses complete exterior vehicle spray painting up to RM2,000 after repair.
9. **Gas Conversion Kit and Tank (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
10. **Legal Liability of Passengers (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
11. **Legal Liability to Passengers (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury or death to passengers.
12. **Key Care Replacement (`key-replacement`)** — Reimburses key and lock replacement up to RM2,000 due to theft or loss.
13. **Strike, Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Covers physical loss or damage caused by strikes, riots or unrest.
14. **Windscreen Coverage (`windscreen`)** — Covers windscreen, window glass and tint repair without affecting NCD.
15. **Personal Accident (`personal-accident`)** — Accidental death, permanent disability and towing protection package.
16. **EV Wall Charger Cover (`ev-wall-charger`)** — Covers accidental damage, fire or theft of home EV wallbox charger.
17. **EV Battery Towing (`ev-battery-depletion-towing`)** — Emergency flatbed towing to nearest public EV charging station.
18. **EV Charger Liability (`ev-home-charger-liability`)** — Third-party injury and property liability from home EV charger.

---

## 5. Berjaya Sompo Insurance (`berjaya-sompo`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Agreed Value Settlement (`agreed-value-market-value`)** — Settles total loss or theft on agreed value for vehicles up to 3 years.
2. **All Drivers Excess Waiver (`all-drivers`)** — Waives RM400 compulsory excess for all authorized licensed drivers 21+.
3. **Emergency Towing Assistance (`towing`)** — 24/7 unlimited distance towing to panel workshops and roadside repairs.
4. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.
5. **Panel Repair Workmanship Warranty (`repair-warranty`)** — 12-month warranty on repair workmanship and replacement parts from panel shops.
6. **Personal Accident (`personal-accident`)** — Lump-sum cash benefit paid to beneficiaries upon accidental road death.
7. **Special Perils (`special-perils`)** — Built-in full protection against flood, typhoon, storm and natural disasters.

### Add-ons (Optional Riders):
1. **Accidental Boom Damage (`boom-damage`)** — Covers accidental damage to crane booms, jibs and hydraulic apparatus.
2. **Attached Trailers Cover (`trailers`)** — Extends third-party liability and damage cover to attached trailers.
3. **Betterment Waiver (`betterment-protection`)** — Waives betterment cost-sharing on new replacement parts for cars up to 15 yrs.
4. **Compensation for Assessed Repair Time (`repair-allowance`)** — Daily cash payout during workshop repair period assessed by claims adjuster.
5. **Driver & Passenger Personal Accident (`personal-accident`)** — Comprehensive tiered personal accident protection for driver and passengers.
6. **E-Hailing (`e-hailing`)** — Comprehensive coverage during commercial ride-hailing and e-hailing operations.
7. **Unlimited Towing Upgrade (`towing-upgrade`)** — Extended towing distance providing nationwide breakdown and accident recovery.
8. **Legal Liability of Passengers (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
9. **Legal Liability to Passengers (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury or death to passengers.
10. **Motorcycle PA Protection (`motorcycle-pa-bundle`)** — Personal accident protection and emergency towing for riders and pillions.
11. **NCD Relief (`ncd-relief`)** — Preserves the value of your No Claim Discount after an own-damage claim.
12. **SOMPO Motor N-hancer Multi-Pack (`sompo-n-hancer`)** — Multi-benefit bundle combining e-hailing CART, liability, and personal accident.
13. **Special Perils (`special-perils`)** — Full protection against flood, storm, landslide and natural disasters.
14. **Strike, Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Protection against damage caused by strikers, riots or civil unrest.
15. **Tool of Trade Risks (`tool-of-trade`)** — Third-party liability cover while machinery operates as a tool of trade.
16. **Windscreen Coverage (`windscreen`)** — Repair and replacement of windscreen, window glass and tint without losing NCD.
17. **EV Wall Charger Cover (`ev-wall-charger`)** — Covers accidental damage, fire or theft of home EV wallbox charger.
18. **EV Battery Towing (`ev-battery-depletion-towing`)** — Emergency flatbed towing to nearest public EV charging station.
19. **EV Charger Liability (`ev-home-charger-liability`)** — Third-party injury and property liability from home EV charger.

---

## 6. Tune Protect (`tune-protect`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Drive-Less Save-More (`drive-less-save-more`)** — Cash rebate up to 30% of base premium for low annual mileage driving.
2. **Emergency Towing Assistance (`towing`)** — 24/7 accidental towing assistance to nearest workshop up to RM200.
3. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.

### Add-ons (Optional Riders):
1. **All Drivers Excess Waiver (`all-drivers`)** — Waives RM400 compulsory excess penalty for unnamed authorized drivers.
2. **Windscreen Coverage (`windscreen`)** — Covers windscreen, window glass and tint repair without affecting NCD.
3. **Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake and fallen trees.
4. **Legal Liability to Passengers (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury or death to passengers.
5. **Legal Liability of Passengers (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
6. **Vehicle Accessories (`vehicle-accessories`)** — Covers fitted aftermarket accessories, multimedia, dashcams and rims.
7. **Gas Conversion Kit and Tank (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
8. **Attached Trailers Cover (`trailers`)** — Extends damage and liability coverage to attached luggage or caravan trailers.
9. **Compensation for Assessed Repair Time (`repair-allowance`)** — Daily cash allowance for workshop repair days assessed by claims adjuster.
10. **Ferry Transit Cover (`ferry-transit`)** — Covers loss or damage while vehicle is transported by ferry or vessel.
11. **Strike, Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Covers damage directly caused by strikes, riots or civil commotion.
12. **Cross-Border Extension (`cross-border`)** — Extends comprehensive insurance coverage into Thailand and Kalimantan.
13. **Tune Drive Protect (`tune-drive-protect`)** — Personal accident, medical, and hospital income protection bundle.
14. **Betterment Waiver (`betterment-protection`)** — Waives betterment cost-sharing on new replacement parts for cars up to 10 yrs.
15. **MotorShield Multi-Pack (`motor-shield`)** — Bundles personal accident, excess waiver, side mirror, keys and towing.
16. **EV Wall Charger Cover (`ev-wall-charger`)** — Covers accidental damage, fire or theft of home EV wallbox charger.
17. **EV Battery Towing (`ev-battery-depletion-towing`)** — Emergency flatbed towing to nearest public EV charging station.
18. **EV Charger Liability (`ev-home-charger-liability`)** — Third-party injury and property liability from home EV charger.

---

## 7. AmAssurance / Liberty Insurance (`amassurance`)

### Defaults (Included at RM 0 / Base Cover — Comprehensive):
1. **Betterment Scale (`betterment-protection`)** — Tariff cost-sharing scale applied when repairing with new original parts.
2. **Emergency Towing Assistance (`towing`)** — Built-in 24/7 emergency accident towing assistance up to policy limit.
3. **Legal Defense Costs (`legal-costs-defense`)** — Reimburses court legal representation and defense fees up to RM2,000.
4. **Panel Repair Workmanship Warranty (`repair-warranty`)** — Guaranteed warranty covering repair workmanship and replacement parts.

### Add-ons (Optional Riders):
1. **E-Hailing (`e-hailing`)** — Permits comprehensive motor insurance coverage during commercial ride-hailing.
2. **Compensation for Assessed Repair Time (`repair-allowance`)** — Daily cash payout for workshop repair period assessed by claims adjuster.
3. **NCD Relief (`ncd-relief`)** — Preserves the value of forfeited No Claim Discount after an own-damage claim.
4. **Special Perils (`special-perils`)** — Full cover for flood, storm, landslide, earthquake and natural disasters.
5. **Legal Liability of Passengers (`legal-liability-of-passengers`)** — Protects against third-party claims caused by passenger negligence.
6. **Legal Liability to Passengers (`legal-liability-to-passengers`)** — Protects driver from lawsuits for injury or death to passengers.
7. **Gas Conversion Kit and Tank (`gas-conversion`)** — Dedicated damage cover for installed NGV gas conversion tanks and kits.
8. **Strike, Riot & Civil Commotion (`strike-riot-civil-commotion`)** — Covers physical loss or damage caused by strikes, riots or civil unrest.
9. **Betterment Waiver (`betterment-protection`)** — Waives betterment contribution on new original parts for vehicles 5+ years old.
10. **Windscreen Coverage (`windscreen`)** — Repair and replacement of windscreen and glass without affecting NCD.
11. **Solar Tint Film Coverage (`windscreen-tint`)** — Repair and replacement of solar tint film inclusive of labour cost.
12. **Driver & Passenger Personal Accident (`personal-accident`)** — Multi-plan personal accident protection for driver and passengers.
13. **EV Wall Charger Cover (`ev-wall-charger`)** — Covers accidental damage, fire or theft of home EV wallbox charger.
14. **EV Battery Towing (`ev-battery-depletion-towing`)** — Emergency flatbed towing to nearest public EV charging station.
15. **EV Charger Liability (`ev-home-charger-liability`)** — Third-party injury and property liability from home EV charger.

---
