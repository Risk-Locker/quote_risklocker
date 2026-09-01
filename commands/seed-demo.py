"""Seed verified demo data and clean up junk test rows.

Usage:
    python commands/seed-demo.py           # Dry-run (reports proposed changes)
    python commands/seed-demo.py --apply   # Commits changes to the database
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, or_, select, text, update
from app.db.session import SessionLocal
from app.models.tables import (
    BenefitAlias,
    BenefitCatalog,
    BenefitCatalogRevision,
    BenefitConcept,
    BenefitPackage,
    BenefitPackagePlan,
    BenefitPackagePlanItem,
    BenefitRelation,
    BusinessAsset,
    CatalogOffering,
    CompanyAlias,
    CoverageType,
    InsuranceCompany,
    InsuranceProduct,
    InsuranceProductTier,
    QuotationDraft,
    Segment,
    TrashRecord,
    VehicleCategory,
    new_id,
    utcnow,
)


def _normalize_phrase(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

BENEFIT_CONCEPTS_DATA: list[dict[str, Any]] = [{'concept_key': 'own-damage', 'label': 'Own Damage', 'category': 'default', 'asset_label': 'Car Theft / Total Loss Assistance', 'description': 'Accidental collision, overturning, fire, explosion, lightning, burglary, theft, malicious act, and inland transit.', 'match_dataset': ['own damage', 'comprehensive own damage', 'accidental damage', 'collision'], 'sort_order': 1}, {'concept_key': 'third-party-bi', 'label': 'Third Party Bodily Injury', 'category': 'default', 'asset_label': 'Personal Accident', 'description': 'Unlimited statutory legal liability protection for death or bodily injury sustained by third parties.', 'match_dataset': ['third party bodily injury', 'third party bi', 'bodily injury and death'], 'sort_order': 2}, {'concept_key': 'third-party-property', 'label': 'Third Party Property Damage', 'category': 'default', 'asset_label': 'Out-of-Pocket Allowance', 'description': 'Indemnity against legal liability for damage caused to third-party vehicles, fixtures, and properties up to RM 3,000,000.', 'match_dataset': ['third party property', 'tppd', 'property damage'], 'sort_order': 3}, {'concept_key': 'fire-theft', 'label': 'Fire & Theft Cover', 'category': 'default', 'asset_label': 'Car Theft / Total Loss Assistance', 'description': 'Protection against accidental fire, explosion, self-ignition, lightning, vehicle theft, and break-in.', 'match_dataset': ['fire and theft', 'fire & theft', 'theft indemnity', 'fire explosion'], 'sort_order': 4}, {'concept_key': 'towing', 'label': 'Emergency Towing Assistance', 'category': 'default', 'asset_label': 'Towing', 'description': '24/7 accident emergency towing assistance to nearest approved repairer or safe storage up to designated limit.', 'match_dataset': ['towing', 'emergency towing', 'towing assistance', 'breakdown towing'], 'sort_order': 5}, {'concept_key': 'roadside-assistance', 'label': 'Roadside Assistance', 'category': 'default', 'asset_label': 'Emergency Roadside Assistance', 'description': '24/7 on-site breakdown assistance including jump-start, minor mechanical fixes, and roadside repair support.', 'match_dataset': ['roadside assistance', 'road assist', 'tele bantuan', 'auto assist'], 'sort_order': 6}, {'concept_key': 'repair-workmanship-warranty', 'label': 'Workmanship Warranty', 'category': 'default', 'asset_label': 'Repair Workmanship Warranty', 'description': '6-month to 3-year warranty on bodywork, spray painting, and replacement parts from approved panel workshops.', 'match_dataset': ['workmanship warranty', 'repair warranty', 'panel warranty', 'workmanship'], 'sort_order': 7}, {'concept_key': 'legal-costs-defense', 'label': 'Legal Defense Costs', 'category': 'default', 'asset_label': 'Legal Liability of Passengers', 'description': 'Reimbursement of approved legal representation expenses incurred in court defense up to RM 2,000.', 'match_dataset': ['legal defense', 'legal costs', 'court defense'], 'sort_order': 8}, {'concept_key': 'betterment-protection', 'label': 'Betterment Waiver / Scale', 'category': 'default', 'asset_label': 'Waiver of Betterment', 'description': 'Waiver or standard tariff scale (0%-40%) for new original replacement parts on vehicles aged 5-15 years.', 'match_dataset': ['betterment', 'betterment waiver', 'waiver of betterment', 'betterment scale', 'betterment buyback'], 'sort_order': 9}, {'concept_key': 'all-drivers', 'label': 'All Drivers Excess Waiver', 'category': 'default', 'asset_label': 'All Drivers Coverage', 'description': 'Extends policy coverage to any authorized licensed driver and waives the RM 400 unnamed driver compulsory excess.', 'match_dataset': ['all drivers', 'unnamed drivers', 'all drivers waiver', 'any driver', 'all-riders'], 'sort_order': 10}, {'concept_key': 'agreed-value-market-value', 'label': 'Agreed Value Settlement', 'category': 'default', 'asset_label': 'Agreed Value / Market Value Settlement', 'description': 'Guaranteed settlement based on agreed sum insured or ISM valuation with zero market depreciation disputes upon total loss.', 'match_dataset': ['agreed value', 'agreed value settlement', 'market value settlement'], 'sort_order': 11}, {'concept_key': 'cashback-no-claim', 'label': 'No-Claim Cashback / Rebate', 'category': 'default', 'asset_label': 'No-Claim Cashback / NCD / Cashback Reward', 'description': 'Cashback reward or distributable surplus payout via Hibah of 15% to 30% for claim-free policy terms.', 'match_dataset': ['cashback', 'no claim cashback', 'hibah cashback', 'surplus cashback'], 'sort_order': 12}, {'concept_key': 'payd-telematics', 'label': 'Pay-As-You-Drive Telematics', 'category': 'default', 'asset_label': 'No-Claim Cashback / NCD / Cashback Reward', 'description': 'Smart telematics driving reward offering 15% to 20% premium cash refund based on low daily vehicle mileage.', 'match_dataset': ['payd', 'pay as you drive', 'telematics', 'driving less rebate'], 'sort_order': 13}, {'concept_key': 'windscreen', 'label': 'Windscreen & Window Glass', 'category': 'addon', 'asset_label': 'Windscreen Coverage', 'description': 'Repair or replacement of broken windscreen, windows, and sunroof glass including solar tint film without NCD penalty.', 'match_dataset': ['windscreen', 'windshield', 'window glass', 'sunroof glass', 'cermin depan', 'end 89', 'end 89a'], 'sort_order': 14}, {'concept_key': 'special-perils', 'label': 'Inclusion of Special Perils', 'category': 'addon', 'asset_label': 'Special Perils', 'description': 'Full comprehensive protection against natural disasters including flood, storm, typhoon, landslide, and earthquakes.', 'match_dataset': ['special perils', 'flood', 'bencana alam', 'banjir', 'perils', 'end 57'], 'sort_order': 15}, {'concept_key': 'first-loss-flood', 'label': 'First Loss Flood', 'category': 'addon', 'asset_label': 'Flood Coverage / Flood Damage Protection', 'description': 'Standalone first loss natural disaster and flood damage coverage up to RM 10,000 without under-insurance penalty.', 'match_dataset': ['first loss flood', 'first loss special perils', 'end 117'], 'sort_order': 16}, {'concept_key': 'strike-riot-civil-commotion', 'label': 'Strike, Riot & Civil Commotion', 'category': 'addon', 'asset_label': 'Strike, Riot and Civil Commotion', 'description': 'Loss or physical damage protection caused by strikers, locked-out workers, riots, and public civil unrest.', 'match_dataset': ['srcc', 'strike riot', 'civil commotion', 'rusuhan', 'end 25'], 'sort_order': 17}, {'concept_key': 'legal-liability-to-passengers', 'label': 'Legal Liability to Passengers', 'category': 'addon', 'asset_label': 'Legal Liability to Passengers', 'description': 'Legal liability indemnity for accidental bodily injury or death claims made by authorized vehicle passengers.', 'match_dataset': ['llp', 'legal liability to passengers', 'passenger liability', 'end 100', 'end 19'], 'sort_order': 18}, {'concept_key': 'legal-liability-of-passengers', 'label': 'Legal Liability of Passengers', 'category': 'addon', 'asset_label': 'Legal Liability of Passengers', 'description': 'Protection against legal liability for third-party property damage or negligence caused by vehicle passengers.', 'match_dataset': ['llop', 'legal liability of passengers', 'end 72'], 'sort_order': 19}, {'concept_key': 'legal-liability-to-pillion', 'label': 'Legal Liability to Pillion', 'category': 'addon', 'asset_label': 'Legal Liability to Passengers', 'description': 'Extends rider legal liability coverage for accidental bodily injury or death to authorized pillion passengers.', 'match_dataset': ['legal liability to pillion', 'pillion liability', 'llp pillion', 'end 108'], 'sort_order': 20}, {'concept_key': 'repair-allowance', 'label': 'Compensation for Assessed Repair Time (CART)', 'category': 'addon', 'asset_label': 'Transportation Allowance', 'description': 'Daily compensation allowance (RM 50-RM 100/day for 7-14 days) during vehicle workshop repairs without NCD loss.', 'match_dataset': ['cart', 'repair allowance', 'assessed repair time', 'cash assistance', 'end 112'], 'sort_order': 21}, {'concept_key': 'key-replacement', 'label': 'Key Care & Replacement', 'category': 'addon', 'asset_label': 'Key Replacement / Key Care', 'description': 'Reimbursement for replacement, repair, or reprogramming of lost, stolen, or damaged smart keys and locks up to RM 1,000.', 'match_dataset': ['key replacement', 'key care', 'smart key', 'kunci', 'end dt5'], 'sort_order': 22}, {'concept_key': 'personal-belongings-theft', 'label': 'Personal Belongings Theft', 'category': 'addon', 'asset_label': 'Window Snatch Theft / Smash and Grab', 'description': 'Reimbursement for personal belongings, handbag, or laptop lost due to vehicle break-in or smash-and-grab theft.', 'match_dataset': ['snatch theft', 'personal belongings', 'smash and grab', 'ragut'], 'sort_order': 23}, {'concept_key': 'total-loss-theft-allowance', 'label': 'Total Loss / Theft Allowance', 'category': 'addon', 'asset_label': 'Compassionate Allowance for Loss of Vehicle', 'description': 'Compassionate lump-sum cash allowance of 5% to 10% sum insured upon total constructive loss or vehicle theft.', 'match_dataset': ['total loss allowance', 'calv', 'theft allowance', 'convenience cash'], 'sort_order': 24}, {'concept_key': 'flood-relief-allowance', 'label': 'Flood Relief Cash Allowance', 'category': 'addon', 'asset_label': 'Flood Relief Allowance / Cash Assistance', 'description': 'Immediate lump-sum compassionate cash allowance (RM 1,500 - RM 3,000) payable upon flood or water damage.', 'match_dataset': ['flood relief', 'flood allowance', 'compassionate flood'], 'sort_order': 25}, {'concept_key': 'ambulance-fees', 'label': 'Ambulance Transport Fees', 'category': 'addon', 'asset_label': 'Ambulance Fees', 'description': 'Reimbursement for emergency ambulance transport fees to hospital following a road traffic accident.', 'match_dataset': ['ambulance', 'ambulance fees', 'ambulance reimbursement'], 'sort_order': 26}, {'concept_key': 'medical-expenses', 'label': 'Medical Expenses Reimbursement', 'category': 'addon', 'asset_label': 'Medical Expenses', 'description': 'Reimbursement of medical, clinical, and hospitalisation expenses incurred from motor accident injuries.', 'match_dataset': ['medical expenses', 'medical reimbursement', 'clinical expenses'], 'sort_order': 27}, {'concept_key': 'hospital-income', 'label': 'Daily Hospital Income', 'category': 'addon', 'asset_label': 'Daily Hospital Income', 'description': 'Daily hospitalization cash allowance (RM 20 - RM 100/day up to 30-60 days) for inpatient accident treatment.', 'match_dataset': ['hospital income', 'hospital allowance', 'daily hospital cash'], 'sort_order': 28}, {'concept_key': 'bereavement-allowance', 'label': 'Bereavement & Funeral Cash', 'category': 'addon', 'asset_label': 'Bereavement Allowance', 'description': 'Lump-sum compassionate bereavement benefit (RM 1,000 - RM 3,000) payable to next-of-kin upon accidental death.', 'match_dataset': ['bereavement', 'bereavement allowance', 'funeral expenses', 'khairat kematian'], 'sort_order': 29}, {'concept_key': 'car-detailing-cleanup', 'label': 'Flood Detailing & Cleaning', 'category': 'addon', 'asset_label': 'Flood Relief Allowance / Cash Assistance', 'description': 'Professional interior vehicle cleaning and sanitisation reimbursement (up to RM 1,500) following flood damage.', 'match_dataset': ['flood cleaning', 'car detailing', 'water damage cleaning', 'interior cleaning'], 'sort_order': 30}, {'concept_key': 'repaint-spray-paint', 'label': 'Full Car Spray Painting', 'category': 'addon', 'asset_label': 'Whole Car Spray Painting / New Coat of Paint', 'description': 'Full exterior vehicle body spray painting coverage (up to RM 2,000) following approved accident repairs.', 'match_dataset': ['spray painting', 'respray', 'cat baru', 'paint cover'], 'sort_order': 31}, {'concept_key': 'child-car-seat', 'label': 'Child Car Safety Seat Cover', 'category': 'addon', 'asset_label': 'Child Car Seat Coverage', 'description': 'Reimbursement for repair or replacement of child safety car seats (up to RM 500) damaged by accident, flood, or theft.', 'match_dataset': ['child seat', 'child car seat', 'safety seat'], 'sort_order': 32}, {'concept_key': 'side-mirror-protection', 'label': 'Side Mirror Replacement', 'category': 'addon', 'asset_label': 'Side Mirror Coverage', 'description': 'Repair or replacement of broken exterior wing mirrors and electronic side mirror assemblies up to RM 1,000.', 'match_dataset': ['side mirror', 'wing mirror', 'cermin sisi'], 'sort_order': 33}, {'concept_key': 'ev-wall-charger', 'label': 'EV Charger & Wallbox Cover', 'category': 'addon', 'asset_label': 'Out-of-Pocket Allowance', 'description': 'Dedicated EV protection covering home wallbox damage, third-party charger liability, and battery depletion towing.', 'match_dataset': ['ev wall charger', 'ev charger', 'wallbox', 'ev smart pack'], 'sort_order': 34}, {'concept_key': 'vehicle-accessories', 'label': 'Vehicle Accessories', 'category': 'addon', 'asset_label': 'Side Mirror Coverage', 'description': 'Separate coverage for non-factory fitted multimedia systems, dashcams, alloy rims, and aerodynamic body kits.', 'match_dataset': ['accessories', 'vehicle accessories', 'non-standard accessories', 'aksesori', 'end 97'], 'sort_order': 35}, {'concept_key': 'e-hailing-extension', 'label': 'E-Hailing / Private Hire', 'category': 'addon', 'asset_label': 'e-Hailing / Private Hire Extension', 'description': 'Comprehensive endorsement authorizing commercial e-hailing operations (Grab, AirAsia Ride) with passenger liability.', 'match_dataset': ['e-hailing', 'ehailing', 'private hire', 'grab cover'], 'sort_order': 36}, {'concept_key': 'ncd-relief', 'label': 'Current Year NCD Relief', 'category': 'addon', 'asset_label': 'No-Claim Cashback / NCD / Cashback Reward', 'description': 'Reimburses or protects the accumulated No Claim Discount entitlement from reset following an own-damage claim.', 'match_dataset': ['ncd relief', 'current year ncd', 'ncd protection', 'end 111'], 'sort_order': 37}, {'concept_key': 'increased-tppd', 'label': 'Increased TPPD Limit', 'category': 'addon', 'asset_label': 'Out-of-Pocket Allowance', 'description': 'Upgrades third-party property damage indemnity limit from RM 3,000,000 up to RM 4,000,000 - RM 6,000,000.', 'match_dataset': ['increased tppd', 'tppd limit', 'end 105'], 'sort_order': 38}, {'concept_key': 'ferry-transit', 'label': 'Ferry Transit (Sabah-Labuan)', 'category': 'addon', 'asset_label': 'Transportation Allowance', 'description': 'Marine transit loss or damage coverage across Sabah, Sarawak, FT Labuan, or Penang island waterways.', 'match_dataset': ['ferry transit', 'marine transit', 'sabah-labuan ferry', 'end 109'], 'sort_order': 39}, {'concept_key': 'cross-border', 'label': 'Cross-Border (Thailand/Kalimantan)', 'category': 'addon', 'asset_label': 'Courtesy Car / Replacement Car', 'description': 'Geographical policy extension into the Kingdom of Thailand, Kalimantan, or Brunei with TPPD indemnity.', 'match_dataset': ['cross-border', 'cross border', 'thailand extension', 'kalimantan extension', 'end 101', 'end 102'], 'sort_order': 40}, {'concept_key': 'overturning', 'label': 'Vehicle Overturning Damage', 'category': 'addon', 'asset_label': 'Special Perils', 'description': 'Inclusion of accidental damage caused by vehicle overturning or load shifts during commercial transport.', 'match_dataset': ['overturning', 'overturn inclusion', 'end 38'], 'sort_order': 41}, {'concept_key': 'authorized-attendants', 'label': 'Authorized Attendants Liability', 'category': 'addon', 'asset_label': 'Legal Liability to Passengers', 'description': 'Legal liability protection for authorized corporate crew members, loaders, or cabin attendants being carried.', 'match_dataset': ['authorized attendants', 'cabin attendants', 'attendant liability', 'end 19i'], 'sort_order': 42}, {'concept_key': 'boom-damage', 'label': 'Crane Boom Damage', 'category': 'addon', 'asset_label': 'Special Perils', 'description': 'Accidental and unforeseen physical damage protection to crane boom attachment while in use as a tool of trade.', 'match_dataset': ['boom damage', 'crane boom', 'end 38a'], 'sort_order': 43}, {'concept_key': 'tool-of-trade', 'label': 'Tool of Trade Working Risks', 'category': 'addon', 'asset_label': 'Legal Liability of Passengers', 'description': 'Third-party bodily injury and property damage liability while vehicle is operating as a mobile plant / tool of trade.', 'match_dataset': ['tool of trade', 'mobile plant', 'working risks', 'end 41', 'end 42'], 'sort_order': 44}, {'concept_key': 'attached-trailers', 'label': 'Attached Trailers & Couplings', 'category': 'addon', 'asset_label': 'Transportation Allowance', 'description': 'Indemnity extension covering unspecified attached trailer units and commercial couplings in transit.', 'match_dataset': ['attached trailers', 'trailer cover', 'end 54'], 'sort_order': 45}, {'concept_key': 'gas-conversion-kit', 'label': 'NGV Gas Conversion Kit', 'category': 'addon', 'asset_label': 'Side Mirror Coverage', 'description': 'Separate insurance protection for installed natural gas fuel conversion tanks, valves, and kit hardware.', 'match_dataset': ['gas conversion kit', 'ngv gas kit', 'gas tank'], 'sort_order': 46}, {'concept_key': 'cargo-protection', 'label': 'Cargo & Goods in Transit', 'category': 'addon', 'asset_label': 'Out-of-Pocket Allowance', 'description': 'Protection for enterprise trade merchandise and goods carried under commercial C-Permit / A-Permit haulage.', 'match_dataset': ['cargo protection', 'goods in transit', 'cargo liability'], 'sort_order': 47}, {'concept_key': 'accidental-death', 'label': 'Accidental Death Benefit', 'category': 'addon', 'asset_label': 'Personal Accident', 'description': 'Lump-sum accidental death benefit per insured person in the vehicle.', 'match_dataset': ['accidental death', 'kematian akibat kemalangan'], 'sort_order': 48}, {'concept_key': 'permanent-disablement', 'label': 'Permanent Disablement Benefit', 'category': 'addon', 'asset_label': 'Personal Accident', 'description': 'Tiered lump-sum compensation for permanent total or partial disablement per insured person.', 'match_dataset': ['permanent disablement', 'keilatan kekal', 'tpd'], 'sort_order': 49}, {'concept_key': 'double-indemnity', 'label': 'Double Indemnity', 'category': 'addon', 'asset_label': 'Personal Accident', 'description': 'Double benefit payout for quadriplegia or accidents occurring during national public holidays.', 'match_dataset': ['double indemnity', 'ganti rugi berganda'], 'sort_order': 50}, {'concept_key': 'auto-assistance', 'label': 'Auto Assistance / Towing Rider', 'category': 'addon', 'asset_label': 'Emergency Roadside Assistance', 'description': 'Standalone 24-hour unlimited mileage towing and nationwide roadside emergency breakdown assistance rider.', 'match_dataset': ['auto assistance', 'extended towing rider'], 'sort_order': 51}]

INSURER_CONFIGS: list[dict[str, Any]] = [{'company_slug': 'amassurance', 'company_name': 'AmAssurance', 'products': [{'product_key': 'amassurance-auto365-lite', 'product_name': 'Auto365 Comprehensive Lite', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'amassurance-auto365-plus', 'product_name': 'Auto365 Comprehensive Plus', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'Waives unnamed driver excess', 'price': 0}, {'concept_key': 'flood-relief-allowance', 'display_value': 'Immediate flood assistance cash', 'price': 0}, {'concept_key': 'key-replacement', 'display_value': 'Lost/stolen smart key', 'price': 0}, {'concept_key': 'personal-belongings-theft', 'display_value': 'In-car snatch theft', 'price': 0}, {'concept_key': 'ambulance-fees', 'display_value': 'Emergency ambulance costs', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'amassurance-auto365-premier', 'product_name': 'Auto365 Comprehensive Premier', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'Waives unnamed driver excess', 'price': 0}, {'concept_key': 'flood-relief-allowance', 'display_value': 'Immediate flood assistance cash', 'price': 0}, {'concept_key': 'key-replacement', 'display_value': 'Lost/stolen smart key', 'price': 0}, {'concept_key': 'personal-belongings-theft', 'display_value': 'In-car snatch theft', 'price': 0}, {'concept_key': 'ambulance-fees', 'display_value': 'Emergency ambulance costs', 'price': 0}, {'concept_key': 'out-of-pocket-allowance', 'display_value': 'Total loss lifestyle payout', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'amassurance-motorcycle-standard', 'product_name': 'Standard Motorcycle Comprehensive', 'segment_key': 'private', 'vehicle_key': 'motorcycle', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental collision, fire & theft', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All authorized riders covered', 'price': 0}]}]}, {'company_slug': 'berjaya-sompo', 'company_name': 'Berjaya Sompo', 'products': [{'product_key': 'berjayasompo-private-car', 'product_name': 'Private Car Comprehensive', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'berjayasompo-motorcycle', 'product_name': 'Motorcycle Comprehensive', 'segment_key': 'private', 'vehicle_key': 'motorcycle', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental collision, fire & theft', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All authorized riders covered', 'price': 0}]}]}, {'company_slug': 'etiqa', 'company_name': 'Etiqa', 'products': [{'product_key': 'etiqa-private-car', 'product_name': 'Etiqa Private Car Comprehensive', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 Roadside towing (200km)', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'etiqa-motorcycle', 'product_name': 'Etiqa Motorcycle Comprehensive', 'segment_key': 'private', 'vehicle_key': 'motorcycle', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental collision, fire & theft', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All authorized riders covered', 'price': 0}]}]}, {'company_slug': 'lonpac', 'company_name': 'Lonpac', 'products': [{'product_key': 'lonpac-private-car', 'product_name': 'Lonpac Private Car Comprehensive', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'lonpac-motorcycle', 'product_name': 'Lonpac Motorcycle Comprehensive', 'segment_key': 'private', 'vehicle_key': 'motorcycle', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental collision, fire & theft', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All authorized riders covered', 'price': 0}]}]}, {'company_slug': 'qbe', 'company_name': 'QBE', 'products': [{'product_key': 'qbe-private-car', 'product_name': 'QBE Private Car Comprehensive', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'qbe-motorcycle', 'product_name': 'QBE Motorcycle Comprehensive', 'segment_key': 'private', 'vehicle_key': 'motorcycle', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental collision, fire & theft', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All authorized riders covered', 'price': 0}]}]}, {'company_slug': 'takaful-malaysia', 'company_name': 'Takaful Malaysia', 'products': [{'product_key': 'stmb-private-car', 'product_name': 'STMB Private Car Comprehensive', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'stmb-motorcycle', 'product_name': 'STMB Motorcycle Comprehensive', 'segment_key': 'private', 'vehicle_key': 'motorcycle', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental collision, fire & theft', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All authorized riders covered', 'price': 0}]}]}, {'company_slug': 'tune-protect', 'company_name': 'Tune Protect', 'products': [{'product_key': 'tune-protect-motor-easy', 'product_name': 'Tune Protect Motor Easy', 'segment_key': 'private', 'vehicle_key': 'car', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental damage, fire & theft', 'price': 0}, {'concept_key': 'towing', 'display_value': '24/7 accident & breakdown towing', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}, {'concept_key': 'flood-relief-allowance', 'display_value': 'Compassionate flood relief', 'price': 0}], 'addons': [{'concept_key': 'windscreen', 'display_value': 'Windscreen & glass replacement', 'price': 0}, {'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'legal-liability-to-passengers', 'display_value': 'Legal liability to passengers', 'price': 0}, {'concept_key': 'legal-liability-of-passengers', 'display_value': 'Legal liability of passengers', 'price': 0}, {'concept_key': 'repair-allowance', 'display_value': 'Compensation for repair time', 'price': 0}, {'concept_key': 'vehicle-accessories', 'display_value': 'Non-standard accessories', 'price': 0}, {'concept_key': 'e-hailing-extension', 'display_value': 'Commercial private hire coverage', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All unnamed drivers covered', 'price': 0}]}, {'product_key': 'tune-protect-motorcycle', 'product_name': 'Tune Protect Motorcycle', 'segment_key': 'private', 'vehicle_key': 'motorcycle', 'coverage_key': 'comprehensive', 'default_benefits': [{'concept_key': 'own-damage', 'display_value': 'Accidental collision, fire & theft', 'price': 0}, {'concept_key': 'betterment-protection', 'display_value': 'Waiver of betterment charges', 'price': 0}, {'concept_key': 'legal-costs-defense', 'display_value': 'Traffic court legal defense', 'price': 0}], 'addons': [{'concept_key': 'special-perils', 'display_value': 'Flood, storm & natural disasters', 'price': 0}, {'concept_key': 'strike-riot-civil-commotion', 'display_value': 'Strike, riot & civil commotion', 'price': 0}, {'concept_key': 'all-drivers', 'display_value': 'All authorized riders covered', 'price': 0}]}]}]

def cleanup_junk(db, dry_run: bool) -> list[str]:
    logs = []
    db.execute(delete(TrashRecord).where(TrashRecord.purge_after < utcnow()))
    logs.append("Purged expired trash records")
    return logs


def seed_global_benefits(db, dry_run: bool) -> dict[str, BenefitConcept]:
    assets_by_label = {a.label: a for a in db.scalars(select(BusinessAsset)).all()}
    concepts_by_key = {}
    for c_data in BENEFIT_CONCEPTS_DATA:
        k = c_data["concept_key"]
        concept = db.scalar(select(BenefitConcept).where(BenefitConcept.concept_key == k))
        asset_obj = assets_by_label.get(c_data["asset_label"])
        if not concept:
            concept = BenefitConcept(
                id=new_id(),
                concept_key=k,
                label=c_data["label"],
                value_schema={"type": "object"},
                display_template="{label}",
                required_variables=[],
                optional_variables=[],
                validation_rules={},
                default_asset_id=asset_obj.id if asset_obj else None,
                description=c_data["description"],
                demo_value=None,
                match_dataset=c_data["match_dataset"],
                value_pattern_dataset=[],
                description_variants=[{"category": c_data.get("category", "default")}],
                sort_order=c_data["sort_order"],
                revision=1,
                status="active",
            )
            if not dry_run:
                db.add(concept)
                db.flush()
        else:
            if not dry_run:
                concept.label = c_data["label"]
                concept.description = c_data["description"]
                concept.sort_order = c_data["sort_order"]
                concept.match_dataset = c_data["match_dataset"]
                if asset_obj:
                    concept.default_asset_id = asset_obj.id
                concept.description_variants = [{"category": c_data.get("category", "default")}]
                db.flush()
        concepts_by_key[k] = concept

    # Scoped aliases with in-memory deduplication
    existing_aliases = {(a.benefit_id, a.normalized_phrase) for a in db.scalars(select(BenefitAlias)).all()}
    for c_data in BENEFIT_CONCEPTS_DATA:
        k = str(c_data["concept_key"])
        target = concepts_by_key.get(k)
        if not target:
            continue
        match_dataset: list[str] = list(c_data.get("match_dataset") or [])
        for phrase in match_dataset:
            norm = _normalize_phrase(phrase)
            if not norm or (target.id, norm) in existing_aliases:
                continue
            existing_aliases.add((target.id, norm))
            if not dry_run:
                alias = BenefitAlias(
                    id=new_id(),
                    benefit_id=target.id,
                    phrase=phrase,
                    normalized_phrase=norm,
                    scope="global",
                    status="active",
                )
                db.add(alias)

    if not dry_run:
        db.flush()

    return concepts_by_key


def seed_company_package_chains(db, dry_run: bool) -> list[str]:
    logs = []
    concepts = {bc.concept_key: bc for bc in db.scalars(select(BenefitConcept)).all()}
    segments = {s.segment_key: s for s in db.scalars(select(Segment)).all()}
    vehicles = {v.category_key: v for v in db.scalars(select(VehicleCategory)).all()}
    coverages = {c.coverage_key: c for c in db.scalars(select(CoverageType)).all()}

    for c_data in INSURER_CONFIGS:
        c_slug = str(c_data["company_slug"])
        c_name = str(c_data["company_name"])
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == c_slug))
        if not company:
            logs.append(f"Company {c_name} ({c_slug}) not found, skipping")
            continue

        products: list[dict[str, Any]] = list(c_data.get("products") or [])
        for p_info in products:
            base_p_key = str(p_info["product_key"])
            base_p_name = str(p_info["product_name"])
            seg_key = str(p_info.get("segment_key") or "private")
            veh_key = str(p_info.get("vehicle_key") or "car")

            seg_obj = segments.get(seg_key)
            veh_obj = vehicles.get(veh_key)

            if p_info.get("only_comprehensive") or "-plus" in base_p_key or "-premier" in base_p_key:
                cov_definitions = [
                    ("comprehensive", base_p_key, base_p_name),
                ]
            else:
                cov_definitions = [
                    ("comprehensive", base_p_key, base_p_name),
                    ("third_party_fire_theft", f"{base_p_key}-tpft", f"{base_p_name} (TPFT)"),
                    ("third_party", f"{base_p_key}-tpo", f"{base_p_name} (Third Party)"),
                ]

            for cov_key, p_key, p_name in cov_definitions:
                target_cov_obj = coverages.get(cov_key)
                if not target_cov_obj:
                    continue

                product = db.scalar(select(InsuranceProduct).where(
                    InsuranceProduct.company_id == company.id,
                    InsuranceProduct.product_key == p_key
                ))
                if not product:
                    product = InsuranceProduct(
                        id=new_id(),
                        company_id=company.id,
                        product_key=p_key,
                        name=p_name,
                        status="active",
                        revision=1
                    )
                    if not dry_run:
                        db.add(product)
                        db.flush()
                    logs.append(f"Created product '{p_name}' for {c_name}")
                elif not dry_run:
                    product.name = p_name
                    product.status = "active"
                    db.flush()

                catalog = db.scalar(select(BenefitCatalog).where(
                    BenefitCatalog.product_id == product.id
                ))
                if not catalog:
                    catalog = BenefitCatalog(
                        id=new_id(),
                        company_id=company.id,
                        product_id=product.id,
                        segment_id=seg_obj.id if seg_obj else None,
                        vehicle_category_id=veh_obj.id if veh_obj else None,
                        coverage_type_id=target_cov_obj.id,
                        name=p_name,
                        status="active",
                        revision=1
                    )
                    if not dry_run:
                        db.add(catalog)
                        db.flush()
                elif not dry_run:
                    catalog.name = p_name
                    catalog.segment_id = seg_obj.id if seg_obj else None
                    catalog.vehicle_category_id = veh_obj.id if veh_obj else None
                    catalog.coverage_type_id = target_cov_obj.id
                    catalog.status = "active"
                    db.flush()

                if dry_run:
                    continue

                latest_rev = db.scalar(select(BenefitCatalogRevision).where(
                    BenefitCatalogRevision.catalog_id == catalog.id
                ).order_by(BenefitCatalogRevision.revision_number.desc()))

                if latest_rev and latest_rev.state == "draft":
                    rev = latest_rev
                else:
                    next_rev_num = (latest_rev.revision_number + 1) if latest_rev else 1
                    rev = BenefitCatalogRevision(
                        id=new_id(),
                        catalog_id=catalog.id,
                        revision_number=next_rev_num,
                        state="draft",
                        content_hash="seed_hash",
                        published_by=None,
                        published_at=None
                    )
                    db.add(rev)
                    db.flush()

                existing_offs = list(db.scalars(select(CatalogOffering).where(
                    CatalogOffering.catalog_revision_id == rev.id
                )).all())
                existing_off_keys = {o.offering_key: o for o in existing_offs}

                order_idx = 1

                defaults_list: list[dict[str, Any]] = []
                if cov_key == "comprehensive":
                    defaults_list = list(p_info.get("default_benefits") or [])
                elif cov_key == "third_party_fire_theft":
                    defaults_list = [
                        {"concept_key": "fire-theft", "display_value": "Accidental fire, explosion, lightning, and theft indemnity", "price": 0},
                        {"concept_key": "third-party-bi", "display_value": "Unlimited coverage for third-party bodily injury and death", "price": 0},
                        {"concept_key": "third-party-property", "display_value": "Third-party property damage coverage up to RM3,000,000", "price": 0},
                        {"concept_key": "legal-costs-defense", "display_value": "Court legal defense costs coverage up to RM2,000", "price": 0},
                    ]
                elif cov_key == "third_party":
                    defaults_list = [
                        {"concept_key": "third-party-bi", "display_value": "Unlimited coverage for third-party bodily injury and death", "price": 0},
                        {"concept_key": "third-party-property", "display_value": "Third-party property damage coverage up to RM3,000,000", "price": 0},
                        {"concept_key": "legal-costs-defense", "display_value": "Court legal defense costs coverage up to RM2,000", "price": 0},
                    ]

                for d_item in defaults_list:
                    ck = d_item["concept_key"]
                    if ck not in concepts:
                        continue
                    off_key = f"{catalog.id[:8]}-def-{ck}"
                    off = existing_off_keys.get(off_key)
                    if not off:
                        off = CatalogOffering(
                            id=new_id(),
                            catalog_revision_id=rev.id,
                            offering_key=off_key,
                            concept_id=concepts[ck].id,
                            offering_kind="base",
                            applies_to_type=None,
                            applies_to_id=None,
                            role="included",
                            label_override=d_item.get("label_override"),
                            display_value=d_item.get("display_value"),
                            typed_value={"type": "text", "value": d_item.get("display_value")},
                            optional_price=None,
                            sort_order=order_idx,
                            status="active",
                        )
                        db.add(off)
                    else:
                        off.display_value = d_item.get("display_value")
                        off.role = "included"
                        off.status = "active"
                        off.sort_order = order_idx
                    order_idx += 1

                addons_raw: list[dict[str, Any]] = list(p_info.get("addons") or [])
                addons_list: list[dict[str, Any]] = []
                if cov_key == "comprehensive":
                    addons_list = addons_raw
                elif cov_key == "third_party_fire_theft":
                    addons_list = [a for a in addons_raw if str(a.get("concept_key")) in {"windscreen", "first-loss-flood", "strike-riot-civil-commotion", "legal-liability-to-passengers", "legal-liability-of-passengers", "all-drivers", "driver-passenger-protector"}]
                elif cov_key == "third_party":
                    addons_list = [a for a in addons_raw if str(a.get("concept_key")) in {"legal-liability-to-passengers", "legal-liability-of-passengers", "all-drivers", "driver-passenger-protector"}]

                for a_item in addons_list:
                    ck = a_item["concept_key"]
                    if ck not in concepts:
                        continue
                    off_key = f"{catalog.id[:8]}-add-{ck}"
                    price_val = a_item.get("price")
                    opt_price = {"type": "money", "value": float(price_val), "currency": "MYR"} if price_val is not None else None
                    off = existing_off_keys.get(off_key)
                    if not off:
                        off = CatalogOffering(
                            id=new_id(),
                            catalog_revision_id=rev.id,
                            offering_key=off_key,
                            concept_id=concepts[ck].id,
                            offering_kind="optional",
                            applies_to_type=None,
                            applies_to_id=None,
                            role="addon_option",
                            label_override=a_item.get("label_override"),
                            display_value=a_item.get("display_value"),
                            typed_value={"type": "text", "value": a_item.get("display_value")} if a_item.get("display_value") else None,
                            optional_price=opt_price,
                            sort_order=order_idx,
                            status="active",
                        )
                        db.add(off)
                    else:
                        off.display_value = a_item.get("display_value")
                        if a_item.get("display_value"):
                            off.typed_value = {"type": "text", "value": a_item.get("display_value")}
                        off.optional_price = opt_price
                        off.role = "addon_option"
                        off.status = "active"
                        off.sort_order = order_idx
                    order_idx += 1

                if cov_key == "comprehensive":
                    bundles: list[dict[str, Any]] = list(p_info.get("bundles") or [])
                    for b_data in bundles:
                        pkg_key = str(b_data["package_key"])
                        pkg_name = str(b_data["name"])

                        pkg = db.scalar(select(BenefitPackage).where(
                            BenefitPackage.catalog_revision_id == rev.id,
                            BenefitPackage.package_key == pkg_key
                        ))
                        if not pkg:
                            pkg = BenefitPackage(
                                id=new_id(),
                                catalog_revision_id=rev.id,
                                package_key=pkg_key,
                                name=pkg_name,
                                package_kind="addon_bundle",
                                sort_order=1,
                                status="active",
                                revision=1
                            )
                            db.add(pkg)
                            db.flush()
                        else:
                            pkg.name = pkg_name
                            pkg.status = "active"
                            db.flush()

                        plans: list[dict[str, Any]] = list(b_data.get("plans") or [])
                        for plan_idx, plan_data in enumerate(plans):
                            pl_key = str(plan_data["plan_key"])
                            pl_name = plan_data["name"]
                            pl_price = plan_data.get("price", 0.0)

                            plan = db.scalar(select(BenefitPackagePlan).where(
                                BenefitPackagePlan.package_id == pkg.id,
                                BenefitPackagePlan.plan_key == pl_key
                            ))
                            if not plan:
                                plan = BenefitPackagePlan(
                                    id=new_id(),
                                    package_id=pkg.id,
                                    plan_key=pl_key,
                                    name=pl_name,
                                    sort_order=plan_idx + 1,
                                    status="active"
                                )
                                db.add(plan)
                                db.flush()
                            else:
                                plan.name = pl_name
                                plan.sort_order = plan_idx + 1
                                plan.status = "active"
                                db.flush()

                            old_items = list(db.scalars(select(BenefitPackagePlanItem).where(
                                BenefitPackagePlanItem.plan_id == plan.id
                            )).all())
                            for oi in old_items:
                                db.delete(oi)
                            db.flush()

                            items: list[dict[str, Any]] = list(plan_data.get("items") or [])
                            for item_idx, itm in enumerate(items):
                                ick = str(itm["concept_key"])
                                if ick not in concepts:
                                    continue

                                item_off_key = f"{pkg.id[:8]}-{pl_key}-{ick}-{item_idx}"
                                off_item = db.scalar(select(CatalogOffering).where(
                                    CatalogOffering.catalog_revision_id == rev.id,
                                    CatalogOffering.offering_key == item_off_key
                                ))
                                if not off_item:
                                    off_item = CatalogOffering(
                                        id=new_id(),
                                        catalog_revision_id=rev.id,
                                        offering_key=item_off_key,
                                        concept_id=concepts[ick].id,
                                        offering_kind="upgrade",
                                        applies_to_type="package",
                                        applies_to_id=pkg.id,
                                        role="bundle_component",
                                        label_override=None,
                                        display_value=itm.get("display_value"),
                                        typed_value={"type": "text", "value": itm.get("display_value")},
                                        optional_price={"type": "money", "value": float(pl_price), "currency": "MYR"} if pl_price else None,
                                        sort_order=item_idx + 1,
                                        status="active"
                                    )
                                    db.add(off_item)
                                    db.flush()
                                else:
                                    off_item.display_value = itm.get("display_value")
                                    off_item.status = "active"
                                    db.flush()

                                plan_item = BenefitPackagePlanItem(
                                    id=new_id(),
                                    plan_id=plan.id,
                                    offering_id=off_item.id,
                                    typed_value_override={"type": "text", "value": itm.get("display_value")},
                                    sort_order=item_idx + 1
                                )
                                db.add(plan_item)
                            db.flush()

                rev.state = "published"
                rev.published_at = utcnow()
                db.flush()
        logs.append(f"Processed 6 vehicle lines and 3 coverage types for {c_name}")
    return logs


COMPANY_ALIASES_MAP = {
    "amassurance": [
        "AmAssurance",
        "AmGeneral",
        "AmGen",
        "Liberty General Insurance",
        "Liberty Insurance",
    ],
    "takaful-malaysia": [
        "Takaful Malaysia",
        "Syarikat Takaful Malaysia Am Berhad",
        "STMB",
    ],
    "tune-protect": [
        "Tune Protect",
        "Tune Insurance",
        "Tune Insurance Malaysia Berhad",
    ],
    "lonpac": [
        "Lonpac",
        "Lonpac Insurance",
        "Lonpac Insurance Berhad",
    ],
    "etiqa": [
        "Etiqa",
        "Etiqa General Insurance",
        "Etiqa General Takaful",
        "Etiqa Takaful",
        "Etiqa Insurance",
    ],
    "qbe": [
        "QBE",
        "QBE Insurance",
        "QBE Insurance (Malaysia) Berhad",
    ],
    "berjaya-sompo": [
        "Berjaya Sompo",
        "Berjaya Sompo Insurance",
        "Sompo",
    ],
}


def seed_company_aliases(db, dry_run: bool) -> list[str]:
    logs = []
    for slug, aliases in COMPANY_ALIASES_MAP.items():
        company = db.scalar(select(InsuranceCompany).where(InsuranceCompany.slug == slug))
        if not company:
            continue
        for raw_alias in aliases:
            norm = re.sub(r"[^a-z0-9]+", " ", raw_alias.lower()).strip()
            existing = db.scalar(select(CompanyAlias).where(CompanyAlias.normalized_alias == norm))
            if existing is None:
                alias_obj = CompanyAlias(
                    id=new_id(),
                    company_id=company.id,
                    alias=raw_alias,
                    normalized_alias=norm,
                    alias_kind="detection",
                    status="active",
                )
                if not dry_run:
                    db.add(alias_obj)
                logs.append(f"Added alias '{raw_alias}' -> {company.name}")
    if not dry_run:
        db.flush()
    return logs


def main():
    parser = argparse.ArgumentParser(description="Seed demo benefits and configurations.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Perform a trial run with no changes committed (default)")
    args = parser.parse_args()

    dry_run = not args.apply
    mode_str = "DRY-RUN" if dry_run else "APPLY"
    print(f"=== Starting seed-demo.py [{mode_str}] ===")

    with SessionLocal() as db:
        try:
            cleanup_logs = cleanup_junk(db, dry_run=dry_run)
            for log in cleanup_logs:
                print(f"[CLEANUP] {log}")

            concepts = seed_global_benefits(db, dry_run=dry_run)
            print(f"[BENEFITS] Upserted {len(concepts)} Global Benefits with rich descriptions.")

            alias_logs = seed_company_aliases(db, dry_run=dry_run)
            print(f"[ALIASES] Verified {len(COMPANY_ALIASES_MAP)} company alias mappings.")

            chain_logs = seed_company_package_chains(db, dry_run=dry_run)
            for log in chain_logs:
                print(f"[CONFIG] {log}")

            if dry_run:
                print("\n[DRY-RUN COMPLETE] No database changes committed. Run with --apply to commit.")
            else:
                db.commit()
                print("\n[APPLY COMPLETE] Database changes successfully committed.")
        except Exception as e:
            db.rollback()
            print(f"\n[ERROR in seed-demo]: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
