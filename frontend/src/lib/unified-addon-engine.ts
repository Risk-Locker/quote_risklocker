/**
 * Unified Add-On & Benefits Engine (TypeScript Counterpart)
 *
 * Synced 1:1 with `backend/app/rendering/unified_addon_engine.py`.
 * Merges default perks, purchased extras, and optional add-ons into a single unified
 * 4-column card matrix. Selected / ticked benefits float dynamically to the top (slots 01, 02..),
 * followed by unselected catalog benefits in their standard sequence.
 */

export interface UnifiedAddonCard {
  id: string;
  code: string;
  title: string;
  description: string;
  value?: string;
  icon_hint?: string;
  is_selected: boolean;
  serial_number: string;
  cost_status?: string;
  price?: any;
  concept_key?: string;
  asset_id?: string;
}

export interface FreeCoverageItem {
  title: string;
  description: string;
}

export const CANONICAL_24_CATALOG: Array<{
  id: string;
  title: string;
  description: string;
  default_value: string;
  icon_hint: string;
}> = [
    {
      id: "windscreen",
      title: "Windscreen Coverage",
      description: "Covers windscreen, window glass and tint repair without affecting NCD.",
      default_value: "RM 10,000.00",
      icon_hint: "windscreen",
    },
    {
      id: "towing",
      title: "Unlimited Towing",
      description: "24/7 emergency unlimited towing assistance all over Malaysia.",
      default_value: "Unlimited",
      icon_hint: "towing",
    },
    {
      id: "llop",
      title: "Legal Liability of Passengers",
      description: "Protects against third-party claims caused by passenger negligence.",
      default_value: "",
      icon_hint: "llop",
    },
    {
      id: "llp",
      title: "Legal Liability to Passengers",
      description: "Protects driver from lawsuits for injury or death to passengers.",
      default_value: "",
      icon_hint: "llp",
    },
    {
      id: "special_perils",
      title: "Special Perils",
      description: "Full cover for flood, storm, landslide, earthquake and fallen trees.",
      default_value: "Full Coverage",
      icon_hint: "special_perils",
    },
    {
      id: "all_drivers",
      title: "All Drivers Excess Waiver",
      description: "Waives RM400 compulsory excess penalty for all authorized drivers.",
      default_value: "",
      icon_hint: "all_driver",
    },
    {
      id: "pa",
      title: "Motor PA Plus",
      description: "Named personal accident protection for driver and passengers.",
      default_value: "",
      icon_hint: "pa",
    },
    {
      id: "betterment",
      title: "Waiver of Betterment",
      description: "Waives betterment deduction on new parts for vehicles up to 15 years.",
      default_value: "Up to 15 Years",
      icon_hint: "betterment",
    },
    {
      id: "srcc",
      title: "Strike, Riot & Civil Commotion",
      description: "Covers physical loss or damage caused by strikes, riots or public unrest.",
      default_value: "",
      icon_hint: "srcc",
    },
    {
      id: "respray",
      title: "Vehicle Respray Cover",
      description: "Reimburses full exterior vehicle spray painting up to RM1,000 after repairs.",
      default_value: "RM 1,000.00",
      icon_hint: "respray",
    },
    {
      id: "gas_conversion",
      title: "Gas Conversion Kit Cover",
      description: "Dedicated damage cover for installed NGV gas conversion tanks and kits.",
      default_value: "",
      icon_hint: "gas_conversion",
    },
    {
      id: "cart",
      title: "Compensation for Assessed Repair Time",
      description: "Daily cash allowance during workshop repairs assessed by claims adjuster.",
      default_value: "",
      icon_hint: "cart",
    },
    {
      id: "accessories",
      title: "Vehicle Accessories Cover",
      description: "Covers installed aftermarket accessories, dashcams, multimedia and rims.",
      default_value: "",
      icon_hint: "accessories",
    },
    {
      id: "ncd_protector",
      title: "NCD Protector",
      description: "Protects No-Claim Discount entitlement against eligible fault claims.",
      default_value: "",
      icon_hint: "ncd",
    },
    {
      id: "key_care",
      title: "Key Care Replacement",
      description: "Reimburses key and lock replacement up to RM1,000 following theft or loss.",
      default_value: "RM 1,000.00",
      icon_hint: "key_care",
    },
    {
      id: "international_towing",
      title: "International Towing Assistance",
      description: "Up to 50km from Malaysia border.",
      default_value: "50 km",
      icon_hint: "international_towing",
    },
    {
      id: "ev_wall_charger",
      title: "EV Wall Charger Cover",
      description: "Covers accidental damage, fire or theft of home EV wallbox charger.",
      default_value: "",
      icon_hint: "ev_charger",
    },
    {
      id: "ev_out_of_charge",
      title: "EV Battery Out Of Charge Towing",
      description: "Emergency flatbed towing to nearest public EV charging station.",
      default_value: "",
      icon_hint: "ev_towing",
    },
    {
      id: "ev_charger_liability",
      title: "EV Charger Liability",
      description: "Third-party injury and property liability from home EV charger.",
      default_value: "",
      icon_hint: "ev_liability",
    },
    {
      id: "ehailing",
      title: "Private Hire Car (E-Hailing)",
      description: "Coverage while providing a legitimate E-Hailing Service.",
      default_value: "",
      icon_hint: "ehailing",
    },
    {
      id: "non_fare_passenger",
      title: "Legal Liability to Non-Fare Paying Passengers",
      description: "Commercial Vehicle",
      default_value: "",
      icon_hint: "non_fare_passenger",
    },
    {
      id: "third_party_working",
      title: "Third Party Working Risk",
      description: "Commercial Vehicle - Crane",
      default_value: "",
      icon_hint: "third_party_working",
    },
    {
      id: "boom_damage",
      title: "Accidental Damage to Boom",
      description: "Commercial Vehicle - Crane",
      default_value: "",
      icon_hint: "boom_damage",
    },
    {
      id: "overturning",
      title: "Damage by Overturning",
      description: "Commercial Vehicle - Crane",
      default_value: "",
      icon_hint: "overturning",
    },
  ];

export const FALLBACK_ICE_PERKS_CATALOG: Array<{
  id: string;
  title: string;
  description: string;
  default_value: string;
  icon_hint: string;
}> = [
    {
      id: "child_seat",
      title: "Child Car Safety Seat",
      description: "Reimburses replacement of damaged child car safety seat up to RM500.",
      default_value: "RM 500.00",
      icon_hint: "child_seat",
    },
    {
      id: "inconvenience_allowance",
      title: "Inconvenience Allowance",
      description: "Lump sum cash payout for travel inconvenience during vehicle repairs.",
      default_value: "RM 500.00",
      icon_hint: "allowance",
    },
    {
      id: "car_replacement",
      title: "Courtesy Car Replacement",
      description: "Temporary courtesy car replacement while vehicle is under workshop repair.",
      default_value: "Up to 14 Days",
      icon_hint: "car_replacement",
    },
    {
      id: "rim_tyre",
      title: "Rim & Tyre Protection",
      description: "Covers accidental tyre puncture or alloy wheel rim kerb damage.",
      default_value: "RM 1,000.00",
      icon_hint: "rim_tyre",
    },
    {
      id: "flood_allowance",
      title: "Flood Relief Allowance",
      description: "Immediate cash relief payout upon flood damage claims.",
      default_value: "RM 1,000.00",
      icon_hint: "flood",
    },
    {
      id: "airbag_replacement",
      title: "Airbag Replacement Cover",
      description: "Reimburses genuine OEM airbag modules following collision deployment.",
      default_value: "Up to Sum Insured",
      icon_hint: "airbag",
    },
    {
      id: "ambulance_fees",
      title: "Emergency Ambulance Service",
      description: "Reimbursement of emergency ambulance transport charges up to RM500.",
      default_value: "RM 500.00",
      icon_hint: "pa",
    },
    {
      id: "legal_defense",
      title: "Legal Representation & Defense",
      description: "Covers court legal defense counsel costs up to RM2,000.",
      default_value: "RM 2,000.00",
      icon_hint: "legal_defense",
    },
  ];

const CANONICAL_BY_ID: Record<string, (typeof CANONICAL_24_CATALOG)[number]> = Object.fromEntries(
  CANONICAL_24_CATALOG.map((c) => [c.id, c])
);

const SUPPRESSED_VALUES = new Set([
  "",
  "0",
  "0.0",
  "0.00",
  "rm 0",
  "rm 0.0",
  "rm 0.00",
  "rm0",
  "rm0.00",
  "included",
  "included standard cover",
  "foc",
  "as quoted",
  "selected",
  "yes",
  "true",
  "standard",
  "optional",
  "none",
  "null",
  "nil",
  "-",
  "—",
]);

const EXACT_ID_ALIASES: Record<string, string> = {
  windscreen: "windscreen",
  windscreen_coverage: "windscreen",
  windscreen_protection: "windscreen",
  towing: "towing",
  unlimited_towing: "towing",
  unlimited_towing_distance: "towing",
  llop: "llop",
  legal_liability_of_passengers: "llop",
  legal_liability_of_passengers_llop: "llop",
  llp: "llp",
  lltp: "llp",
  legal_liability_to_passengers: "llp",
  legal_liability_to_passengers_lltp: "llp",
  special_perils: "special_perils",
  flood_special_perils: "special_perils",
  flood_and_special_perils: "special_perils",
  betterment: "betterment",
  betterment_protection: "betterment",
  betterment_waiver: "betterment",
  waiver_of_betterment: "betterment",
  all_driver: "all_drivers",
  all_drivers: "all_drivers",
  all_drivers_excess_waiver: "all_drivers",
  srcc: "srcc",
  strike_riot_civil_commotion: "srcc",
  respray: "respray",
  repaint_spray_paint: "respray",
  vehicle_respray_cover: "respray",
  car_spray_repainting: "respray",
  gas_conversion: "gas_conversion",
  gas_conversion_kit: "gas_conversion",
  gas_conversion_kit_cover: "gas_conversion",
  cart: "cart",
  repair_allowance: "cart",
  compensation_for_assessed_repair_time: "cart",
  accessories: "accessories",
  vehicle_accessories: "accessories",
  vehicle_accessories_cover: "accessories",
  vehicle_accessories_protection: "accessories",
  ncd_protector: "ncd_protector",
  ncd_relief: "ncd_protector",
  pa: "pa",
  personal_accident: "pa",
  motor_pa_plus: "pa",
  driver_passenger_pa: "pa",
  driver_and_passenger_pa: "pa",
  driver_passenger_personal_accident: "pa",
  key_care: "key_care",
  key_replacement: "key_care",
  key_care_replacement: "key_care",
  key_care_protection: "key_care",
  international_towing: "international_towing",
  international_towing_assistance: "international_towing",
  ev_wall_charger: "ev_wall_charger",
  ev_wall_charger_cover: "ev_wall_charger",
  ev_out_of_charge: "ev_out_of_charge",
  ev_battery_towing: "ev_out_of_charge",
  ev_battery_depletion_towing: "ev_out_of_charge",
  ev_battery_out_of_charge_towing: "ev_out_of_charge",
  ev_charger_liability: "ev_charger_liability",
  ev_home_charger_liability: "ev_charger_liability",
  ehailing: "ehailing",
  e_hailing: "ehailing",
  e_hailing_cover: "ehailing",
  e_hailing_extension: "ehailing",
  private_hire_car_e_hailing: "ehailing",
  non_fare_passenger: "non_fare_passenger",
  legal_liability_to_non_fare_paying_passenger: "non_fare_passenger",
  third_party_working: "third_party_working",
  third_party_working_risk: "third_party_working",
  boom_damage: "boom_damage",
  accidental_damage_to_boom: "boom_damage",
  overturning: "overturning",
  damage_by_overturning: "overturning",
};

function normalizeCode(s: string): string {
  return (s || "").toLowerCase().replace(/[^a-z0-9]/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
}

export function formatAddonValue(rawVal: unknown): string {
  if (rawVal === undefined || rawVal === null) return "";
  const s = String(rawVal).replace(/\s+/g, " ").trim();
  if (!s) return "";
  const low = s.toLowerCase().replace(/[ .]+$/, "");
  if (SUPPRESSED_VALUES.has(low)) return "";

  // 0. Betterment: Never display an RM monetary amount. Normalize to vehicle age limit or "Betterment Waived".
  if (low.includes("betterment")) {
    const mBet = s.match(/(?:up to\s+)?(\d+\s*(?:years?|yrs?))/i);
    if (mBet) {
      return `Up to ${mBet[1].replace(/\b\w/g, (ch) => ch.toUpperCase())}`;
    }
    return "Betterment Waived";
  }

  // 1. Exact RM amount formatting: "RM 1000", "RM 1,000.00" -> "RM 1,000.00"
  const rmMatch = s.match(/^rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)$/i);
  if (rmMatch) {
    const num = parseFloat(rmMatch[1].replace(/,/g, ""));
    if (!isNaN(num)) {
      if (num <= 0) return "";
      return `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return s;
  }

  // 2. Pure numeric coverage limit (e.g. "1000.0", "350000.0") -> "RM 1,000.00"; preserve single-digit plan numbers ("1"-"9")
  if (/^[0-9][0-9,]*(?:\.[0-9]+)?$/.test(s)) {
    const num = parseFloat(s.replace(/,/g, ""));
    if (!isNaN(num)) {
      if (num <= 0) return "";
      if (num < 10 && !s.includes(".")) return s;
      return `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return s;
  }

  // 3. Betterment: Keep super short (e.g. "Up to 10 Years", "Betterment Waived")
  if (low.includes("betterment") || low.includes("up to ")) {
    const m = s.match(/up to\s+(\d+\s*(?:years?|yrs?))/i);
    if (m) {
      return `Up to ${m[1].replace(/\b\w/g, (ch) => ch.toUpperCase())}`;
    }
    if (low.includes("waiv")) {
      return "Betterment Waived";
    }
  }

  // 4. Excess Waiver: e.g. "Compulsory RM400 excess waived" -> "RM 400.00 Waived"
  if (low.includes("excess")) {
    const m = s.match(/rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)/i);
    if (m) {
      const num = parseFloat(m[1].replace(/,/g, ""));
      if (!isNaN(num)) {
        return `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Waived`;
      }
    }
    if (low.includes("waiv")) {
      return "Excess Waived";
    }
  }

  // 5. Personal Accident (PA): e.g. "RM 10,000 per person" -> "RM 10,000 / pax"
  if (low.includes("per person") || low.includes("pax")) {
    const m = s.match(/rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)/i);
    if (m) {
      const num = parseFloat(m[1].replace(/,/g, ""));
      if (!isNaN(num)) {
        return `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} / pax`;
      }
    }
  }

  // 6. CART / Repair Time: e.g. "14 Days @ RM 100/day" -> "14 Days @ RM100"
  const mCart = s.match(/(\d+\s*days?)\s*@\s*rm\s*(\d+)/i);
  if (mCart) {
    return `${mCart[1].replace(/\b\w/g, (ch) => ch.toUpperCase())} @ RM${mCart[2]}`;
  }

  // 7. Special Perils: e.g. "Full Sum Insured Coverage" -> "Full Sum Insured"
  if (low.includes("peril") || low.includes("flood")) {
    if (low.includes("sum insured") || low.includes("full")) {
      return "Full Sum Insured";
    }
  }

  // 8. Distance / Towing: e.g. "Unlimited Distance" -> "Unlimited", preserve "Unlimited - Plan 1"
  if (low.includes("unlimited")) {
    if ((s.includes("-") || low.includes("plan")) && s.split(/\s+/).length <= 5 && s.length <= 32) {
      return s;
    }
    return "Unlimited";
  }
  const mKm = s.match(/(\d+)\s*km/i);
  if (mKm) {
    return `${mKm[1]} km`;
  }

  // 9. Embedded RM Extraction from verbose sentences:
  // e.g. "Covers wall charger damage up to RM 12,000.00" -> "RM 12,000.00"
  const mRm = s.match(/\brm\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b/i);
  if (mRm) {
    const num = parseFloat(mRm[1].replace(/,/g, ""));
    if (!isNaN(num) && num > 0) {
      return `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
  }

  // 10. General Word Clamping: Never turn prose descriptions (>5 words or >32 chars) into coverage limits
  const words = s.split(/\s+/);
  if (words.length > 5 || s.length > 32) {
    return "";
  }

  return s;
}

function isBasicEmergencyTowing(title: string, desc: string, val: string): boolean {
  const combined = `${title} ${desc} ${val}`.toLowerCase();
  if (combined.includes("unlimited") || combined.includes("international") || combined.includes("ev battery") || combined.includes("out of charge")) {
    return false;
  }
  return title.toLowerCase().includes("emergency towing") || (title.toLowerCase().includes("roadside assistance") && !combined.includes("unlimited"));
}

function matchCatalogItem(item: any) {
  const targetTitle = String(item?.title || item?.label || "").trim();
  const targetTitleL = targetTitle.toLowerCase();
  const targetDescL = String(item?.description || item?.short_description || "").toLowerCase();
  const targetValL = String(item?.value || "").toLowerCase();
  const isPromotedOrExtra = Boolean(item?.promoted_to_addon || item?.is_extra);

  if (!isPromotedOrExtra && isBasicEmergencyTowing(targetTitleL, targetDescL, targetValL)) {
    return null;
  }

  const candidateCodes = [
    normalizeCode(String(item?.id || "")),
    normalizeCode(String(item?.concept_key || "")),
    normalizeCode(String(item?.code || "")),
    normalizeCode(targetTitle),
  ];
  const rawCk = String(item?.card_key || "");
  if (rawCk && !rawCk.includes(":")) {
    candidateCodes.push(normalizeCode(rawCk));
  }

  for (const code of candidateCodes) {
    if (!code) continue;
    const mappedId = EXACT_ID_ALIASES[code];
    if (mappedId) {
      if (mappedId === "towing" && !isPromotedOrExtra && isBasicEmergencyTowing(targetTitleL, targetDescL, targetValL)) {
        return null;
      }
      if (CANONICAL_BY_ID[mappedId]) return CANONICAL_BY_ID[mappedId];
    }
    if (CANONICAL_BY_ID[code]) return CANONICAL_BY_ID[code];
  }

  const words = new Set(normalizeCode(targetTitleL).split("_"));

  if (targetTitleL.includes("windscreen")) return CANONICAL_BY_ID.windscreen;
  if (targetTitleL.includes("towing") && (isPromotedOrExtra || targetTitleL.includes("unlimited") || targetValL.includes("unlimited") || targetDescL.includes("unlimited"))) {
    return CANONICAL_BY_ID.towing;
  }
  if (targetTitleL.includes("towing") && targetTitleL.includes("international")) return CANONICAL_BY_ID.international_towing;
  if (targetTitleL.includes("towing") && (words.has("ev") || targetTitleL.includes("battery") || targetTitleL.includes("out of charge") || targetTitleL.includes("depletion"))) {
    return CANONICAL_BY_ID.ev_out_of_charge;
  }
  if (words.has("non") && words.has("fare")) return CANONICAL_BY_ID.non_fare_passenger;
  if (targetTitleL.includes("passengers") && (words.has("of") || words.has("llop"))) return CANONICAL_BY_ID.llop;
  if (targetTitleL.includes("passengers") && (words.has("to") || words.has("llp") || words.has("lltp"))) return CANONICAL_BY_ID.llp;
  if (targetTitleL.includes("special peril") || targetTitleL.includes("flood & special") || targetTitleL.includes("flood and special")) return CANONICAL_BY_ID.special_perils;
  if (targetTitleL.includes("betterment")) return CANONICAL_BY_ID.betterment;
  if (targetTitleL.includes("all driver")) return CANONICAL_BY_ID.all_drivers;
  if (targetTitleL.includes("strike") || targetTitleL.includes("riot") || words.has("srcc")) return CANONICAL_BY_ID.srcc;
  if (targetTitleL.includes("respray") || targetTitleL.includes("spray paint") || targetTitleL.includes("repaint")) return CANONICAL_BY_ID.respray;
  if (words.has("gas") && targetTitleL.includes("conversion")) return CANONICAL_BY_ID.gas_conversion;
  if (words.has("cart") || targetTitleL.includes("assessed repair") || targetTitleL.includes("repair allowance") || targetTitleL.includes("compensation repair")) return CANONICAL_BY_ID.cart;
  if (targetTitleL.includes("accessories")) return CANONICAL_BY_ID.accessories;
  if (words.has("ncd") && (targetTitleL.includes("protector") || targetTitleL.includes("relief"))) return CANONICAL_BY_ID.ncd_protector;
  if (targetTitleL.includes("personal accident") || targetTitleL.includes("driver passenger") || targetTitleL.includes("driver & passenger pa") || targetTitleL.includes("motor pa")) {
    return CANONICAL_BY_ID.pa;
  }
  if (words.has("key") && (words.has("care") || words.has("replacement"))) return CANONICAL_BY_ID.key_care;
  if (targetTitleL.includes("charger") && targetTitleL.includes("liability")) return CANONICAL_BY_ID.ev_charger_liability;
  if (targetTitleL.includes("wall") && targetTitleL.includes("charger")) return CANONICAL_BY_ID.ev_wall_charger;
  if (targetTitleL.includes("out of charge") || targetTitleL.includes("battery depletion") || targetTitleL.includes("ev battery")) return CANONICAL_BY_ID.ev_out_of_charge;
  if (targetTitleL.includes("e-hailing") || targetTitleL.includes("ehailing") || targetTitleL.includes("e hailing") || targetTitleL.includes("private hire")) return CANONICAL_BY_ID.ehailing;
  if (words.has("boom")) return CANONICAL_BY_ID.boom_damage;
  if (words.has("overturning")) return CANONICAL_BY_ID.overturning;
  if (targetTitleL.includes("working risk")) return CANONICAL_BY_ID.third_party_working;

  return null;
}

function inferIconHint(item: any, matchedCat: any): string {
  const txt = `${item?.id || ""} ${item?.concept_key || ""} ${item?.title || item?.label || ""}`.toLowerCase();
  if (item?.icon_hint && item.icon_hint !== "generic") return String(item.icon_hint);
  if (txt.includes("towing") && txt.includes("unlimited") && !txt.includes("battery") && !txt.includes("international")) {
    return "unlimited_towing";
  }
  if (matchedCat?.icon_hint) return String(matchedCat.icon_hint);
  if (txt.includes("ncd") || txt.includes("cashback")) return "ncd";
  if (txt.includes("detail") || txt.includes("clean") || txt.includes("respray") || txt.includes("paint")) return "respray";
  if (txt.includes("out of pocket") || txt.includes("cart") || txt.includes("allowance") || txt.includes("courtesy")) return "cart";
  if (txt.includes("agreed value") || txt.includes("market value") || txt.includes("settlement")) return "ncd";
  if (txt.includes("child") || txt.includes("seat") || txt.split(/[^a-z0-9]/).includes("pa")) return "pa";
  if (txt.includes("tyre") || txt.includes("tire") || txt.includes("rim") || txt.includes("accessor")) return "accessories";
  return "generic";
}

function hasPositivePrice(item: any): boolean {
  const price = item?.price ?? item?.cost_value;
  if (price === undefined || price === null) return false;
  const val = typeof price === "object" ? (price.amount ?? price.value) : price;
  if (val === undefined || val === null) return false;
  const num = parseFloat(String(val).replace(/[^0-9.]/g, ""));
  return !isNaN(num) && num > 0;
}

export function isBenefitSelected(
  item: any,
  selectedIds?: Set<string>,
  sourceKind: "generic" | "active" | "available" = "generic",
  matchedCatId?: string
): boolean {
  if (selectedIds) {
    const candidates = [
      String(item?.id || ""),
      String(item?.code || ""),
      String(item?.card_key || ""),
      String(item?.selection_id || ""),
      String(item?.concept_key || ""),
      String(item?.title || item?.label || "").trim(),
    ];
    if (matchedCatId) candidates.push(matchedCatId);
    for (const c of candidates) {
      if (!c) continue;
      if (selectedIds.has(c) || selectedIds.has(normalizeCode(c))) return true;
    }
  }

  if (item?.selected === true || item?.is_selected === true) return true;

  if (item?.selected === false || item?.is_selected === false) return false;

  if (sourceKind === "available") {
    return false;
  }

  if (item?.promoted_to_addon || item?.is_bundle_effect || item?.cost_status === "bundle_included") return true;

  if (item?.is_extra || item?.cost_status === "paid" || hasPositivePrice(item)) return true;

  if (sourceKind === "active") {
    // FOC / included perks stay in Free Added Coverage, not marked as purchased add-on riders
    if (item?.cost_status === "included" || item?.cost_status === "foc" || item?.is_extra === false) {
      if (!hasPositivePrice(item) && item?.is_extra !== true) return false;
    }
    if (matchedCatId && item?.is_extra === true) return true;
    if (matchedCatId && item?.selection_id && (item?.is_extra || item?.cost_status === "paid" || hasPositivePrice(item))) return true;
  }

  return false;
}

export const COMMERCIAL_EXCLUDED_MATRIX_IDS = new Set([
  "towing",
  "international_towing",
  "ev_wall_charger",
  "ev_out_of_charge",
  "ev_charger_liability",
  "ehailing",
  "key_care",
  "child_seat",
]);

export const PRIVATE_CAR_EXCLUDED_MATRIX_IDS = new Set([
  "non_fare_passenger",
  "third_party_working",
  "boom_damage",
  "overturning",
]);

export const ICE_EXCLUDED_MATRIX_IDS = new Set([
  "ev_wall_charger",
  "ev_out_of_charge",
  "ev_charger_liability",
]);

export function isEVVehicle(
  vehicleType: string = "",
  carModel: string = "",
  fields?: Record<string, any>
): boolean {
  let raw = `${vehicleType || ""} ${carModel || ""}`.toLowerCase();
  if (fields) {
    raw += ` ${fields.vehicle_type || ""} ${fields.powertrain || ""} ${fields.engine_cc || ""}`.toLowerCase();
  }
  return raw.includes("ev") || raw.includes("electric") || raw.includes("zev") || raw.includes("bev") || raw.includes("kw");
}

export const COMMERCIAL_KEYWORDS = [
  "lorry", "truck", "hino", "fuso", "canter", "rigid", "trailer", "tipper",
  "prime mover", "c permit", "a permit", "haulage", "commercial", "isuzu npr",
  "isuzu nqr", "isuzu elf", "ud trucks", "scania", "sinotruk", "daihatsu delta",
  "toyota dyna", "goods vehicle"
];

export function isCommercialVehicle(
  vehicleType: string = "",
  carModel: string = "",
  fields?: Record<string, any>
): boolean {
  let raw = `${vehicleType || ""} ${carModel || ""}`.toLowerCase();
  if (fields) {
    raw += ` ${fields.vehicle_type || ""} ${fields.car_model || ""} ${fields.capacity || ""}`.toLowerCase();
  }
  return COMMERCIAL_KEYWORDS.some((k) => raw.includes(k)) || raw.includes("kg") || raw.includes("bdm");
}

export function extractFreeCoverageItems(
  activeBenefits: any[] = [],
  insurerName: string | number = "",
  limit: number = 6,
  vehicleType: string = "",
  carModel: string = "",
  fields?: Record<string, any>
): FreeCoverageItem[] {
  const insNameStr = typeof insurerName === "string" ? insurerName : "";
  const finalLimit = typeof insurerName === "number" ? insurerName : limit;

  const insLow = insNameStr.trim().toLowerCase();
  if (insLow.includes("mmip") || insLow.includes("motor insurance pool")) {
    return [
      {
        title: "Third Party Bodily Injury",
        description: "Covers legal liability for death or bodily injury to any third party caused by your vehicle.",
      },
      {
        title: "Third Party Property Damage",
        description: "Covers legal liability for accidental loss or damage to third-party property up to RM 3,000,000.",
      },
    ].slice(0, finalLimit);
  }

  const seen = new Set<string>();
  const items: FreeCoverageItem[] = [];
  const isComm = isCommercialVehicle(vehicleType, carModel, fields);

  const covRaw = fields && typeof fields === "object" ? (fields as any).coverage_type : null;
  const covVal = String(covRaw && typeof covRaw === "object" ? covRaw.value ?? "" : covRaw ?? "").trim().toLowerCase();
  const isNonComp =
    (covVal.includes("third party") || covVal.includes("tpft") || ["tp", "tpo", "act"].includes(covVal)) &&
    !covVal.includes("comprehensive");

  const isBaseTowingCard = (raw: any): boolean => {
    if (raw?.is_extra || raw?.cost_status === "paid" || hasPositivePrice(raw)) return false;
    const ckey = String(raw?.concept_key || "").trim().toLowerCase();
    if (ckey === "towing") return true;
    if (ckey === "ev-battery-depletion-towing") return false;
    const tNorm = normalizeCode(String(raw?.title || raw?.label || ""));
    return tNorm.includes("towing") && !tNorm.includes("battery");
  };

  const isCoverageHiddenOrCleared = (raw: any): boolean => {
    if (raw?.hide_coverage === true || raw?.show_coverage === false) return true;
    for (const k of ["typed_value_override", "typed_value"]) {
      const tv = raw?.[k];
      if (tv && typeof tv === "object") {
        if (tv.hide_limit === true || tv.hideCoverage === true) return true;
        if ("display_text" in tv && String(tv.display_text ?? "").trim() === "" && (tv.value === undefined || tv.value === null || tv.value === "")) {
          return true;
        }
      }
    }
    return false;
  };

  const stripTrailingMetricParens = (titleStr: string): string => {
    return (titleStr || "")
      .trim()
      .replace(/\s*\((?:(?:rm|myr)\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km|unlimited[^)]*)\)\s*$/i, "")
      .trim();
  };

  const formatTowingTitle = (baseLabel: string, limitVal: string, isManualVal: boolean = false): string => {
    let cleanTitle = (baseLabel || "Emergency Towing Assistance").trim();
    const rawVal = (limitVal || "").trim();
    if (!rawVal) return cleanTitle;
    if (isManualVal) {
      cleanTitle = stripTrailingMetricParens(cleanTitle);
    }
    const isConciseLimit =
      (isManualVal && rawVal.length <= 40) ||
      /^(?:unlimited(?:\s*(?:-\s*[a-z0-9 ]+|km|distance|mileage|towing|costs?))?|(?:rm|myr)\s*[\d,]+(?:\.\d{1,2})?|\d+\s*km)$/i.test(rawVal);
    if (!isConciseLimit) return cleanTitle;
    const valCompact = rawVal.replace(/\.00\b/g, "").toLowerCase();
    const titleLow = cleanTitle.toLowerCase();
    if (titleLow.includes(rawVal.toLowerCase()) || (valCompact && titleLow.includes(valCompact))) {
      return cleanTitle;
    }
    if (/\([^)]+\)$/.test(cleanTitle)) return cleanTitle;
    return `${cleanTitle} (${rawVal})`;
  };

  const hasManualValueOverride = (raw: any): boolean => {
    if (raw?.has_manual_value_override) return true;
    for (const k of ["typed_value_override", "typed_value"]) {
      const tv = raw?.[k];
      if (tv && typeof tv === "object" && (tv.type === "custom" || "display_text" in tv)) {
        return true;
      }
    }
    return false;
  };

  for (const raw of activeBenefits || []) {
    if (
      raw?.promoted_to_addon ||
      raw?.is_bundle ||
      raw?.is_bundle_effect ||
      raw?.cost_status === "bundle_included" ||
      raw?.is_extra ||
      raw?.cost_status === "paid" ||
      hasPositivePrice(raw)
    ) continue;

    const isHideCov = isCoverageHiddenOrCleared(raw);
    const hasManualValOvr = hasManualValueOverride(raw);

    if (isBaseTowingCard(raw)) {
      let cTitle = String(raw.label || raw.title || "Emergency Towing Assistance").trim();
      const cVal = isHideCov ? "" : String(raw.value || raw.display_value || raw.coverage_limit || "").trim();
      if (isHideCov || hasManualValOvr) {
        cTitle = stripTrailingMetricParens(cTitle);
      }
      const cDesc = String(raw.description || raw.short_description || "").trim();
      const outTitle = formatTowingTitle(cTitle, cVal, hasManualValOvr);
      const outDesc = cDesc || "24/7 accidental towing service to nearest panel workshop or approved repairer.";
      const normOut = normalizeCode(outTitle);
      if (!seen.has(normOut) && !seen.has("emergency_towing_assistance")) {
        seen.add(normOut);
        seen.add("emergency_towing_assistance");
        seen.add("unlimited_towing_assistance");
        items.push({ title: outTitle, description: outDesc });
      }
      if (items.length >= finalLimit) break;
      continue;
    }

    let title = String(raw?.title || raw?.label || "").trim();
    if (!title) continue;
    if (isHideCov) {
      title = stripTrailingMetricParens(title);
    } else if (hasManualValOvr) {
      const cVal = String(raw?.value || "").trim();
      const cleanBase = stripTrailingMetricParens(title);
      if (cVal && cVal.length <= 40 && !cleanBase.toLowerCase().includes(cVal.toLowerCase())) {
        title = `${cleanBase} (${cVal})`;
      } else {
        title = cleanBase;
      }
    }
    const norm = normalizeCode(title);
    if (seen.has(norm)) continue;
    seen.add(norm);
    // Box 1 standard cards render Title + Description only unless manually overridden
    const desc = String(raw?.description || raw?.short_description || "").trim();
    items.push({ title, description: desc });
    if (items.length >= finalLimit) break;
  }

  return items.slice(0, finalLimit);
}

export function sortUnifiedAddons(
  items: any[],
  selectedIds?: Set<string>
): UnifiedAddonCard[] {
  const selected: UnifiedAddonCard[] = [];
  const unselected: UnifiedAddonCard[] = [];

  for (const item of items) {
    const sel = isBenefitSelected(item, selectedIds, "generic");
    const title = item.title || item.label || "Benefit";
    const formattedVal = formatAddonValue(item.value);
    const card: UnifiedAddonCard = {
      id: item.id || normalizeCode(title),
      code: item.code || normalizeCode(title),
      title,
      description: item.description || "",
      value: formattedVal || undefined,
      icon_hint: item.icon_hint || "generic",
      is_selected: sel,
      serial_number: "01",
      cost_status: item.cost_status,
      price: item.price,
      concept_key: item.concept_key,
      asset_id: item.asset_id,
    };
    if (sel) {
      selected.push(card);
    } else {
      unselected.push(card);
    }
  }

  const combined = [...selected, ...unselected];
  return combined.map((card, idx) => ({
    ...card,
    serial_number: String(idx + 1).padStart(2, "0"),
  }));
}

export function buildUnifiedMatrixCards(
  activeBenefits: any[] = [],
  availableAddons: any[] = [],
  selectedIds?: Set<string> | string[] | null,
  fillToSlots: number = 0,
  maxSlots: number = 24,
  insurerName: string = "",
  vehicleType: string = "",
  carModel: string = "",
  fields?: Record<string, any>
): UnifiedAddonCard[] {
  const insLow = (insurerName || "").trim().toLowerCase();
  if (insLow.includes("mmip") || insLow.includes("motor insurance pool")) {
    return [];
  }
  const isComm = isCommercialVehicle(vehicleType, carModel, fields);
  const isEv = isEVVehicle(vehicleType, carModel, fields);
  const excludedIds = new Set(
    isComm
      ? [...COMMERCIAL_EXCLUDED_MATRIX_IDS]
      : !isEv
        ? [...PRIVATE_CAR_EXCLUDED_MATRIX_IDS, ...ICE_EXCLUDED_MATRIX_IDS]
        : [...PRIVATE_CAR_EXCLUDED_MATRIX_IDS]
  );

  const selSet =
    selectedIds instanceof Set
      ? selectedIds
      : Array.isArray(selectedIds)
        ? new Set(selectedIds)
        : undefined;
  const canonicalOverrides: Record<string, any> = {};
  const customCards: any[] = [];
  const seenCustomIds = new Set<string>();
  const orderedActiveIds: string[] = [];

  const buildCardObj = (item: any, catId: string, sel: boolean, matched: any) => {
    let rawVal = item.value;
    if (!(item.promoted_to_addon && "value" in item)) {
      if (rawVal === undefined || rawVal === "") {
        rawVal = item.coverage_limit;
      }
      if ((rawVal === undefined || rawVal === "") && typeof item.typed_value === "object" && item.typed_value?.display_text) {
        rawVal = item.typed_value.display_text;
      }
      if ((rawVal === undefined || rawVal === "") && typeof item.typed_value_override === "object" && item.typed_value_override?.display_text) {
        rawVal = item.typed_value_override.display_text;
      }
    }

    // Betterment protection: Never display an RM monetary amount for Waiver of Betterment
    const isBetterment = catId === "betterment" || (matched && matched.id === "betterment");
    let formattedVal = "";
    if (isBetterment) {
      if (typeof rawVal === "string" && /^\s*rm\b/i.test(rawVal.trim())) {
        rawVal = "";
      }
      const compL = (insurerName || "").toLowerCase();
      const defaultYears = (compL.includes("qbe") || compL.includes("lonpac") || compL.includes("stmb") || compL.includes("takaful"))
        ? "Up to 10 Years"
        : "Up to 15 Years";
      if (!rawVal || rawVal === "Up to 10 Years" || rawVal === "Up to 15 Years" || rawVal === "Standard") {
        formattedVal = defaultYears;
      } else {
        formattedVal = formatAddonValue(rawVal) || defaultYears;
      }
    } else {
      formattedVal = formatAddonValue(rawVal);
      if (!formattedVal && matched?.default_value && !item.promoted_to_addon && !item.is_bundle) {
        formattedVal = formatAddonValue(matched.default_value);
      }
    }

    const titleStr = String(item.title || item.label || matched?.title || catId);

    if (Boolean(item?.is_bundle) && !Boolean(item?.is_bundle_effect) && formattedVal) {
      const fvL = formattedVal.trim().toLowerCase();
      const tierL = String(item?.selected_bundle_tier_label || "").trim().toLowerCase();
      const isTierToken =
        (Boolean(tierL) && fvL === tierL) ||
        /^(?:(?:plans?|pelan|tier|pakej)\s*(?:no\.?\s*)?(?:\d+|[a-d])(?:\s*[-–/,&to]+\s*(?:\d+|[a-d]))*|(?:\d+|[a-d])(?:\s*[-–/,&to]+\s*(?:\d+|[a-d]))+|ev\s*plan|driver\s*plan\s*\d+|included)$/i.test(fvL) ||
        (titleStr.toLowerCase().includes(fvL) && !/(?:rm|myr|km|%)/i.test(fvL));
      if (isTierToken) {
        formattedVal = "";
      }
    }

    // Check if coverage limit is explicitly hidden (Windscreen is strictly mandatory on Malaysian motor quotes)
    const isHideCov = Boolean(
      item.hide_coverage ||
      item.show_coverage === false ||
      (typeof item.typed_value === "object" && item.typed_value?.hide_limit === true) ||
      (typeof item.typed_value_override === "object" && item.typed_value_override?.hide_limit === true)
    );
    const isMandatoryCov = catId.toLowerCase().includes("windscreen") || titleStr.toLowerCase().includes("windscreen");
    if (isHideCov && !isMandatoryCov) {
      formattedVal = "";
    }

    const isBundleEff = Boolean(item?.is_bundle_effect || item?.cost_status === "bundle_included");
    const costStatus = isBundleEff
      ? "bundle_included"
      : sel
        ? String(item.cost_status || "paid")
        : item.cost_status === "included"
          ? "included"
          : "optional";
    const assetId = item.asset_id || item.default_asset_id || matched?.default_asset_id;
    return {
      id: catId,
      code: catId,
      title: titleStr,
      description: String(item.description || item.short_description || matched?.description || ""),
      value: formattedVal,
      icon_hint: inferIconHint(item, matched),
      is_selected: sel,
      cost_status: costStatus,
      is_bundle_effect: isBundleEff,
      price: isBundleEff ? undefined : (item.price ?? item.optional_price),
      concept_key: item.concept_key || catId,
      asset_id: assetId || undefined,
    };
  };

  const pushItem = (item: any, sourceKind: "active" | "available") => {
    let matched = matchCatalogItem(item);
    if (matched && Boolean(item?.is_bundle) && !Boolean(item?.is_bundle_effect)) {
      matched = null;
    }
    const sel = isBenefitSelected(item, selSet, sourceKind, matched?.id);

    // Keep non-matrix unselected basic perks strictly inside "Free Added Coverage"
    if (sourceKind === "active" && !sel) {
      return;
    }

    const catId = matched?.id || normalizeCode(String(item.concept_key || item.id || item.title || item.label || ""));
    if (!catId) return;

    if (matched) {
      const existing = canonicalOverrides[catId];
      const nextCard = buildCardObj(item, catId, sel, matched);
      if (!existing) {
        canonicalOverrides[catId] = nextCard;
        orderedActiveIds.push(catId);
      } else if (
        Boolean(item?.is_bundle_effect || item?.cost_status === "bundle_included") &&
        !Boolean(existing.is_bundle_effect)
      ) {
        canonicalOverrides[catId] = { ...nextCard, is_selected: true };
      } else {
        if (!existing.value && nextCard.value) existing.value = nextCard.value;
        if (!existing.price && nextCard.price) existing.price = nextCard.price;
        if (!existing.description && nextCard.description) existing.description = nextCard.description;
        if (!existing.asset_id && nextCard.asset_id) existing.asset_id = nextCard.asset_id;
        if (sel && !existing.is_selected) {
          existing.is_selected = true;
          existing.cost_status = nextCard.cost_status;
        }
      }
    } else {
      if (seenCustomIds.has(catId)) return;
      seenCustomIds.add(catId);
      customCards.push(buildCardObj(item, catId, sel, null));
    }
  };

  for (const item of activeBenefits || []) {
    pushItem(item, "active");
  }
  for (const item of availableAddons || []) {
    pushItem(item, "available");
  }

  const processed: any[] = [];
  const seenInOutput = new Set<string>();

  // 1. Add provided canonical overrides (in canonical catalog sequence)
  for (const cat of CANONICAL_24_CATALOG) {
    if (isComm && excludedIds.has(cat.id) && !canonicalOverrides[cat.id]?.is_selected) {
      continue;
    }
    if (
      cat.id === "towing" &&
      isComm &&
      !canonicalOverrides[cat.id]?.is_selected
    ) {
      continue;
    }
    if (canonicalOverrides[cat.id]) {
      seenInOutput.add(cat.id);
      processed.push(canonicalOverrides[cat.id]);
    }
  }

  // 2. Add active draft benefits matching other canonical slots
  for (const cid of orderedActiveIds) {
    if (!seenInOutput.has(cid) && canonicalOverrides[cid]) {
      if (isComm && excludedIds.has(cid) && !canonicalOverrides[cid]?.is_selected) {
        continue;
      }
      seenInOutput.add(cid);
      processed.push(canonicalOverrides[cid]);
    }
  }

  // 3. Add custom active benefits and available addons provided for this quote
  for (const custom of customCards) {
    const cId = custom.id || custom.concept_key;
    if (cId && !seenInOutput.has(cId)) {
      if (isComm && (String(cId).toLowerCase().includes("towing") || String(cId).toLowerCase().includes("roadside"))) {
        continue;
      }
      seenInOutput.add(cId);
      processed.push(custom);
    }
  }

  // 4. Fill remaining slots up to fillToSlots from CANONICAL_24_CATALOG and FALLBACK_ICE_PERKS_CATALOG
  if (fillToSlots > 0) {
    for (const cat of [...CANONICAL_24_CATALOG, ...FALLBACK_ICE_PERKS_CATALOG]) {
      if (processed.length >= fillToSlots) {
        break;
      }
      if (excludedIds.has(cat.id)) {
        continue;
      }
      if (cat.id === "towing" && !canonicalOverrides[cat.id]) {
        continue;
      }
      if (!seenInOutput.has(cat.id)) {
        seenInOutput.add(cat.id);
        let fillVal = formatAddonValue(cat.default_value);
        if (cat.id === "betterment") {
          const compL = (insurerName || "").toLowerCase();
          fillVal = (compL.includes("qbe") || compL.includes("lonpac") || compL.includes("stmb") || compL.includes("takaful"))
            ? "Up to 10 Years"
            : "Up to 15 Years";
        }
        processed.push({
          id: cat.id,
          code: cat.id,
          title: cat.title,
          description: cat.description,
          value: fillVal,
          icon_hint: cat.icon_hint,
          is_selected: false,
          cost_status: "paid",
          concept_key: cat.id,
        });
      }
    }
  }

  const sortedCards = sortUnifiedAddons(processed, selSet);
  if (fillToSlots > 0) {
    return sortedCards.slice(0, fillToSlots);
  }
  return sortedCards;
}
