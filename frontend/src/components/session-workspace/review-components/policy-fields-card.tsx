"use client";

import React from "react";
import {
  ArrowCounterClockwise,
  CaretDown,
  CaretUp,
  Check,
  Copy,
  Sparkle,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { GeminiQuotaInfoButton, type GeminiQuota } from "@/components/gemini-quota-meter";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { WorkspaceField, WorkspaceSnapshot } from "../types";

export type FieldKind = "text" | "date" | "percent" | "money" | "total" | "vehicle_type" | "valuation_type";

export type FormField = { name: string; label: string; kind: FieldKind };

export const FORM_FIELDS: FormField[] = [
  { name: "customer_name", label: "Insured name", kind: "text" },
  { name: "ic_or_brn", label: "NRIC / Business Reg. No.", kind: "text" },
  { name: "quotation_reference", label: "Quotation ref", kind: "text" },
  { name: "vehicle_no", label: "Vehicle no. / Car plate", kind: "text" },
  { name: "vehicle_year", label: "Year of make", kind: "text" },
  { name: "vehicle_type", label: "Vehicle type", kind: "vehicle_type" },
  { name: "car_model", label: "Car model", kind: "text" },
  { name: "engine_cc", label: "Engine CC / Capacity", kind: "text" },
  { name: "chassis_no", label: "Chassis / VIN No.", kind: "text" },
  { name: "engine_no", label: "Engine No.", kind: "text" },
  { name: "sum_insured", label: "Sum insured / Market value", kind: "money" },
  { name: "insurance_company", label: "Insurance name", kind: "text" },
  { name: "coverage_type", label: "Coverage type", kind: "text" },
  { name: "cover_period", label: "Cover period", kind: "text" },
  { name: "valuation_type", label: "Valuation Type", kind: "valuation_type" },
  { name: "valid_until", label: "Quotation validity", kind: "text" },
  { name: "excess_amount", label: "Excess amount", kind: "money" },
  { name: "compulsory_excess", label: "Compulsory excess", kind: "money" },
  { name: "ncd_percent", label: "NCD", kind: "percent" },
  { name: "loading_amount", label: "Loading amount", kind: "money" },
  { name: "gross_premium", label: "Gross premium", kind: "money" },
  { name: "service_tax", label: "Service tax (SST)", kind: "money" },
  { name: "stamp_duty", label: "Stamp duty", kind: "money" },
  { name: "premium", label: "Insurance Premium After NCD, Excluding Add-Ons", kind: "money" },
  { name: "insurance_premium_total", label: "Insurance premium", kind: "total" },
  { name: "roadtax", label: "Road tax", kind: "money" },
  { name: "service_fee", label: "Runner fee", kind: "money" },
  { name: "total_amount", label: "Total Payable", kind: "total" },
];

export function detectEVCategory(
  carBrand?: string | null,
  carModel?: string | null,
  capacityStr?: string | null
): "EVSaloonCar" | "EVNonSaloonCar" | "EVMotorcycle" | null {
  const brand = (carBrand || "").trim().toUpperCase();
  const model = (carModel || "").trim().toUpperCase();
  const text = `${brand} ${model}`.trim();

  // Electric Motorcycles
  if (/\b(BLUESHARK|LUMEN|E-MAX|SUPER SOCO|HORWIN|CAKE|ENERGICA|ZERO|STARK VARG|NINEBOT|YADEA|GOGORO|NIU)\b/i.test(text)) {
    return "EVMotorcycle";
  }

  // Electric Non-Saloon (SUV / MPV / Pickup / Crossover)
  if (
    /\b(MODEL Y|MODEL X|ATTO 3|ATTO|SEALION|TANG|SONG|E6|DENZA D9|DENZA|MIFA 9|MIFA 7|MIFA|IONIQ 5|IONIQ 7|EV6|EV9|NEXO|KONA ELECTRIC|KONA EV|EQA|EQB|EQC|EQE SUV|EQS SUV|IX1|IX2|IX3|IX|E-TRON|Q4 E-TRON|Q8 E-TRON|MACAN EV|TIGUAN EV|ID\.4|ID\.5|ID\.BUZZ|EX30|EX90|XC40 RECHARGE|C40 RECHARGE|C40|SMART #1|SMART #3|NETA V|NETA U|NETA X|GWM TANK|TANK 500|ZEEKR X|ZEEKR 009|XPENG G6|XPENG G9|AVATR 11|CHERY OMODA E5|OMODA E5|JAECOO J6|DEEPAL S07|LOTUS ELETRE|POLESTAR 3|POLESTAR 4)\b/i.test(
      text
    )
  ) {
    return "EVNonSaloonCar";
  }

  // Electric Saloon (Sedan / Coupe / Hatchback)
  if (
    /\b(MODEL 3|MODEL S|SEAL|HAN|QIN|DOLPHIN|SEAGULL|IONIQ 6|TAYCAN|EQE|EQS|I4|I5|I7|E-TRON GT|ID\.3|ID\.7|POLESTAR 2|ORA GOOD CAT|GOOD CAT|ORA 07|ZEEKR 001|ZEEKR 007|XPENG P7|XPENG P5|DEEPAL L07|LOTUS EMEYA)\b/i.test(
      text
    )
  ) {
    return "EVSaloonCar";
  }

  // Generic EV brands/markers
  if (
    /\b(TESLA|BYD|ZEEKR|XPENG|NIO|POLESTAR|RIVIAN|LUCID|VINFAST|SMART #)\b/i.test(text) ||
    /\b(BEV|ZEV|ELECTRIC VEHICLE|EV)\b/i.test(text)
  ) {
    if (/\b(SUV|MPV|CROSSOVER|4X4|PICKUP)\b/i.test(text)) return "EVNonSaloonCar";
    return "EVSaloonCar";
  }

  return null;
}

export function computeMalaysianRoadTax(
  cc: number,
  vehicleType: string = "Car",
  ownerType: string = "Individual"
): number {
  if (!cc || cc <= 0) return 0;
  const normType = (vehicleType || "Car").toLowerCase();
  const normOwner = (ownerType || "Individual").toLowerCase();
  const isCompany = normOwner.includes("company") || normOwner.includes("corp") || normType.includes("company");

  // 1. Electric Vehicle (ZEV 2026 Guidelines - Identical for Private & Company)
  const isEVMotorcycle =
    normType.includes("evmotor") || (normType.includes("ev") && (normType.includes("bike") || normType.includes("motor")));
  const isEVNonSaloon =
    normType.includes("evnonsaloon") ||
    normType.includes("evcommercial") ||
    (normType.includes("ev") &&
      (normType.includes("suv") ||
        normType.includes("mpv") ||
        normType.includes("non") ||
        normType.includes("commercial") ||
        normType.includes("lorry")));
  const isEVSaloon = normType.includes("evsaloon") || (normType.includes("ev") && !isEVMotorcycle && !isEVNonSaloon);

  if (isEVMotorcycle || isEVNonSaloon || isEVSaloon) {
    const kw = cc >= 1000 ? cc / 1000 : cc;
    if (isEVMotorcycle) {
      if (kw <= 7.5) return 2.0;
      if (kw <= 10.0) return 9.0;
      if (kw <= 12.5) return 12.0;
      if (kw <= 25.0) return 30.0;
      if (kw <= 40.0) return 40.0;
      return 42.0;
    }
    // Electric Passenger Cars (Saloon & Non-Saloon share official 2026 JPJ power bands)
    if (kw <= 50.0) return 20.0;
    if (kw <= 100.0) {
      const blocks = Math.ceil((kw - 50.0) / 10.0);
      return 20.0 + blocks * 10.0;
    }
    if (kw <= 210.0) {
      const blocks = Math.ceil((kw - 100.0) / 10.0);
      return 80.0 + (blocks - 1) * 20.0;
    }
    if (kw <= 310.0) {
      const blocks = Math.ceil((kw - 210.0) / 10.0);
      return 305.0 + (blocks - 1) * 30.0;
    }
    if (kw <= 410.0) {
      const blocks = Math.ceil((kw - 310.0) / 10.0);
      return 615.0 + (blocks - 1) * 50.0;
    }
    if (kw <= 510.0) {
      const blocks = Math.ceil((kw - 410.0) / 10.0);
      return 1140.0 + (blocks - 1) * 100.0;
    }
    if (kw <= 610.0) {
      const blocks = Math.ceil((kw - 510.0) / 10.0);
      return 2165.0 + (blocks - 1) * 150.0;
    }
    if (kw <= 710.0) {
      const blocks = Math.ceil((kw - 610.0) / 10.0);
      return 3695.0 + (blocks - 1) * 200.0;
    }
    if (kw <= 810.0) {
      const blocks = Math.ceil((kw - 710.0) / 10.0);
      return 5745.0 + (blocks - 1) * 250.0;
    }
    if (kw <= 910.0) {
      const blocks = Math.ceil((kw - 810.0) / 10.0);
      return 8295.0 + (blocks - 1) * 300.0;
    }
    if (kw <= 1010.0) {
      const blocks = Math.ceil((kw - 910.0) / 10.0);
      return 11345.0 + (blocks - 1) * 350.0;
    }
    const blocks = Math.ceil((kw - 1010.0) / 10.0);
    return 14895.0 + (blocks - 1) * 400.0;
  }

  if (cc > 7000) return 0;

  // Non-Saloon Car (SUV / MPV / 4x4 / Pickup) - Identical for Private & Company
  if (
    normType.includes("nonsaloon") ||
    normType.includes("non-saloon") ||
    normType.includes("suv") ||
    normType.includes("mpv")
  ) {
    if (cc <= 1000) return 20;
    if (cc <= 1200) return 85;
    if (cc <= 1400) return 100;
    if (cc <= 1600) return 120;
    if (cc <= 1800) return 300 + (cc - 1600) * 0.3;
    if (cc <= 2000) return 360 + (cc - 1800) * 0.4;
    if (cc <= 2500) return 440 + (cc - 2000) * 0.8;
    if (cc <= 3000) return 840 + (cc - 2500) * 1.6;
    return 1640 + (cc - 3000) * 1.6;
  }

  if (normType.includes("motor") || normType.includes("bike")) {
    if (cc <= 150) return 2;
    if (cc <= 200) return 30;
    if (cc <= 250) return 50;
    if (cc <= 500) return isCompany ? 180 : 100;
    if (cc <= 800) return 250;
    return 350;
  }

  if (
    normType.includes("lorry") ||
    normType.includes("other") ||
    normType.includes("truck") ||
    normType.includes("commercial")
  ) {
    if (cc <= 1600) return 120;
    if (cc <= 2500) return 240;
    return 480;
  }

  if (isCompany) {
    if (cc <= 1000) return 20;
    if (cc <= 1200) return 110;
    if (cc <= 1400) return 140;
    if (cc <= 1600) return 180;
    if (cc <= 1800) return 400 + (cc - 1600) * 0.8;
    if (cc <= 2000) return 560 + (cc - 1800) * 1.0;
    if (cc <= 2500) return 760 + (cc - 2000) * 3.0;
    if (cc <= 3000) return 2260 + (cc - 2500) * 7.5;
    return 6010 + (cc - 3000) * 13.5;
  }

  // Private Saloon Car
  if (cc <= 1000) return 20;
  if (cc <= 1200) return 55;
  if (cc <= 1400) return 70;
  if (cc <= 1600) return 90;
  if (cc <= 1800) return 200 + (cc - 1600) * 0.4;
  if (cc <= 2000) return 280 + (cc - 1800) * 0.5;
  if (cc <= 2500) return 380 + (cc - 2000) * 1.0;
  if (cc <= 3000) return 840 + (cc - 2500) * 2.5;
  return 2130 + (cc - 3000) * 4.5;
}

export function isNonSaloonCarModel(modelStr: string | null | undefined): boolean {
  if (!modelStr) return false;
  const s = modelStr.toUpperCase();
  if (
    /\b(ALZA|EXORA|INNOVA|VELLFIRE|ALPHARD|SERENA|AVANZA|VELOZ|SIENTA|CARNIVAL|STARIA|VOXY|NOAH|ESQUIRE|ESTIMA|WISH|STREAM|FREED|BIANTE|ERTIGA|LIVINA|GRAND LIVINA|LODGY|SPACIO|TOURAN|SHARAN|ODYSSEY|CITAN|TRAVET|HIACE|URVAN|VAN|MPV)\b/i.test(
      s
    )
  )
    return true;
  if (
    /\b(ATIVA|ARUZ|X50|X70|X90|CR-V|CRV|HR-V|HRV|BR-V|BRV|WR-V|WRV|ZR-V|ZRV|FORTUNER|HARRIER|COROLLA CROSS|CROSS|CX-3|CX-5|CX-8|CX-30|CX-60|CX-90|TUCSON|SANTA FE|CRETA|KONA|SPORTAGE|SORENTO|SELTOS|FORESTER|XV|OUTBACK|CROSSTREK|RAV4|KICKS|X-TRAIL|XTRAIL|TIGUAN|TOUAREG|Q3|Q5|Q7|GLA|GLB|GLC|GLE|GLS|X1|X3|X4|X5|X6|X7|MACAN|CAYENNE|URUS|DEFENDER|DISCOVERY|RANGE ROVER|EVOQUE|VELAR|CHEROKEE|WRANGLER|COMPASS|RENEGADE|DMAX|D-MAX|HILUX|RANGER|TRITON|NAVARA|BT-50|BT50|GLADIATOR|AMAROK|COLORADO|4X4|4WD|PICKUP|SUV)\b/i.test(
      s
    )
  )
    return true;
  return false;
}

export function inferCCFromCarModel(modelStr: string | null | undefined): number | null {
  if (!modelStr) return null;
  const matchDirect = modelStr.match(/\b([0-9]{3,4})\s*(?:cc|c\.c\.)\b/i);
  if (matchDirect) return parseInt(matchDirect[1], 10);

  const matchLitre = modelStr.match(/\b([1-9]\.[0-9])\b/i);
  if (matchLitre) {
    const litres = parseFloat(matchLitre[1]);
    const mapping: Record<number, number> = {
      1.0: 998,
      1.2: 1197,
      1.3: 1329,
      1.4: 1395,
      1.5: 1496,
      1.6: 1598,
      1.8: 1798,
      2.0: 1998,
      2.2: 2198,
      2.4: 2362,
      2.5: 2494,
      2.8: 2755,
      3.0: 2997,
      3.5: 3456,
    };
    return mapping[litres] || Math.round(litres * 1000);
  }
  return null;
}

export function getProductVehicleCategory(productName: string): "Car" | "Motorcycle" | "Lorry" {
  const lower = (productName || "").toLowerCase();
  if (/motorcycle|motor\s*cycle|motosikal|bike/i.test(lower)) {
    return "Motorcycle";
  }
  if (/lorry|truck|rigid|trailer|tipper|prime mover|haulage|commercial\s*vehicle|c\s*permit|a\s*permit/i.test(lower)) {
    return "Lorry";
  }
  return "Car";
}

export function formatProductLabel(rawName: string): string {
  let label = rawName;
  if (!/\b(Comprehensive|TPFT|TPO|Third Party)\b/i.test(rawName)) {
    const lowerName = rawName.toLowerCase();
    let covLabel = "Comprehensive";
    if (lowerName.includes("tpft") || (lowerName.includes("third party") && lowerName.includes("fire"))) {
      covLabel = "TPFT";
    } else if (lowerName.includes("third") || lowerName.includes("tpo") || lowerName.includes("party")) {
      covLabel = "TPO";
    }
    label = `${rawName} (${covLabel})`;
  }
  return label;
}

export interface PolicyFieldsCardProps {
  workspace: WorkspaceSnapshot;
  formValues: Record<string, string>;
  setFormValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  previousValuesRef: React.MutableRefObject<Record<string, string>>;
  extractedValuesCollapsed: boolean;
  setExtractedValuesCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  copiedInfo: boolean;
  handleCopyExtractedInfo: () => void;
  geminiExtracting: boolean;
  triggerGeminiExtraction: () => void;
  geminiQuotaInfo: GeminiQuota | null;
  previewFields: Record<string, string>;
  companies: Array<{ id: string; name: string }>;
  roundTotal: boolean;
  toggleRoundTotal: () => void;
  isFieldModified: (fieldName: string) => boolean;
  getDetectedValue: (fieldName: string) => string | null;
  handleResetField: (field: FormField) => void;
  commitField: (field: FormField) => void;
  commitFieldDirectly: (name: string, value: string) => void;
  syncHighlight: { field: "vehicle_type" | "product_package"; prev: string; next: string; timestamp: number } | null;
  setSyncHighlight: React.Dispatch<React.SetStateAction<{ field: "vehicle_type" | "product_package"; prev: string; next: string; timestamp: number } | null>>;
  companyWorkspace: any | null;
  categorizedProducts: { cars: any[]; motorcycles: any[]; lorries: any[] };
  pinCatalog: (companyId: string, productId: string) => void;
}

export function PolicyFieldsCard({
  workspace,
  formValues,
  setFormValues,
  previousValuesRef,
  extractedValuesCollapsed,
  setExtractedValuesCollapsed,
  copiedInfo,
  handleCopyExtractedInfo,
  geminiExtracting,
  triggerGeminiExtraction,
  geminiQuotaInfo,
  previewFields,
  companies,
  roundTotal,
  toggleRoundTotal,
  isFieldModified,
  getDetectedValue,
  handleResetField,
  commitField,
  commitFieldDirectly,
  syncHighlight,
  setSyncHighlight,
  companyWorkspace,
  categorizedProducts,
  pinCatalog,
}: PolicyFieldsCardProps) {
  return (
    <Card className="rl-tour-fields grid gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between border-b border-[var(--rl-border)] pb-2 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Extracted values</h2>
            <Badge variant="success">Gemini AI Active</Badge>
          </div>
          <p className="text-xs text-[var(--rl-text-muted)]">Verified quotation details formatted for the master template.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={handleCopyExtractedInfo}
            className="h-7 text-xs font-semibold gap-1.5"
            title="Copy all extracted policy, vehicle, and extra benefit information to clipboard"
          >
            {copiedInfo ? <Check size={13} weight="bold" className="text-emerald-600" /> : <Copy size={13} weight="bold" />}
            <span>{copiedInfo ? "Copied Info!" : "Copy Info"}</span>
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={geminiExtracting}
            onClick={triggerGeminiExtraction}
            className="h-7 text-xs font-semibold gap-1.5"
            title="Run Gemini Multimodal AI extraction to auto-detect customer name, coverage, car model, and benefits"
          >
            <Sparkle
              size={13}
              weight="fill"
              className={geminiExtracting ? "animate-spin text-[var(--rl-black)]" : "text-[var(--rl-text-strong)]"}
            />
            <span>{geminiExtracting ? "Extracting with AI..." : "Re-Extract with AI"}</span>
          </Button>
          <GeminiQuotaInfoButton quota={geminiQuotaInfo} />
          <Badge variant="default">{FORM_FIELDS.length} fields</Badge>
          <button
            type="button"
            onClick={() => setExtractedValuesCollapsed((v) => !v)}
            className="flex items-center gap-1 rounded-[var(--rl-radius-sm)] px-2 py-0.5 text-xs font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
            title={extractedValuesCollapsed ? "Expand Extracted Values" : "Collapse Extracted Values"}
          >
            {extractedValuesCollapsed ? <CaretDown size={14} weight="bold" /> : <CaretUp size={14} weight="bold" />}
            <span>{extractedValuesCollapsed ? "Expand" : "Collapse"}</span>
          </button>
        </div>
      </div>

      {extractedValuesCollapsed ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded bg-gray-50 p-2.5 text-xs">
          <div>
            <span className="text-[var(--rl-text-muted)]">Plate:</span>{" "}
            <strong className="text-[var(--rl-text-strong)] font-mono">{formValues.vehicle_no || "—"}</strong>
          </div>
          <div>
            <span className="text-[var(--rl-text-muted)]">Insured:</span>{" "}
            <strong className="text-[var(--rl-text-strong)] truncate max-w-[140px] inline-block align-bottom">
              {formValues.customer_name || "—"}
            </strong>
          </div>
          <div>
            <span className="text-[var(--rl-text-muted)]">TOTAL PAYABLE:</span>{" "}
            <strong className="text-[var(--rl-red)] font-mono font-bold">
              RM {previewFields["total_amount"] || formValues.total_amount || "0.00"}
            </strong>
          </div>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {FORM_FIELDS.map((field) => {
              let stored = workspace.fields[field.name] as WorkspaceField | undefined;
              if (field.name === "sum_insured") {
                const numStored = parseFloat(String(stored?.value || "").replace(/[^0-9.]/g, ""));
                const altCov = (workspace.fields["coverage_amount"] as WorkspaceField | undefined)?.value;
                const numAlt = parseFloat(String(altCov || "").replace(/[^0-9.]/g, ""));
                if ((!stored?.value || numStored < 1000) && numAlt >= 1000) {
                  stored = workspace.fields["coverage_amount"] as WorkspaceField | undefined;
                } else if (!stored?.value) {
                  stored =
                    (workspace.fields["market_value"] as WorkspaceField | undefined) ||
                    (workspace.fields["agreed_value"] as WorkspaceField | undefined);
                }
              }
              const empty = !stored?.value;
              const needsCheck = !empty && stored?.status === "check_needed";
              const isCurrentEV = (
                formValues["vehicle_type"] ||
                (workspace.fields?.vehicle_type as WorkspaceField | undefined)?.value ||
                ""
              )
                .toLowerCase()
                .includes("ev");
              const fieldLabel =
                field.name === "engine_cc"
                  ? isCurrentEV
                    ? "Motor Output (kW)"
                    : "Engine Capacity (CC)"
                  : field.label;
              const fieldModified = isFieldModified(field.name);
              return (
                <label key={field.name} className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                  <span className="flex items-center justify-between gap-1">
                    <span className="truncate">{fieldLabel}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {needsCheck ? <span className="text-[10px] text-amber-700 font-bold">Check value</span> : null}
                      {field.name === "total_amount" ? (
                        <button
                          type="button"
                          onClick={toggleRoundTotal}
                          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold transition-all shadow-2xs ${
                            roundTotal
                              ? "bg-emerald-600 text-white border border-emerald-700"
                              : "bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200"
                          }`}
                          title={
                            roundTotal
                              ? "Round figure active (0 cents). Click to toggle."
                              : "Click to round figure total to whole RM (0 cents)."
                          }
                        >
                          <Check size={11} weight="bold" className={roundTotal ? "opacity-100" : "opacity-0"} />
                          <span>Round Figure</span>
                        </button>
                      ) : null}
                      {field.kind !== "total" && fieldModified ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            handleResetField(field);
                          }}
                          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold text-amber-800 bg-amber-50 border border-amber-300 hover:bg-amber-100 hover:text-amber-950 transition-colors shadow-2xs"
                          title={`Reset to detected: "${getDetectedValue(field.name)}"`}
                        >
                          <ArrowCounterClockwise size={11} weight="bold" />
                          <span>Reset</span>
                        </button>
                      ) : null}
                    </div>
                    {field.kind === "vehicle_type" &&
                    syncHighlight &&
                    syncHighlight.field === "vehicle_type" &&
                    Date.now() - syncHighlight.timestamp < 6000 ? (
                      <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 border border-emerald-300 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 shadow-xs animate-pulse">
                        <span className="text-[10px] text-emerald-600 font-bold uppercase tracking-wider">Auto-synced</span>
                        <span className="line-through text-slate-400 font-normal">{syncHighlight.prev}</span>
                        <span className="text-emerald-500 font-bold">→</span>
                        <span className="bg-emerald-100 text-emerald-900 px-1 rounded font-bold">{syncHighlight.next}</span>
                      </span>
                    ) : null}
                  </span>
                  {field.kind === "vehicle_type" ? (
                    <div className="grid gap-1.5">
                      {/* Engine Type Segmented Toggle */}
                      <div className="flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-0.5 text-xs">
                        {(["ICE", "EV"] as const).map((eng) => {
                          const currentVal = String(formValues[field.name] || "");
                          const isCurrentEVVal = currentVal.startsWith("EV");
                          const active = eng === "EV" ? isCurrentEVVal : !isCurrentEVVal;
                          return (
                            <button
                              key={eng}
                              type="button"
                              onClick={() => {
                                if (eng === "EV" && !isCurrentEVVal) {
                                  const newVtype =
                                    currentVal === "NonSaloonCar"
                                      ? "EVNonSaloonCar"
                                      : currentVal.toLowerCase().includes("motor")
                                      ? "EVMotorcycle"
                                      : currentVal.toLowerCase().includes("lorry") || currentVal.toLowerCase().includes("other")
                                      ? "EVCommercial"
                                      : "EVSaloonCar";
                                  setFormValues((v) => ({ ...v, [field.name]: newVtype }));
                                  commitFieldDirectly(field.name, newVtype);

                                  const currentProd = (companyWorkspace?.products || []).find(
                                    (p: any) => p.id === workspace?.pinned?.product_id
                                  );
                                  const companyProds = companyWorkspace?.products || [];
                                  const matchingEv = companyProds.find((p: any) => {
                                    const nm = (p.name || "").toLowerCase();
                                    if (!/\(ev\)|(\bev\b)|electric/i.test(nm)) return false;
                                    if (newVtype.includes("Motor")) return /motor/i.test(nm);
                                    if (newVtype.includes("Commercial") || newVtype.toLowerCase().includes("lorry"))
                                      return /lorry|commercial/i.test(nm);
                                    return !/motor|lorry|commercial/i.test(nm);
                                  });
                                  if (matchingEv && workspace?.pinned.company_id) {
                                    pinCatalog(workspace.pinned.company_id as string, matchingEv.id);
                                    setSyncHighlight({
                                      field: "product_package",
                                      prev: currentProd ? formatProductLabel(currentProd.name) : "ICE Package",
                                      next: formatProductLabel(matchingEv.name),
                                      timestamp: Date.now(),
                                    });
                                  }
                                } else if (eng === "ICE" && isCurrentEVVal) {
                                  const newVtype =
                                    currentVal === "EVNonSaloonCar"
                                      ? "NonSaloonCar"
                                      : currentVal === "EVMotorcycle"
                                      ? "Motorcycle"
                                      : currentVal === "EVCommercial"
                                      ? "Lorry"
                                      : "Car";
                                  setFormValues((v) => ({ ...v, [field.name]: newVtype }));
                                  commitFieldDirectly(field.name, newVtype);

                                  const currentProd = (companyWorkspace?.products || []).find(
                                    (p: any) => p.id === workspace?.pinned?.product_id
                                  );
                                  const companyProds = companyWorkspace?.products || [];
                                  const matchingIce = companyProds.find((p: any) => {
                                    const nm = (p.name || "").toLowerCase();
                                    if (/\(ev\)|(\bev\b)|electric/i.test(nm)) return false;
                                    if (newVtype.includes("Motor")) return /motor/i.test(nm);
                                    if (newVtype.includes("Commercial") || newVtype.toLowerCase().includes("lorry"))
                                      return /lorry|commercial/i.test(nm);
                                    return !/motor|lorry|commercial/i.test(nm);
                                  });
                                  if (matchingIce && workspace?.pinned.company_id) {
                                    pinCatalog(workspace.pinned.company_id as string, matchingIce.id);
                                    setSyncHighlight({
                                      field: "product_package",
                                      prev: currentProd ? formatProductLabel(currentProd.name) : "EV Package",
                                      next: formatProductLabel(matchingIce.name),
                                      timestamp: Date.now(),
                                    });
                                  }
                                }
                              }}
                              className={`flex-1 py-1 text-center font-bold text-[11px] rounded-[3px] transition-all ${
                                active
                                  ? "bg-[var(--rl-black)] text-white shadow-xs"
                                  : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                              }`}
                            >
                              {eng === "ICE" ? "ICE (Petrol / Diesel)" : "EV (Electric)"}
                            </button>
                          );
                        })}
                      </div>

                      {/* Filtered Vehicle Type Dropdown */}
                      <Select
                        value={
                          formValues[field.name] ||
                          (String(formValues[field.name] || "").startsWith("EV") ? "EVSaloonCar" : "Car")
                        }
                        onChange={(event) => {
                          const newVtype = event.target.value;
                          const isCompany =
                            newVtype.toLowerCase().includes("company") || newVtype.toLowerCase().includes("corp");
                          setFormValues((values) => ({
                            ...values,
                            [field.name]: newVtype,
                            ...(isCompany ? { client_type: "Company" } : {}),
                          }));
                          commitFieldDirectly(field.name, newVtype);
                          if (isCompany) {
                            commitFieldDirectly("client_type", "Company");
                          }

                          // Two-way synchronization: Auto-sync matching package if vehicle category changed
                          const currentProd = (companyWorkspace?.products || []).find(
                            (p: any) => p.id === workspace?.pinned?.product_id
                          );
                          const currentProdCat = currentProd ? getProductVehicleCategory(currentProd.name || "") : null;
                          const targetCat: "Car" | "Motorcycle" | "Lorry" = newVtype.toLowerCase().includes("motor")
                            ? "Motorcycle"
                            : newVtype.toLowerCase().includes("lorry") ||
                              newVtype.toLowerCase().includes("other") ||
                              newVtype.toLowerCase().includes("commercial")
                            ? "Lorry"
                            : "Car";

                          if ((!currentProd || currentProdCat !== targetCat) && workspace?.pinned.company_id) {
                            const targetPool =
                              targetCat === "Motorcycle"
                                ? categorizedProducts.motorcycles
                                : targetCat === "Lorry"
                                ? categorizedProducts.lorries
                                : categorizedProducts.cars;

                            // Prefer Comprehensive coverage or canonical package if available
                            const bestMatching =
                              targetPool.find((p) =>
                                /private car protector|auto365.*lite|sompo motor|private car secure|comprehensive private car|takaful mymotor|tune protect motor easy|commercial lorry.*own goods.*c permit|c permit|own goods|motorcycle policy \(private\)/i.test(
                                  p.name
                                )
                              ) ||
                              targetPool.find((p) => /comprehensive/i.test(p.name || "")) ||
                              targetPool[0];

                            if (bestMatching) {
                              pinCatalog(workspace.pinned.company_id as string, bestMatching.id);
                              setSyncHighlight({
                                field: "product_package",
                                prev: currentProd ? formatProductLabel(currentProd.name || "") : "Previous Package",
                                next: formatProductLabel(bestMatching.name || ""),
                                timestamp: Date.now(),
                              });
                            }
                          }

                          const currentCCStr =
                            formValues["engine_cc"] ||
                            (workspace.fields["engine_cc"] as WorkspaceField | undefined)?.value;
                          const isEVType = newVtype.startsWith("EV");
                          const rawParsed = currentCCStr
                            ? parseFloat(String(currentCCStr).replace(/[^0-9.]/g, ""))
                            : isEVType
                            ? null
                            : inferCCFromCarModel(
                                formValues["car_model"] ||
                                  (workspace.fields["car_model"] as WorkspaceField | undefined)?.value
                              );
                          if (rawParsed && rawParsed > 0) {
                            if (isEVType) {
                              const computedRT = computeMalaysianRoadTax(rawParsed, newVtype, "Individual");
                              if (computedRT > 0) {
                                const rtFormatted = computedRT.toFixed(2);
                                setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
                                commitFieldDirectly("roadtax", rtFormatted);
                              }
                            } else if (rawParsed <= 7000) {
                              const parsedCC = Math.round(rawParsed);
                              const baseType =
                                newVtype === "NonSaloonCar"
                                  ? "NonSaloonCar"
                                  : newVtype.toLowerCase().includes("motor")
                                  ? "Motorcycle"
                                  : newVtype.toLowerCase().includes("lorry") || newVtype.toLowerCase().includes("other")
                                  ? "Lorry"
                                  : "Car";
                              const computedRT = computeMalaysianRoadTax(
                                parsedCC,
                                baseType,
                                isCompany ? "Company" : "Individual"
                              );
                              if (computedRT > 0) {
                                const rtFormatted = computedRT.toFixed(2);
                                setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
                                commitFieldDirectly("roadtax", rtFormatted);
                              }
                            }
                          }
                        }}
                        className={`text-xs font-medium transition-all duration-300 ${
                          syncHighlight &&
                          syncHighlight.field === "vehicle_type" &&
                          Date.now() - syncHighlight.timestamp < 6000
                            ? "border-emerald-500 ring-2 ring-emerald-300 bg-emerald-50/20"
                            : ""
                        }`}
                      >
                        {String(formValues[field.name] || "").startsWith("EV") ? (
                          <>
                            <option value="EVSaloonCar">EV Saloon (Sedan / Coupe - Private & Company)</option>
                            <option value="EVNonSaloonCar">EV Non-Saloon (SUV / MPV / Crossover / Pickup)</option>
                            <option value="EVMotorcycle">Electric Motorcycle (Private & Company)</option>
                            <option value="EVCommercial">EV Commercial (Van / Lorry / Fleet)</option>
                          </>
                        ) : (
                          <>
                            <option value="Car">Car (Private Saloon)</option>
                            <option value="CompanyCar">Car (Company / Corporate Saloon)</option>
                            <option value="NonSaloonCar">Non-Saloon (SUV / MPV / 4x4 / Pickup)</option>
                            <option value="Motorcycle">Motorcycle (Private)</option>
                            <option value="CompanyMotorcycle">Motorcycle (Corporate)</option>
                            <option value="Lorry">Lorry / Commercial</option>
                            <option value="Others">Others</option>
                          </>
                        )}
                      </Select>
                    </div>
                  ) : field.kind === "valuation_type" ? (
                    <Select
                      value={formValues[field.name] || "Market Value"}
                      onChange={(event) => {
                        const val = event.target.value;
                        setFormValues((values) => ({ ...values, [field.name]: val }));
                        commitFieldDirectly(field.name, val);
                      }}
                      className="text-xs font-medium"
                    >
                      <option value="Agreed Value">Agreed Value (Nilai Dipersetujui)</option>
                      <option value="Market Value">Market Value (Nilai Pasaran)</option>
                    </Select>
                  ) : (
                    <span className="relative">
                      {field.kind === "money" || field.kind === "total" ? (
                        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-xs font-bold text-[var(--rl-text-muted)]">
                          RM
                        </span>
                      ) : null}
                      <Input
                        value={
                          field.kind === "total"
                            ? previewFields[field.name] || formValues[field.name] || ""
                            : formValues[field.name] ?? ""
                        }
                        disabled={field.kind === "total"}
                        placeholder={
                          empty ? "Missing" : field.name === "engine_cc" ? (isCurrentEV ? "150 kW" : "1498 CC") : ""
                        }
                        list={field.name === "insurance_company" ? "company-suggestions" : undefined}
                        className={`${
                          field.kind === "money" || field.kind === "total"
                            ? "pl-8 text-xs font-mono font-medium"
                            : "text-xs font-medium"
                        } ${needsCheck ? "border-amber-400 bg-amber-50/50 ring-1 ring-amber-300" : ""}`}
                        onChange={(event) => {
                          const newVal = event.target.value;
                          if (previousValuesRef.current[field.name] === undefined) {
                            previousValuesRef.current[field.name] = formValues[field.name] || "";
                          }
                          setFormValues((values) => ({ ...values, [field.name]: newVal }));
                        }}
                        onBlur={() => {
                          commitField(field);
                          if (
                            field.name === "engine_cc" ||
                            field.name === "car_model" ||
                            field.name === "insured_name" ||
                            field.name === "customer_name" ||
                            field.name === "client_type"
                          ) {
                            const custName = formValues["insured_name"] || formValues["customer_name"] || "";
                            const isCorp =
                              /(SDN\s*BHD|BHD|ENTERPRISE|TRADING|LTD|LLC|PLT|COMPANY|ENT\.|CORP|HOLDINGS|CO\.)/i.test(
                                String(custName)
                              ) || String(formValues["client_type"] || "").toLowerCase().includes("company");
                            const carModel = formValues["car_model"] || "";
                            const carBrand =
                              formValues["car_brand"] ||
                              (workspace.fields?.car_brand as WorkspaceField | undefined)?.value ||
                              "";
                            let vtype = formValues["vehicle_type"] || "Car";
                            const evCat = detectEVCategory(carBrand, carModel, formValues["engine_cc"]);

                            if (vtype.startsWith("EV") || evCat) {
                              vtype = vtype.startsWith("EV") ? vtype : evCat || "EVSaloonCar";
                              setFormValues((v) => ({ ...v, vehicle_type: vtype }));
                              commitFieldDirectly("vehicle_type", vtype);
                            } else if (isNonSaloonCarModel(carModel) || vtype === "NonSaloonCar") {
                              vtype = "NonSaloonCar";
                              setFormValues((v) => ({ ...v, vehicle_type: "NonSaloonCar" }));
                              commitFieldDirectly("vehicle_type", "NonSaloonCar");
                            } else if (isCorp && (vtype === "Car" || vtype.toLowerCase().includes("saloon"))) {
                              vtype = "CompanyCar";
                              setFormValues((v) => ({ ...v, vehicle_type: "CompanyCar", client_type: "Company" }));
                              commitFieldDirectly("vehicle_type", "CompanyCar");
                              commitFieldDirectly("client_type", "Company");
                            } else if (isCorp && !formValues["client_type"]) {
                              setFormValues((v) => ({ ...v, client_type: "Company" }));
                              commitFieldDirectly("client_type", "Company");
                            }

                            const isEV = vtype.startsWith("EV");
                            const currentCCStr =
                              formValues["engine_cc"] ||
                              (field.name === "car_model"
                                ? inferCCFromCarModel(formValues["car_model"])?.toString()
                                : null);
                            const rawParsed = currentCCStr
                              ? parseFloat(String(currentCCStr).replace(/[^0-9.]/g, ""))
                              : null;
                            if (rawParsed && rawParsed > 0) {
                              if (isEV) {
                                const kw = rawParsed >= 1000 ? rawParsed / 1000 : rawParsed;
                                const formattedPower = `${Number.isInteger(kw) ? kw : kw.toFixed(1)} kW`;
                                setFormValues((values) => ({ ...values, engine_cc: formattedPower }));
                                commitFieldDirectly("engine_cc", formattedPower);
                                const computedRT = computeMalaysianRoadTax(rawParsed, vtype, "Individual");
                                if (computedRT > 0) {
                                  const rtFormatted = computedRT.toFixed(2);
                                  setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
                                  commitFieldDirectly("roadtax", rtFormatted);
                                }
                              } else if (rawParsed <= 7000) {
                                const parsedCC = Math.round(rawParsed);
                                if (!formValues["engine_cc"] || !formValues["engine_cc"].includes("CC")) {
                                  setFormValues((values) => ({ ...values, engine_cc: `${parsedCC} CC` }));
                                  commitFieldDirectly("engine_cc", `${parsedCC} CC`);
                                }
                                const isCompany =
                                  isCorp ||
                                  vtype.toLowerCase().includes("company") ||
                                  vtype.toLowerCase().includes("corp");
                                const baseType =
                                  vtype === "NonSaloonCar"
                                    ? "NonSaloonCar"
                                    : vtype.toLowerCase().includes("motor")
                                    ? "Motorcycle"
                                    : vtype.toLowerCase().includes("lorry") || vtype.toLowerCase().includes("other")
                                    ? "Lorry"
                                    : "Car";
                                const computedRT = computeMalaysianRoadTax(
                                  parsedCC,
                                  baseType,
                                  isCompany ? "Company" : "Individual"
                                );
                                if (computedRT > 0) {
                                  const rtFormatted = computedRT.toFixed(2);
                                  setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
                                  commitFieldDirectly("roadtax", rtFormatted);
                                }
                              }
                            }
                          }
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") (event.target as HTMLInputElement).blur();
                        }}
                      />
                    </span>
                  )}
                </label>
              );
            })}
            {/* Dynamic Additional Extracted Fields */}
            {Object.entries(workspace.fields || {})
              .filter(
                ([k, v]) =>
                  !FORM_FIELDS.some((f) => f.name === k) &&
                  !k.startsWith("_") &&
                  v &&
                  typeof v === "object" &&
                  "value" in v &&
                  (v as WorkspaceField).value
              )
              .map(([extraKey, extraField]) => {
                const wf = extraField as WorkspaceField;
                const label = extraKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
                const fieldModified = isFieldModified(extraKey);
                return (
                  <label key={extraKey} className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                    <span className="flex items-center justify-between gap-1">
                      <span className="truncate">{label}</span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {wf.status === "check_needed" ? (
                          <span className="text-[10px] text-amber-700 font-bold">Check value</span>
                        ) : null}
                        {fieldModified ? (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              handleResetField({ name: extraKey, label, kind: "text" });
                            }}
                            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold text-amber-800 bg-amber-50 border border-amber-300 hover:bg-amber-100 hover:text-amber-950 transition-colors shadow-2xs"
                            title={`Reset to detected: "${getDetectedValue(extraKey)}"`}
                          >
                            <ArrowCounterClockwise size={11} weight="bold" />
                            <span>Reset</span>
                          </button>
                        ) : null}
                      </div>
                    </span>
                    <span className="relative">
                      <Input
                        value={formValues[extraKey] ?? (wf.value || "")}
                        placeholder="Missing"
                        className={`text-xs font-medium ${
                          wf.status === "check_needed" ? "border-amber-400 bg-amber-50/50 ring-1 ring-amber-300" : ""
                        }`}
                        onChange={(event) => {
                          const newVal = event.target.value;
                          if (previousValuesRef.current[extraKey] === undefined) {
                            previousValuesRef.current[extraKey] = formValues[extraKey] || wf.value || "";
                          }
                          setFormValues((values) => ({ ...values, [extraKey]: newVal }));
                        }}
                        onBlur={() => {
                          commitFieldDirectly(extraKey, formValues[extraKey] ?? (wf.value || ""));
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") (event.target as HTMLInputElement).blur();
                        }}
                      />
                    </span>
                  </label>
                );
              })}
          </div>
          <datalist id="company-suggestions">
            {companies.map((c) => (
              <option key={c.id} value={c.name} />
            ))}
          </datalist>
          <p className="text-[11px] text-[var(--rl-text-muted)]">
            Amounts are formatted in RM. Totals compute automatically from premium, road tax, and runner fee.
          </p>
        </>
      )}
    </Card>
  );
}
