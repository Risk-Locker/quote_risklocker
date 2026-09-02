"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import type {
  BenefitCardSummary,
  MutationState,
  ScalarDecision,
  WorkspaceOperation,
  WorkspaceSnapshot,
} from "./types";

/** Recalculate the adjusted final price from base premium + roadtax + runner fee + extras prices. */
function _recalcAdjustedTotal(snapshot: WorkspaceSnapshot, nextExtras: WorkspaceSnapshot["extras"]): string {
  const pRaw = snapshot.fields?.premium;
  const pVal = typeof pRaw === "object" && pRaw !== null ? (pRaw as Record<string, unknown>).value : pRaw;
  const basePremium = parseFloat(String(pVal ?? "").replace(/[^0-9.]/g, "")) || 0;

  const rtRaw = snapshot.fields?.roadtax;
  const rtVal = typeof rtRaw === "object" && rtRaw !== null ? (rtRaw as Record<string, unknown>).value : rtRaw;
  let rt = parseFloat(String(rtVal ?? "").replace(/[^0-9.]/g, "")) || 0;
  if (rt === 0) {
    const ccRaw = snapshot.fields?.engine_cc;
    const ccVal = typeof ccRaw === "object" && ccRaw !== null ? (ccRaw as Record<string, unknown>).value : ccRaw;
    const parsedCC = ccVal ? parseInt(String(ccVal).replace(/[^0-9]/g, ""), 10) : 0;
    if (parsedCC > 0) {
      const carRaw = snapshot.fields?.car_model || snapshot.fields?.vehicle_model;
      const carVal = typeof carRaw === "object" && carRaw !== null ? (carRaw as any).value : carRaw;
      const carModel = String(carVal ?? "").toUpperCase();

      const custRaw = snapshot.fields?.customer_name || snapshot.fields?.insured_name;
      const custVal = typeof custRaw === "object" && custRaw !== null ? (custRaw as any).value : custRaw;
      const custName = String(custVal ?? "").toUpperCase();

      const isCompany = /(SDN\s*BHD|BHD|ENTERPRISE|TRADING|LTD|LLC|PLT|COMPANY|ENT\.)/i.test(custName);
      const isNonSaloon = /(RANGER|HILUX|TRITON|D-MAX|NAVARA|BT-50|COLORADO|CR-V|HR-V|BR-V|X70|X50|X90|ARUZ|FORTUNER|CX-3|CX-5|CX-8|CX-9|SPORTAGE|TUCSON|SANTA FE|HARRIER|CROSS|RUSH|PAJERO|OUTLANDER|MU-X|EVEREST|TIGUAN|MACAN|CAYENNE|DEFENDER|DISCOVERY|EVOQUE|GLC|GLE|X1|X3|X4|X5|X6|XC40|XC60|XC90|ALZA|INNOVA|EXORA|VELLFIRE|ALPHARD|SERENA|ESTIMA|AVANZA|VELOZ|HIACE|URVAN|VAN|LORRY|TRUCK)/i.test(carModel);

      if (isNonSaloon) {
        if (parsedCC <= 1000) rt = 20;
        else if (parsedCC <= 1200) rt = 85;
        else if (parsedCC <= 1400) rt = 100;
        else if (parsedCC <= 1600) rt = 120;
        else if (parsedCC <= 1800) rt = 300 + (parsedCC - 1600) * 0.30;
        else if (parsedCC <= 2000) rt = 360 + (parsedCC - 1800) * 0.40;
        else if (parsedCC <= 2500) rt = 440 + (parsedCC - 2000) * 0.80;
        else if (parsedCC <= 3000) rt = 840 + (parsedCC - 2500) * 1.60;
        else rt = 1640 + (parsedCC - 3000) * 1.60;
      } else if (isCompany) {
        if (parsedCC <= 1000) rt = 20;
        else if (parsedCC <= 1200) rt = 110;
        else if (parsedCC <= 1400) rt = 140;
        else if (parsedCC <= 1600) rt = 180;
        else if (parsedCC <= 1800) rt = 400 + (parsedCC - 1600) * 0.80;
        else if (parsedCC <= 2000) rt = 560 + (parsedCC - 1800) * 1.00;
        else if (parsedCC <= 2500) rt = 760 + (parsedCC - 2000) * 3.00;
        else if (parsedCC <= 3000) rt = 2260 + (parsedCC - 2500) * 7.50;
        else rt = 6010 + (parsedCC - 3000) * 13.50;
      } else {
        if (parsedCC <= 1000) rt = 20;
        else if (parsedCC <= 1200) rt = 55;
        else if (parsedCC <= 1400) rt = 70;
        else if (parsedCC <= 1600) rt = 90;
        else if (parsedCC <= 1800) rt = 200 + (parsedCC - 1600) * 0.40;
        else if (parsedCC <= 2000) rt = 280 + (parsedCC - 1800) * 0.50;
        else if (parsedCC <= 2500) rt = 380 + (parsedCC - 2000) * 1.00;
        else if (parsedCC <= 3000) rt = 880 + (parsedCC - 2500) * 2.50;
        else rt = 2130 + (parsedCC - 3000) * 4.50;
      }
    }
  }

  const sfRaw = snapshot.fields?.service_fee;
  const sfVal = typeof sfRaw === "object" && sfRaw !== null ? (sfRaw as Record<string, unknown>).value : sfRaw;
  const sf = parseFloat(String(sfVal ?? "").replace(/[^0-9.]/g, "")) || 0;

  const extrasSum = nextExtras.reduce((acc, ex) => {
    const p = ex.price;
    const amt = p ? (p.amount ?? (p as any).value ?? 0) : 0;
    const num = typeof amt === "string" ? parseFloat(amt.replace(/,/g, "")) : (typeof amt === "number" ? amt : 0);
    return acc + (Number.isFinite(num) ? num : 0);
  }, 0);

  let total = 0;
  if (basePremium > 0) {
    total = basePremium + rt + sf + extrasSum;
  } else {
    const raw = snapshot.fields?.total_amount;
    const baseVal = typeof raw === "object" && raw !== null ? (raw as Record<string, unknown>).value : raw;
    const base = parseFloat(String(baseVal ?? "").replace(/[^0-9.]/g, "")) || 0;
    total = base;
  }
  return total > 0 ? total.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
}

type DataContextValue = {
  workspace: WorkspaceSnapshot | null;
  loading: boolean;
  loadError: string | null;
};

type ActionsContextValue = {
  reload: () => Promise<void>;
  queueOperation: (operation: WorkspaceOperation, dirtyPath: string) => void;
  decideField: (field: string, decision: ScalarDecision, value?: string | null) => void;
  save: () => Promise<WorkspaceSnapshot>;
  discard: () => Promise<void>;
  navigate: (href: string) => void;
};

const DataContext = createContext<DataContextValue | null>(null);
const ActionsContext = createContext<ActionsContextValue | null>(null);
const MutationContext = createContext<MutationState | null>(null);

function applyWorkingOperation(snapshot: WorkspaceSnapshot, operation: WorkspaceOperation): WorkspaceSnapshot {
  if (operation.op === "scalar_decision") {
    const fieldName = String(operation.field || "");
    const current = snapshot.fields[fieldName] || {
      value: null,
      status: "ready",
      message: "",
      warnings: [],
    };
    const decision = operation.decision as ScalarDecision;
    const next = { ...current, decision: { decision } };
    if (decision === "edit") next.value = operation.value as string | null;
    if (decision === "clear") next.value = null;
    next.status = decision === "keep_check_needed" ? "check_needed" : "ready";
    next.message = decision === "keep_check_needed" ? "Please check this value." : "";
    return { ...snapshot, fields: { ...snapshot.fields, [fieldName]: next } };
  }
  if (operation.op === "source_disposition") {
    const sourceLineId = String(operation.source_line_id || "");
    return {
      ...snapshot,
      source_lines: snapshot.source_lines.map((line) => line.source_line_id === sourceLineId
        ? { ...line, disposition: String(operation.disposition || "unresolved") }
        : line),
    };
  }
  if (operation.op === "create_custom_benefit") {
    const key = String(operation.selection_key || `custom:${Date.now()}`);
    const selectionId = `pending:${key}`;
    const typed = operation.typed_value as Record<string, unknown> | null | undefined;
    const value = String(typed?.display_text || typed?.value || operation.label || "Included");
    const isAddon = operation.state === "available_addon";
    const newCard: BenefitCardSummary = {
      card_key: selectionId,
      selection_id: selectionId,
      offering_id: `custom:${key}`,
      offering_key: key,
      concept_id: selectionId,
      concept_key: key,
      label: String(operation.label || "Custom benefit"),
      value,
      cost_status: String(operation.cost_status || (isAddon ? "paid" : "included")),
    };

    // Build updated extras: if this is a current benefit with a price, add to extras
    const price = operation.price as { amount?: number | string; currency?: string } | null | undefined;
    const isCurrent = operation.state === "current";
    let nextExtras = [...snapshot.extras];
    if (price && isCurrent) {
      nextExtras.push({
        selection_id: selectionId,
        label: String(operation.label || "Custom benefit"),
        price: { amount: price.amount, currency: price.currency || "MYR" },
      });
    }
    const nextAdjusted = _recalcAdjustedTotal(snapshot, nextExtras);

    return {
      ...snapshot,
      benefits: [...snapshot.benefits, {
        id: selectionId,
        selection_key: key,
        label: String(operation.label || "Custom benefit"),
        state: isAddon ? "available_addon" : "current",
        cost_status: String(operation.cost_status || (isAddon ? "paid" : "included")),
        concept_id: null,
        item_kind: "custom",
        typed_value: typed || null,
      }],
      benefit_cards: {
        current_benefits: isAddon
          ? snapshot.benefit_cards.current_benefits
          : [...snapshot.benefit_cards.current_benefits, newCard],
        available_addons: isAddon
          ? [...snapshot.benefit_cards.available_addons, newCard]
          : snapshot.benefit_cards.available_addons,
      },
      extras: nextExtras,
      total_premium_adjusted: nextAdjusted || snapshot.total_premium_adjusted,
    };
  }
  if (operation.op === "select_catalog_offering") {
    const offeringId = String(operation.offering_id || "");
    const offer = snapshot.benefit_cards.available_addons.find((item) => item.offering_id === offeringId) ||
                  snapshot.benefit_cards.current_benefits.find((item) => item.offering_id === offeringId);
    if (!offer) return snapshot;
    const isAddon = operation.state === "available_addon";
    const isRemoved = operation.state === "removed";
    const selectionId = offer.selection_id && !String(offer.selection_id).startsWith("pending:")
      ? offer.selection_id
      : `pending:catalog:${offer.offering_key}`;

    const priceVal = (operation.price as Record<string, unknown> | undefined) || offer.price || offer.optional_price;
    const costStatus = String(operation.cost_status || (isAddon ? "paid" : (priceVal ? "paid" : "included")));

    const updatedCard: BenefitCardSummary = {
      ...offer,
      card_key: selectionId,
      selection_id: selectionId,
      cost_status: costStatus,
      price: priceVal as any,
    };

    let nextCurrent = snapshot.benefit_cards.current_benefits;
    let nextAddons = snapshot.benefit_cards.available_addons;
    let nextExtras = snapshot.extras;

    if (isRemoved) {
      nextCurrent = nextCurrent.filter((item) => item.offering_id !== offeringId && item.selection_id !== selectionId);
      nextAddons = nextAddons.filter((item) => item.offering_id !== offeringId && item.selection_id !== selectionId);
      nextExtras = nextExtras.filter((ex) => ex.selection_id !== selectionId);
    } else if (isAddon) {
      nextCurrent = nextCurrent.filter((item) => item.offering_id !== offeringId && item.selection_id !== selectionId);
      nextAddons = [
        ...nextAddons.filter((item) => item.offering_id !== offeringId && item.selection_id !== selectionId),
        updatedCard,
      ];
      nextExtras = nextExtras.filter((ex) => ex.selection_id !== selectionId);
    } else {
      nextAddons = nextAddons.filter((item) => item.offering_id !== offeringId && item.selection_id !== selectionId);
      nextCurrent = [
        ...nextCurrent.filter((item) => item.concept_id !== offer.concept_id && item.selection_id !== selectionId),
        updatedCard,
      ];
      if (priceVal && costStatus !== "included") {
        nextExtras = [
          ...nextExtras.filter((ex) => ex.selection_id !== selectionId),
          {
            selection_id: selectionId,
            label: updatedCard.label,
            price: priceVal as any,
            sort_order: updatedCard.sort_order || 0,
          },
        ];
      }
    }

    const nextBenefits = snapshot.benefits.filter((item) => item.id !== selectionId);
    if (!isRemoved) {
      nextBenefits.push({
        id: selectionId,
        selection_key: `catalog:${offer.offering_key}`,
        catalog_offering_id: offer.offering_id,
        concept_id: offer.concept_id,
        state: isAddon ? "available_addon" : "current",
        cost_status: costStatus,
        item_kind: "catalog",
      });
    }

    const nextAdjusted = nextExtras !== snapshot.extras
      ? _recalcAdjustedTotal(snapshot, nextExtras)
      : snapshot.total_premium_adjusted;

    return {
      ...snapshot,
      benefits: nextBenefits,
      benefit_cards: {
        current_benefits: nextCurrent,
        available_addons: nextAddons,
      },
      extras: nextExtras,
      total_premium_adjusted: nextAdjusted || snapshot.total_premium_adjusted,
    };
  }
  if (operation.op === "benefit_update") {
    const selectionId = String(operation.selection_id || "");
    const state = operation.state ? String(operation.state) : null;
    const costStatus = operation.cost_status ? String(operation.cost_status) : null;
    const typed = operation.typed_value as Record<string, unknown> | null | undefined;
    const nextBenefits = snapshot.benefits.map((item) => item.id === selectionId ? {
      ...item,
      ...(state ? { state } : {}),
      ...(costStatus ? { cost_status: costStatus } : {}),
      ...(operation.typed_value !== undefined ? { typed_value: typed } : {}),
    } : item);

    // Find the target card in either current_benefits or available_addons
    const inCurrent = snapshot.benefit_cards.current_benefits.find((item) => item.selection_id === selectionId);
    const inAddon = snapshot.benefit_cards.available_addons.find((item) => item.selection_id === selectionId);
    const targetCard = inCurrent || inAddon;

    let nextCurrent = snapshot.benefit_cards.current_benefits;
    let nextAddons = snapshot.benefit_cards.available_addons;
    let nextExtras = snapshot.extras;

    if (state === "removed") {
      nextCurrent = nextCurrent.filter((item) => item.selection_id !== selectionId && item.card_key !== selectionId);
      nextAddons = nextAddons.filter((item) => item.selection_id !== selectionId && item.card_key !== selectionId);
      nextExtras = nextExtras.filter((item) => item.selection_id !== selectionId);
    } else if (state === "available_addon" && inCurrent) {
      // Move from current to addon
      nextCurrent = nextCurrent.filter((item) => item.selection_id !== selectionId);
      nextAddons = [...nextAddons, {
        ...inCurrent,
        ...(costStatus ? { cost_status: costStatus } : {}),
      }];
    } else if (state === "current" && inAddon) {
      // Move from addon to current
      nextAddons = nextAddons.filter((item) => item.selection_id !== selectionId);
      const movedCard = {
        ...inAddon,
        ...(costStatus ? { cost_status: costStatus } : {}),
      };
      nextCurrent = [...nextCurrent, movedCard];
      const priceVal = (operation.price as Record<string, unknown> | undefined) || movedCard.price || movedCard.optional_price;
      if (priceVal && costStatus !== "included") {
        nextExtras = [...nextExtras.filter((ex) => ex.selection_id !== selectionId), {
          selection_id: selectionId,
          label: movedCard.label,
          price: priceVal,
          sort_order: movedCard.sort_order || 0,
        }];
      }
    } else {
      // Update in-place
      nextCurrent = nextCurrent.map((item) => item.selection_id === selectionId ? {
        ...item,
        ...(costStatus ? { cost_status: costStatus } : {}),
        ...(typed ? { value: String(typed.display_text ?? typed.value ?? item.value) } : {}),
      } : item);
      nextAddons = nextAddons.map((item) => item.selection_id === selectionId ? {
        ...item,
        ...(costStatus ? { cost_status: costStatus } : {}),
        ...(typed ? { value: String(typed.display_text ?? typed.value ?? item.value) } : {}),
      } : item);
    }

    // Remove from extras if a priced benefit was removed or moved to add-on
    if (state === "removed" || state === "available_addon") {
      nextExtras = nextExtras.filter((ex) => ex.selection_id !== selectionId);
    }
    const nextAdjusted = nextExtras !== snapshot.extras
      ? _recalcAdjustedTotal(snapshot, nextExtras)
      : snapshot.total_premium_adjusted;

    return {
      ...snapshot,
      benefits: nextBenefits,
      benefit_cards: {
        current_benefits: nextCurrent,
        available_addons: nextAddons,
      },
      extras: nextExtras,
      total_premium_adjusted: nextAdjusted || snapshot.total_premium_adjusted,
    };
  }
  if (operation.op === "layout_override") {
    return {
      ...snapshot,
      layout_override: operation.layout as Record<string, unknown>,
      layout_binding: {
        template_id: String(operation.template_id || "") || null,
        template_revision_id: String(operation.template_revision_id || "") || null,
        base_hash: String(operation.base_hash || "") || null,
      },
    };
  }
  if (operation.op === "pin_catalog") {
    return {
      ...snapshot,
      pinned: {
        ...snapshot.pinned,
        company_id: String(operation.company_id || "") || null,
        product_id: String(operation.product_id || "") || null,
        tier_id: String(operation.tier_id || "") || null,
        catalog_revision_id: null,
      },
      pinned_names: {
        company_name: String(operation.company_name || "") || null,
        product_name: String(operation.product_name || "") || null,
        tier_name: String(operation.tier_name || "") || null,
      },
      generation_blockers: snapshot.generation_blockers.filter(
        (blocker) => blocker.code !== "missing_catalog" || Boolean(operation.tier_id),
      ),
    };
  }
  if (operation.op === "template_selection") {
    const templateRevisionId = String(operation.template_revision_id || "") || null;
    return {
      ...snapshot,
      pinned: { ...snapshot.pinned, template_revision_id: templateRevisionId },
      template: templateRevisionId ? {
        id: String(operation.template_id || ""),
        revision_id: templateRevisionId,
        revision_number: Number(operation.revision_number || 0),
        config_hash: String(operation.config_hash || ""),
      } : null,
      layout_override: null,
      layout_binding: { template_id: null, template_revision_id: null, base_hash: null },
      generation_blockers: snapshot.generation_blockers.filter((blocker) => !["missing_template", "stale_layout_override", "scalar_check_needed", "missing_catalog"].includes(blocker.code)),
    };
  }
  return snapshot;
}

function applyPendingOperations(snapshot: WorkspaceSnapshot, operations: WorkspaceOperation[]) {
  return operations.reduce(applyWorkingOperation, snapshot);
}

export function SessionWorkspaceProvider({ sessionId, children }: { sessionId: string; children: ReactNode }) {
  const router = useRouter();
  const [serverSnapshot, setServerSnapshot] = useState<WorkspaceSnapshot | null>(null);
  const [workingSnapshot, setWorkingSnapshot] = useState<WorkspaceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [dirtyPaths, setDirtyPaths] = useState<string[]>([]);
  const operationsRef = useRef<Map<string, WorkspaceOperation>>(new Map());
  const operationVersionsRef = useRef<Map<string, number>>(new Map());
  const operationSequenceRef = useRef(0);
  const serverSnapshotRef = useRef<WorkspaceSnapshot | null>(null);
  const workingSnapshotRef = useRef<WorkspaceSnapshot | null>(null);
  const saveQueueRef = useRef<Promise<WorkspaceSnapshot> | null>(null);

  const updateWorkingSnapshot = useCallback((snapshot: WorkspaceSnapshot | null) => {
    workingSnapshotRef.current = snapshot;
    setWorkingSnapshot(snapshot);
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const result = await api<{ workspace: WorkspaceSnapshot }>(`/sessions/${sessionId}/workspace`);
      serverSnapshotRef.current = result.workspace;
      setServerSnapshot(result.workspace);
      updateWorkingSnapshot(result.workspace);
      operationsRef.current.clear();
      operationVersionsRef.current.clear();
      setDirtyPaths([]);
    } catch (error) {
      setLoadError(apiErrorMessage(error));
      throw error;
    } finally {
      setLoading(false);
    }
  }, [sessionId, updateWorkingSnapshot]);

  useEffect(() => {
    reload().catch(() => undefined);
  }, [reload]);

  const queueOperation = useCallback((operation: WorkspaceOperation, dirtyPath: string) => {
    operationSequenceRef.current += 1;
    if (operation.op === "benefit_update" && operation.state === "removed") {
      const selId = String(operation.selection_id || "");
      if (selId.startsWith("pending:")) {
        const rawKey = selId.replace("pending:", "");
        for (const k of [...operationsRef.current.keys()]) {
          if (k.includes(rawKey)) {
            operationsRef.current.delete(k);
            operationVersionsRef.current.delete(k);
          }
        }
        setDirtyPaths([...operationsRef.current.keys()]);
        const current = workingSnapshotRef.current;
        if (current) updateWorkingSnapshot(applyWorkingOperation(current, operation));
        setSaveError(null);
        return;
      }
    }
    operationsRef.current.set(dirtyPath, operation);
    operationVersionsRef.current.set(dirtyPath, operationSequenceRef.current);
    setDirtyPaths([...operationsRef.current.keys()]);
    const current = workingSnapshotRef.current;
    if (current) updateWorkingSnapshot(applyWorkingOperation(current, operation));
    setSaveError(null);
  }, [updateWorkingSnapshot]);

  const decideField = useCallback((field: string, decision: ScalarDecision, value?: string | null) => {
    queueOperation(
      { op: "scalar_decision", field, decision, ...(value !== undefined ? { value: value ?? "" } : {}) },
      `fields.${field}`,
    );
  }, [queueOperation]);

  const runSave = useCallback(async (): Promise<WorkspaceSnapshot> => {
    let baseSnapshot = serverSnapshotRef.current;
    if (!baseSnapshot) throw new Error("The quotation workspace is not loaded.");
    const sentEntries = [...operationsRef.current.entries()];
    const operations = sentEntries.map(([, operation]) => operation);
    const sentVersions = new Map(sentEntries.map(([path]) => [path, operationVersionsRef.current.get(path)]));
    if (!operations.length) return workingSnapshotRef.current || baseSnapshot;
    setSaving(true);
    setSaveError(null);
    try {
      try {
        await api<{ workspace: Partial<WorkspaceSnapshot> & { revision: number } }>(`/drafts/${baseSnapshot.draft_id}/workspace`, {
          method: "PATCH",
          body: JSON.stringify({ base_revision: baseSnapshot.revision, operations }),
        });
      } catch (err: unknown) {
        const msg = apiErrorMessage(err);
        if (msg.includes("409") || msg.includes("changed elsewhere") || (err as { status?: number })?.status === 409) {
          const fresh = await api<{ workspace: WorkspaceSnapshot }>(`/sessions/${sessionId}/workspace`);
          serverSnapshotRef.current = fresh.workspace;
          setServerSnapshot(fresh.workspace);
          baseSnapshot = fresh.workspace;
          await api<{ workspace: Partial<WorkspaceSnapshot> & { revision: number } }>(`/drafts/${baseSnapshot.draft_id}/workspace`, {
            method: "PATCH",
            body: JSON.stringify({ base_revision: baseSnapshot.revision, operations }),
          });
        } else {
          throw err;
        }
      }
      const canonical = await api<{ workspace: WorkspaceSnapshot }>(`/sessions/${sessionId}/workspace`);
      for (const [path, version] of sentVersions) {
        if (operationVersionsRef.current.get(path) === version) {
          operationsRef.current.delete(path);
          operationVersionsRef.current.delete(path);
        }
      }
      serverSnapshotRef.current = canonical.workspace;
      setServerSnapshot(canonical.workspace);
      updateWorkingSnapshot(applyPendingOperations(canonical.workspace, [...operationsRef.current.values()]));
      setDirtyPaths([...operationsRef.current.keys()]);
      setLastSavedAt(new Date().toISOString());
      return workingSnapshotRef.current || canonical.workspace;
    } catch (error) {
      const message = apiErrorMessage(error);
      setSaveError(message);
      throw error;
    } finally {
      setSaving(false);
    }
  }, [sessionId, updateWorkingSnapshot]);

  const save = useCallback(() => {
    const previous = saveQueueRef.current;
    const queued = (previous ? previous.catch(() => serverSnapshotRef.current as WorkspaceSnapshot).then(() => runSave()) : runSave());
    saveQueueRef.current = queued;
    return queued.finally(() => {
      if (saveQueueRef.current === queued) saveQueueRef.current = null;
    });
  }, [runSave]);

  const discard = useCallback(async () => {
    operationsRef.current.clear();
    operationVersionsRef.current.clear();
    setDirtyPaths([]);
    setSaveError(null);
    updateWorkingSnapshot(serverSnapshotRef.current);
  }, [updateWorkingSnapshot]);

  const navigate = useCallback((href: string) => {
    if (!operationsRef.current.size) {
      router.push(href as Route);
      return;
    }
    const choice = window.confirm("Save your quotation changes before leaving this step?");
    if (choice) {
      save().then(() => router.push(href as Route)).catch(() => undefined);
      return;
    }
    const discardChanges = window.confirm("Discard unsaved quotation changes?");
    if (discardChanges) {
      discard().then(() => router.push(href as Route));
    }
  }, [discard, router, save]);

  useEffect(() => {
    function beforeUnload(event: BeforeUnloadEvent) {
      if (!operationsRef.current.size) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, []);

  const data = useMemo<DataContextValue>(() => ({ workspace: workingSnapshot, loading, loadError }), [workingSnapshot, loading, loadError]);
  const actions = useMemo<ActionsContextValue>(() => ({ reload, queueOperation, decideField, save, discard, navigate }), [reload, queueOperation, decideField, save, discard, navigate]);
  const mutation = useMemo<MutationState>(() => ({
    dirty: dirtyPaths.length > 0,
    dirtyPaths,
    saving,
    saveError,
    lastSavedAt,
  }), [dirtyPaths, saving, saveError, lastSavedAt]);

  return (
    <DataContext.Provider value={data}>
      <ActionsContext.Provider value={actions}>
        <MutationContext.Provider value={mutation}>{children}</MutationContext.Provider>
      </ActionsContext.Provider>
    </DataContext.Provider>
  );
}

export function useWorkspaceData() {
  const value = useContext(DataContext);
  if (!value) throw new Error("useWorkspaceData must be used inside SessionWorkspaceProvider");
  return value;
}

export function useWorkspaceActions() {
  const value = useContext(ActionsContext);
  if (!value) throw new Error("useWorkspaceActions must be used inside SessionWorkspaceProvider");
  return value;
}

export function useWorkspaceMutation() {
  const value = useContext(MutationContext);
  if (!value) throw new Error("useWorkspaceMutation must be used inside SessionWorkspaceProvider");
  return value;
}
