"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowArcLeft,
  ArrowArcRight,
  ArrowCounterClockwise,
  ArrowRight,
  ArrowsInSimple,
  ArrowsOutSimple,
  ArrowSquareOut,
  CaretDown,
  CaretLeft,
  CaretUp,
  Check,
  CheckCircle,
  Copy,
  DownloadSimple,
  Eye,
  FilePdf,
  FloppyDisk,
  Lightning,
  Lock,
  MagnifyingGlass,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  Package as PackageIcon,
  PencilSimple,
  Plus,
  Sparkle,
  X,
} from "@phosphor-icons/react";
import { toBlob, toPng } from "html-to-image";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GuidedTour } from "@/components/guided-tour";
import { Card } from "@/components/ui/card";
import { GeminiQuotaInfoButton, type GeminiQuota } from "@/components/gemini-quota-meter";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import {
  CanvasElementView,
  balanceBenefitGridElements,
  type CanvasElement,
} from "@/components/template-canvas/shared";
import { SYSTEM_BENEFIT_PRESETS, applyPresetToCanvasElement } from "@/lib/benefit-presets";
import {
  useWorkspaceActions,
  useWorkspaceData,
  useWorkspaceMutation,
} from "@/components/session-workspace/provider";
import type { BenefitCardSummary, WorkspaceField } from "@/components/session-workspace/types";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type FieldKind = "text" | "date" | "percent" | "money" | "total" | "vehicle_type";

type FormField = { name: string; label: string; kind: FieldKind };

const FORM_FIELDS: FormField[] = [
  { name: "customer_name", label: "Insured name", kind: "text" },
  { name: "quotation_reference", label: "Quotation ref", kind: "text" },
  { name: "vehicle_no", label: "Vehicle no. / Car plate", kind: "text" },
  { name: "vehicle_type", label: "Vehicle type", kind: "vehicle_type" },
  { name: "car_model", label: "Car model", kind: "text" },
  { name: "engine_cc", label: "Engine CC / Capacity", kind: "text" },
  { name: "sum_insured", label: "Sum insured / Market value", kind: "money" },
  { name: "insurance_company", label: "Insurance name", kind: "text" },
  { name: "coverage_type", label: "Coverage type", kind: "text" },
  { name: "cover_period", label: "Cover period", kind: "text" },
  { name: "valid_until", label: "Quotation validity", kind: "text" },
  { name: "excess_amount", label: "Excess amount", kind: "money" },
  { name: "ncd_percent", label: "NCD", kind: "percent" },
  { name: "premium", label: "Insurance premium (no extras)", kind: "money" },
  { name: "insurance_premium_total", label: "Insurance premium", kind: "total" },
  { name: "roadtax", label: "Road tax", kind: "money" },
  { name: "service_fee", label: "Runner fee", kind: "money" },
  { name: "total_amount", label: "Total Payable", kind: "total" },
];

// The 7 Core Baseline Comprehensive Benefits
const BASELINE_COMPREHENSIVE_KEYS = [
  "special-perils",
  "repair-allowance-cart",
  "legal-liability-to-passengers",
  "strike-riot-civil-commotion",
  "roadside-assistance",
  "towing",
  "repair-workmanship-warranty",
];

const GLOBAL_BENEFIT_KEYS = new Set([
  "towing",
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

type CompanyOption = { id: string; name: string };
type CompanyWorkspace = {
  company: { id: string; name: string };
  products: Array<{ id: string; name: string }>;
  tiers: Array<{ id: string; product_id: string; name: string }>;
  catalogs?: Array<{ id: string; offerings?: Array<{ id: string; concept_key?: string; concept_id?: string; concept?: { id?: string; concept_key?: string } }> }>;
};

type PublishedTemplateOption = {
  template_id: string;
  template_revision_id: string;
  name: string;
  revision_number: number;
  config_hash: string;
  config?: TemplateConfig;
  page_profile: { name: string; width: number; height: number; unit: string };
};

type TemplateSelectionImpact = {
  current_template_revision_id: string | null;
  target: { template_id: string; template_revision_id: string; revision_number: number; name: string; config_hash: string };
  will_reset_layout_override: boolean;
  requires_confirmation: boolean;
  messages: string[];
};

type GlobalConcept = {
  id: string;
  concept_key: string;
  label: string;
  description: string | null;
  sort_order: number;
  default_asset_id?: string | null;
  default_asset?: { id: string; label: string; url: string } | null;
};

type TemplateConfig = {
  canvas: { width: number; height: number; elements: CanvasElement[] };
  assets?: Record<string, string>;
  [key: string]: unknown;
};

type TemplatePayload = {
  template_id: string;
  template_revision_id: string;
  revision_number: number;
  config_hash: string;
  source: string;
  config: TemplateConfig;
  binding: { template_id: string; template_revision_id: string; base_hash: string };
};

const LEARNABLE = new Map<string, string>([
  ["car_model", "car_model"],
  ["car_brand", "car_brand"],
]);

function formatMoney(raw: string | null | undefined): string {
  const number = Number(String(raw ?? "").replace(/[^0-9.-]/g, ""));
  if (!raw || Number.isNaN(number)) return "";
  return number.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(raw: string | null | undefined): string {
  const value = String(raw ?? "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-");
    return `${day}-${month}-${year}`;
  }
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(value)) {
    return value.replace(/\//g, "-");
  }
  return value;
}

function formatCoverPeriod(raw: string | null | undefined): string {
  const value = String(raw ?? "").trim();
  if (!value) return "";
  return value
    .replace(/(\d{4})-(\d{2})-(\d{2})/g, "$3-$2-$1")
    .replace(/(\d{2})\/(\d{2})\/(\d{4})/g, "$1-$2-$3");
}

function computeMalaysianRoadTax(cc: number, vehicleType: string = "Car", ownerType: string = "Individual"): number {
  if (!cc || cc <= 0) return 0;
  const normType = (vehicleType || "Car").toLowerCase();
  const normOwner = (ownerType || "Individual").toLowerCase();
  const isCompany = normOwner.includes("company") || normOwner.includes("corp") || normType.includes("company");

  if (normType.includes("motor") || normType.includes("bike")) {
    if (cc <= 150) return 2;
    if (cc <= 200) return 30;
    if (cc <= 250) return 50;
    if (cc <= 500) return isCompany ? 180 : 100;
    if (cc <= 800) return 250;
    return 350;
  }

  if (normType.includes("lorry") || normType.includes("other") || normType.includes("truck") || normType.includes("commercial")) {
    if (cc <= 1600) return 120;
    if (cc <= 2500) return 240;
    return 480;
  }

  if (isCompany) {
    if (cc <= 1000) return 20;
    if (cc <= 1200) return 110;
    if (cc <= 1400) return 140;
    if (cc <= 1600) return 180;
    if (cc <= 1800) return 400 + ((cc - 1600) * 0.80);
    if (cc <= 2000) return 560 + ((cc - 1800) * 1.00);
    if (cc <= 2500) return 760 + ((cc - 2000) * 3.00);
    if (cc <= 3000) return 2260 + ((cc - 2500) * 7.50);
    return 6010 + ((cc - 3000) * 13.50);
  }

  // Private Saloon Car
  if (cc <= 1000) return 20;
  if (cc <= 1200) return 55;
  if (cc <= 1400) return 70;
  if (cc <= 1600) return 90;
  if (cc <= 1800) return 200 + ((cc - 1600) * 0.40);
  if (cc <= 2000) return 280 + ((cc - 1800) * 0.50);
  if (cc <= 2500) return 380 + ((cc - 2000) * 1.00);
  if (cc <= 3000) return 840 + ((cc - 2500) * 2.50);
  return 2130 + ((cc - 3000) * 4.50);
}

function inferCCFromCarModel(modelStr: string | null | undefined): number | null {
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

function displayValue(kind: FieldKind, value: string | null | undefined): string {
  if (kind === "money") return formatMoney(value);
  if (kind === "date") return formatDate(value);
  if (kind === "percent") return value ? `${String(value).replace(/%/g, "")}%` : "";
  if (kind === "vehicle_type") return String(value || "Car");
  return formatCoverPeriod(String(value ?? ""));
}

function IncludedCard({
  card,
  index,
  assetUrl,
  selection,
  canUndo,
  onQueue,
}: {
  card: BenefitCardSummary;
  index: number;
  assetUrl?: string | null;
  selection?: { id: string; cost_status: string } | Record<string, unknown> | null;
  canUndo: boolean;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
}) {
  const selectionId = selection && typeof selection === "object" && "id" in selection ? String(selection.id) : (card.selection_id || null);
  const pending = !selectionId || String(selectionId).startsWith("pending:");

  const handleMoveToAddon = () => {
    if (!window.confirm(`Are you sure you want to move "${card.label}" to add-ons?`)) return;
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid" },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "included" }
      );
    } else {
      const customKey = `addon:${card.concept_key || index}`;
      onQueue(
        { op: "create_custom_benefit", selection_key: customKey, state: "available_addon", cost_status: "paid", label: card.label },
        `benefits.add.${index}`,
        { op: "benefit_update", selection_id: customKey, state: "removed" }
      );
    }
  };

  const handleRemove = () => {
    if (!window.confirm(`Are you sure you want to remove "${card.label}" completely?`)) return;
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "removed" },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: "included" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "included" },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: "included" }
      );
    } else if (card.concept_key) {
      onQueue(
        { op: "benefit_update", selection_id: card.concept_key, state: "removed" },
        `benefits.${card.concept_key}.state`,
        { op: "benefit_update", selection_id: card.concept_key, state: "current", cost_status: "included" }
      );
    }
  };

  return (
    <article className={`flex items-start justify-between gap-2.5 rounded-[var(--rl-radius-sm)] border p-2.5 shadow-xs transition-all ${card.is_detected
      ? "border-amber-300 bg-amber-50/50 ring-1 ring-amber-300/60"
      : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:border-[var(--rl-border-strong)]"
      }`}>
      {/* Left: index + image */}
      <div className="flex items-start gap-2 shrink-0">
        <span className="flex h-6 w-6 items-center justify-center rounded bg-neutral-100 font-mono text-[10px] font-bold text-[var(--rl-text-muted)] mt-0.5">
          #{index + 1}
        </span>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
          {assetUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fileUrl(assetUrl)} alt={card.label} className="h-full w-full object-contain" />
          ) : (
            <Sparkle size={18} className="text-[var(--rl-text-muted)]" />
          )}
        </div>
      </div>
      {/* Body: title, detected badge, value, description */}
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <h3 className="text-xs font-bold text-[var(--rl-text-strong)] leading-tight truncate">{card.label}</h3>
          {card.is_detected ? (
            <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold text-amber-800 ring-1 ring-amber-400/50 shrink-0">★ Detected</span>
          ) : null}
        </div>
        {card.value && !["", "Included standard cover", "Included", "FOC", "As quoted"].includes(card.value) && (
          <p className="text-[11px] font-bold text-[var(--rl-red)] leading-tight truncate">
            {card.value}
          </p>
        )}
        {card.description && (
          <p className="text-[10px] text-[var(--rl-text-muted)] leading-snug line-clamp-2">
            {card.description}
          </p>
        )}
      </div>
      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
        <Button
          variant="secondary"
          size="sm"
          title="Move this benefit to Optional Add-ons"
          onClick={handleMoveToAddon}
          className="text-[11px] h-7 px-2"
        >
          → Add-on
        </Button>
        <button
          type="button"
          aria-label={`Remove ${card.label} from this quotation`}
          onClick={handleRemove}
          className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors cursor-pointer"
          title="Remove benefit completely"
        >
          <X size={14} weight="bold" />
        </button>
      </div>
    </article>
  );
}

function AddonCard({
  card,
  index,
  assetUrl,
  onQueue,
}: {
  card: BenefitCardSummary;
  index: number;
  assetUrl?: string | null;
  onQueue: (operation: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) => void;
}) {
  const selectionId = card.selection_id;
  const pending = !selectionId || String(selectionId).startsWith("pending:");

  const currentPriceObj = card.price || card.optional_price;
  const currentAmount = currentPriceObj ? (typeof currentPriceObj === "object" ? (currentPriceObj.amount ?? (currentPriceObj as any).value) : currentPriceObj) : null;
  const currentPriceNum = currentAmount !== null && currentAmount !== "" && !isNaN(Number(currentAmount)) ? Number(currentAmount) : null;

  const initialPriceObj = card.initial_price || card.optional_price;
  const initialAmount = initialPriceObj ? (typeof initialPriceObj === "object" ? (initialPriceObj.amount ?? (initialPriceObj as any).value) : initialPriceObj) : null;
  const initialPriceNum = initialAmount !== null && initialAmount !== "" && !isNaN(Number(initialAmount)) ? Number(initialAmount) : null;

  const [isEditingPrice, setIsEditingPrice] = useState(false);
  const [priceInput, setPriceInput] = useState(currentPriceNum !== null ? String(currentPriceNum) : "");

  useEffect(() => {
    setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : "");
  }, [currentPriceNum]);

  const handlePriceCommit = (newValStr: string) => {
    setIsEditingPrice(false);
    const cleanNum = parseFloat(newValStr.replace(/[^0-9.]/g, ""));
    if (isNaN(cleanNum)) return;
    const newPrice = { amount: cleanNum, currency: "MYR" };
    if (selectionId && !pending) {
      onQueue({ op: "benefit_update", selection_id: selectionId, price: newPrice, cost_status: "paid" }, `benefits.${selectionId}.price`);
    } else if (card.offering_id) {
      onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid", price: newPrice }, `benefits.offer.${card.offering_id}`);
    }
  };

  const handleRevertPrice = () => {
    setIsEditingPrice(false);
    if (initialPriceNum !== null) {
      setPriceInput(String(initialPriceNum));
      const resetPrice = { amount: initialPriceNum, currency: "MYR" };
      if (selectionId && !pending) {
        onQueue({ op: "benefit_update", selection_id: selectionId, price: resetPrice, cost_status: "paid" }, `benefits.${selectionId}.price`);
      } else if (card.offering_id) {
        onQueue({ op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid", price: resetPrice }, `benefits.offer.${card.offering_id}`);
      }
    }
  };

  const hasPriceDiff = initialPriceNum !== null && currentPriceNum !== null && Math.abs(initialPriceNum - currentPriceNum) > 0.01;

  const handleMoveToDefault = () => {
    const priceVal = card.price || card.optional_price || null;
    const costStatus = priceVal ? "paid" : "included";
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "current", cost_status: costStatus, ...(priceVal ? { price: priceVal } : {}) },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "current", cost_status: costStatus, ...(priceVal ? { price: priceVal } : {}) },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "included" }
      );
    } else {
      const customKey = `default:${card.concept_key || index}`;
      onQueue(
        { op: "create_custom_benefit", selection_key: customKey, state: "current", cost_status: costStatus, label: card.label, ...(priceVal ? { price: priceVal } : {}) },
        `benefits.add.${index}`,
        { op: "benefit_update", selection_id: customKey, state: "removed" }
      );
    }
  };

  const handleRemove = () => {
    if (selectionId) {
      onQueue(
        { op: "benefit_update", selection_id: selectionId, state: "removed" },
        `benefits.${selectionId}.state`,
        { op: "benefit_update", selection_id: selectionId, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.offering_id && !String(card.offering_id).startsWith("pending:") && !String(card.offering_id).startsWith("custom:")) {
      onQueue(
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "removed", cost_status: "paid" },
        `benefits.offer.${card.offering_id}`,
        { op: "select_catalog_offering", offering_id: card.offering_id, state: "available_addon", cost_status: "paid" }
      );
    } else if (card.concept_key) {
      onQueue(
        { op: "benefit_update", selection_id: card.concept_key, state: "removed" },
        `benefits.${card.concept_key}.state`,
        { op: "benefit_update", selection_id: card.concept_key, state: "available_addon", cost_status: "paid" }
      );
    }
  };

  return (
    <article className={`group flex items-start justify-between gap-2.5 rounded-[var(--rl-radius-sm)] border border-dashed p-2.5 transition-all ${card.is_detected
      ? "border-amber-400 bg-amber-50/50 ring-1 ring-amber-300/60"
      : "border-[var(--rl-border)] bg-[var(--rl-surface)] hover:border-[var(--rl-black)] hover:bg-white"
      }`}>
      {/* Left: index + image */}
      <div className="flex items-start gap-2 shrink-0">
        <span className="flex h-6 w-6 items-center justify-center rounded bg-neutral-100 font-mono text-[10px] font-bold text-[var(--rl-text-muted)] mt-0.5">
          #{index + 1}
        </span>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
          {assetUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fileUrl(assetUrl)} alt={card.label} className="h-full w-full object-contain" />
          ) : (
            <Sparkle size={18} className="text-[var(--rl-text-muted)]" />
          )}
        </div>
      </div>
      {/* Body: title, detected badge, coverage, description, price */}
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <h3 className="text-xs font-bold text-[var(--rl-text-strong)] leading-tight truncate">{card.label}</h3>
          {card.is_detected ? (
            <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold text-amber-800 ring-1 ring-amber-400/50 shrink-0">★ Detected</span>
          ) : null}
        </div>
        {card.value && !["", "Optional payable add-on", "Included", "FOC", "As quoted"].includes(card.value) && (
          <p className="text-[11px] font-bold text-[var(--rl-red)] leading-tight truncate">
            {card.value}
          </p>
        )}
        {card.description && (
          <p className="text-[10px] text-[var(--rl-text-muted)] leading-snug line-clamp-2">
            {card.description}
          </p>
        )}
        {/* Price Tag & Revert Controls */}
        <div className="flex items-center gap-1.5 mt-1">
          {isEditingPrice ? (
            <div className="flex items-center gap-1">
              <span className="text-[10px] font-bold text-[var(--rl-text-muted)]">RM</span>
              <input
                type="number"
                step="any"
                value={priceInput}
                autoFocus
                onChange={(e) => setPriceInput(e.target.value)}
                onBlur={() => handlePriceCommit(priceInput)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handlePriceCommit(priceInput);
                  if (e.key === "Escape") { setIsEditingPrice(false); setPriceInput(currentPriceNum !== null ? String(currentPriceNum) : ""); }
                }}
                className="h-5 w-16 rounded border border-[var(--rl-black)] px-1 font-mono text-[11px] font-bold text-[var(--rl-text-strong)] focus:outline-none"
              />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setIsEditingPrice(true)}
              className="group/price flex items-center gap-1 rounded bg-red-50 hover:bg-red-100/80 px-1.5 py-0.5 text-[10px] font-bold text-[var(--rl-red)] transition-colors"
              title="Click to edit price"
            >
              <span>{currentPriceNum !== null ? `RM ${currentPriceNum.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "Set price"}</span>
              <PencilSimple size={10} className="text-[var(--rl-text-muted)] group-hover/price:text-[var(--rl-red)]" />
            </button>
          )}
          {hasPriceDiff ? (
            <button
              type="button"
              onClick={handleRevertPrice}
              className="flex items-center gap-0.5 rounded bg-gray-100 hover:bg-gray-200 px-1.5 py-0.5 text-[9px] font-semibold text-gray-600 transition-colors"
              title={`Revert to initial catalog price (RM ${initialPriceNum})`}
            >
              <ArrowCounterClockwise size={10} weight="bold" />
              <span>Revert (RM {initialPriceNum})</span>
            </button>
          ) : null}
        </div>
      </div>
      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
        <Button
          size="sm"
          variant="secondary"
          title="Move to Default / FOC Benefits"
          onClick={handleMoveToDefault}
          className="text-[11px] h-7 px-2 group-hover:bg-[var(--rl-black)] group-hover:text-white"
        >
          ← Default/FOC
        </Button>
        <button
          type="button"
          aria-label={`Remove ${card.label}`}
          onClick={handleRemove}
          className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)] transition-colors"
          title="Remove add-on completely"
        >
          <X size={14} weight="bold" />
        </button>
      </div>
    </article>
  );
}

export function ReviewPhase({ id, onNext }: { id: string; onNext: () => void }) {
  const { workspace, loading, loadError } = useWorkspaceData();
  const { decideField, save, reload, queueOperation } = useWorkspaceActions();
  const mutation = useWorkspaceMutation();

  const [pdfOpen, setPdfOpen] = useState(false);
  const [formValues, setFormValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(FORM_FIELDS.map((field) => [field.name, ""]))
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [companyWorkspace, setCompanyWorkspace] = useState<CompanyWorkspace | null>(null);
  const [pinLoading, setPinLoading] = useState(false);
  const [globalConcepts, setGlobalConcepts] = useState<GlobalConcept[]>([]);
  const [showGlobalModal, setShowGlobalModal] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const [modalFilter, setModalFilter] = useState<"all" | "insurer" | "global" | "addons">("all");
  const [undoStack, setUndoStack] = useState<{ op: Record<string, unknown> & { op: string }; path: string; desc: string; revertOp?: Record<string, unknown> & { op: string } }[]>([]);
  const [redoStack, setRedoStack] = useState<{ op: Record<string, unknown> & { op: string }; path: string; desc: string; revertOp?: Record<string, unknown> & { op: string } }[]>([]);
  const [activeTab, setActiveTab] = useState<"included" | "addons">("included");
  const [modalTarget, setModalTarget] = useState<"current" | "available_addon">("current");
  const [benefitsViewMode, setBenefitsViewMode] = useState<"defaults" | "addons" | "both">("both");
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [benefitsExpanded, setBenefitsExpanded] = useState(false);
  const [templateCollapsed, setTemplateCollapsed] = useState(false);
  const [extractedValuesCollapsed, setExtractedValuesCollapsed] = useState(false);
  const [extractedBenefitsCollapsed, setExtractedBenefitsCollapsed] = useState(false);
  // RL-DISABLED extractedBenefitsViewMode — disabled 2026-08-28; unused after removing evidence tab
  const [previewCollapsed, setPreviewCollapsed] = useState(false);
  const [benefitsCollapsed, setBenefitsCollapsed] = useState(false);

  // Benefit Pack (bundle plan) manager state
  const [packPlanSelections, setPackPlanSelections] = useState<Record<string, string>>({});
  const [customPrice, setCustomPrice] = useState("");

  // Quick Action Export States (PNG / PDF)
  const debouncedSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** Coalesce rapid benefit mutations into a single save after 800ms idle. */
  const scheduleSave = useCallback(() => {
    if (debouncedSaveRef.current !== null) clearTimeout(debouncedSaveRef.current);
    debouncedSaveRef.current = setTimeout(() => {
      debouncedSaveRef.current = null;
      save().catch(() => undefined);
    }, 800);
  }, [save]);

  function onQueue(op: Record<string, unknown> & { op: string }, path: string, revertOp?: Record<string, unknown> & { op: string }) {
    queueOperation(op, path);
    setUndoStack((prev) => [...prev, { op, path, revertOp, desc: "Benefit update" }]);
    setRedoStack([]);
    scheduleSave();
  }

  const [copyingPng, setCopyingPng] = useState(false);
  const [copiedPng, setCopiedPng] = useState(false);
  const [downloadingPng, setDownloadingPng] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [viewLoading, setViewLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Gemini AI Extraction & Quota State
  const [geminiExtracting, setGeminiExtracting] = useState(false);
  const [geminiQuotaInfo, setGeminiQuotaInfo] = useState<GeminiQuota | null>(null);

  useEffect(() => {
    api<{ gemini?: GeminiQuota }>("/settings/limits")
      .then((res) => {
        if (res.gemini) setGeminiQuotaInfo(res.gemini);
      })
      .catch(() => { });
  }, []);

  async function triggerGeminiExtraction() {
    setGeminiExtracting(true);
    try {
      const res = await api<{
        success: boolean;
        message: string;
        quota: GeminiQuota;
        gemini_result: Record<string, unknown>;
      }>(`/sessions/${id}/extract-gemini`, { method: "POST" });
      setGeminiQuotaInfo(res.quota);
      setToastMessage(res.message || "Gemini AI extracted values successfully!");
      await reload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Gemini extraction failed. Check your API key in .env.");
    } finally {
      setGeminiExtracting(false);
    }
  }

  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(null), 3000);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  // Pure Flexbox Drag-to-Resize State
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState<"pdf" | "main" | null>(null);
  const [colSizes, setColSizes] = useState({ pdf: 25, middle: 35, right: 40 });
  const [split2Col, setSplit2Col] = useState(45);
  const [isDesktop, setIsDesktop] = useState(true);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(typeof window !== "undefined" ? window.innerWidth >= 1024 : true);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handlePointerDown = useCallback((which: "pdf" | "main") => (e: React.PointerEvent) => {
    e.preventDefault();
    setIsDragging(which);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handlePointerMove = (e: PointerEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalWidth = rect.width;
      if (totalWidth <= 0) return;

      const offsetX = e.clientX - rect.left;
      const percent = Math.max(10, Math.min(90, (offsetX / totalWidth) * 100));

      if (pdfOpen) {
        if (isDragging === "pdf") {
          const newPdf = Math.max(15, Math.min(45, percent));
          setColSizes((prev) => {
            const remaining = 100 - newPdf;
            const currentMiddleRight = prev.middle + prev.right || 1;
            const middleRatio = prev.middle / currentMiddleRight;
            const newMiddle = Math.max(20, Math.min(remaining - 20, remaining * middleRatio));
            const newRight = remaining - newMiddle;
            return { pdf: newPdf, middle: newMiddle, right: newRight };
          });
        } else if (isDragging === "main") {
          setColSizes((prev) => {
            const minMiddle = 20;
            const maxMiddle = 100 - prev.pdf - 20;
            const newMiddle = Math.max(minMiddle, Math.min(maxMiddle, percent - prev.pdf));
            const newRight = Math.max(20, 100 - prev.pdf - newMiddle);
            return { ...prev, middle: newMiddle, right: newRight };
          });
        }
      } else {
        const newLeft = Math.max(20, Math.min(80, percent));
        setSplit2Col(newLeft);
      }
    };

    const handlePointerUp = () => {
      setIsDragging(null);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isDragging, pdfOpen]);

  const [customLabel, setCustomLabel] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [learnPrompt, setLearnPrompt] = useState<{ field: string; value: string } | null>(null);
  const promptedRef = useRef<Set<string>>(new Set());

  const [publishedTemplates, setPublishedTemplates] = useState<PublishedTemplateOption[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [templateImpact, setTemplateImpact] = useState<TemplateSelectionImpact | null>(null);

  // Live Canvas Preview state
  const [previewTemplate, setPreviewTemplate] = useState<TemplatePayload | null>(null);
  const [previewZoom, setPreviewZoom] = useState(0.48);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [selectedBenefitPreset, setSelectedBenefitPreset] = useState<string>(() => {
    try {
      const stored = (workspace?.fields?.benefit_preset as any)?.value;
      if (stored) return stored;
      return localStorage.getItem("risklocker_default_benefit_preset") || "masonry-flow";
    } catch {
      return "masonry-flow";
    }
  });

  const handleSelectBenefitPreset = useCallback((presetId: string) => {
    setSelectedBenefitPreset(presetId);
    try {
      localStorage.setItem("risklocker_default_benefit_preset", presetId);
    } catch {}
    decideField("benefit_preset", "edit", presetId);
  }, [decideField]);

  const balancedElements = useMemo(() => {
    if (!previewTemplate?.config?.canvas) return [];
    const rawElements = (previewTemplate.config.canvas.elements || []).map((el: any) => {
      if (el.type === "benefit-grid") {
        return applyPresetToCanvasElement(el, selectedBenefitPreset);
      }
      return el;
    });
    return balanceBenefitGridElements(rawElements, {
      ...workspace?.benefit_cards,
      extras: workspace?.extras,
    } as any);
  }, [previewTemplate, workspace?.benefit_cards, workspace?.extras, selectedBenefitPreset]);

  const canvasH = useMemo(() => {
    const baseHeight = previewTemplate?.config?.canvas?.height || 1123;
    if (!balancedElements.length) return baseHeight;
    const maxElementBottom = Math.max(0, ...balancedElements.map((e: any) => (e.y || 0) + (e.h || 0)));
    return maxElementBottom + 30 > baseHeight ? maxElementBottom + 30 : baseHeight;
  }, [balancedElements, previewTemplate]);

  const syncForm = useCallback(() => {
    if (!workspace) return;
    const values: Record<string, string> = {};
    for (const field of FORM_FIELDS) {
      let stored = (workspace.fields[field.name] as WorkspaceField | undefined)?.value;
      if (!stored && field.name === "sum_insured") {
        stored = (workspace.fields["coverage_amount"] as WorkspaceField | undefined)?.value ||
                 (workspace.fields["market_value"] as WorkspaceField | undefined)?.value ||
                 (workspace.fields["agreed_value"] as WorkspaceField | undefined)?.value;
      }
      values[field.name] = displayValue(field.kind, stored ?? null);
    }

    // Auto-compute road tax if missing or 0
    const currentRT = parseFloat(String(values.roadtax || "").replace(/[^0-9.]/g, "")) || 0;
    if (currentRT === 0) {
      const ccStr = values.engine_cc || (workspace.fields?.engine_cc as WorkspaceField | undefined)?.value || "";
      const parsedCC = ccStr ? parseInt(String(ccStr).replace(/[^0-9]/g, ""), 10) : 0;
      if (parsedCC > 0) {
        const vtype = values.vehicle_type || (workspace.fields?.vehicle_type as WorkspaceField | undefined)?.value || "Car";
        const isCompany = String(vtype).toLowerCase().includes("company") || String(vtype).toLowerCase().includes("corp");
        const baseType = String(vtype).toLowerCase().includes("motor") ? "Motorcycle" : (String(vtype).toLowerCase().includes("lorry") || String(vtype).toLowerCase().includes("other")) ? "Lorry" : "Car";
        const computedRT = computeMalaysianRoadTax(parsedCC, baseType, isCompany ? "Company" : "Individual");
        if (computedRT > 0) {
          values.roadtax = computedRT.toFixed(2);
        }
      }
    }

    // Sync Total Premium with roadtax, runner fee, and extras
    const pNum = parseFloat(String(values.premium || "").replace(/[^0-9.]/g, "")) || 0;
    const rtNum = parseFloat(String(values.roadtax || "").replace(/[^0-9.]/g, "")) || 0;
    const sfNum = parseFloat(String(values.service_fee || "").replace(/[^0-9.]/g, "")) || 0;
    const extrasTotal = (workspace.extras || []).reduce((acc, ex) => {
      const amt = (ex as Record<string, unknown>)?.price;
      const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
      const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
      return acc + (Number.isFinite(num) ? num : 0);
    }, 0);

    if (pNum > 0) {
      const combinedPremium = pNum + extrasTotal;
      values.insurance_premium_total = combinedPremium > 0 ? combinedPremium.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
      values.total_amount = (pNum + rtNum + sfNum + extrasTotal).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (workspace.total_premium_adjusted) {
      values.total_amount = formatMoney(workspace.total_premium_adjusted);
    }

    setFormValues(values);
  }, [workspace]);

  useEffect(() => {
    syncForm();
  }, [syncForm, mutation.lastSavedAt]);

  useEffect(() => {
    let cancelled = false;
    api<{ companies: { items: Array<{ id: string; name: string }> } }>("/business/companies?page_size=100")
      .then((result) => { if (!cancelled) setCompanies(result.companies?.items || []); })
      .catch(() => undefined);

    api<{ benefit_concepts: { items: GlobalConcept[] } }>("/business/benefit-concepts?page=1&page_size=100")
      .then((res) => { if (!cancelled) setGlobalConcepts(res.benefit_concepts?.items || []); })
      .catch(() => undefined);

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const companyId = workspace?.pinned.company_id;
    if (!companyId) {
      setCompanyWorkspace(null);
      return;
    }
    let cancelled = false;
    api<{ workspace: CompanyWorkspace }>(`/business/companies/${companyId}/workspace`)
      .then((result) => { if (!cancelled) setCompanyWorkspace(result.workspace); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [workspace?.pinned.company_id]);

  useEffect(() => {
    let cancelled = false;
    setTemplatesLoading(true);
    api<{ templates: PublishedTemplateOption[] }>("/business/templates/published")
      .then((result) => {
        if (!cancelled) {
          const list = result.templates || [];
          setPublishedTemplates(list);
          if (list.length > 0) {
            const currentRevisionId = workspace?.pinned.template_revision_id;
            const matching = list.find((item) => item.template_revision_id === currentRevisionId) || list[0];
            if (matching.config && !previewTemplate) {
              setPreviewTemplate({
                template_id: matching.template_id,
                template_revision_id: matching.template_revision_id,
                revision_number: matching.revision_number,
                config_hash: matching.config_hash,
                source: "template_revision",
                config: matching.config,
                binding: { template_id: matching.template_id, template_revision_id: matching.template_revision_id, base_hash: matching.config_hash },
              });
            }
            if (!currentRevisionId && matching.template_revision_id) {
              selectTemplateDirectly(matching.template_revision_id, list);
            }
          }
        }
      })
      .catch((error) => { if (!cancelled) setTemplateError(apiErrorMessage(error)); })
      .finally(() => { if (!cancelled) setTemplatesLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Load template config for real-time live preview
  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    api<{ template: TemplatePayload | null }>(`/sessions/${id}/template-config`)
      .then((res) => {
        if (!cancelled && res.template) setPreviewTemplate(res.template);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => { cancelled = true; };
  }, [id, workspace?.pinned.template_revision_id]);

  async function selectTemplate(templateRevisionId: string) {
    setTemplateError(null);
    if (!templateRevisionId || templateRevisionId === workspace?.pinned.template_revision_id) return;
    const option = publishedTemplates.find((item) => item.template_revision_id === templateRevisionId);
    if (!option) return;
    try {
      const res = await api<{ impact: TemplateSelectionImpact }>(`/sessions/${id}/template-selection-impact`, {
        method: "POST",
        body: JSON.stringify({ base_revision: workspace?.revision || 1, template_revision_id: option.template_revision_id }),
      });
      if (res.impact.requires_confirmation) {
        setTemplateImpact(res.impact);
      } else {
        await selectTemplateDirectly(templateRevisionId);
      }
    } catch {
      await selectTemplateDirectly(templateRevisionId);
    }
  }

  async function selectTemplateDirectly(templateRevisionId: string, customList?: PublishedTemplateOption[]) {
    setTemplateError(null);
    setTemplateImpact(null);
    if (!templateRevisionId) return;
    const pool = customList && customList.length > 0 ? customList : publishedTemplates;
    const option = pool.find((item) => item.template_revision_id === templateRevisionId) || pool[0];
    if (!option) {
      return;
    }
    if (option.config) {
      setPreviewTemplate({
        template_id: option.template_id,
        template_revision_id: option.template_revision_id,
        revision_number: option.revision_number,
        config_hash: option.config_hash,
        source: "template_revision",
        config: option.config,
        binding: { template_id: option.template_id, template_revision_id: option.template_revision_id, base_hash: option.config_hash },
      });
    }
    if (templateRevisionId === workspace?.pinned.template_revision_id) return;
    queueOperation({
      op: "template_selection",
      template_revision_id: option.template_revision_id,
      template_id: option.template_id,
      revision_number: option.revision_number,
      config_hash: option.config_hash,
      confirmed: true,
    }, "template_revision_id");

    try {
      await save();
    } catch {
      // optimistic state active
    }
  }

  function confirmTemplateSelection() {
    if (!templateImpact) return;
    const option = publishedTemplates.find((item) => item.template_revision_id === templateImpact.target.template_revision_id);
    if (!option) {
      setTemplateError("That published template is no longer available. Refresh this page.");
      return;
    }
    queueOperation({
      op: "template_selection",
      template_revision_id: option.template_revision_id,
      template_id: option.template_id,
      revision_number: option.revision_number,
      config_hash: option.config_hash,
      confirmed: true,
    }, "template_revision_id");
    setTemplateImpact(null);
    save().catch(() => undefined);
  }

  const productOptions = useMemo(() => {
    const raw = companyWorkspace?.products || [];
    const fields = workspace?.fields;
    const vehicleText = [
      fields?.vehicle_type?.value,
      fields?.vehicle_category?.value,
      fields?.car_model?.value,
      fields?.vehicle_description?.value,
      fields?.product_name?.value,
    ].filter(Boolean).join(" ").toLowerCase();

    const isMotorcycle = /motorcycle|motor\s*cycle|motor|bike|kapcai|scooter/.test(vehicleText);
    const isCommercial = /lorry|truck|commercial|rigid|trailer|tipper|van|bus|prime mover/.test(vehicleText);
    const isCar = !isMotorcycle && !isCommercial;

    if (isCar) {
      const filtered = raw.filter((p) => {
        if (p.id === workspace?.pinned.product_id) return true;
        const name = (p.name || "").toLowerCase();
        if (/motorcycle|motor\s*cycle|bike|lorry|commercial\s*vehicle/.test(name)) return false;
        return true;
      });
      return filtered.length > 0 ? filtered : raw;
    }
    if (isMotorcycle) {
      const filtered = raw.filter((p) => {
        if (p.id === workspace?.pinned.product_id) return true;
        const name = (p.name || "").toLowerCase();
        return /motorcycle|motor\s*cycle|bike|motor/.test(name);
      });
      return filtered.length > 0 ? filtered : raw;
    }
    return raw;
  }, [companyWorkspace, workspace?.fields, workspace?.pinned.product_id]);

  const tierOptions = useMemo(
    () => (companyWorkspace?.tiers || []).filter((tier) => tier.product_id === workspace?.pinned.product_id),
    [companyWorkspace, workspace?.pinned.product_id],
  );

  const companyName = workspace?.pinned_names.company_name;

  const insurerConceptKeys = useMemo(() => {
    const keys = new Set<string>();
    if (companyWorkspace?.catalogs) {
      for (const cat of companyWorkspace.catalogs) {
        for (const off of (cat.offerings || [])) {
          if (off.concept_key) keys.add(String(off.concept_key));
          if (off.concept?.concept_key) keys.add(String(off.concept.concept_key));
          if (off.concept_id) keys.add(String(off.concept_id));
          if (off.concept?.id) keys.add(String(off.concept.id));
        }
      }
    }
    if ((workspace as any)?.catalog_offerings) {
      for (const off of ((workspace as any).catalog_offerings as any[])) {
        if (off.concept_key) keys.add(String(off.concept_key));
        if (off.concept?.concept_key) keys.add(String(off.concept.concept_key));
        if (off.concept_id) keys.add(String(off.concept_id));
      }
    }
    if (workspace?.benefits) {
      for (const b of workspace.benefits) {
        if (b && typeof b === "object") {
          const cKey = (b as any).concept_key;
          const cId = (b as any).concept_id;
          if (cKey && typeof cKey === "string") keys.add(cKey);
          if (cId && typeof cId === "string") keys.add(cId);
        }
      }
    }
    return keys;
  }, [companyWorkspace, workspace]);

  const filteredConcepts = useMemo(() => {
    return globalConcepts.filter((c) => {
      if (modalFilter === "insurer" && !insurerConceptKeys.has(c.concept_key) && !insurerConceptKeys.has(c.id)) return false;
      if (modalFilter === "global" && !GLOBAL_BENEFIT_KEYS.has(c.concept_key)) return false;
      if (modalFilter === "addons" && GLOBAL_BENEFIT_KEYS.has(c.concept_key)) return false;
      if (!globalSearch.trim()) return true;
      const term = globalSearch.toLowerCase();
      return c.label.toLowerCase().includes(term) || c.concept_key.toLowerCase().includes(term);
    });
  }, [globalConcepts, modalFilter, globalSearch, insurerConceptKeys]);

  const conceptAssets = useMemo(() => {
    const map: Record<string, string> = {};
    for (const c of globalConcepts) {
      const url = c.default_asset?.url || (c.default_asset_id ? `/business/assets/${c.default_asset_id}/content?profile=ui` : null);
      if (url) {
        if (c.concept_key) map[c.concept_key] = url;
        if (c.id) map[c.id] = url;
        if (c.label) {
          map[c.label.toLowerCase()] = url;
          map[c.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] = url;
        }
      }
    }
    return map;
  }, [globalConcepts]);

  const previewTemplateAssets = useMemo(() => {
    if (!previewTemplate?.config) return [];
    const list: Array<{ id: string; label: string; url: string }> = Object.entries(previewTemplate.config.assets || {}).map(([key, id]) => ({
      id,
      label: key,
      url: id.includes("-") ? `/business/assets/${id}/content?profile=ui` : `/template-assets/${id}`,
    }));
    for (const el of previewTemplate.config.canvas?.elements || []) {
      if (el.assetId && !list.some((a) => a.id === el.assetId)) {
        list.push({
          id: el.assetId,
          label: el.name || "Asset",
          url: el.assetId.includes("-") ? `/business/assets/${el.assetId}/content?profile=ui` : `/template-assets/${el.assetId}`,
        });
      }
    }
    return list;
  }, [previewTemplate]);

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
    const effectiveCompany = formValues["insurance_company"] || fields["insurance_company"] || companyName || workspace?.pinned_names?.company_name || "";
    if (effectiveCompany) {
      fields["insurance_company"] = effectiveCompany;
      fields["insurance_name"] = effectiveCompany;
      fields["company_name"] = effectiveCompany;
      fields["insurer_name"] = effectiveCompany;
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
    let rtax = formValues["roadtax"] || fields["roadtax"] || formValues["road_tax_amount"] || fields["road_tax_amount"] || "";
    if (!rtax || rtax === "0" || rtax === "0.00") {
      const ccStr = formValues["engine_cc"] || fields["engine_cc"] || "";
      const parsedCC = ccStr ? parseInt(String(ccStr).replace(/[^0-9]/g, ""), 10) : 0;
      if (parsedCC > 0) {
        const vtype = formValues["vehicle_type"] || fields["vehicle_type"] || "Car";
        const isCompany = String(vtype).toLowerCase().includes("company") || String(vtype).toLowerCase().includes("corp");
        const baseType = String(vtype).toLowerCase().includes("motor") ? "Motorcycle" : (String(vtype).toLowerCase().includes("lorry") || String(vtype).toLowerCase().includes("other")) ? "Lorry" : "Car";
        const computedRT = computeMalaysianRoadTax(parsedCC, baseType, isCompany ? "Company" : "Individual");
        if (computedRT > 0) {
          rtax = computedRT.toFixed(2);
        }
      }
    }
    if (rtax) {
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
    const rtNum = parseFloat(String(fields["roadtax"] || "").replace(/[^0-9.]/g, "")) || 0;
    const sfNum = parseFloat(String(fields["service_fee"] || "").replace(/[^0-9.]/g, "")) || 0;
    const extrasTotal = (workspace?.extras || []).reduce((acc, ex) => {
      const amt = (ex as Record<string, unknown>)?.price;
      const val = typeof amt === "object" && amt !== null ? ((amt as Record<string, unknown>).amount ?? (amt as Record<string, unknown>).value) : amt;
      const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : (typeof val === "number" ? val : 0);
      return acc + (Number.isFinite(num) ? num : 0);
    }, 0);

    const calculatedTotal = pNum + extrasTotal + rtNum + sfNum;
    const effTotal = calculatedTotal > 0
      ? calculatedTotal.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : (formValues["total_amount"] || fields["total_amount"] || workspace?.total_premium_adjusted || "");

    const calculatedPremium = pNum + extrasTotal;
    fields["insurance_premium_total"] = calculatedPremium > 0
      ? calculatedPremium.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : "";

    // Validity date aliases
    const vUntil = formValues["valid_until"] || fields["valid_until"] || formValues["quotation_validity"] || fields["quotation_validity"] || "";
    if (vUntil) {
      fields["valid_until"] = vUntil;
      fields["quotation_validity"] = vUntil;
    }

    fields["total_amount"] = effTotal;
    fields["total_premium_adjusted"] = effTotal;
    return fields;
  }, [workspace?.fields, workspace?.total_premium_adjusted, workspace?.extras, workspace?.pinned_names?.company_name, formValues, companyName]);

  function commitField(field: FormField) {
    const current = formValues[field.name];
    if (current === undefined || current.trim() === "") return;
    if (field.kind === "total") return;
    decideField(field.name, "edit", current);

    if (field.name === "sum_insured") {
      decideField("coverage_amount", "edit", current);
      decideField("market_value", "edit", current);
    }

    if (field.name === "insurance_company") {
      const match = companies.find(
        (c) => c.name.toLowerCase().trim() === current.toLowerCase().trim()
      );
      if (match && match.id !== workspace?.pinned.company_id) {
        pinCatalog(match.id);
      }
    }
  }

  function commitFieldDirectly(name: string, value: string) {
    if (value === undefined || value.trim() === "") return;
    decideField(name, "edit", value);
    if (name === "sum_insured") {
      decideField("coverage_amount", "edit", value);
      decideField("market_value", "edit", value);
    }
    if (name === "insurance_company") {
      const match = companies.find(
        (c) => c.name.toLowerCase().trim() === value.toLowerCase().trim()
      );
      if (match && match.id !== workspace?.pinned.company_id) {
        pinCatalog(match.id);
      }
    }
  }

  async function pinCatalog(companyId: string, productId?: string | null, tierId?: string | null) {
    setPinLoading(true);
    const company = companies.find((item) => item.id === companyId);
    const product = productId ? productOptions.find((item) => item.id === productId) : null;
    const tier = tierId ? tierOptions.find((item) => item.id === tierId) : null;

    if (company) {
      setFormValues((prev) => ({
        ...prev,
        insurance_company: company.name,
      }));
    }

    onQueue({
      op: "pin_catalog",
      company_id: companyId,
      ...(productId ? { product_id: productId } : {}),
      ...(tierId ? { tier_id: tierId } : {}),
      company_name: company?.name || workspace?.pinned_names.company_name,
      ...(product ? { product_name: product.name } : {}),
      ...(tier ? { tier_name: tier.name } : {}),
    }, "catalog");

    try {
      await save();
    } catch {
      // Best effort
    } finally {
      setPinLoading(false);
    }
  }

  // Pin a specific package tier (package-system insurers) by its package_id.
  async function pinPackageTier(packageId: string) {
    if (!workspace?.pinned.company_id) return;
    setPinLoading(true);
    onQueue({
      op: "select_package_tier",
      package_id: packageId,
    }, "package_tier");
    try {
      await save();
    } catch {
      // Best effort
    } finally {
      setPinLoading(false);
    }
  }

  function addConceptAsBenefit(
    concept: GlobalConcept,
    state: "current" | "available_addon" = "current",
    price?: { amount: number; currency: string } | null,
    coverageLimit?: string | null
  ) {
    const key = `concept:${concept.concept_key}:${crypto.randomUUID().slice(0, 8)}`;
    const costStatus = price ? "paid" : state === "current" ? "included" : "paid";
    const cleanLimit = coverageLimit && typeof coverageLimit === "string" && !coverageLimit.includes("[object") ? coverageLimit.trim() : "";
    const typedValue = cleanLimit
      ? { type: "custom", display_text: cleanLimit.startsWith("RM") ? cleanLimit : `RM ${cleanLimit}` }
      : { type: "custom", display_text: concept.label };
    const op = {
      op: "create_custom_benefit",
      selection_key: key,
      concept_id: concept.id,
      concept_key: concept.concept_key,
      label: concept.label,
      typed_value: typedValue,
      cost_status: costStatus,
      state,
      price: price || null,
    };
    onQueue(op, `benefits.${key}`);
    setRedoStack([]);
    setShowGlobalModal(false);
  }

  // Reset all benefits back to company defaults and detected extraction items (idempotent)
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
      // Undo a custom benefit by removing it via its selection_key (not a UUID selection_id)
      queueOperation({ op: "benefit_update", selection_id: (last.op as any).selection_key, state: "removed" }, last.path);
    } else if (last.op.op === "select_catalog_offering" && last.op.offering_id) {
      queueOperation({ op: "select_catalog_offering", offering_id: last.op.offering_id, state: "removed", cost_status: "included" }, last.path);
    } else {
      queueOperation({ op: "reset_benefits" }, "benefits");
    }
    try {
      scheduleSave();
      setToastMessage("Undid benefit change.");
    } catch {}
  }, [undoStack, queueOperation, scheduleSave]);

  const handleRedo = useCallback(async () => {
    if (!redoStack.length) return;
    const next = redoStack[redoStack.length - 1];
    setRedoStack((prev) => prev.slice(0, -1));
    setUndoStack((prev) => [...prev, next]);
    queueOperation(next.op, next.path);
    try {
      scheduleSave();
      setToastMessage("Redid benefit change.");
    } catch {}
  }, [redoStack, queueOperation, scheduleSave]);

  function addCustomBenefit(targetState: "current" | "available_addon" = "current") {
    const label = customLabel.trim();
    if (!label) return;
    const isAddon = targetState === "available_addon";
    const key = `custom:${crypto.randomUUID()}`;
    const priceText = customPrice.trim();
    const price = priceText
      ? { amount: priceText.replace(/,/g, ""), currency: "MYR" }
      : undefined;
    const costStatus = price ? "paid" : isAddon ? "paid" : "included";
    const op = {
      op: "create_custom_benefit",
      selection_key: key,
      label,
      typed_value: customValue.trim() ? { type: "custom", display_text: customValue.trim() } : { type: "custom", display_text: label },
      cost_status: costStatus,
      state: targetState,
      ...(price ? { price } : {}),
    };
    queueOperation(op, `benefits.${key}`);
    setUndoStack((prev) => [...prev, { op, path: `benefits.${key}`, desc: `Added ${label}` }]);
    setRedoStack([]);
    setCustomLabel("");
    setCustomValue("");
    setCustomPrice("");
    scheduleSave();
  }

  // ── Benefit Pack (bundle plan) actions ─────────────────────────────────
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

  async function generateCanvasBlob(): Promise<Blob | null> {
    const live = document.getElementById("rl-live-canvas-inner");
    if (!live || !previewTemplate) return null;

    const width = previewTemplate.config.canvas?.width || 794;
    const height = canvasH;

    return await toBlob(live, {
      cacheBust: false,
      backgroundColor: "#ffffff",
      width,
      height,
      pixelRatio: 2.5,
      skipFonts: false,
      style: {
        transform: "none",
        transformOrigin: "top left",
        width: `${width}px`,
        height: `${height}px`,
        margin: "0",
        position: "static",
      },
    });
  }

  function triggerDownload(url: string, filename: string) {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function handleCopyPng() {
    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before copying PNG, proceeding with live canvas:", err);
      }
    }
    setCopyingPng(true);
    setActionError(null);
    try {
      const blob = await generateCanvasBlob();
      if (!blob) throw new Error("Could not capture quotation template canvas.");

      if (typeof ClipboardItem !== "undefined" && navigator.clipboard && typeof navigator.clipboard.write === "function") {
        await navigator.clipboard.write([
          new ClipboardItem({ "image/png": blob }),
        ]);
        setCopiedPng(true);
        setToastMessage("High-definition quotation PNG copied to clipboard!");
        setTimeout(() => setCopiedPng(false), 2500);
        return;
      }

      const url = URL.createObjectURL(blob);
      triggerDownload(url, `quotation_${formValues.vehicle_no || id}.png`);
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setToastMessage("Quotation PNG downloaded (clipboard was restricted by browser).");
    } catch (err: unknown) {
      console.error("[handleCopyPng error]", err);
      setActionError("Could not export quotation PNG: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setCopyingPng(false);
    }
  }

  async function handleDownloadPng() {
    if (mutation.dirty) {
      try {
        await save();
      } catch (err) {
        console.warn("Could not save workspace before downloading PNG, proceeding with live canvas:", err);
      }
    }
    setDownloadingPng(true);
    setActionError(null);
    try {
      const blob = await generateCanvasBlob();
      if (!blob) throw new Error("Could not generate quotation image blob");
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      triggerDownload(url, `quotation_${formValues.vehicle_no || id}.png`);
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      setToastMessage("High-definition quotation PNG opened in new tab and downloaded!");
    } catch (err: unknown) {
      console.error("[handleDownloadPng error]", err);
      setActionError("Could not generate PNG for download: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setDownloadingPng(false);
    }
  }

  async function handleDownloadPdf() {
    if (!workspace) return;
    setPdfLoading(true);
    setActionError(null);

    // Auto-confirm all non-empty fields in formValues and clear empty fields so all fields have an explicit scalar decision
    let queuedAny = false;
    for (const field of FORM_FIELDS) {
      const decision = workspace.fields[field.name]?.decision?.decision;
      if (!decision) {
        const val = formValues[field.name];
        if (val && String(val).trim()) {
          decideField(field.name, "edit", String(val).trim());
        } else {
          decideField(field.name, "clear", null);
        }
        queuedAny = true;
      }
    }

    let currentRevision = workspace.revision;
    if (mutation.dirty || queuedAny) {
      try {
        const saved = await save();
        currentRevision = saved.revision;
      } catch (err) {
        setActionError("Please resolve errors before downloading PDF: " + apiErrorMessage(err));
        setPdfLoading(false);
        return;
      }
    } else {
      try {
        const latest = await api<{ revision: number }>(`/sessions/${id}/workspace`);
        currentRevision = latest.revision;
      } catch (e) {}
    }
    if (currentRevision == null) {
      setPdfLoading(false);
      return;
    }

    try {
      const nonFatalBlockers = (workspace.generation_blockers || []).filter(
        (b) => b.code !== "scalar_check_needed" && b.code !== "missing_catalog"
      );
      if (nonFatalBlockers.length > 0) {
        throw new Error(nonFatalBlockers[0].message || "Resolve generation blockers before creating the PDF.");
      }

      const requested = await api<{ job?: { id: string }; version?: { id: string } }>(
        `/sessions/${id}/versions`,
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ draft_revision: currentRevision }),
        }
      );

      let versionId = requested.version?.id;
      const jobId = requested.job?.id;
      if (!versionId && jobId) {
        for (let attempt = 0; attempt < 40; attempt += 1) {
          const status = await api<{ job: { state: string; result?: { version_id?: string }; error?: { message?: string } } }>(`/jobs/${jobId}`);
          if (status.job.state === "completed") {
            versionId = status.job.result?.version_id;
            break;
          }
          if (status.job.state === "failed" || status.job.state === "cancelled") {
            throw new Error(status.job.error?.message || "PDF generation did not complete.");
          }
          await new Promise((resolve) => window.setTimeout(resolve, 800));
        }
      }

      if (versionId) {
        await reload();
        const viewUrl = fileUrl(`/versions/${versionId}/pdf`);
        const downloadUrl = fileUrl(`/versions/${versionId}/pdf?download=true`);
        window.open(viewUrl, "_blank");
        triggerDownload(downloadUrl, `quotation_${formValues.vehicle_no || id}.pdf`);
        setToastMessage("Official PDF opened in new tab and downloaded!");
        return;
      }
    } catch (backendError) {
      setActionError("PDF generation failed: " + apiErrorMessage(backendError) + " — Please try again or contact support.");
      setPdfLoading(false);
      return;
    }

    // If we reach here without a versionId, something unexpected happened
    setActionError("PDF generation did not return a version. Please try again.");
    setPdfLoading(false);
  }

  if (loading) return <PageLoading />;
  if (loadError || !workspace) {
    return (
      <Card className="grid gap-3 p-6" role="alert">
        <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Could not load quotation</h1>
        <p className="text-sm text-[var(--rl-text)]">{loadError || "The quotation workspace is unavailable."}</p>
        <Button className="w-fit" onClick={() => reload().catch(() => undefined)}>Retry</Button>
      </Card>
    );
  }

  const currentCards = workspace.benefit_cards.current_benefits;
  const addonCards = workspace.benefit_cards.available_addons;

  return (
    <section className="grid gap-4 max-w-7xl mx-auto pb-12">
      {/* Top Header Bar */}
      <Card className="sticky top-[68px] z-20 p-4 border border-[var(--rl-border)] bg-[var(--rl-surface)]/95 backdrop-blur-md shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Quotation Workspace</h1>
              {companyName ? <Badge variant="default">{companyName}</Badge> : null}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <StatusBadge status={workspace.status} />
              {mutation.dirty ? <Badge variant="warning">Unsaved changes</Badge> : <Badge variant="success">Saved</Badge>}
              <span className="text-xs text-[var(--rl-text-muted)] font-mono">
                {formValues.vehicle_no || "Draft"} · {formValues.customer_name || "Client"}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <GuidedTour
              storageKey="tour:session-workspace"
              title="Quotation Workspace"
              description="Review the AI-extracted values, pin the insurer catalog (and package tier), manage benefits and add-ons, preview the quotation live, and generate the official PDF."
              steps={[
                { target: ".rl-tour-template", title: "Master template & catalog", body: "Pin the published template, the insurer catalog, and (for package-system insurers) the package tier. Switching a tier re-pins that catalog's benefits." },
                { target: ".rl-tour-fields", title: "Extracted values", body: "AI-extracted policy and vehicle values. Review each — anything uncertain is marked 'Check value'. You can edit and confirm them here." },
                { target: ".rl-tour-benefits", title: "Benefits & add-ons", body: "Defaults are the included covers; add-ons are payable extras. Add a Benefit Pack (e.g. Driver Protection Pack) to add several benefits at once and upgrade existing ones in place." },
                { target: ".rl-tour-preview", title: "Live preview", body: "Real-time preview of the quotation on the pinned template. Export as PNG or generate the official PDF from here." },
              ]}
            />
            <Button
              variant="secondary"
              size="sm"
              icon={pdfOpen ? <CaretLeft weight="bold" /> : <FilePdf weight="bold" />}
              onClick={() => setPdfOpen((v) => !v)}
            >
              {pdfOpen ? "Hide PDF" : "Show source PDF"}
            </Button>
            <Button
              variant={mutation.dirty ? "primary" : "secondary"}
              loading={mutation.saving}
              icon={<FloppyDisk weight="bold" />}
              onClick={() => saveAndCheckLearning()}
            >
              {mutation.dirty ? "Save Changes" : "Saved"}
            </Button>

            {/* PNG Actions Button (Copy as PNG | Download PNG) */}
            {/* Unified Action 1: Copy as PNG */}
            <Button
              variant="secondary"
              size="sm"
              icon={copiedPng ? <Check weight="bold" className="text-emerald-600" /> : <Copy weight="bold" />}
              onClick={handleCopyPng}
              disabled={copyingPng}
              title={mutation.dirty ? "Save changes first to copy PNG" : "Copy high-resolution quotation PNG to clipboard"}
            >
              {copiedPng ? "Copied PNG!" : copyingPng ? "Copying..." : "Copy as PNG"}
            </Button>

            {/* Unified Action 2: Download as PNG */}
            <Button
              variant="secondary"
              size="sm"
              icon={<DownloadSimple weight="bold" />}
              onClick={handleDownloadPng}
              disabled={downloadingPng}
              title={mutation.dirty ? "Save changes first to download PNG" : "Open in new tab and download high-resolution PNG"}
            >
              {downloadingPng ? "Generating..." : "Download as PNG"}
            </Button>

            {/* Unified Action 3: Download PDF */}
            <Button
              variant="primary"
              size="sm"
              icon={<FilePdf weight="bold" />}
              onClick={handleDownloadPdf}
              disabled={pdfLoading}
              title={mutation.dirty ? "Save changes first to download PDF" : "Open in new tab and download official PDF"}
            >
              {pdfLoading ? "Generating..." : "Download PDF"}
            </Button>
          </div>
        </div>
      </Card>

      {actionError || mutation.saveError ? (
        <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-3 text-sm font-semibold text-[var(--rl-red)]">
          {actionError || mutation.saveError}
        </div>
      ) : null}

      {learnPrompt ? (
        <Card role="status" className="flex flex-wrap items-center justify-between gap-3 border-amber-300 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-[var(--rl-text-strong)]">
            Save &quot;{learnPrompt.value}&quot; to the {learnPrompt.field === "car_brand" ? "vehicle make" : "vehicle model"} dataset?
          </p>
          <div className="flex gap-2">
            <Button size="sm" onClick={learnValue}>Yes, add it</Button>
            <Button variant="secondary" size="sm" onClick={() => setLearnPrompt(null)}>No</Button>
          </div>
        </Card>
      ) : null}

      {/* 3-Column Resizable Workspace with Draggable Flexbox Sliders */}
      <div
        ref={containerRef}
        className="flex flex-col lg:flex-row items-stretch min-h-[580px] w-full gap-0 select-none relative"
      >
        {/* Column 1 (Optional): Source Quotation PDF */}
        {pdfOpen ? (
          <>
            <div
              style={{ width: isDesktop ? `${colSizes.pdf}%` : "100%" }}
              className="w-full lg:w-auto min-w-0 flex-shrink-0 relative overflow-hidden pr-0 lg:pr-1"
            >
              <div className="relative min-w-0 h-full">
                <Card className="sticky top-[140px] h-[calc(100vh-180px)] p-2">
                  <div className="flex items-center justify-between px-1 pb-1.5 border-b border-[var(--rl-border)] mb-1">
                    <span className="text-xs font-bold text-[var(--rl-text-strong)]">Source Quotation PDF</span>
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-6 px-2 text-[11px] gap-1"
                      onClick={() => {
                        const srcUrl = fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`);
                        window.open(srcUrl, "_blank");
                        triggerDownload(srcUrl, `source_quotation_${formValues.vehicle_no || id}.pdf`);
                      }}
                      title="Open source PDF in new tab and download"
                    >
                      <DownloadSimple size={12} weight="bold" />
                      Download Source PDF
                    </Button>
                  </div>
                  <iframe
                    title="Source quotation PDF"
                    src={fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`)}
                    className={`h-[calc(100%-32px)] w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white ${isDragging ? "pointer-events-none" : ""}`}
                  />
                </Card>
              </div>
            </div>
            {/* Draggable Slider 1 (between PDF and Form) */}
            <div
              onPointerDown={handlePointerDown("pdf")}
              role="separator"
              aria-orientation="vertical"
              className="group w-3.5 -mx-1 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex"
            >
              <div className={`w-1 h-full rounded-full transition-colors ${isDragging === "pdf" ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"}`} />
            </div>
          </>
        ) : null}

        {/* Column 2: Master Template + Extracted Values */}
        <div
          style={{ width: isDesktop ? (pdfOpen ? `${colSizes.middle}%` : `${split2Col}%`) : "100%" }}
          className="w-full lg:w-auto min-w-0 flex-shrink-0 px-0 lg:px-2"
        >
          <section aria-label="Template configuration and extracted values" className="grid grid-cols-1 gap-4 content-start">
            {/* Hierarchy & Quotation Context Overview Bar */}
            <div className="flex flex-wrap items-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2.5 text-xs shadow-xs">
              <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                <span className="text-[var(--rl-text-muted)] text-[11px]">Insurer:</span>
                <span className="rounded bg-gray-100 px-2 py-0.5 font-bold text-gray-900 border border-gray-200">
                  {workspace.hierarchy?.company_name || companyName || "Etiqa"}
                </span>
              </div>
              <div className="h-3 w-px bg-[var(--rl-border)]" />
              <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                <span className="text-[var(--rl-text-muted)] text-[11px]">Vehicle:</span>
                <span className="rounded bg-blue-50 px-2 py-0.5 font-bold text-blue-700 border border-blue-200">
                  {workspace.hierarchy?.vehicle_category || (formValues.vehicle_type || "Private Car")}
                </span>
              </div>
              <div className="h-3 w-px bg-[var(--rl-border)]" />
              <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                <span className="text-[var(--rl-text-muted)] text-[11px]">Usage:</span>
                <span className="rounded bg-emerald-50 px-2 py-0.5 font-bold text-emerald-700 border border-emerald-200">
                  {workspace.hierarchy?.segment || "Private"}
                </span>
              </div>
              <div className="h-3 w-px bg-[var(--rl-border)]" />
              <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                <span className="text-[var(--rl-text-muted)] text-[11px]">Coverage:</span>
                <span className="rounded bg-purple-50 px-2 py-0.5 font-bold text-purple-700 border border-purple-200">
                  {workspace.hierarchy?.coverage_type || (formValues.coverage_type || "Comprehensive")}
                </span>
              </div>
              <div className="h-3 w-px bg-[var(--rl-border)]" />
              <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)] min-w-0">
                <span className="text-[var(--rl-text-muted)] text-[11px]">Model:</span>
                <strong className="truncate font-bold text-gray-900">{formValues.car_model || workspace.hierarchy?.car_model || "—"}</strong>
              </div>
            </div>

            {/* Row 1: Master Template Selection */}
            <Card className="rl-tour-template grid gap-3 p-4 border border-[var(--rl-border)] bg-white shadow-xs">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Master template</h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">Pins the exact published revision used for rendering.</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="default">Published</Badge>
                  <button
                    type="button"
                    onClick={() => setTemplateCollapsed((v) => !v)}
                    className="flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
                    title={templateCollapsed ? "Expand Master Template" : "Collapse Master Template"}
                  >
                    {templateCollapsed ? <CaretDown size={14} weight="bold" /> : <CaretUp size={14} weight="bold" />}
                    <span>{templateCollapsed ? "Expand" : "Collapse"}</span>
                  </button>
                </div>
              </div>

              {templateCollapsed ? (
                <div className="flex flex-wrap items-center justify-between text-xs text-[var(--rl-text-muted)] pt-2 border-t border-[var(--rl-border)]">
                  <span>Template: <strong className="text-[var(--rl-text-strong)] font-semibold">{publishedTemplates.find((t) => t.template_revision_id === workspace.pinned.template_revision_id)?.name || "Master Template"}</strong></span>
                  <span>Insurer: <strong className="text-[var(--rl-text-strong)] font-semibold">{companyName || "Standard Motor"}</strong></span>
                </div>
              ) : (
                <>
                  <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
                    Published template revision
                    <Select
                      value={workspace.pinned.template_revision_id || (publishedTemplates[0]?.template_revision_id ?? "")}
                      disabled={templatesLoading || !publishedTemplates.length}
                      onChange={(event) => selectTemplateDirectly(event.target.value)}
                    >
                      {publishedTemplates.map((option) => (
                        <option key={option.template_revision_id} value={option.template_revision_id}>
                          {option.name} · r{option.revision_number} · {option.page_profile.name}
                        </option>
                      ))}
                    </Select>
                  </label>

                  {templateError ? <p role="alert" className="text-xs font-semibold text-[var(--rl-red)]">{templateError}</p> : null}

                  {templateImpact ? (
                    <div className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 p-3">
                      <p className="text-sm font-bold text-[var(--rl-text-strong)]">Change to {templateImpact.target.name} revision {templateImpact.target.revision_number}?</p>
                      {templateImpact.messages.map((message) => <p key={message} className="text-xs font-semibold text-amber-800">{message}</p>)}
                      <div className="flex flex-wrap gap-2 pt-1">
                        <Button size="sm" onClick={confirmTemplateSelection}>Confirm template change</Button>
                        <Button variant="secondary" size="sm" onClick={() => setTemplateImpact(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : null}

                  {/* Insurer / Product Context Selectors */}
                  <div className="grid grid-cols-2 gap-2 pt-1 border-t border-[var(--rl-border)]">
                    <label className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                      Insurer catalog
                      <Select
                        value={workspace.pinned.company_id || ""}
                        disabled={pinLoading || !companies.length}
                        onChange={(event) => pinCatalog(event.target.value)}
                      >
                        <option value="">Choose insurer</option>
                        {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                      </Select>
                    </label>

                    <label className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                      Product / Package
                      <Select
                        value={workspace.pinned.product_id || ""}
                        disabled={pinLoading || !productOptions.length}
                        onChange={(event) => pinCatalog(workspace.pinned.company_id as string, event.target.value)}
                      >
                        <option value="">{productOptions.length ? "Choose package" : "Standard Motor"}</option>
                        {productOptions.map((product) => {
                          const rawName = product.name || "";
                          let label = rawName;
                          if (!/\((Comprehensive|TPFT|TPO|Third Party)\)/i.test(rawName)) {
                            const lowerName = rawName.toLowerCase();
                            let covLabel = "Comprehensive";
                            if (lowerName.includes("tpft") || (lowerName.includes("third party") && lowerName.includes("fire"))) {
                              covLabel = "TPFT";
                            } else if (lowerName.includes("third") || lowerName.includes("tpo") || lowerName.includes("party")) {
                              covLabel = "TPO";
                            }
                            label = `${rawName} (${covLabel})`;
                          }
                          return (
                            <option key={product.id} value={product.id}>
                              {label}
                            </option>
                          );
                        })}
                      </Select>
                    </label>
                  </div>

                  {/* Package Tier Ladder (package-system insurers) */}
                  {workspace.package_tiers.length > 1 ? (
                    <div className="grid gap-2 pt-1 border-t border-[var(--rl-border)]">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          Package tier
                        </span>
                        <span className="text-[10px] text-[var(--rl-text-muted)]">
                          {workspace.package_tiers.length} tiers · click to switch
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        {workspace.package_tiers.map((tier, idx) => {
                          const active = tier.is_current;
                          const isTop = idx === workspace.package_tiers.length - 1;
                          return (
                            <button
                              key={tier.package_id}
                              type="button"
                              disabled={pinLoading}
                              onClick={() => pinPackageTier(tier.package_id)}
                              className={`flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-2.5 text-left transition-all ${active
                                  ? "border-[var(--rl-black)] bg-[var(--rl-bg)] shadow-sm ring-1 ring-[var(--rl-black)]"
                                  : "border-[var(--rl-border)] bg-white hover:border-[var(--rl-text-muted)]"
                                }`}
                            >
                              <div className="flex items-center justify-between gap-1">
                                <span className="rounded-[4px] bg-[var(--rl-surface)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[9px] font-bold text-[var(--rl-text-muted)]">
                                  Tier {idx + 1} {isTop ? "· Top" : ""}
                                </span>
                                {active ? (
                                  <span className="flex items-center gap-0.5 text-[10px] font-bold text-[var(--rl-black)]">
                                    <Check size={11} weight="bold" /> Active
                                  </span>
                                ) : null}
                              </div>
                              <span className="mt-1.5 text-[11px] font-bold leading-tight text-[var(--rl-text-strong)]">
                                {tier.name}
                              </span>
                              <span className="mt-1 text-[10px] text-[var(--rl-text-muted)]">
                                {tier.defaults_count} defaults · {tier.addons_count} add-ons
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}

                  {/* Benefits Card Template Switcher */}
                  <div className="grid gap-2 pt-2 border-t border-[var(--rl-border)]">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                        <Sparkle size={13} className="text-[var(--rl-red)]" weight="fill" />
                        Benefits Card Template
                      </label>
                      <span className="text-[11px] text-[var(--rl-text-muted)] font-medium">
                        {SYSTEM_BENEFIT_PRESETS.find((p) => p.id === selectedBenefitPreset)?.name || "Masonry Flow"}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                      {SYSTEM_BENEFIT_PRESETS.map((preset) => {
                        const isSelected = selectedBenefitPreset === preset.id;
                        return (
                          <button
                            key={preset.id}
                            type="button"
                            onClick={() => handleSelectBenefitPreset(preset.id)}
                            title={preset.description}
                            className={`flex flex-col items-start rounded-[var(--rl-radius-sm)] border p-2 text-left transition-all ${
                              isSelected
                                ? "border-[var(--rl-red)] bg-red-50/70 shadow-xs ring-1 ring-[var(--rl-red)]/30"
                                : "border-[var(--rl-border)] bg-white hover:border-gray-300 hover:bg-gray-50/80"
                            }`}
                          >
                            <span className={`text-[11px] font-bold leading-tight ${isSelected ? "text-[var(--rl-red)]" : "text-[var(--rl-text-strong)]"}`}>
                              {preset.shortName}
                            </span>
                            <span className="text-[9.5px] text-[var(--rl-text-muted)] mt-0.5 leading-snug line-clamp-2">
                              {preset.description}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </>
              )}
            </Card>

            {/* Row 2: Extracted Policy & Vehicle Values */}
            <Card className="rl-tour-fields grid gap-3 p-4 border border-[var(--rl-border)] bg-white shadow-xs">
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
                    disabled={geminiExtracting}
                    onClick={triggerGeminiExtraction}
                    className="h-7 text-xs font-semibold gap-1.5"
                    title="Run Gemini Multimodal AI extraction to auto-detect customer name, coverage, car model, and benefits"
                  >
                    <Sparkle size={13} weight="fill" className={geminiExtracting ? "animate-spin text-[var(--rl-black)]" : "text-[var(--rl-text-strong)]"} />
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
                  <div><span className="text-[var(--rl-text-muted)]">Plate:</span> <strong className="text-[var(--rl-text-strong)] font-mono">{formValues.vehicle_no || "—"}</strong></div>
                  <div><span className="text-[var(--rl-text-muted)]">Insured:</span> <strong className="text-[var(--rl-text-strong)] truncate max-w-[140px] inline-block align-bottom">{formValues.customer_name || "—"}</strong></div>
                  <div><span className="text-[var(--rl-text-muted)]">TOTAL PAYABLE:</span> <strong className="text-[var(--rl-red)] font-mono font-bold">RM {previewFields["total_amount"] || formValues.total_amount || "0.00"}</strong></div>
                </div>
              ) : (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {FORM_FIELDS.map((field) => {
                      let stored = workspace.fields[field.name] as WorkspaceField | undefined;
                      if (!stored?.value && field.name === "sum_insured") {
                        stored = (workspace.fields["coverage_amount"] as WorkspaceField | undefined) ||
                                 (workspace.fields["market_value"] as WorkspaceField | undefined) ||
                                 (workspace.fields["agreed_value"] as WorkspaceField | undefined);
                      }
                      const empty = !(stored?.value);
                      const needsCheck = !empty && stored?.status === "check_needed";
                      return (
                        <label key={field.name} className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
                          <span className="flex items-center justify-between">
                            {field.label}
                            {needsCheck ? <span className="text-[10px] text-amber-700 font-bold">Check value</span> : null}
                          </span>
                          {field.kind === "vehicle_type" ? (
                            <Select
                              value={formValues[field.name] || "Car"}
                              onChange={(event) => {
                                const newVtype = event.target.value;
                                setFormValues((values) => ({ ...values, [field.name]: newVtype }));
                                commitFieldDirectly(field.name, newVtype);
                                const currentCCStr = formValues["engine_cc"] || (workspace.fields["engine_cc"] as WorkspaceField | undefined)?.value;
                                const parsedCC = currentCCStr ? parseInt(currentCCStr.replace(/[^0-9]/g, ""), 10) : inferCCFromCarModel(formValues["car_model"] || (workspace.fields["car_model"] as WorkspaceField | undefined)?.value);
                                if (parsedCC && parsedCC > 0) {
                                  const isCompany = newVtype.toLowerCase().includes("company") || newVtype.toLowerCase().includes("corp");
                                  const baseType = newVtype.toLowerCase().includes("motor") ? "Motorcycle" : (newVtype.toLowerCase().includes("lorry") || newVtype.toLowerCase().includes("other")) ? "Lorry" : "Car";
                                  const computedRT = computeMalaysianRoadTax(parsedCC, baseType, isCompany ? "Company" : "Individual");
                                  if (computedRT > 0) {
                                    const rtFormatted = computedRT.toFixed(2);
                                    setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
                                    commitFieldDirectly("roadtax", rtFormatted);
                                  }
                                }
                              }}
                              className="text-xs font-medium"
                            >
                              <option value="Car">Car (Private Saloon)</option>
                              <option value="CompanyCar">Car (Company / Corporate Saloon)</option>
                              <option value="Motorcycle">Motorcycle (Private)</option>
                              <option value="CompanyMotorcycle">Motorcycle (Corporate)</option>
                              <option value="Lorry">Lorry / Commercial</option>
                              <option value="Others">Others</option>
                            </Select>
                          ) : (
                            <span className="relative">
                              {field.kind === "money" || field.kind === "total" ? (
                                <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-xs font-bold text-[var(--rl-text-muted)]">
                                  RM
                                </span>
                              ) : null}
                              <Input
                                value={field.kind === "total" ? (previewFields[field.name] || formValues[field.name] || "") : (formValues[field.name] ?? "")}
                                disabled={field.kind === "total"}
                                placeholder={empty ? "Missing" : ""}
                                list={field.name === "insurance_company" ? "company-suggestions" : undefined}
                                className={`${field.kind === "money" || field.kind === "total" ? "pl-8 text-xs font-mono font-medium" : "text-xs font-medium"} ${needsCheck ? "border-amber-400 bg-amber-50/50 ring-1 ring-amber-300" : ""}`}
                                onChange={(event) => setFormValues((values) => ({ ...values, [field.name]: event.target.value }))}
                                onBlur={() => {
                                  commitField(field);
                                  if (field.name === "engine_cc" || field.name === "car_model") {
                                    const currentCCStr = formValues["engine_cc"] || (field.name === "car_model" ? inferCCFromCarModel(formValues["car_model"])?.toString() : null);
                                    const parsedCC = currentCCStr ? parseInt(currentCCStr.replace(/[^0-9]/g, ""), 10) : null;
                                    if (parsedCC && parsedCC > 0) {
                                      if (!formValues["engine_cc"]) {
                                        setFormValues((values) => ({ ...values, engine_cc: `${parsedCC} CC` }));
                                        commitFieldDirectly("engine_cc", `${parsedCC} CC`);
                                      }
                                      const vtype = formValues["vehicle_type"] || "Car";
                                      const isCompany = vtype.toLowerCase().includes("company") || vtype.toLowerCase().includes("corp");
                                      const baseType = vtype.toLowerCase().includes("motor") ? "Motorcycle" : (vtype.toLowerCase().includes("lorry") || vtype.toLowerCase().includes("other")) ? "Lorry" : "Car";
                                      const computedRT = computeMalaysianRoadTax(parsedCC, baseType, isCompany ? "Company" : "Individual");
                                      if (computedRT > 0) {
                                        const rtFormatted = computedRT.toFixed(2);
                                        setFormValues((values) => ({ ...values, roadtax: rtFormatted }));
                                        commitFieldDirectly("roadtax", rtFormatted);
                                      }
                                    }
                                  }
                                }}
                                onKeyDown={(event) => { if (event.key === "Enter") (event.target as HTMLInputElement).blur(); }}
                              />
                            </span>
                          )}
                        </label>
                      );
                    })}
                  </div>
                  <datalist id="company-suggestions">
                    {companies.map((c) => (
                      <option key={c.id} value={c.name} />
                    ))}
                  </datalist>
                  <p className="text-[11px] text-[var(--rl-text-muted)]">Amounts are formatted in RM. Totals compute automatically from premium, road tax, and runner fee.</p>
                </>
              )}
            </Card>

            {/* Card 3: Extracted Benefits, Extras & Packages */}
            <Card className="grid gap-3.5 p-4 border border-[var(--rl-border)] shadow-sm bg-white rounded-xl">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100">
                    <Sparkle size={16} weight="fill" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-[var(--rl-text-strong)] flex items-center gap-2">
                      Extra Benefits
                      {workspace.extracted_benefits_section?.extras?.length ? (
                        <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-bold text-indigo-700 font-mono">
                          {workspace.extracted_benefits_section.extras.length} detected
                        </span>
                      ) : null}
                    </h2>
                    <p className="text-[11px] text-[var(--rl-text-muted)]">
                      Optional covers detected from the uploaded quotation.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {workspace.extracted_benefits_section?.total_optional_cover_amount ? (
                    <span className="rounded-md bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-xs font-bold text-emerald-800 font-mono">
                      Optional Covers: RM {workspace.extracted_benefits_section.total_optional_cover_amount}
                    </span>
                  ) : null}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExtractedBenefitsCollapsed(!extractedBenefitsCollapsed)}
                    className="text-xs h-7 px-2 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  >
                    {extractedBenefitsCollapsed ? "Expand" : "Collapse"}
                  </Button>
                </div>
              </div>

              {!extractedBenefitsCollapsed && (
                <div className="grid gap-3.5">
                  {/* Detected Package / Plan Banner */}
                  {workspace.extracted_benefits_section?.detected_package?.name ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-blue-200 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-600 text-white font-bold text-xs shadow-sm">
                          PRO
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-blue-800">Detected Insurance Package</span>
                            {workspace.extracted_benefits_section.detected_package.is_active_tier ? (
                              <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-bold text-emerald-800">
                                Active Tier
                              </span>
                            ) : null}
                          </div>
                          <p className="text-xs font-bold text-[var(--rl-text-strong)]">
                            {workspace.extracted_benefits_section.detected_package.name}
                          </p>
                        </div>
                      </div>

                      {workspace.extracted_benefits_section.detected_package.matching_package_id &&
                        !workspace.extracted_benefits_section.detected_package.is_active_tier ? (
                        <Button
                          size="sm"
                          variant="primary"
                          disabled={pinLoading}
                          onClick={() => pinPackageTier(workspace.extracted_benefits_section!.detected_package!.matching_package_id!)}
                          className="text-xs font-semibold h-8 bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                        >
                          Switch to this Tier →
                        </Button>
                      ) : null}
                    </div>
                  ) : null}

                  {/* RL-DISABLED raw_evidence_toggle — disabled 2026-08-28; restore when debug evidence tab is needed */}

                  {/* Detected Add-ons List */}
                  <div className="grid gap-2">
                    {workspace.extracted_benefits_section?.extras && workspace.extracted_benefits_section.extras.length > 0 ? (
                      <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 overflow-hidden bg-white shadow-xs">
                        {workspace.extracted_benefits_section.extras.map((extra, idx) => {
                          const hasCost = extra.cost && extra.cost !== "0.00" && extra.cost !== "0";
                          return (
                            <div
                              key={extra.id || idx}
                              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 hover:bg-gray-50/80 transition-colors"
                            >
                              <div className="grid gap-0.5 min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                                    {extra.label}
                                  </span>
                                  {extra.is_applied ? (
                                    <span className="rounded bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700">
                                      ✓ Included in Grid
                                    </span>
                                  ) : (
                                    <span className="rounded bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[9px] font-bold text-amber-700">
                                      Detected in PDF
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-1 sm:pt-0 border-t sm:border-t-0 border-gray-100">
                                {(() => {
                                  const rawLimit = extra.coverage_limit && typeof extra.coverage_limit === "string" && !extra.coverage_limit.includes("[object") ? extra.coverage_limit.trim() : "";
                                  const costNum = extra.cost ? parseFloat(String(extra.cost).replace(/[^0-9.]/g, "")) : null;
                                  const limitNum = rawLimit ? parseFloat(rawLimit.replace(/[^0-9.]/g, "")) : null;
                                  const isGenuine = Boolean(rawLimit && limitNum !== null && limitNum > 0 && (costNum === null || Math.abs(limitNum - costNum) > 0.01));
                                  if (!isGenuine) return null;
                                  return (
                                    <div className="text-right">
                                      <span className="block text-[9px] uppercase font-bold text-[var(--rl-text-muted)]">Limit / Sum</span>
                                      <span className="text-xs font-semibold text-[var(--rl-text-strong)] font-mono">
                                        {rawLimit.startsWith("RM") ? rawLimit : `RM ${rawLimit}`}
                                      </span>
                                    </div>
                                  );
                                })()}

                                {hasCost && extra.cost ? (
                                  <div className="text-right">
                                    <span className="block text-[9px] uppercase font-bold text-[var(--rl-text-muted)]">Cost</span>
                                    <span className="text-xs font-bold text-[var(--rl-red)] font-mono">
                                      {String(extra.cost).startsWith("RM") ? String(extra.cost) : `RM ${extra.cost}`}
                                    </span>
                                  </div>
                                ) : (
                                  <div className="text-right">
                                    <span className="block text-[9px] uppercase font-bold text-[var(--rl-text-muted)]">Cost</span>
                                    <span className="text-[11px] font-medium text-gray-400">Included</span>
                                  </div>
                                )}

                                {!extra.is_applied && extra.concept_key ? (
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => {
                                      const concept = globalConcepts.find((c) => c.concept_key === extra.concept_key);
                                      if (concept) {
                                        const cleanCost = extra.cost ? Number(String(extra.cost).replace(/[^0-9.]/g, "")) : null;
                                        const priceObj = cleanCost && Number.isFinite(cleanCost) ? { amount: cleanCost, currency: "MYR" } : null;
                                        const cleanLimit = extra.coverage_limit && typeof extra.coverage_limit === "string" ? extra.coverage_limit.trim() : null;
                                        addConceptAsBenefit(concept, "available_addon", priceObj, cleanLimit);
                                      }
                                    }}
                                    className="text-[11px] h-7 px-2.5 shrink-0 font-medium"
                                    title="Add this detected cover to optional add-ons list"
                                  >
                                    + Add to add-ons
                                  </Button>
                                ) : null}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-gray-200 p-6 text-center text-xs text-[var(--rl-text-muted)]">
                        No add-ons or optional covers detected yet. Upload an insurance quotation PDF or run Gemini extraction.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Card>
          </section>
        </div>

        {/* Draggable Slider 2 (between Form and Live Preview) */}
        <div
          onPointerDown={handlePointerDown("main")}
          role="separator"
          aria-orientation="vertical"
          className="group w-3.5 -mx-1 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex"
        >
          <div className={`w-1 h-full rounded-full transition-colors ${isDragging === "main" ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"}`} />
        </div>

        {/* Column 3: Live Quotation Preview + Insurer Benefits */}
        <div
          style={{ width: isDesktop ? (pdfOpen ? `${colSizes.right}%` : `${100 - split2Col}%`) : "100%" }}
          className="w-full lg:w-auto min-w-0 flex-1 pl-0 lg:pl-2"
        >
          <section aria-label="Live preview and benefits manager" className="grid grid-cols-1 gap-4 content-start">
            {/* Row 1: Real-time Live Preview Canvas */}
            <Card className="rl-tour-preview grid gap-2.5 p-3.5 border border-[var(--rl-border)] bg-white shadow-xs overflow-hidden">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Live Quotation Preview</h2>
                  <span className="flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    Real-time
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="secondary"
                    className="h-7 px-2 text-[11px] gap-1"
                    onClick={handleDownloadPng}
                    disabled={downloadingPng}
                    title="Download quotation as PNG (opens in new tab & saves)"
                  >
                    <DownloadSimple size={13} weight="bold" />
                    PNG
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="h-7 px-2 text-[11px] gap-1 text-[var(--rl-red)]"
                    onClick={handleDownloadPdf}
                    disabled={pdfLoading}
                    title="Download quotation as PDF (opens in new tab & saves)"
                  >
                    <FilePdf size={13} weight="bold" />
                    PDF
                  </Button>
                  <div className="h-4 w-px bg-[var(--rl-border)] mx-0.5" />
                  {!previewCollapsed ? (
                    <>
                      <button
                        type="button"
                        onClick={() => setPreviewZoom((z) => Math.max(0.25, z - 0.1))}
                        className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100"
                        title="Zoom Out"
                      >
                        <MagnifyingGlassMinus size={16} />
                      </button>
                      <span className="text-[11px] font-mono text-[var(--rl-text-muted)] w-10 text-center">
                        {Math.round(previewZoom * 100)}%
                      </span>
                      <button
                        type="button"
                        onClick={() => setPreviewZoom((z) => Math.min(2.0, z + 0.1))}
                        className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100"
                        title="Zoom In"
                      >
                        <MagnifyingGlassPlus size={16} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setPreviewZoom(0.48)}
                        className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100"
                      >
                        Fit
                      </button>
                      <div className="h-4 w-px bg-[var(--rl-border)] mx-1" />
                      <div className="hidden sm:flex items-center gap-1 bg-gray-100/90 rounded px-1.5 py-0.5 border border-gray-200 text-[10px]">
                        <span className="font-bold text-[var(--rl-text-muted)]">Style:</span>
                        <select
                          value={selectedBenefitPreset}
                          onChange={(e) => handleSelectBenefitPreset(e.target.value)}
                          className="bg-transparent font-semibold text-[var(--rl-text-strong)] cursor-pointer outline-hidden"
                        >
                          {SYSTEM_BENEFIT_PRESETS.map((p) => (
                            <option key={p.id} value={p.id}>{p.shortName}</option>
                          ))}
                        </select>
                      </div>
                      <div className="h-4 w-px bg-[var(--rl-border)] mx-1" />
                      <button
                        type="button"
                        onClick={() => setPreviewExpanded((v) => !v)}
                        className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
                        title={previewExpanded ? "Compress live preview" : "Expand live preview"}
                      >
                        {previewExpanded ? <ArrowsInSimple size={14} weight="bold" /> : <ArrowsOutSimple size={14} weight="bold" />}
                        <span>{previewExpanded ? "Compress" : "Expand"}</span>
                      </button>
                      <div className="h-4 w-px bg-[var(--rl-border)] mx-1" />
                    </>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => setPreviewCollapsed((v) => !v)}
                    className="flex items-center gap-1 rounded px-2 py-1 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
                    title={previewCollapsed ? "Expand live preview canvas" : "Collapse live preview canvas"}
                  >
                    {previewCollapsed ? <CaretDown size={14} weight="bold" /> : <CaretUp size={14} weight="bold" />}
                    <span>{previewCollapsed ? "Expand" : "Collapse"}</span>
                  </button>
                </div>
              </div>

              {previewCollapsed ? (
                <div className="flex items-center justify-center p-3.5 text-xs text-[var(--rl-text-muted)] italic bg-gray-50/70 rounded">
                  Live quotation preview canvas is collapsed. Click Expand to preview document.
                </div>
              ) : (
                /* Canvas Render Container */
                <div className={`flex ${previewExpanded ? "h-[640px]" : "h-[380px]"} w-full items-start justify-center overflow-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/80 p-3 transition-all duration-200`}>
                  {previewLoading && !previewTemplate ? (
                    <div className="flex h-full items-center justify-center text-xs text-[var(--rl-text-muted)]">
                      Loading preview template...
                    </div>
                  ) : previewTemplate ? (
                    <div
                      style={{
                        width: (previewTemplate.config.canvas?.width || 794) * previewZoom,
                        height: canvasH * previewZoom,
                        position: "relative",
                        backgroundColor: "#ffffff",
                        boxShadow: "0 4px 14px rgba(0,0,0,0.08)",
                        borderRadius: "4px",
                        overflow: "hidden",
                        flexShrink: 0,
                      }}
                    >
                      <div
                        id="rl-live-canvas-inner"
                        style={{
                          width: previewTemplate.config.canvas?.width || 794,
                          height: canvasH,
                          transform: `scale(${previewZoom})`,
                          transformOrigin: "top left",
                          position: "relative",
                        }}
                      >
                        {balancedElements.map((element: CanvasElement) => (
                          <CanvasElementView
                            key={element.id}
                            element={element}
                            selected={false}
                            readOnly={true}
                            onPointerDown={() => { }}
                            variableValues={previewFields}
                            benefitData={{ ...workspace.benefit_cards, extras: workspace.extras }}
                            conceptAssets={conceptAssets}
                            assets={previewTemplateAssets}
                          />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-[var(--rl-text-muted)]">
                      Select a template to generate live preview
                    </div>
                  )}
                </div>
              )}
            </Card>

            {/* Row 2: Interactive Benefits & Add-ons Manager with Tabs */}
            <div className="rl-tour-benefits grid gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-card transition-all">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-bold text-[var(--rl-text-strong)]">
                    {companyName ? `${companyName} Benefits & Add-ons` : "Benefits & Add-ons"}
                  </h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Manage policy defaults and payable add-ons with automatic canvas and PDF slot alignment.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {!benefitsCollapsed ? (
                    <div className="flex items-center gap-1 rounded-md border border-[var(--rl-border)] bg-gray-100 p-1">
                      <button
                        type="button"
                        onClick={() => setBenefitsViewMode("defaults")}
                        className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-all ${benefitsViewMode === "defaults"
                          ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                          : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                          }`}
                      >
                        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-800">
                          {currentCards.length}
                        </span>
                        Default / FOC Benefits
                      </button>

                      <button
                        type="button"
                        onClick={() => setBenefitsViewMode("addons")}
                        className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-all ${benefitsViewMode === "addons"
                          ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                          : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                          }`}
                      >
                        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-800">
                          {addonCards.length}
                        </span>
                        Optional Add-ons
                      </button>

                      <button
                        type="button"
                        onClick={() => setBenefitsViewMode("both")}
                        className={`flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-all ${benefitsViewMode === "both"
                          ? "bg-white text-[var(--rl-text-strong)] shadow-xs"
                          : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                          }`}
                      >
                        Side by Side
                      </button>
                    </div>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => setBenefitsCollapsed((v) => !v)}
                    className="flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors"
                    title={benefitsCollapsed ? "Expand Benefits & Add-ons" : "Collapse Benefits & Add-ons"}
                  >
                    {benefitsCollapsed ? <CaretDown size={14} weight="bold" /> : <CaretUp size={14} weight="bold" />}
                    <span>{benefitsCollapsed ? "Expand" : "Collapse"}</span>
                  </button>
                </div>
              </div>

              {benefitsCollapsed ? (
                <div className="flex flex-wrap items-center justify-between text-xs text-[var(--rl-text-muted)] pt-2 border-t border-[var(--rl-border)]">
                  <span>Included / FOC: <strong className="text-emerald-700 font-semibold">{currentCards.length} active</strong></span>
                  <span>Optional Add-ons: <strong className="text-blue-700 font-semibold">{addonCards.length} configured</strong></span>
                </div>
              ) : (
                <>
                  {/* Global Actions Toolbar */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<ArrowCounterClockwise size={14} weight="bold" className="text-amber-600" />}
                        onClick={handleReset}
                        title="Reset to initial insurance defaults and detections"
                      >
                        Reset
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<ArrowArcLeft size={14} weight="bold" />}
                        onClick={handleUndo}
                        disabled={undoStack.length === 0}
                        title="Undo recent benefit change"
                      >
                        Undo
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<ArrowArcRight size={14} weight="bold" />}
                        onClick={handleRedo}
                        disabled={redoStack.length === 0}
                        title="Redo benefit change"
                      >
                        Redo
                      </Button>
                      <span className="text-xs text-[var(--rl-text-muted)]">
                        {currentCards.length} active standard covers
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<Sparkle size={14} weight="bold" className="text-[var(--rl-red)]" />}
                        onClick={() => {
                          setModalTarget("available_addon");
                          setShowGlobalModal(true);
                        }}
                      >
                        + Global Library
                      </Button>
                    </div>
                  </div>

                  {/* Two-Box Interactive Grid Display */}
                  <div className={`grid gap-4 ${benefitsViewMode === "both" ? "lg:grid-cols-2" : "grid-cols-1"}`}>
                    {/* BOX 1: Default / FOC Included Benefits */}
                    {(benefitsViewMode === "defaults" || benefitsViewMode === "both") && (
                      <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/60 p-3 flex flex-col gap-2.5">
                        <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                          <div className="flex items-center gap-1.5">
                            <CheckCircle size={16} weight="fill" className="text-emerald-600" />
                            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                              Included / FOC Benefits
                            </h3>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800">
                              {currentCards.length} standard covers (constant)
                            </span>
                            {/* RL-DISABLED add_to_defaults_button — disabled 2026-08-28; restore when defaults can receive additions */}
                          </div>
                        </div>

                        <div className="grid gap-2 max-h-[380px] overflow-y-auto pr-1">
                          {currentCards.length === 0 ? (
                            <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-[var(--rl-text-muted)]">
                              <p>No included benefits active.</p>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={handleReset}
                                className="mt-2 text-xs"
                              >
                                Reset to insurance defaults
                              </Button>
                            </div>
                          ) : (
                            currentCards.map((card, idx) => {
                              const selection = workspace.benefits.find((item) => item.catalog_offering_id === card.offering_id || item.selection_key === card.card_key);
                              const concept = globalConcepts.find(
                                (c) => c.concept_key === card.concept_key || c.id === card.concept_id || c.label.toLowerCase() === card.label.toLowerCase()
                              );
                              const assetUrl =
                                concept?.default_asset?.url ||
                                (concept?.default_asset_id ? `/business/assets/${concept.default_asset_id}/content?profile=ui` : null) ||
                                (card.asset_id ? `/business/assets/${card.asset_id}/content?profile=ui` : null) ||
                                (card.label ? conceptAssets[card.label.toLowerCase()] || conceptAssets[card.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] : null);
                              return (
                                <IncludedCard
                                  key={card.offering_id || card.card_key || idx}
                                  card={card}
                                  index={idx}
                                  assetUrl={assetUrl}
                                  selection={selection}
                                  canUndo={Boolean(card.branch_key)}
                                  onQueue={onQueue}
                                />
                              );
                            })
                          )}
                        </div>
                      </div>
                    )}

                    {/* BOX 2: Optional Payable Add-ons */}
                    {(benefitsViewMode === "addons" || benefitsViewMode === "both") && (
                      <div className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/60 p-3 flex flex-col gap-2.5">
                        <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-2">
                          <div className="flex items-center gap-1.5">
                            <Lightning size={16} weight="fill" className="text-blue-600" />
                            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                              Optional Add-on Covers
                            </h3>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                              {addonCards.length} available
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                setModalTarget("available_addon");
                                setShowGlobalModal(true);
                              }}
                              className="rounded p-1 text-blue-700 hover:bg-blue-100"
                              title="Add from Global Library to Add-ons"
                            >
                              <Plus size={14} weight="bold" />
                            </button>
                          </div>
                        </div>

                        {workspace.packs.length > 0 ? (
                          <div className="grid gap-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1.5">
                                <PackageIcon size={16} weight="fill" className="text-[var(--rl-red)]" />
                                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--rl-text-strong)]">
                                  Add-on Bundle Packages
                                </h4>
                              </div>
                              <span className="text-[10px] font-bold text-[var(--rl-red)] bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
                                Stack Cards ({workspace.packs.length} bundles)
                              </span>
                            </div>
                            <p className="text-[11px] text-[var(--rl-text-muted)] -mt-1.5">
                              Pre-bundled multi-benefit packs. Choose a plan tier to see included benefits and add to quotation.
                            </p>
                            {workspace.packs.map((pack) => {
                              const activeGroup = workspace.benefit_cards.groups?.find((g) =>
                                pack.plans.some((p) => p.plan_id === g.plan_id)
                              );
                              const selectedPlanId = packPlanSelections[pack.package_id] || pack.plans[0]?.plan_id || "";
                              const selectedPlan = pack.plans.find((p) => p.plan_id === selectedPlanId) || pack.plans[0];
                              return (
                                <div
                                  key={pack.package_id}
                                  className="relative rounded-[var(--rl-radius-sm)] border-2 border-red-200/80 bg-white p-3.5 shadow-sm transition-all hover:border-[var(--rl-red)]/60"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2">
                                    <div className="flex items-center gap-2">
                                      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--rl-red-light)] text-[var(--rl-red)]">
                                        <PackageIcon size={16} weight="bold" />
                                      </div>
                                      <div>
                                        <div className="flex items-center gap-1.5">
                                          <h5 className="text-xs font-bold text-[var(--rl-text-strong)]">{pack.name}</h5>
                                          <span className="rounded bg-gray-100 px-1.5 py-0.2 text-[9px] font-bold text-gray-600 uppercase">
                                            Bundle Stack
                                          </span>
                                        </div>
                                        {activeGroup ? (
                                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700">
                                            <Check size={11} weight="bold" /> Active on Quote ({activeGroup.plan_label})
                                          </span>
                                        ) : null}
                                      </div>
                                    </div>

                                    {activeGroup ? (
                                      <button
                                        type="button"
                                        onClick={() => removePack(activeGroup.plan_id)}
                                        className="rounded border border-red-200 bg-red-50 px-2.5 py-1 text-[11px] font-bold text-[var(--rl-red)] hover:bg-red-100 transition-colors"
                                      >
                                        Remove Bundle
                                      </button>
                                    ) : null}
                                  </div>

                                  {/* Plan Tier Selector Pills */}
                                  <div className="mt-2.5">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">Select Plan Tier:</span>
                                    <div className="mt-1 flex flex-wrap gap-1.5">
                                      {pack.plans.map((plan) => {
                                        const isSelected = plan.plan_id === selectedPlanId;
                                        return (
                                          <button
                                            key={plan.plan_id}
                                            type="button"
                                            onClick={() => setPackPlanSelections((prev) => ({ ...prev, [pack.package_id]: plan.plan_id }))}
                                            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold transition-all ${
                                              isSelected
                                                ? "bg-[var(--rl-red)] text-white shadow-xs"
                                                : "bg-gray-100 text-[var(--rl-text-strong)] hover:bg-gray-200"
                                            }`}
                                          >
                                            <span>{plan.name}</span>
                                          </button>
                                        );
                                      })}
                                    </div>
                                  </div>

                                  {/* Included Member Benefit Boxes Preview */}
                                  {selectedPlan ? (
                                    <div className="mt-3 rounded-lg border border-gray-100 bg-neutral-50/70 p-2.5">
                                      <div className="flex items-center justify-between mb-1.5">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                                          Includes {selectedPlan.members.length} benefits in this tier:
                                        </span>
                                      </div>
                                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                                        {selectedPlan.members.map((m, mIdx) => (
                                          <div
                                            key={m.offering_id || mIdx}
                                            className="flex items-center justify-between gap-1.5 rounded bg-white p-1.5 border border-gray-200/70 text-xs shadow-2xs"
                                          >
                                            <div className="flex items-center gap-1.5 min-w-0">
                                              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-[9px] font-bold text-emerald-800">
                                                ✓
                                              </span>
                                              <span className="truncate font-semibold text-[11px] text-[var(--rl-text-strong)]">
                                                {m.label}
                                              </span>
                                            </div>
                                            {m.typed_value_override && typeof m.typed_value_override.display_text === "string" ? (
                                              <span className="shrink-0 text-[10px] font-mono font-bold text-gray-500">
                                                {String(m.typed_value_override.display_text)}
                                              </span>
                                            ) : null}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  ) : null}

                                  <div className="mt-3 flex items-center justify-end">
                                    <Button
                                      size="sm"
                                      onClick={() => addPack(pack, selectedPlanId)}
                                      disabled={!selectedPlanId}
                                      className="text-xs font-bold h-8 px-4 bg-[var(--rl-red)] hover:bg-red-700 text-white shadow-xs"
                                    >
                                      {activeGroup ? `Switch to ${selectedPlan?.name || "Tier"}` : `Apply ${selectedPlan?.name || "Bundle"} →`}
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : null}

                        <div className="grid gap-2 max-h-[380px] overflow-y-auto pr-1">
                          {addonCards.length === 0 ? (
                            <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-[var(--rl-text-muted)]">
                              <p>No optional add-ons configured for this quotation.</p>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => {
                                  setModalTarget("available_addon");
                                  setShowGlobalModal(true);
                                }}
                                className="mt-2 text-xs"
                              >
                                Browse Global Add-ons
                              </Button>
                            </div>
                          ) : (
                            addonCards.map((card, idx) => {
                              const concept = globalConcepts.find(
                                (c) => c.concept_key === card.concept_key || c.id === card.concept_id || c.label.toLowerCase() === card.label.toLowerCase()
                              );
                              const assetUrl =
                                concept?.default_asset?.url ||
                                (concept?.default_asset_id ? `/business/assets/${concept.default_asset_id}/content?profile=ui` : null) ||
                                (card.asset_id ? `/business/assets/${card.asset_id}/content?profile=ui` : null) ||
                                (card.label ? conceptAssets[card.label.toLowerCase()] || conceptAssets[card.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")] : null);
                              return (
                                <AddonCard
                                  key={card.offering_id || card.card_key || idx}
                                  card={card}
                                  index={idx}
                                  assetUrl={assetUrl}
                                  onQueue={onQueue}
                                />
                              );
                            })
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Quick Custom Benefit Adder Row */}
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[var(--rl-border)]">
                    <div className="flex-1 min-w-[200px]">
                      <Input
                        value={customLabel}
                        placeholder="Type custom benefit name (e.g. Free 24h Car Wash, Special Battery Cover)..."
                        onChange={(e) => setCustomLabel(e.target.value)}
                        className="text-xs font-medium"
                      />
                    </div>
                    <div className="w-36">
                      <Input
                        value={customValue}
                        placeholder="Value (e.g. FOC, RM 500)"
                        onChange={(e) => setCustomValue(e.target.value)}
                        className="text-xs font-medium"
                      />
                    </div>
                    <div className="w-28">
                      <Input
                        value={customPrice}
                        placeholder="Price RM (add-ons)"
                        onChange={(e) => setCustomPrice(e.target.value)}
                        className="text-xs font-medium"
                        title="Optional price shown in the Extras section and added to the total premium"
                      />
                    </div>
                    <Button
                      size="sm"
                      onClick={() => addCustomBenefit("current")}
                      disabled={!customLabel.trim()}
                      className="text-xs"
                    >
                      + Add to Default / FOC
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => addCustomBenefit("available_addon")}
                      disabled={!customLabel.trim()}
                      className="text-xs"
                    >
                      + Add to Add-ons
                    </Button>
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* Global Benefit Library Modal */}
      {showGlobalModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <Card className="flex flex-col max-h-[85vh] w-full max-w-3xl border border-[var(--rl-border)] bg-white shadow-xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] p-4">
              <div>
                <h3 className="text-base font-bold text-[var(--rl-text-strong)]">Global Benefits & Add-ons Library</h3>
                <p className="text-xs text-[var(--rl-text-muted)]">
                  Currently adding to: <strong className="text-[var(--rl-text-strong)]">{modalTarget === "current" ? "Default / FOC Benefits" : "Optional Add-ons"}</strong>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowGlobalModal(false)}
                className="rounded-full p-1 text-[var(--rl-text-muted)] hover:bg-gray-100"
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            {/* Modal Controls: Search & Category Filter */}
            <div className="p-4 border-b border-[var(--rl-border)] bg-gray-50/50 flex flex-wrap items-center justify-between gap-3">
              <div className="relative flex-1 min-w-[220px]">
                <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                <Input
                  value={globalSearch}
                  placeholder="Search benefits (Towing, Windscreen, Flood, CART)..."
                  className="pl-9 text-xs"
                  onChange={(e) => setGlobalSearch(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setModalFilter("insurer")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all ${modalFilter === "insurer" ? "bg-[var(--rl-black)] text-white" : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
                >
                  🏢 {companyName ? `${companyName}` : "This Insurer"} ({globalConcepts.filter((c) => insurerConceptKeys.has(c.concept_key) || insurerConceptKeys.has(c.id)).length})
                </button>
                <button
                  type="button"
                  onClick={() => setModalFilter("all")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all ${modalFilter === "all" ? "bg-[var(--rl-black)] text-white" : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
                >
                  All ({globalConcepts.length})
                </button>
                <button
                  type="button"
                  onClick={() => setModalFilter("global")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all ${modalFilter === "global" ? "bg-[var(--rl-black)] text-white" : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
                >
                  Table 1: Global (14)
                </button>
                <button
                  type="button"
                  onClick={() => setModalFilter("addons")}
                  className={`rounded-md px-2.5 py-1 text-xs font-bold transition-all ${modalFilter === "addons" ? "bg-[var(--rl-black)] text-white" : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"}`}
                >
                  Table 2: Add-ons (18)
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 grid gap-2 sm:grid-cols-2">
              {filteredConcepts.map((concept) => (
                <div
                  key={concept.id}
                  className="group flex items-center justify-between gap-2.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-2.5 transition-all hover:border-[var(--rl-border-strong)] hover:bg-gray-50/70"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md border border-[var(--rl-border)] bg-white p-1">
                      {concept.default_asset?.url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={fileUrl(concept.default_asset.url)} alt={concept.label} className="h-full w-full object-contain" />
                      ) : (
                        <Sparkle size={18} className="text-[var(--rl-text-muted)]" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <h4 className="truncate text-xs font-bold text-[var(--rl-text-strong)]">{concept.label}</h4>
                      <p className="truncate text-[10px] text-[var(--rl-text-muted)] font-mono">{concept.concept_key}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => addConceptAsBenefit(concept, "current")}
                      className="text-[10px] h-7 px-2"
                      title="Add to Default / FOC Benefits"
                    >
                      + Default
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => addConceptAsBenefit(concept, "available_addon")}
                      className="text-[10px] h-7 px-2"
                      title="Add to Optional Add-ons"
                    >
                      + Add-on
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end border-t border-[var(--rl-border)] p-3 bg-gray-50">
              <Button variant="secondary" size="sm" onClick={() => setShowGlobalModal(false)}>
                Close
              </Button>
            </div>
          </Card>
        </div>
      ) : null}



      {/* Floating Action Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 rounded-[var(--rl-radius-sm)] border border-neutral-800 bg-neutral-900/95 px-4 py-3 text-xs font-semibold text-white shadow-2xl backdrop-blur-md transition-all">
          <CheckCircle size={17} weight="fill" className="text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}
    </section>
  );
}
