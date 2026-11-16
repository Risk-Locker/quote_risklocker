"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useWorkspaceActions,
  useWorkspaceData,
  useWorkspaceMutation,
} from "@/components/session-workspace/provider";
import type { WorkspaceField } from "@/components/session-workspace/types";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import {
  FORM_FIELDS,
  type FieldKind,
  type FormField,
  detectEVCategory,
  isNonSaloonCarModel,
  inferCCFromCarModel,
} from "./policy-fields-card";

export const LEARNABLE = new Map<string, string>([
  ["car_brand", "car_brands"],
  ["car_model", "car_models"],
  ["client_type", "client_types"],
  ["vehicle_type", "vehicle_types"],
  ["region", "regions"],
  ["coverage_type", "coverage_types"],
]);

export function formatMoney(raw: string | null | undefined): string {
  const number = Number(String(raw ?? "").replace(/[^0-9.-]/g, ""));
  return Number.isFinite(number)
    ? number.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "";
}

export function formatDate(raw: string | null | undefined): string {
  const value = String(raw ?? "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
  }
  return value;
}

export function formatCoverPeriod(raw: string | null | undefined): string {
  const value = String(raw ?? "").trim();
  if (value.includes(" to ")) {
    const [start, end] = value.split(" to ");
    return `${formatDate(start)} to ${formatDate(end)}`;
  }
  return value;
}

export function displayValue(kind: FieldKind, value: string | null | undefined): string {
  if (value === null || value === undefined || String(value).trim() === "") return "";
  if (kind === "money" || kind === "total") return formatMoney(value);
  if (kind === "date") return formatDate(value);
  return String(value);
}

export interface UseReviewWorkspaceStateProps {
  id?: string;
  companies?: Array<{ id: string; name: string }>;
  pinCatalog?: (companyId: string, productId?: string | null, tierId?: string | null) => Promise<void>;
}

export function useReviewWorkspaceState(props: UseReviewWorkspaceStateProps = {}) {
  const { companies = [], pinCatalog } = props;
  const { workspace } = useWorkspaceData();
  const { decideField, save, queueOperation } = useWorkspaceActions();
  const mutation = useWorkspaceMutation();

  const [formValues, setFormValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(FORM_FIELDS.map((field) => [field.name, ""]))
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Sync highlight tracking
  const [syncHighlight, setSyncHighlight] = useState<{
    field: "vehicle_type" | "product_package";
    prev: string;
    next: string;
    timestamp: number;
  } | null>(null);

  // Rounding and Schedule Toggles
  const [roundTotal, setRoundTotal] = useState<boolean>(() =>
    (workspace?.display_options as Record<string, unknown> | undefined)?.round_total !== false
  );
  const [showDesign2Schedule, setShowDesign2Schedule] = useState<boolean>(() =>
    Boolean((workspace?.display_options as Record<string, unknown> | undefined)?.include_benefit_schedule)
  );
  const [extrasDisplayMode, setExtrasDisplayMode] = useState<"itemized" | "lump_sum" | "none">(() => {
    const mode = (workspace?.display_options as Record<string, unknown> | undefined)?.extras_mode;
    if (mode === "none" || mode === "lump_sum" || mode === "itemized") return mode;
    return "itemized";
  });

  const previousValuesRef = useRef<Record<string, string>>({});
  const debouncedSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSyncedRevisionRef = useRef<number | null>(null);
  const promptedRef = useRef<Set<string>>(new Set());
  const [learnPrompt, setLearnPrompt] = useState<{ field: string; value: string } | null>(null);

  /** Coalesce rapid mutations into a single save after 800ms idle. */
  const scheduleSave = useCallback(() => {
    if (debouncedSaveRef.current !== null) clearTimeout(debouncedSaveRef.current);
    debouncedSaveRef.current = setTimeout(() => {
      debouncedSaveRef.current = null;
      save().catch(() => undefined);
    }, 800);
  }, [save]);

  useEffect(() => {
    if (workspace?.display_options) {
      if (lastSyncedRevisionRef.current === null || workspace.revision !== lastSyncedRevisionRef.current) {
        lastSyncedRevisionRef.current = workspace.revision;
        if ("round_total" in workspace.display_options) {
          setRoundTotal((workspace.display_options as Record<string, unknown>).round_total !== false);
        }
        if ("include_benefit_schedule" in workspace.display_options) {
          setShowDesign2Schedule(Boolean((workspace.display_options as Record<string, unknown>).include_benefit_schedule));
        }
        if ("extras_mode" in workspace.display_options) {
          const mode = (workspace.display_options as Record<string, unknown>).extras_mode;
          if (mode === "none" || mode === "lump_sum" || mode === "itemized") {
            setExtrasDisplayMode(mode);
          }
        }
      }
    }
  }, [workspace?.display_options, workspace?.revision]);

  const handleExtrasDisplayModeChange = useCallback(
    (mode: "itemized" | "lump_sum" | "none") => {
      setExtrasDisplayMode(mode);
      queueOperation(
        { op: "update_display_options", options: { extras_mode: mode } },
        "display_options"
      );
      scheduleSave();
    },
    [queueOperation, scheduleSave]
  );

  const toggleDesign2Schedule = useCallback(() => {
    const nextVal = !showDesign2Schedule;
    setShowDesign2Schedule(nextVal);
    queueOperation(
      { op: "update_display_options", options: { include_benefit_schedule: nextVal } },
      "display_options"
    );
    scheduleSave();
  }, [showDesign2Schedule, queueOperation, scheduleSave]);

  const toggleRoundTotal = useCallback(() => {
    const nextVal = !roundTotal;
    setRoundTotal(nextVal);
    decideField("total_amount", "clear", "");

    setFormValues((prev) => {
      const rawStoredPrem = (workspace?.fields?.premium as any)?.detected_value ?? (workspace?.fields?.premium as any)?.value;
      const baseRaw = nextVal ? (prev["premium"] || rawStoredPrem || "") : (rawStoredPrem || prev["premium"] || "");
      const pNum = parseFloat(String(baseRaw).replace(/[^0-9.]/g, "")) || 0;
      const effPremiumNum = nextVal && pNum > 0 ? Math.round(pNum) : pNum;
      const formattedPremium = pNum > 0 ? effPremiumNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : prev["premium"];

      const rtNum = parseFloat(String(prev["roadtax"] || (workspace?.fields?.roadtax as any)?.value || "").replace(/[^0-9.]/g, "")) || 0;
      const sfNum = parseFloat(String(prev["service_fee"] || (workspace?.fields?.service_fee as any)?.value || "").replace(/[^0-9.]/g, "")) || 0;
      const extrasTotal = (workspace?.extras || []).reduce((acc, ex) => {
        const amt = (ex as Record<string, unknown>)?.price;
        const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
        const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
        return acc + (Number.isFinite(num) ? num : 0);
      }, 0);

      const calcTotal = effPremiumNum + extrasTotal + rtNum + sfNum;
      if (calcTotal > 0) {
        const finalTot = nextVal ? Math.round(calcTotal) : calcTotal;
        const formattedTotal = finalTot.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return { ...prev, premium: formattedPremium, total_amount: formattedTotal };
      }
      const curTot = parseFloat(String(prev["total_amount"] || (workspace?.fields?.total_amount as any)?.value || "").replace(/[^0-9.]/g, "")) || 0;
      if (curTot > 0) {
        const finalTot = nextVal ? Math.round(curTot) : curTot;
        const formattedTotal = finalTot.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return { ...prev, premium: formattedPremium, total_amount: formattedTotal };
      }
      return { ...prev, premium: formattedPremium };
    });

    queueOperation(
      { op: "update_display_options", options: { round_total: nextVal } },
      "display_options"
    );
    scheduleSave();
  }, [roundTotal, workspace, decideField, queueOperation, scheduleSave]);

  const getDetectedValue = useCallback((fieldName: string): string => {
    if (!workspace?.fields) return "";
    const f = workspace.fields[fieldName] as (WorkspaceField & { detected_value?: string }) | undefined;
    let det = f?.detected_value ?? f?.value ?? "";
    if (fieldName === "sum_insured") {
      const numDet = parseFloat(String(det || "").replace(/[^0-9.]/g, ""));
      const covF = workspace.fields["coverage_amount"] as (WorkspaceField & { detected_value?: string }) | undefined;
      const covDet = covF?.detected_value ?? covF?.value ?? "";
      const numCov = parseFloat(String(covDet || "").replace(/[^0-9.]/g, ""));
      if ((!det || numDet < 1000) && numCov >= 1000) {
        det = covDet;
      }
    }
    const formField = FORM_FIELDS.find((item) => item.name === fieldName);
    return displayValue(formField?.kind || "text", det);
  }, [workspace?.fields]);

  const isFieldModified = useCallback((fieldName: string): boolean => {
    const current = String(formValues[fieldName] ?? "").trim();
    const detected = String(getDetectedValue(fieldName)).trim();
    const prev = String(previousValuesRef.current[fieldName] ?? "").trim();
    if (current === "" && detected === "") return false;
    return (detected !== "" && current !== detected) || (prev !== "" && current !== prev);
  }, [formValues, getDetectedValue]);

  // Derived preview fields with Bug FE-01 Fix: Zero direct mutation of formValues inside useMemo
  const previewFields = useMemo(() => {
    const fields: Record<string, string> = {};
    if (workspace?.fields) {
      for (const [name, field] of Object.entries(workspace.fields)) {
        fields[name] = String(field?.value ?? "");
      }
    }
    // Overlay real-time active form values on every keystroke
    for (const [name, val] of Object.entries(formValues)) {
      if (val !== undefined && val !== null && String(val).trim() !== "") {
        fields[name] = String(val);
      }
    }

    // Quotation reference aliases
    const qref = formValues["quotation_reference"] || fields["quotation_reference"] || formValues["quotation_ref"] || fields["quotation_ref"] || "";
    if (qref) {
      fields["quotation_reference"] = qref;
      fields["quotation_ref"] = qref;
      fields["quote_ref"] = qref;
      fields["reference_no"] = qref;
    }

    // Vehicle plate aliases
    const plate = formValues["vehicle_no"] || fields["vehicle_no"] || "";
    if (plate) {
      fields["vehicle_no"] = plate;
      fields["vehicle_plate"] = plate;
      fields["car_plate"] = plate;
      fields["plate_no"] = plate;
    }

    // Insurer name aliases
    const companyName = workspace?.pinned_names?.company_name || "";
    const effectiveCompany = formValues["insurance_company"] || fields["insurance_company"] || companyName;
    if (effectiveCompany) {
      const upperCompany = effectiveCompany.toUpperCase();
      fields["insurance_company"] = upperCompany;
      fields["insurance_name"] = upperCompany;
      fields["company_name"] = upperCompany;
      fields["insurer_name"] = upperCompany;
    }

    // Sum insured / coverage amount
    const sumIns = formValues["sum_insured"] || fields["sum_insured"] || formValues["coverage_amount"] || fields["coverage_amount"] || "";
    if (sumIns) {
      fields["sum_insured"] = sumIns;
      fields["coverage_amount"] = sumIns;
    }

    // Engine CC aliases
    const cc = formValues["engine_cc"] || fields["engine_cc"] || "";
    if (cc) {
      fields["engine_cc"] = cc;
      fields["vehicle_cc"] = cc;
      fields["engine_capacity"] = cc;
    }

    // NCD aliases
    const ncd = formValues["ncd_percent"] || fields["ncd_percent"] || formValues["ncd_percentage"] || fields["ncd_percentage"] || "";
    if (ncd) {
      fields["ncd_percent"] = ncd;
      fields["ncd_percentage"] = ncd;
    }

    // Premium aliases
    const prem = formValues["premium"] || fields["premium"] || formValues["coverage_premium"] || fields["coverage_premium"] || "";
    if (prem) {
      fields["premium"] = prem;
      fields["coverage_premium"] = prem;
      fields["basic_premium_vehicle"] = prem;
    }

    // Road tax aliases
    const custName = formValues["insured_name"] || formValues["customer_name"] || fields["insured_name"] || fields["customer_name"] || "";
    const clientType = formValues["client_type"] || fields["client_type"] || "";
    const isCorpName = /(SDN\s*BHD|BHD|ENTERPRISE|TRADING|LTD|LLC|PLT|COMPANY|ENT\.|CORP|HOLDINGS|CO\.)/i.test(String(custName));
    const isCorp = String(clientType).toLowerCase().includes("company") || String(clientType).toLowerCase().includes("corp") || isCorpName;

    const carModel = formValues["car_model"] || fields["car_model"] || "";
    const carBrand = formValues["car_brand"] || fields["car_brand"] || (workspace?.fields?.car_brand as WorkspaceField | undefined)?.value || "";
    let rtax = formValues["roadtax"] || fields["roadtax"] || formValues["road_tax_amount"] || fields["road_tax_amount"] || "";
    const ccStr = formValues["engine_cc"] || fields["engine_cc"] || "";
    let vtype = formValues["vehicle_type"] || fields["vehicle_type"] || "Car";
    const evCat = detectEVCategory(carBrand, carModel, ccStr);

    const hasExplicitVtype = !!(formValues["vehicle_type"] || (workspace?.fields?.vehicle_type as WorkspaceField | undefined)?.value);
    if (!hasExplicitVtype) {
      if (vtype.startsWith("EV") || evCat) {
        vtype = vtype.startsWith("EV") ? vtype : (evCat || "EVSaloonCar");
        // FIX FE-01: Compute derived value purely on fields, eliminate direct mutation of formValues
        fields["vehicle_type"] = vtype;
      } else if (isNonSaloonCarModel(carModel) || vtype.toLowerCase().includes("nonsaloon") || vtype.toLowerCase().includes("non-saloon") || vtype.toLowerCase().includes("suv") || vtype.toLowerCase().includes("mpv")) {
        vtype = "NonSaloonCar";
        // FIX FE-01: Compute derived value purely on fields, eliminate direct mutation of formValues
        fields["vehicle_type"] = "NonSaloonCar";
      } else if (isCorp && (vtype === "Car" || vtype.toLowerCase().includes("saloon"))) {
        vtype = "CompanyCar";
        // FIX FE-01: Compute derived value purely on fields, eliminate direct mutation of formValues
        fields["vehicle_type"] = "CompanyCar";
      }
    }

    const isEV = vtype.startsWith("EV");
    const rawParsed = ccStr ? parseFloat(String(ccStr).replace(/[^0-9.]/g, "")) : (isEV ? null : inferCCFromCarModel(carModel));
    const rawStoredRT = (workspace?.fields?.roadtax as WorkspaceField | undefined)?.value;
    const hasStoredRT = rawStoredRT !== undefined && rawStoredRT !== null && String(rawStoredRT).trim() !== "";
    const hasFormRT = formValues["roadtax"] !== undefined && formValues["roadtax"] !== null && String(formValues["roadtax"]).trim() !== "";
    if (hasStoredRT && !hasFormRT) {
      rtax = String(rawStoredRT);
    }
    if (rtax !== undefined && rtax !== null && String(rtax).trim() !== "") {
      fields["roadtax"] = rtax;
      fields["road_tax_amount"] = rtax;
    }

    // Runner / Service fee aliases
    const sfee = formValues["service_fee"] || fields["service_fee"] || formValues["runner_fee"] || fields["runner_fee"] || "";
    if (sfee) {
      fields["service_fee"] = sfee;
      fields["runner_fee"] = sfee;
    }

    // Compute live total premium (Insurance Premium + Roadtax + Runner Fee + Extras)
    const pNum = parseFloat(String(fields["premium"] || "").replace(/[^0-9.]/g, "")) || 0;
    const isRound = roundTotal;
    const effPremiumNum = isRound && pNum > 0 ? Math.round(pNum) : pNum;
    if (isRound && pNum > 0) {
      const roundedPremStr = effPremiumNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      fields["premium"] = roundedPremStr;
      fields["coverage_premium"] = roundedPremStr;
      fields["basic_premium_vehicle"] = roundedPremStr;
    }
    const incRT = formValues["include_road_tax"] !== "false" && String((workspace?.fields?.include_road_tax as WorkspaceField | undefined)?.value || "") !== "false";
    const incRF = formValues["include_runner_fee"] !== "false" && String((workspace?.fields?.include_runner_fee as WorkspaceField | undefined)?.value || "") !== "false";
    const rtNum = incRT ? (parseFloat(String(fields["roadtax"] || "").replace(/[^0-9.]/g, "")) || 0) : 0;
    const sfNum = incRF ? (parseFloat(String(fields["service_fee"] || "").replace(/[^0-9.]/g, "")) || 0) : 0;
    const extrasTotal = (workspace?.extras || []).reduce((acc, ex) => {
      const amt = (ex as Record<string, unknown>)?.price;
      const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
      const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
      return acc + (Number.isFinite(num) ? num : 0);
    }, 0);

    const totalField = workspace?.fields?.total_amount as WorkspaceField | undefined;
    const isManualTotal = totalField?.decision?.decision === "edit" && totalField?.value;
    let effTotal = "";
    if (isManualTotal && formValues["total_amount"]) {
      effTotal = formValues["total_amount"];
    } else {
      const calculatedTotal = effPremiumNum + extrasTotal + rtNum + sfNum;
      const finalTotalNum = isRound && calculatedTotal > 0 ? Math.round(calculatedTotal) : calculatedTotal;
      if (finalTotalNum > 0) {
        effTotal = finalTotalNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      } else {
        const rawTot = formValues["total_amount"] || fields["total_amount"] || workspace?.total_premium_adjusted || "";
        const rawNum = parseFloat(String(rawTot).replace(/[^0-9.]/g, ""));
        if (isRound && rawNum > 0) {
          effTotal = Math.round(rawNum).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        } else {
          effTotal = rawTot;
        }
      }
    }

    const calculatedPremium = effPremiumNum + extrasTotal;
    fields["insurance_premium_total"] = calculatedPremium > 0
      ? calculatedPremium.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : "";

    // Validity date aliases
    const vUntil = formValues["valid_until"] || fields["valid_until"] || formValues["quotation_validity"] || fields["quotation_validity"] || "";
    if (vUntil) {
      fields["valid_until"] = vUntil;
      fields["quotation_validity"] = vUntil;
    }

    // Authorized Driver aliases
    const authDriver = formValues["authorized_driver"] || fields["authorized_driver"] || "";
    if (authDriver) {
      fields["authorized_driver"] = authDriver;
      fields["authorised_driver"] = authDriver;
    } else {
      const allText = JSON.stringify(fields).toLowerCase();
      const resolvedDriver = (allText.includes("named driver") || allText.includes("named_driver")) ? "Named Driver" : "All Driver";
      fields["authorized_driver"] = resolvedDriver;
      fields["authorised_driver"] = resolvedDriver;
    }

    fields["total_amount"] = effTotal;
    fields["total_premium_adjusted"] = effTotal;
    return fields;
  }, [workspace?.fields, workspace?.total_premium_adjusted, workspace?.extras, workspace?.pinned_names?.company_name, workspace?.display_options, formValues, roundTotal]);

  function commitField(field: FormField, explicitValue?: string) {
    const current = explicitValue !== undefined ? explicitValue : formValues[field.name];
    if (current === undefined) return;

    if (current.trim() === "") {
      decideField(field.name, "clear", "");
    } else {
      decideField(field.name, "edit", current);
    }

    if (field.name === "sum_insured") {
      decideField("coverage_amount", "edit", current);
      decideField("market_value", "edit", current);
      decideField("agreed_value", "edit", current);
    }

    if (field.name === "insurance_company" && pinCatalog) {
      const match = companies.find(
        (c) => c.name.toLowerCase().trim() === current.toLowerCase().trim()
      );
      if (match && match.id !== workspace?.pinned.company_id) {
        pinCatalog(match.id);
      }
    }

    if (field.name === "premium" || field.name === "roadtax" || field.name === "service_fee") {
      decideField("total_amount", "clear", "");
      setFormValues((prev) => {
        const rawP = field.name === "premium" ? parseFloat(current.replace(/[^0-9.]/g, "")) || 0 : parseFloat(String(prev["premium"] || "").replace(/[^0-9.]/g, "")) || 0;
        const p = roundTotal && rawP > 0 ? Math.round(rawP) : rawP;
        const incRT = prev["include_road_tax"] !== "false";
        const incRF = prev["include_runner_fee"] !== "false";
        const rawRT = field.name === "roadtax" ? parseFloat(current.replace(/[^0-9.]/g, "")) || 0 : parseFloat(String(prev["roadtax"] || "").replace(/[^0-9.]/g, "")) || 0;
        const rawRF = field.name === "service_fee" ? parseFloat(current.replace(/[^0-9.]/g, "")) || 0 : parseFloat(String(prev["service_fee"] || "").replace(/[^0-9.]/g, "")) || 0;
        const rt = incRT ? rawRT : 0;
        const sf = incRF ? rawRF : 0;
        const extrasTotal = (workspace?.extras || []).reduce((acc, ex) => {
          const amt = (ex as Record<string, unknown>)?.price;
          const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
          const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
          return acc + (Number.isFinite(num) ? num : 0);
        }, 0);
        const rawTot = p + rt + sf + extrasTotal;
        if (rawTot > 0) {
          const finalTot = roundTotal ? Math.round(rawTot) : rawTot;
          const formatted = finalTot.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          return {
            ...prev,
            ...(field.name === "premium" && roundTotal && rawP > 0 ? { premium: p.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) } : {}),
            total_amount: formatted,
          };
        }
        return prev;
      });
    }

    scheduleSave();
  }

  function commitFieldDirectly(name: string, value: string) {
    if (value === undefined) return;
    if (name === "include_road_tax" || name === "include_runner_fee") {
      const boolVal = value !== "false";
      queueOperation(
        { op: "update_display_options", options: { [name]: boolVal } },
        `options.${name}`
      );
      decideField(name, "edit", value);
      decideField("total_amount", "clear", "");
      setFormValues((prev) => {
        const rawP = parseFloat(String(prev["premium"] || "").replace(/[^0-9.]/g, "")) || 0;
        const p = roundTotal && rawP > 0 ? Math.round(rawP) : rawP;
        const isIncRT = name === "include_road_tax" ? boolVal : prev["include_road_tax"] !== "false";
        const isIncRF = name === "include_runner_fee" ? boolVal : prev["include_runner_fee"] !== "false";
        const rawRT = parseFloat(String(prev["roadtax"] || "").replace(/[^0-9.]/g, "")) || 0;
        const rawRF = parseFloat(String(prev["service_fee"] || "").replace(/[^0-9.]/g, "")) || 0;
        const rt = isIncRT ? rawRT : 0;
        const sf = isIncRF ? rawRF : 0;
        const extrasTotal = (workspace?.extras || []).reduce((acc, ex) => {
          const amt = (ex as Record<string, unknown>)?.price;
          const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
          const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
          return acc + (Number.isFinite(num) ? num : 0);
        }, 0);
        const rawTot = p + rt + sf + extrasTotal;
        const finalTot = roundTotal && rawTot > 0 ? Math.round(rawTot) : rawTot;
        return {
          ...prev,
          [name]: value,
          total_amount: finalTot > 0 ? finalTot.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "",
        };
      });
      scheduleSave();
      return;
    }
    if (value.trim() === "") {
      decideField(name, "clear", "");
      if (name === "sum_insured") {
        decideField("coverage_amount", "clear", "");
        decideField("market_value", "clear", "");
        decideField("agreed_value", "clear", "");
      }
      scheduleSave();
      return;
    }
    decideField(name, "edit", value);
    if (name === "sum_insured") {
      decideField("coverage_amount", "edit", value);
      decideField("market_value", "edit", value);
      decideField("agreed_value", "edit", value);
    }
    if (name === "insurance_company" && pinCatalog) {
      const match = companies.find(
        (c) => c.name.toLowerCase().trim() === value.toLowerCase().trim()
      );
      if (match && match.id !== workspace?.pinned.company_id) {
        pinCatalog(match.id);
      }
    }
    if (name === "premium" || name === "roadtax" || name === "service_fee") {
      decideField("total_amount", "clear", "");
      setFormValues((prev) => {
        const rawP = name === "premium" ? parseFloat(value.replace(/[^0-9.]/g, "")) || 0 : parseFloat(String(prev["premium"] || "").replace(/[^0-9.]/g, "")) || 0;
        const p = roundTotal && rawP > 0 ? Math.round(rawP) : rawP;
        const rt = name === "roadtax" ? parseFloat(value.replace(/[^0-9.]/g, "")) || 0 : parseFloat(String(prev["roadtax"] || "").replace(/[^0-9.]/g, "")) || 0;
        const sf = name === "service_fee" ? parseFloat(value.replace(/[^0-9.]/g, "")) || 0 : parseFloat(String(prev["service_fee"] || "").replace(/[^0-9.]/g, "")) || 0;
        const extrasTotal = (workspace?.extras || []).reduce((acc, ex) => {
          const amt = (ex as Record<string, unknown>)?.price;
          const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
          const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
          return acc + (Number.isFinite(num) ? num : 0);
        }, 0);
        const rawTot = p + rt + sf + extrasTotal;
        if (rawTot > 0) {
          const finalTot = roundTotal ? Math.round(rawTot) : rawTot;
          const formatted = finalTot.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          return {
            ...prev,
            ...(name === "premium" && roundTotal && rawP > 0 ? { premium: p.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) } : {}),
            total_amount: formatted,
          };
        }
        return prev;
      });
    }
    scheduleSave();
  }

  const handleResetField = useCallback((field: FormField) => {
    if (field.name === "total_amount") {
      const resetTotal = previewFields["total_amount"] || "";
      setFormValues((prev) => ({ ...prev, total_amount: resetTotal }));
      decideField("total_amount", "clear", "");
      delete previousValuesRef.current["total_amount"];
      scheduleSave();
      return;
    }
    const detVal = getDetectedValue(field.name);
    const targetVal = detVal !== "" ? detVal : (previousValuesRef.current[field.name] || "");
    setFormValues((prev) => ({ ...prev, [field.name]: targetVal }));
    commitFieldDirectly(field.name, targetVal);
    if (field.name === "sum_insured") {
      commitFieldDirectly("coverage_amount", targetVal);
      commitFieldDirectly("market_value", targetVal);
      commitFieldDirectly("agreed_value", targetVal);
    }
    delete previousValuesRef.current[field.name];
  }, [getDetectedValue, previewFields, decideField, scheduleSave]);

  const syncForm = useCallback(() => {
    if (!workspace) return;
    const values: Record<string, string> = {};
    for (const field of FORM_FIELDS) {
      let stored = (workspace.fields[field.name] as WorkspaceField | undefined)?.value;
      if (field.name === "sum_insured") {
        const numStored = parseFloat(String(stored || "").replace(/[^0-9.]/g, ""));
        const altCov = (workspace.fields["coverage_amount"] as WorkspaceField | undefined)?.value;
        const numAlt = parseFloat(String(altCov || "").replace(/[^0-9.]/g, ""));
        if ((!stored || numStored < 1000) && numAlt >= 1000) {
          stored = altCov;
        } else if (!stored) {
          stored = (workspace.fields["market_value"] as WorkspaceField | undefined)?.value ||
                   (workspace.fields["agreed_value"] as WorkspaceField | undefined)?.value;
        }
      }
      if (field.name === "quotation_reference") {
        const qrefCandidate = stored || workspace.quotation_ref;
        if (qrefCandidate && (!stored || !String(stored).startsWith("RL"))) {
          stored = workspace.quotation_ref || stored;
        }
      }
      values[field.name] = displayValue(field.kind, stored ?? null);
    }

    if (!values.excess_amount || values.excess_amount.trim() === "" || values.excess_amount === "—") {
      values.excess_amount = "0.00";
    }

    if (!values.compulsory_excess || values.compulsory_excess.trim() === "" || values.compulsory_excess === "—") {
      values.compulsory_excess = "0.00";
    }

    // Auto-compute road tax if missing, 0, or corporate mismatch
    const custName = values.insured_name || values.customer_name || (workspace.fields?.insured_name as WorkspaceField | undefined)?.value || "";
    const clientType = values.client_type || (workspace.fields?.client_type as WorkspaceField | undefined)?.value || "";
    const isCorpName = /(SDN\s*BHD|BHD|ENTERPRISE|TRADING|LTD|LLC|PLT|COMPANY|ENT\.|CORP|HOLDINGS|CO\.)/i.test(String(custName));
    const isCorp = String(clientType).toLowerCase().includes("company") || String(clientType).toLowerCase().includes("corp") || isCorpName;

    const carModel = values.car_model || (workspace.fields?.car_model as WorkspaceField | undefined)?.value || "";
    const carBrand = values.car_brand || (workspace.fields?.car_brand as WorkspaceField | undefined)?.value || "";
    let vtype = values.vehicle_type || (workspace.fields?.vehicle_type as WorkspaceField | undefined)?.value || "Car";

    const ccStr = values.engine_cc || (workspace.fields?.engine_cc as WorkspaceField | undefined)?.value || "";
    const evCat = detectEVCategory(carBrand, carModel, ccStr);

    const hasExplicitVtype = !!(values.vehicle_type || (workspace.fields?.vehicle_type as WorkspaceField | undefined)?.value);
    if (!hasExplicitVtype) {
      if (vtype.startsWith("EV") || evCat) {
        vtype = vtype.startsWith("EV") ? vtype : (evCat || "EVSaloonCar");
        values.vehicle_type = vtype;
      } else if (isNonSaloonCarModel(carModel) || vtype.toLowerCase().includes("nonsaloon") || vtype.toLowerCase().includes("non-saloon") || vtype.toLowerCase().includes("suv") || vtype.toLowerCase().includes("mpv")) {
        vtype = "NonSaloonCar";
        values.vehicle_type = "NonSaloonCar";
      } else if (isCorp && (vtype === "Car" || vtype.toLowerCase().includes("saloon"))) {
        vtype = "CompanyCar";
        values.vehicle_type = "CompanyCar";
      } else if (isCorp && vtype === "Motorcycle") {
        vtype = "CompanyMotorcycle";
        values.vehicle_type = "CompanyMotorcycle";
      }
    }
    if (isCorp && !values.client_type) {
      values.client_type = "Company";
    }

    const isEV = vtype.startsWith("EV");
    const rawParsed = ccStr ? parseFloat(String(ccStr).replace(/[^0-9.]/g, "")) : (isEV ? null : inferCCFromCarModel(carModel));
    const rawStoredRT = (workspace.fields?.roadtax as WorkspaceField | undefined)?.value;
    const hasStoredRT = rawStoredRT !== undefined && rawStoredRT !== null && String(rawStoredRT).trim() !== "";
    const hasExplicitRT = values.roadtax !== undefined && values.roadtax !== null && String(values.roadtax).trim() !== "";
    if (isEV && rawParsed && rawParsed > 0) {
      if (rawParsed >= 1000) {
        const kw = rawParsed / 1000;
        values.engine_cc = `${Number.isInteger(kw) ? kw : kw.toFixed(1)} kW`;
      } else if (!values.engine_cc?.includes("kW")) {
        values.engine_cc = `${Number.isInteger(rawParsed) ? rawParsed : rawParsed.toFixed(1)} kW`;
      }
    }
    if (hasStoredRT && !hasExplicitRT) {
      values.roadtax = String(rawStoredRT);
    }

    // Sync Total Premium with roadtax, runner fee, and extras
    const pNum = parseFloat(String(values.premium || "").replace(/[^0-9.]/g, "")) || 0;
    const isRound = roundTotal;
    const effPremiumNum = isRound && pNum > 0 ? Math.round(pNum) : pNum;
    if (isRound && pNum > 0) {
      values.premium = effPremiumNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    const incRT = values.include_road_tax !== "false" && String((workspace.fields?.include_road_tax as WorkspaceField | undefined)?.value || "") !== "false";
    const incRF = values.include_runner_fee !== "false" && String((workspace.fields?.include_runner_fee as WorkspaceField | undefined)?.value || "") !== "false";
    const rtNum = incRT ? (parseFloat(String(values.roadtax || "").replace(/[^0-9.]/g, "")) || 0) : 0;
    const sfNum = incRF ? (parseFloat(String(values.service_fee || "").replace(/[^0-9.]/g, "")) || 0) : 0;
    const extrasTotal = (workspace.extras || []).reduce((acc, ex) => {
      const amt = (ex as Record<string, unknown>)?.price;
      const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
      const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
      return acc + (Number.isFinite(num) ? num : 0);
    }, 0);

    const totalField = workspace.fields?.total_amount as WorkspaceField | undefined;
    const isManualTotal = totalField?.decision?.decision === "edit" && totalField?.value;
    if (isManualTotal) {
      values.total_amount = displayValue("money", totalField.value);
    } else if (pNum > 0) {
      const combinedPremium = effPremiumNum + extrasTotal;
      values.insurance_premium_total = combinedPremium > 0 ? combinedPremium.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
      const rawTot = effPremiumNum + rtNum + sfNum + extrasTotal;
      const finalTot = isRound && rawTot > 0 ? Math.round(rawTot) : rawTot;
      values.total_amount = finalTot.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (workspace.total_premium_adjusted) {
      values.total_amount = formatMoney(workspace.total_premium_adjusted);
    }

    setFormValues(values);
  }, [workspace, roundTotal]);

  useEffect(() => {
    syncForm();
  }, [syncForm, mutation.lastSavedAt]);

  async function saveAndCheckLearning() {
    setActionError(null);
    try {
      await save();
      if (!workspace) return;
      for (const fieldName of LEARNABLE.keys()) {
        const stored = (workspace.fields[fieldName] as WorkspaceField | undefined)?.value;
        const value = String(stored ?? "").trim();
        if (!value || promptedRef.current.has(`${fieldName}:${value}`)) continue;
        promptedRef.current.add(`${fieldName}:${value}`);
        try {
          const known = await api<{ known: boolean }>(`/business/dictionaries/contains?field=${encodeURIComponent(LEARNABLE.get(fieldName) || fieldName)}&value=${encodeURIComponent(value)}`);
          if (!known.known) {
            setLearnPrompt({ field: LEARNABLE.get(fieldName) || fieldName, value });
            break;
          }
        } catch {
          // Best effort
        }
      }
    } catch (error) {
      setActionError(apiErrorMessage(error));
    }
  }

  async function learnValue() {
    if (!learnPrompt) return;
    try {
      await api(`/business/dictionaries/learn`, {
        method: "POST",
        body: JSON.stringify({ field: learnPrompt.field, value: learnPrompt.value }),
      });
    } catch {
      // Best effort
    }
    setLearnPrompt(null);
  }

  return {
    formValues,
    setFormValues,
    previewFields,
    isFieldModified,
    getDetectedValue,
    commitField,
    commitFieldDirectly,
    handleResetField,
    syncHighlight,
    setSyncHighlight,
    roundTotal,
    setRoundTotal,
    toggleRoundTotal,
    showDesign2Schedule,
    setShowDesign2Schedule,
    toggleDesign2Schedule,
    extrasDisplayMode,
    setExtrasDisplayMode,
    handleExtrasDisplayModeChange,
    previousValuesRef,
    scheduleSave,
    learnPrompt,
    setLearnPrompt,
    learnValue,
    saveAndCheckLearning,
    actionError,
    setActionError,
    toastMessage,
    setToastMessage,
    syncForm,
    mutation,
  };
}
