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
    title: "Unlimited Towing Distance",
    description: "Provides 24-hour free unlimited towing distance anywhere in Malaysia.",
    default_value: "Unlimited",
    icon_hint: "towing",
  },
  {
    id: "llop",
    title: "Legal Liability Of Passengers",
    description: "Protects against third-party claims caused by passenger negligence.",
    default_value: "",
    icon_hint: "llop",
  },
  {
    id: "llp",
    title: "Legal Liability To Passengers",
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
    id: "betterment",
    title: "Waiver Of Betterment",
    description: "Waives betterment deduction on new replacement parts up to 10 years.",
    default_value: "",
    icon_hint: "betterment",
  },
  {
    id: "all_drivers",
    title: "All Drivers",
    description: "Waives RM400 compulsory excess penalty for unnamed authorized drivers.",
    default_value: "",
    icon_hint: "all_driver",
  },
  {
    id: "srcc",
    title: "Strike, Riot & Civil Commotion",
    description: "Covers physical damage caused by strikes, riots or public unrest.",
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
    description: "Covers fitted aftermarket accessories, dashcams, multimedia and rims.",
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
    id: "pa",
    title: "Driver Passenger Personal Accident",
    description: "Accidental Death, Permanent Disablement and Medical Expenses.",
    default_value: "",
    icon_hint: "pa",
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
    description: "Up to 60km from Malaysia border.",
    default_value: "60 km",
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
    title: "Private Hire Car ( E-HAILING )",
    description: "Coverage while providing a legitimate E-Hailing Service.",
    default_value: "",
    icon_hint: "ehailing",
  },
  {
    id: "non_fare_passenger",
    title: "Legal Liability To Non Fare Paying Passenger",
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
    title: "Accidental Damage To Boom",
    description: "Commercial Vehicle - Crane",
    default_value: "",
    icon_hint: "boom_damage",
  },
  {
    id: "overturning",
    title: "Damage By Overturning",
    description: "Commercial Vehicle - Crane",
    default_value: "",
    icon_hint: "overturning",
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

  const rmMatch = s.match(/^rm\s*([0-9][0-9,]*(?:\.[0-9]+)?)$/i);
  if (rmMatch) {
    const num = parseFloat(rmMatch[1].replace(/,/g, ""));
    if (!isNaN(num)) {
      if (num <= 0) return "";
      return `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return s;
  }

  if (/^[0-9][0-9,]*(?:\.[0-9]+)?$/.test(s)) {
    const num = parseFloat(s.replace(/,/g, ""));
    if (!isNaN(num)) {
      if (num <= 0) return "";
      return `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return s;
  }

  if (low.includes("up to 10 years") && low.includes("betterment")) {
    return "Up to 10 Years";
  }
  if (s.length > 28 && low.includes("up to ")) {
    const m = s.match(/(up to [0-9]+\s+\w+)/i);
    if (m) {
      return m[1].replace(/\b\w/g, (ch) => ch.toUpperCase());
    }
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

  if (isBasicEmergencyTowing(targetTitleL, targetDescL, targetValL)) {
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
      if (mappedId === "towing" && isBasicEmergencyTowing(targetTitleL, targetDescL, targetValL)) {
        return null;
      }
      if (CANONICAL_BY_ID[mappedId]) return CANONICAL_BY_ID[mappedId];
    }
    if (CANONICAL_BY_ID[code]) return CANONICAL_BY_ID[code];
  }

  const words = new Set(normalizeCode(targetTitleL).split("_"));

  if (targetTitleL.includes("windscreen")) return CANONICAL_BY_ID.windscreen;
  if (targetTitleL.includes("towing") && (targetTitleL.includes("unlimited") || targetValL.includes("unlimited") || targetDescL.includes("unlimited"))) {
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
  if (item?.icon_hint && item.icon_hint !== "generic") return String(item.icon_hint);
  if (matchedCat?.icon_hint) return String(matchedCat.icon_hint);
  const txt = `${item?.id || ""} ${item?.concept_key || ""} ${item?.title || item?.label || ""}`.toLowerCase();
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

  if (item?.is_extra || item?.cost_status === "paid" || hasPositivePrice(item)) return true;

  if (sourceKind === "active") {
    if (matchedCatId && item?.is_extra !== false) return true;
    if (matchedCatId && item?.selection_id) return true;
  }

  return false;
}

export function extractFreeCoverageItems(
  activeBenefits: any[] = [],
  limit: number = 6
): FreeCoverageItem[] {
  const seen = new Set<string>();
  const items: FreeCoverageItem[] = [];
  for (const raw of activeBenefits || []) {
    if (raw?.is_extra || raw?.cost_status === "paid" || hasPositivePrice(raw)) continue;
    if (matchCatalogItem(raw) !== null) continue;
    const title = String(raw?.title || raw?.label || "").trim();
    if (!title) continue;
    const norm = normalizeCode(title);
    if (seen.has(norm)) continue;
    seen.add(norm);
    let desc = String(raw?.description || raw?.short_description || "").trim();
    const val = formatAddonValue(raw?.value ?? raw?.coverage_limit);
    if (val) {
      const valCompact = val.replace(/\.00\b/, "").toLowerCase();
      const descNorm = desc.toLowerCase();
      if (!descNorm.includes(val.toLowerCase()) && !descNorm.includes(valCompact)) {
        desc = desc ? `${desc} (${val})` : val;
      }
    }
    items.push({ title, description: desc });
    if (items.length >= limit) break;
  }
  return items;
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
  selectedIds?: Set<string>,
  fillToSlots: number = 24
): UnifiedAddonCard[] {
  const canonicalOverrides: Record<string, any> = {};
  const customCards: any[] = [];
  const seenCustomIds = new Set<string>();
  const orderedActiveIds: string[] = [];

  const buildCardObj = (item: any, catId: string, sel: boolean, matched: any) => {
    const rawVal = item.value !== undefined && item.value !== "" ? item.value : item.coverage_limit;
    let formattedVal = formatAddonValue(rawVal);
    if (!formattedVal && matched?.default_value) {
      formattedVal = formatAddonValue(matched.default_value);
    }
    const costStatus = sel
      ? String(item.cost_status || "paid")
      : item.cost_status === "included"
      ? "included"
      : "optional";
    return {
      id: catId,
      code: catId,
      title: String(item.title || item.label || matched?.title || catId),
      description: String(item.description || item.short_description || matched?.description || ""),
      value: formattedVal,
      icon_hint: inferIconHint(item, matched),
      is_selected: sel,
      cost_status: costStatus,
      price: item.price ?? item.optional_price,
      concept_key: item.concept_key || catId,
    };
  };

  const pushItem = (item: any, sourceKind: "active" | "available") => {
    const matched = matchCatalogItem(item);
    const sel = isBenefitSelected(item, selectedIds, sourceKind, matched?.id);

    if (sourceKind === "active" && !matched && !sel) {
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
      } else {
        if (!existing.value && nextCard.value) existing.value = nextCard.value;
        if (!existing.price && nextCard.price) existing.price = nextCard.price;
        if (!existing.description && nextCard.description) existing.description = nextCard.description;
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
  if (fillToSlots > 0) {
    const seenInOutput = new Set<string>();
    for (const cat of CANONICAL_24_CATALOG.slice(0, fillToSlots)) {
      seenInOutput.add(cat.id);
      if (canonicalOverrides[cat.id]) {
        processed.push(canonicalOverrides[cat.id]);
      } else {
        const isCatSel = Boolean(selectedIds && (selectedIds.has(cat.id) || selectedIds.has(cat.title)));
        processed.push({
          id: cat.id,
          code: cat.id,
          title: cat.title,
          description: cat.description,
          value: formatAddonValue(cat.default_value),
          icon_hint: cat.icon_hint,
          is_selected: isCatSel,
          cost_status: isCatSel ? "paid" : "optional",
          concept_key: cat.id,
        });
      }
    }
    for (const cid of orderedActiveIds) {
      if (!seenInOutput.has(cid)) {
        seenInOutput.add(cid);
        processed.push(canonicalOverrides[cid]);
      }
    }
  } else {
    for (const cid of orderedActiveIds) {
      processed.push(canonicalOverrides[cid]);
    }
  }

  processed.push(...customCards);
  return sortUnifiedAddons(processed, selectedIds);
}
