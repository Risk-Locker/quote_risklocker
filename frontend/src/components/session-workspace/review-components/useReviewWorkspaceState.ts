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
  ["car_brand", "car_brand"],
  ["car_model", "car_model"],
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
  pinCatalog?: (
    companyId: string,
    productId?: string | null,
    tierId?: string | null,
    options?: { stageOnly?: boolean }
  ) => Promise<void>;
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
      (workspace?.display_options as Record<string, unknown> | undefined)?.round_total === true
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
  const lastSyncedRevisionRef = useRef<number | null>(null);
  const promptedRef = useRef<Set<string>>(new Set());
  const [learnPrompt, setLearnPrompt] = useState<{ field: string; value: string } | null>(null);

  /** Staged draft buffer: edits stay local until explicit Save & Sync or pre-flight export. */
  const scheduleSave = useCallback(() => {
    // Deliberately no silent 800ms auto-PATCH so partial edits never cross-sync mid-editing.
  }, []);

  useEffect(() => {
    if (workspace?.display_options) {
      if (lastSyncedRevisionRef.current === null || workspace.revision !== lastSyncedRevisionRef.current) {
        lastSyncedRevisionRef.current = workspace.revision;
        if ("round_total" in workspace.display_options) {
          setRoundTotal((workspace.display_options as Record<string, unknown>).round_total === true);
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
    queueOperation(
      { op: "update_display_options", options: { round_total: nextVal } },
      "display_options"
    );
    setToastMessage(
      nextVal
        ? "Whole-RM rounding enabled (staged). Click Save & Sync to update total."
        : "Exact sen display enabled (staged). Click Save & Sync to update total."
    );
  }, [roundTotal, decideField, queueOperation]);

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
    const includeRt = formValues["include_road_tax"] !== "false" && workspace?.display_options?.include_road_tax !== false;
    const includeRf = formValues["include_runner_fee"] !== "false" && workspace?.display_options?.include_runner_fee !== false;
    const effectiveRtax = includeRt ? rtax : "0.00";
    if (effectiveRtax !== undefined && effectiveRtax !== null && String(effectiveRtax).trim() !== "") {
      fields["roadtax"] = String(effectiveRtax);
      fields["road_tax_amount"] = String(effectiveRtax);
    }

    // Runner / Service fee aliases
    const sfee = includeRf ? (formValues["service_fee"] || fields["service_fee"] || formValues["runner_fee"] || fields["runner_fee"] || "") : "0.00";
    if (sfee) {
      fields["service_fee"] = sfee;
      fields["runner_fee"] = sfee;
    }

    // Authoritative backend totals (zero duplicate client-side rounding or tax arithmetic)
    const totalField = workspace?.fields?.total_amount as WorkspaceField | undefined;
    const isManualTotal = totalField?.decision?.decision === "edit" && totalField?.value;
    const effTotal = isManualTotal && formValues["total_amount"]
      ? formValues["total_amount"]
      : (formValues["total_amount"] || workspace?.total_premium_adjusted || fields["total_amount"] || "");

    if (fields["premium"]) {
      fields["insurance_premium_total"] = fields["premium"];
    }

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
      setFormValues((prev) => ({
        ...prev,
        [name]: value,
      }));
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

    const totalField = workspace.fields?.total_amount as WorkspaceField | undefined;
    const isManualTotal = totalField?.decision?.decision === "edit" && totalField?.value;
    if (isManualTotal) {
      values.total_amount = displayValue("money", totalField.value);
    } else if (workspace.total_premium_adjusted) {
      values.total_amount = formatMoney(workspace.total_premium_adjusted);
    } else if (totalField?.value) {
      values.total_amount = displayValue("money", totalField.value);
    }
    if (values.premium) {
      values.insurance_premium_total = values.premium;
    }

    const storedIncRt = (workspace.fields?.include_road_tax as WorkspaceField | undefined)?.value;
    const dispIncRt = workspace.display_options?.include_road_tax;
    if (storedIncRt !== undefined && storedIncRt !== null && String(storedIncRt).trim() !== "") {
      values.include_road_tax = String(storedIncRt).toLowerCase() === "false" ? "false" : "true";
    } else if (dispIncRt !== undefined) {
      values.include_road_tax = dispIncRt === false ? "false" : "true";
    } else {
      values.include_road_tax = "true";
    }

    const storedIncRf = (workspace.fields?.include_runner_fee as WorkspaceField | undefined)?.value;
    const dispIncRf = workspace.display_options?.include_runner_fee;
    if (storedIncRf !== undefined && storedIncRf !== null && String(storedIncRf).trim() !== "") {
      values.include_runner_fee = String(storedIncRf).toLowerCase() === "false" ? "false" : "true";
    } else if (dispIncRf !== undefined) {
      values.include_runner_fee = dispIncRf === false ? "false" : "true";
    } else {
      values.include_runner_fee = "true";
    }

    setFormValues(values);
  }, [workspace]);

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
    } catch (error) {
      setToastMessage(apiErrorMessage(error));
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
