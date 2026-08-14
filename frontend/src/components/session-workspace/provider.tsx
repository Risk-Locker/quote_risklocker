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
    const current = snapshot.fields[fieldName];
    if (!current) return snapshot;
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
    const key = String(operation.selection_key || "custom");
    const selectionId = `pending:${key}`;
    const typed = operation.typed_value as Record<string, unknown> | undefined;
    const value = String(typed?.display_text ?? typed?.value ?? "");
    return {
      ...snapshot,
      benefits: [...snapshot.benefits, {
        id: selectionId, selection_key: key, label: String(operation.label || "Custom benefit"),
        state: String(operation.state || "current"), cost_status: String(operation.cost_status || "unknown"),
        concept_id: null, item_kind: "custom", typed_value: typed || null,
      }],
      benefit_cards: {
        ...snapshot.benefit_cards,
        current_benefits: [...snapshot.benefit_cards.current_benefits, {
          card_key: selectionId, selection_id: selectionId, offering_id: selectionId, offering_key: key,
          concept_id: selectionId, concept_key: key, label: String(operation.label || "Custom benefit"), value,
          cost_status: String(operation.cost_status || "unknown"),
        }],
      },
    };
  }
  if (operation.op === "select_catalog_offering") {
    const offeringId = String(operation.offering_id || "");
    const offer = snapshot.benefit_cards.available_addons.find((item) => item.offering_id === offeringId);
    if (!offer) return snapshot;
    const selectionId = `pending:catalog:${offer.offering_key}`;
    const nextBenefits = snapshot.benefits.map((item) => item.concept_id === offer.concept_id && item.state === "current"
      ? { ...item, state: "superseded", superseded_by_id: selectionId }
      : item);
    nextBenefits.push({
      id: selectionId, selection_key: `catalog:${offer.offering_key}`, catalog_offering_id: offer.offering_id,
      concept_id: offer.concept_id, state: "current", cost_status: String(operation.cost_status || "unknown"), item_kind: "catalog",
    });
    return {
      ...snapshot,
      benefits: nextBenefits,
      benefit_cards: {
        current_benefits: [
          ...snapshot.benefit_cards.current_benefits.filter((item) => item.concept_id !== offer.concept_id),
          { ...offer, card_key: selectionId, selection_id: selectionId, cost_status: String(operation.cost_status || "unknown") },
        ],
        available_addons: snapshot.benefit_cards.available_addons.filter((item) => item.offering_id !== offeringId),
      },
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
    const nextCards = snapshot.benefit_cards.current_benefits
      .filter((item) => !(item.selection_id === selectionId && state === "removed"))
      .map((item) => item.selection_id === selectionId ? {
        ...item,
        ...(costStatus ? { cost_status: costStatus } : {}),
        ...(typed ? { value: String(typed.display_text ?? typed.value ?? item.value) } : {}),
      } : item);
    return { ...snapshot, benefits: nextBenefits, benefit_cards: { ...snapshot.benefit_cards, current_benefits: nextCards } };
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
      generation_blockers: snapshot.generation_blockers.filter((blocker) => !["missing_template", "stale_layout_override"].includes(blocker.code)),
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
    operationsRef.current.set(dirtyPath, operation);
    operationVersionsRef.current.set(dirtyPath, operationSequenceRef.current);
    setDirtyPaths([...operationsRef.current.keys()]);
    const current = workingSnapshotRef.current;
    if (current) updateWorkingSnapshot(applyWorkingOperation(current, operation));
    setSaveError(null);
  }, [updateWorkingSnapshot]);

  const decideField = useCallback((field: string, decision: ScalarDecision, value?: string | null) => {
    queueOperation(
      { op: "scalar_decision", field, decision, ...(decision === "edit" ? { value: value ?? "" } : {}) },
      `fields.${field}`,
    );
  }, [queueOperation]);

  const runSave = useCallback(async (): Promise<WorkspaceSnapshot> => {
    const baseSnapshot = serverSnapshotRef.current;
    if (!baseSnapshot) throw new Error("The quotation workspace is not loaded.");
    const sentEntries = [...operationsRef.current.entries()];
    const operations = sentEntries.map(([, operation]) => operation);
    const sentVersions = new Map(sentEntries.map(([path]) => [path, operationVersionsRef.current.get(path)]));
    if (!operations.length) return workingSnapshotRef.current || baseSnapshot;
    setSaving(true);
    setSaveError(null);
    try {
      await api<{ workspace: Partial<WorkspaceSnapshot> & { revision: number } }>(`/drafts/${baseSnapshot.draft_id}/workspace`, {
        method: "PATCH",
        body: JSON.stringify({ base_revision: baseSnapshot.revision, operations }),
      });
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
    const queued = (previous ? previous.catch(() => serverSnapshotRef.current as WorkspaceSnapshot).then(runSave) : runSave());
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
