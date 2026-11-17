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
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import type {
  BenefitCardSummary,
  MutationState,
  ScalarDecision,
  WorkspaceOperation,
  WorkspaceSnapshot,
} from "./types";

type DataContextValue = {
  workspace: WorkspaceSnapshot | null;
  loading: boolean;
  loadError: string | null;
};

type ActionsContextValue = {
  reload: () => Promise<void>;
  queueOperation: (operation: WorkspaceOperation, dirtyPath: string) => void;
  decideField: (field: string, decision: ScalarDecision, value?: string | null) => void;
  revertOperation: (dirtyPath: string) => void;
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

    const priceVal = ("price" in operation ? (operation.price as Record<string, unknown> | null | undefined) : undefined) !== undefined
      ? (operation.price as Record<string, unknown> | null)
      : (offer.price || offer.optional_price);
    const costStatus = String(operation.cost_status || (isAddon ? (priceVal ? "paid" : "included") : (priceVal ? "paid" : "included")));

    const labelVal = (operation as any).label || (operation as any).label_override;
    const descVal = (operation as any).description || (operation as any).description_override;

    const updatedCard: BenefitCardSummary = {
      ...offer,
      card_key: selectionId,
      selection_id: selectionId,
      cost_status: costStatus,
      price: priceVal as any,
      ...(labelVal ? { label: labelVal } : {}),
      ...(descVal !== undefined ? { description: descVal } : {}),
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
      if (priceVal && costStatus !== "included" && costStatus !== "foc") {
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

    return {
      ...snapshot,
      benefits: nextBenefits,
      benefit_cards: {
        current_benefits: nextCurrent,
        available_addons: nextAddons,
      },
      extras: nextExtras,
    };
  }
  if (operation.op === "benefit_update") {
    const selectionId = String(operation.selection_id || "");
    const state = operation.state ? String(operation.state) : null;
    const costStatus = operation.cost_status ? String(operation.cost_status) : null;
    const typed = operation.typed_value as Record<string, unknown> | null | undefined;
    const hasPrice = "price" in operation;
    const priceVal = (operation as any).price;
    const labelVal = (operation as any).label || (operation as any).label_override;
    const descVal = (operation as any).description || (operation as any).description_override;

    const nextBenefits = snapshot.benefits.map((item) => item.id === selectionId ? {
      ...item,
      ...(state ? { state } : {}),
      ...(costStatus ? { cost_status: costStatus } : {}),
      ...(operation.typed_value !== undefined ? { typed_value: typed } : {}),
      ...(labelVal ? { label_override: labelVal } : {}),
    } : item);

    // Find the target card in either current_benefits or available_addons
    const inCurrent = snapshot.benefit_cards.current_benefits.find((item) => item.selection_id === selectionId || item.card_key === selectionId);
    const inAddon = snapshot.benefit_cards.available_addons.find((item) => item.selection_id === selectionId || item.card_key === selectionId);
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
      nextCurrent = nextCurrent.filter((item) => item.selection_id !== selectionId && item.card_key !== selectionId);
      nextAddons = [...nextAddons, {
        ...inCurrent,
        ...(costStatus ? { cost_status: costStatus } : {}),
        ...(labelVal ? { label: labelVal } : {}),
        ...(descVal !== undefined ? { description: descVal } : {}),
        ...(hasPrice ? { price: priceVal as any } : {}),
      }];
    } else if (state === "current" && inAddon) {
      // Move from addon to current
      nextAddons = nextAddons.filter((item) => item.selection_id !== selectionId && item.card_key !== selectionId);
      const movedCard = {
        ...inAddon,
        ...(costStatus ? { cost_status: costStatus } : {}),
        ...(labelVal ? { label: labelVal } : {}),
        ...(descVal !== undefined ? { description: descVal } : {}),
        ...(hasPrice ? { price: priceVal as any } : {}),
      };
      nextCurrent = [...nextCurrent, movedCard];
      const effPrice = hasPrice ? priceVal : (movedCard.price || movedCard.optional_price);
      if (effPrice && costStatus !== "included" && costStatus !== "foc") {
        nextExtras = [...nextExtras.filter((ex) => ex.selection_id !== selectionId), {
          selection_id: selectionId,
          label: labelVal || movedCard.label,
          price: effPrice as any,
          sort_order: movedCard.sort_order || 0,
        }];
      }
    } else {
      // Update in-place
      const updateCard = (item: BenefitCardSummary): BenefitCardSummary => {
        if (item.selection_id !== selectionId && item.card_key !== selectionId) return item;
        return {
          ...item,
          ...(costStatus ? { cost_status: costStatus } : {}),
          ...(labelVal ? { label: labelVal } : {}),
          ...(descVal !== undefined ? { description: descVal } : {}),
          ...(typed ? { value: String(typed.display_text ?? typed.value ?? item.value) } : {}),
          ...(hasPrice ? { price: priceVal as any } : {}),
        };
      };
      nextCurrent = nextCurrent.map(updateCard);
      nextAddons = nextAddons.map(updateCard);
      if (labelVal) {
        nextExtras = nextExtras.map((ex) => ex.selection_id === selectionId ? { ...ex, label: labelVal } : ex);
      }
      if (hasPrice) {
        if (priceVal && costStatus !== "included" && costStatus !== "foc") {
          const found = nextExtras.some((ex) => ex.selection_id === selectionId);
          if (found) {
            nextExtras = nextExtras.map((ex) => ex.selection_id === selectionId ? { ...ex, price: priceVal as any } : ex);
          } else if (inCurrent) {
            nextExtras = [...nextExtras, {
              selection_id: selectionId,
              label: labelVal || targetCard?.label || "Add-on",
              price: priceVal as any,
              sort_order: targetCard?.sort_order || 0,
            }];
          }
        } else {
          nextExtras = nextExtras.filter((ex) => ex.selection_id !== selectionId);
        }
      }
    }

    // Remove from extras if a priced benefit was removed or moved to add-on
    if (state === "removed" || state === "available_addon") {
      nextExtras = nextExtras.filter((ex) => ex.selection_id !== selectionId);
    }
    return {
      ...snapshot,
      benefits: nextBenefits,
      benefit_cards: {
        current_benefits: nextCurrent,
        available_addons: nextAddons,
      },
      extras: nextExtras,
    };
  }
  if (operation.op === "update_display_options") {
    const nextOptions = {
      ...(snapshot.display_options || {}),
      ...(operation.options || {}),
    };
    return {
      ...snapshot,
      display_options: nextOptions,
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

function normalizeComparableScalar(raw: unknown): string {
  if (raw === null || raw === undefined) return "";
  const str = String(raw).trim();
  if (!str) return "";
  // Normalize numeric formatting (e.g. "1,200.00" vs "1200.00")
  const cleanedNum = str.replace(/,/g, "");
  if (/^-?\d+(?:\.\d+)?$/.test(cleanedNum)) {
    const parsed = Number(cleanedNum);
    if (Number.isFinite(parsed)) {
      return cleanedNum.includes(".") ? parsed.toFixed(2) : String(parsed);
    }
  }
  return str;
}

function isOperationNoOpAgainstBase(
  base: WorkspaceSnapshot | null,
  operation: WorkspaceOperation
): boolean {
  if (!base) return false;
  if (operation.op === "scalar_decision") {
    const fieldName = String(operation.field || "");
    const baseField = base.fields?.[fieldName];
    const baseVal = normalizeComparableScalar(baseField?.value);
    const nextVal =
      operation.decision === "clear"
        ? ""
        : normalizeComparableScalar(operation.value);
    return baseVal === nextVal;
  }
  if (operation.op === "update_display_options") {
    const opts = (operation.options || {}) as Record<string, unknown>;
    const baseOpts = (base.display_options || {}) as Record<string, unknown>;
    return Object.entries(opts).every(([k, v]) => {
      const baseV =
        baseOpts[k] !== undefined
          ? baseOpts[k]
          : k === "include_road_tax" || k === "include_runner_fee"
          ? true
          : k === "round_total"
          ? false
          : undefined;
      return Boolean(v) === Boolean(baseV);
    });
  }
  if (operation.op === "benefit_update") {
    const selId = String(operation.selection_id || "");
    const inBaseCurrent = base.benefit_cards.current_benefits.some(
      (c) => c.selection_id === selId || c.card_key === selId
    );
    const inBaseAddon = base.benefit_cards.available_addons.some(
      (c) => c.selection_id === selId || c.card_key === selId
    );
    const desiredState = operation.state ? String(operation.state) : null;
    if (desiredState === "current" && inBaseCurrent && !("label" in operation) && !("price" in operation) && !("typed_value" in operation)) {
      return true;
    }
    if (desiredState === "available_addon" && inBaseAddon && !("label" in operation) && !("price" in operation) && !("typed_value" in operation)) {
      return true;
    }
  }
  if (operation.op === "select_catalog_offering") {
    const offeringId = String(operation.offering_id || "");
    const inBaseCurrent = base.benefit_cards.current_benefits.some((c) => c.offering_id === offeringId);
    const inBaseAddon = base.benefit_cards.available_addons.some((c) => c.offering_id === offeringId);
    const desiredState = operation.state ? String(operation.state) : "current";
    if (desiredState === "current" && inBaseCurrent) return true;
    if (desiredState === "available_addon" && inBaseAddon) return true;
  }
  return false;
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
  const [pendingNavHref, setPendingNavHref] = useState<string | null>(null);
  const [navSaving, setNavSaving] = useState(false);
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

  const pruneAutoTotalClearIfClean = useCallback(() => {
    if (operationsRef.current.size === 1 && operationsRef.current.has("fields.total_amount")) {
      const totOp = operationsRef.current.get("fields.total_amount");
      if (totOp && totOp.op === "scalar_decision" && totOp.decision === "clear") {
        operationsRef.current.delete("fields.total_amount");
        operationVersionsRef.current.delete("fields.total_amount");
      }
    }
  }, []);

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
        pruneAutoTotalClearIfClean();
        setDirtyPaths([...operationsRef.current.keys()]);
        const base = serverSnapshotRef.current;
        if (base) updateWorkingSnapshot(applyPendingOperations(base, [...operationsRef.current.values()]));
        setSaveError(null);
        return;
      }
    }

    const base = serverSnapshotRef.current;
    if (dirtyPath !== "fields.total_amount" && isOperationNoOpAgainstBase(base, operation)) {
      operationsRef.current.delete(dirtyPath);
      operationVersionsRef.current.delete(dirtyPath);
      pruneAutoTotalClearIfClean();
      setDirtyPaths([...operationsRef.current.keys()]);
      if (base) {
        updateWorkingSnapshot(applyPendingOperations(base, [...operationsRef.current.values()]));
      }
      setSaveError(null);
      return;
    }

    operationsRef.current.set(dirtyPath, operation);
    operationVersionsRef.current.set(dirtyPath, operationSequenceRef.current);
    pruneAutoTotalClearIfClean();
    setDirtyPaths([...operationsRef.current.keys()]);
    if (base) {
      updateWorkingSnapshot(applyPendingOperations(base, [...operationsRef.current.values()]));
    } else {
      const current = workingSnapshotRef.current;
      if (current) updateWorkingSnapshot(applyWorkingOperation(current, operation));
    }
    setSaveError(null);
  }, [pruneAutoTotalClearIfClean, updateWorkingSnapshot]);

  const revertOperation = useCallback((dirtyPath: string) => {
    operationsRef.current.delete(dirtyPath);
    operationVersionsRef.current.delete(dirtyPath);
    if (dirtyPath === "options.include_road_tax" || dirtyPath === "fields.include_road_tax") {
      operationsRef.current.delete("options.include_road_tax");
      operationsRef.current.delete("fields.include_road_tax");
      operationVersionsRef.current.delete("options.include_road_tax");
      operationVersionsRef.current.delete("fields.include_road_tax");
    }
    if (dirtyPath === "options.include_runner_fee" || dirtyPath === "fields.include_runner_fee") {
      operationsRef.current.delete("options.include_runner_fee");
      operationsRef.current.delete("fields.include_runner_fee");
      operationVersionsRef.current.delete("options.include_runner_fee");
      operationVersionsRef.current.delete("fields.include_runner_fee");
    }
    if (dirtyPath === "fields.sum_insured") {
      for (const alias of ["fields.coverage_amount", "fields.market_value", "fields.agreed_value"]) {
        operationsRef.current.delete(alias);
        operationVersionsRef.current.delete(alias);
      }
    }
    pruneAutoTotalClearIfClean();
    setDirtyPaths([...operationsRef.current.keys()]);
    const base = serverSnapshotRef.current;
    if (base) {
      updateWorkingSnapshot(applyPendingOperations(base, [...operationsRef.current.values()]));
    }
    setSaveError(null);
  }, [pruneAutoTotalClearIfClean, updateWorkingSnapshot]);

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
      // Retain failed operations so `dirty` never resets to false or silently drops edits
      setDirtyPaths([...operationsRef.current.keys()]);
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
    setPendingNavHref(href);
  }, [router]);

  const handleSaveAndNavigate = useCallback(async () => {
    const targetHref = pendingNavHref;
    if (!targetHref) return;
    setNavSaving(true);
    try {
      await save();
      setPendingNavHref(null);
      router.push(targetHref as Route);
    } catch {
      // Save error is retained in saveError & surfaced inside the dialog
    } finally {
      setNavSaving(false);
    }
  }, [pendingNavHref, router, save]);

  const handleDiscardAndNavigate = useCallback(async () => {
    const targetHref = pendingNavHref;
    if (!targetHref) return;
    await discard();
    setPendingNavHref(null);
    router.push(targetHref as Route);
  }, [discard, pendingNavHref, router]);

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
  const actions = useMemo<ActionsContextValue>(() => ({ reload, queueOperation, decideField, revertOperation, save, discard, navigate }), [reload, queueOperation, decideField, revertOperation, save, discard, navigate]);
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
        <MutationContext.Provider value={mutation}>
          {children}
          <Dialog
            open={Boolean(pendingNavHref)}
            onOpenChange={(open) => {
              if (!open && !navSaving) setPendingNavHref(null);
            }}
            title="Unsaved Quotation Changes"
            description="You have unsaved changes staged in this quotation. Save and sync them to the ledger before leaving?"
          >
            {saveError ? (
              <div
                role="alert"
                className="mb-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-red)]/30 bg-[var(--rl-red-light)] px-3 py-2 text-xs font-semibold text-[var(--rl-red)]"
              >
                {saveError}
              </div>
            ) : null}
            <div className="flex flex-wrap justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={navSaving}
                onClick={() => setPendingNavHref(null)}
              >
                Stay Here
              </Button>
              <Button
                type="button"
                variant="danger"
                size="sm"
                disabled={navSaving}
                onClick={handleDiscardAndNavigate}
              >
                Discard &amp; Leave
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                loading={navSaving}
                onClick={handleSaveAndNavigate}
              >
                {navSaving ? "Saving..." : "Save & Leave"}
              </Button>
            </div>
          </Dialog>
        </MutationContext.Provider>
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
