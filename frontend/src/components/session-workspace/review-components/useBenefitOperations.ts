"use client";

import { useCallback, useMemo, useState } from "react";
import type { WorkspaceSnapshot } from "../types";
import { isPaidExtraBenefitCard } from "@/components/template-canvas/shared";

export const GLOBAL_BENEFIT_KEYS = new Set([
  "special-perils",
  "roadside-assistance",
  "repair-workmanship-warranty",
  "all-drivers",
  "personal-accident",
  "repair-allowance-cart",
  "betterment-protection",
  "flood-relief-allowance",
  "total-loss-theft-allowance",
  "key-replacement",
  "ambulance-fees",
  "personal-belongings-theft",
  "falling-object-damage",
  "document-replacement",
]);

export type GlobalConcept = {
  id: string;
  concept_key: string;
  label: string;
  description: string | null;
  sort_order: number;
  default_asset_id?: string | null;
  default_asset?: { url?: string } | null;
};

export interface AddCustomBenefitPayload {
  label: string;
  value?: string;
  price?: number | string | null;
  description?: string;
  icon_hint?: string;
  isSelected?: boolean;
  targetState?: "current" | "available_addon";
  cost_status?: "included" | "paid";
  placement?: "foc" | "addon";
}

export interface UseBenefitOperationsOptions {
  workspace: WorkspaceSnapshot | null;
  formValues: Record<string, string>;
  queueOperation: (op: Record<string, unknown> & { op: string }, path: string) => void;
  scheduleSave: () => void;
  setToastMessage: (msg: string | null) => void;
}

export function useBenefitOperations({
  workspace,
  formValues,
  queueOperation,
  scheduleSave,
  setToastMessage,
}: UseBenefitOperationsOptions) {
  const [undoStack, setUndoStack] = useState<{ op: Record<string, unknown> & { op: string }; path: string; desc: string; revertOp?: Record<string, unknown> & { op: string } }[]>([]);
  const [redoStack, setRedoStack] = useState<{ op: Record<string, unknown> & { op: string }; path: string; desc: string; revertOp?: Record<string, unknown> & { op: string } }[]>([]);
  const [packPlanSelections, setPackPlanSelections] = useState<Record<string, string>>({});
  const [customPrice, setCustomPrice] = useState("");
  const [customLabel, setCustomLabel] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [benefitsViewMode, setBenefitsViewMode] = useState<"defaults" | "addons" | "both">("both");
  const [benefitsCollapsed, setBenefitsCollapsed] = useState(false);
  const [modalTarget, setModalTarget] = useState<"current" | "available_addon">("current");
  const [showGlobalModal, setShowGlobalModal] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const [modalFilter, setModalFilter] = useState<"all" | "insurer" | "global" | "addons">("all");

  const currentVehicleCategory: "Car" | "Motorcycle" | "Lorry" = useMemo(() => {
    const raw = String(formValues?.vehicle_type || workspace?.fields?.vehicle_type?.value || "").toLowerCase();
    if (raw.includes("motor") || raw.includes("bike")) return "Motorcycle";
    if (raw.includes("lorry") || raw.includes("commercial") || raw.includes("truck") || raw.includes("haulage")) return "Lorry";
    return "Car";
  }, [formValues?.vehicle_type, workspace?.fields?.vehicle_type]);

  const isExcludedForVehicle = useCallback(
    (_item: { label?: string; title?: string; concept_key?: string } | null | undefined) => {
      // User retains full control to view, add, or remove any benefit card without arbitrary suppression
      return false;
    },
    []
  );

  const currentCards = useMemo(() => {
    if (!workspace?.benefit_cards?.current_benefits) return [];
    return workspace.benefit_cards.current_benefits.filter((card) => !isExcludedForVehicle(card));
  }, [workspace?.benefit_cards?.current_benefits, isExcludedForVehicle]);

  const addonCards = useMemo(() => {
    if (!workspace?.benefit_cards?.available_addons) return [];
    const currentConceptIds = new Set(currentCards.map((c) => String(c.concept_id || "")).filter(Boolean));
    const currentConceptKeys = new Set(currentCards.map((c) => String(c.concept_key || "")).filter(Boolean));
    const currentLabels = new Set(currentCards.map((c) => String(c.label || "").trim().toLowerCase()).filter(Boolean));

    return workspace.benefit_cards.available_addons
      .filter((card) => !isExcludedForVehicle(card))
      .filter((card) => {
        if (card.concept_id && currentConceptIds.has(String(card.concept_id))) return false;
        if (card.concept_key && currentConceptKeys.has(String(card.concept_key))) return false;
        if (card.label && currentLabels.has(String(card.label).trim().toLowerCase())) return false;
        return true;
      });
  }, [workspace?.benefit_cards?.available_addons, currentCards, isExcludedForVehicle]);

  const focCards = useMemo(() => currentCards.filter((card) => !isPaidExtraBenefitCard(card)), [currentCards]);
  const purchasedAddonCards = useMemo(() => currentCards.filter((card) => isPaidExtraBenefitCard(card)), [currentCards]);

  function onQueue(op: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) {
    queueOperation(op, path);
    setUndoStack((prev) => [...prev, { op, path, revertOp, desc: "Benefit update" }]);
    setRedoStack([]);
    scheduleSave();
  }

  function handleReset() {
    if (!workspace) return;
    const op = { op: "reset_benefits" };
    queueOperation(op, "benefits");
    setUndoStack((prev) => [...prev, { op, path: "benefits", desc: "Reset benefits" }]);
    setRedoStack([]);
    scheduleSave();
  }

  const handleUndo = useCallback(async () => {
    if (!undoStack.length) return;
    const last = undoStack[undoStack.length - 1];
    setUndoStack((prev) => prev.slice(0, -1));
    setRedoStack((prev) => [...prev, last]);
    if (last.revertOp) {
      queueOperation(last.revertOp, last.path);
    } else if (last.op.selection_id) {
      queueOperation({ op: "revert_benefit", selection_id: last.op.selection_id }, last.path);
    } else if (last.op.op === "create_custom_benefit" && (last.op as any).selection_key) {
      queueOperation({ op: "benefit_update", selection_id: (last.op as any).selection_key, state: "removed" }, last.path);
    } else if (last.op.op === "select_catalog_offering" && last.op.offering_id) {
      queueOperation({ op: "select_catalog_offering", offering_id: last.op.offering_id, state: "removed", cost_status: "included" }, last.path);
    } else {
      queueOperation({ op: "reset_benefits" }, "benefits");
    }
    scheduleSave();
    setToastMessage("Undid benefit change.");
  }, [undoStack, queueOperation, scheduleSave, setToastMessage]);

  const handleRedo = useCallback(async () => {
    if (!redoStack.length) return;
    const next = redoStack[redoStack.length - 1];
    setRedoStack((prev) => prev.slice(0, -1));
    setUndoStack((prev) => [...prev, next]);
    queueOperation(next.op, next.path);
    scheduleSave();
    setToastMessage("Redid benefit change.");
  }, [redoStack, queueOperation, scheduleSave, setToastMessage]);

  function addCustomBenefit(payloadOrTarget?: AddCustomBenefitPayload | "current" | "available_addon") {
    let label = "";
    let displayVal = "";
    let targetState: "current" | "available_addon" = "current";
    let costStatus: "included" | "paid" = "paid";
    let priceObj: { amount: string; currency: string } | undefined = undefined;
    let descriptionText = "";
    let iconHintText = "";

    if (typeof payloadOrTarget === "object" && payloadOrTarget !== null) {
      label = payloadOrTarget.label.trim();
      displayVal = payloadOrTarget.value?.trim() || "";
      if (payloadOrTarget.placement === "foc") {
        targetState = "current";
        costStatus = "included";
      } else if (payloadOrTarget.placement === "addon") {
        targetState = payloadOrTarget.targetState || (payloadOrTarget.isSelected === false ? "available_addon" : "current");
        costStatus = "paid";
      } else {
        targetState = payloadOrTarget.targetState || (payloadOrTarget.isSelected === false ? "available_addon" : "current");
        if (payloadOrTarget.cost_status) {
          costStatus = payloadOrTarget.cost_status;
        } else if (payloadOrTarget.price != null && payloadOrTarget.price !== "") {
          costStatus = "paid";
        } else {
          costStatus = "included";
        }
      }

      if (costStatus === "paid" && payloadOrTarget.price != null && payloadOrTarget.price !== "") {
        priceObj = { amount: String(payloadOrTarget.price).replace(/,/g, ""), currency: "MYR" };
      }
      descriptionText = payloadOrTarget.description?.trim() || "";
      iconHintText = payloadOrTarget.icon_hint?.trim() || "";
    } else {
      label = customLabel.trim();
      displayVal = customValue.trim();
      targetState = payloadOrTarget || "current";
      const priceText = customPrice.trim();
      if (priceText) {
        priceObj = { amount: priceText.replace(/,/g, ""), currency: "MYR" };
        costStatus = "paid";
      } else {
        costStatus = "included";
      }
    }

    if (!label) return;
    const key = `custom:${crypto.randomUUID()}`;
    const typedValue = displayVal
      ? {
          type: "custom",
          display_text: displayVal,
          ...(descriptionText ? { description: descriptionText } : {}),
          ...(iconHintText ? { icon_hint: iconHintText } : {}),
        }
      : {
          type: "text",
          display_text: "",
          hide_limit: true,
          ...(descriptionText ? { description: descriptionText } : {}),
          ...(iconHintText ? { icon_hint: iconHintText } : {}),
        };
    const op = {
      op: "create_custom_benefit",
      selection_key: key,
      label,
      typed_value: typedValue,
      cost_status: costStatus,
      state: targetState,
      ...(costStatus === "paid" && priceObj ? { price: priceObj } : {}),
      ...(descriptionText ? { description: descriptionText } : {}),
      ...(iconHintText ? { icon_hint: iconHintText } : {}),
    };
    onQueue(op, `benefits.${key}`);
    setCustomLabel("");
    setCustomValue("");
    setCustomPrice("");
  }

  function addConceptAsBenefit(
    concept: GlobalConcept,
    state: "current" | "available_addon" = "current",
    price?: { amount: number; currency: string } | null,
    coverageLimit?: string | null
  ) {
    const key = `concept:${concept.concept_key}:${crypto.randomUUID().slice(0, 8)}`;
    const cleanLimit = coverageLimit && typeof coverageLimit === "string" && !coverageLimit.includes("[object") ? coverageLimit.trim() : "";
    const hasUnitOrText = /^(?:rm|myr)\b|\b(?:km|years?|yrs?|days?|unlimited|%)\b/i.test(cleanLimit);
    const formattedLimit = cleanLimit ? (hasUnitOrText ? cleanLimit : `RM ${cleanLimit}`) : "";
    const conceptDesc = concept.description?.trim() || "";
    const typedValue = formattedLimit
      ? {
          type: "custom",
          display_text: formattedLimit,
          ...(conceptDesc ? { description: conceptDesc } : {}),
        }
      : {
          type: "text",
          display_text: "",
          hide_limit: true,
          ...(conceptDesc ? { description: conceptDesc } : {}),
        };
    const op = {
      op: "create_custom_benefit",
      selection_key: key,
      concept_id: concept.id,
      concept_key: concept.concept_key,
      label: concept.label,
      typed_value: typedValue,
      cost_status: "paid",
      state,
      price: price || null,
      ...(conceptDesc ? { description: conceptDesc } : {}),
    };
    onQueue(op, `benefits.${key}`);
    setShowGlobalModal(false);
  }

  function addPack(pack: { package_id: string; name: string }, planId: string) {
    if (!planId) return;
    queueOperation({
      op: "select_package_plan",
      package_id: pack.package_id,
      plan_id: planId,
      cost_status: "paid",
    }, `benefits.plan.${planId}`);
    scheduleSave();
  }

  function removePack(planId: string) {
    queueOperation({ op: "remove_package_plan", plan_id: planId }, `benefits.plan.${planId}`);
    scheduleSave();
  }

  return {
    undoStack,
    redoStack,
    packPlanSelections,
    setPackPlanSelections,
    customPrice,
    setCustomPrice,
    customLabel,
    setCustomLabel,
    customValue,
    setCustomValue,
    benefitsViewMode,
    setBenefitsViewMode,
    benefitsCollapsed,
    setBenefitsCollapsed,
    modalTarget,
    setModalTarget,
    showGlobalModal,
    setShowGlobalModal,
    globalSearch,
    setGlobalSearch,
    modalFilter,
    setModalFilter,
    currentVehicleCategory,
    isExcludedForVehicle,
    currentCards,
    addonCards,
    focCards,
    purchasedAddonCards,
    onQueue,
    handleReset,
    handleUndo,
    handleRedo,
    addCustomBenefit,
    addConceptAsBenefit,
    addPack,
    removePack,
  };
}
