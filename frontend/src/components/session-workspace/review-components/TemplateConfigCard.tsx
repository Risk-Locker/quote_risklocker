"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import {
  CaretDown,
  CaretUp,
  Check,
  Sparkle,
} from "@phosphor-icons/react";
import type { BenefitCardStyle } from "@/lib/benefit-presets";
import type { WorkspaceSnapshot } from "../types";

export type PublishedTemplateOption = {
  template_id: string;
  template_revision_id: string;
  name: string;
  revision_number: number;
  config_hash: string;
  config?: any;
  page_profile: { name: string; width: number; height: number; unit: string };
  is_default?: boolean;
};

export type TemplateSelectionImpact = {
  current_template_revision_id: string | null;
  target: { template_id: string; template_revision_id: string; revision_number: number; name: string; config_hash: string };
  will_reset_layout_override: boolean;
  requires_confirmation: boolean;
  messages: string[];
};

export interface TemplateConfigCardProps {
  workspace: WorkspaceSnapshot;
  templateCollapsed: boolean;
  setTemplateCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  publishedTemplates: PublishedTemplateOption[];
  selectedRevisionId: string | null;
  templatesLoading: boolean;
  selectTemplateDirectly: (templateRevisionId: string) => void;
  templateError: string | null;
  templateImpact: TemplateSelectionImpact | null;
  confirmTemplateSelection: () => void;
  setTemplateImpact: (impact: TemplateSelectionImpact | null) => void;
  companyName: string | null | undefined;
  companies: Array<{ id: string; name: string }>;
  pinLoading: boolean;
  pinCatalog: (companyId: string, productId?: string | null) => Promise<void>;
  productOptions: Array<{ id: string; name: string }>;
  categorizedProducts: { cars: any[]; motorcycles: any[]; lorries: any[] };
  handlePackageSelect: (productId: string) => void;
  syncHighlight: { field: string; prev: string; next: string; timestamp: number } | null;
  formatProductLabel: (name: string) => string;
  pinPackageTier: (packageId: string) => Promise<void>;
  allBenefitPresets: BenefitCardStyle[];
  selectedBenefitPreset: string;
  handleSelectBenefitPreset: (presetId: string) => void;
  extrasDisplayMode?: "itemized" | "lump_sum" | "none";
  handleExtrasDisplayModeChange?: (mode: "itemized" | "lump_sum" | "none") => void;
  isDesign2?: boolean;
  showDesign2Schedule?: boolean;
  toggleDesign2Schedule?: () => void;
}

export function TemplateConfigCard({
  workspace,
  templateCollapsed,
  setTemplateCollapsed,
  publishedTemplates,
  selectedRevisionId,
  templatesLoading,
  selectTemplateDirectly,
  templateError,
  templateImpact,
  confirmTemplateSelection,
  setTemplateImpact,
  companyName,
  companies,
  pinLoading,
  pinCatalog,
  productOptions,
  categorizedProducts,
  handlePackageSelect,
  syncHighlight,
  formatProductLabel,
  pinPackageTier,
  allBenefitPresets,
  selectedBenefitPreset,
  handleSelectBenefitPreset,
  extrasDisplayMode = "itemized",
  handleExtrasDisplayModeChange,
  isDesign2 = true,
  showDesign2Schedule = false,
  toggleDesign2Schedule,
}: TemplateConfigCardProps) {
  return (
    <Card className="rl-tour-template grid gap-3 p-4">
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
            className="flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
            title={templateCollapsed ? "Expand Master Template" : "Collapse Master Template"}
          >
            {templateCollapsed ? <CaretDown size={14} weight="bold" /> : <CaretUp size={14} weight="bold" />}
            <span>{templateCollapsed ? "Expand" : "Collapse"}</span>
          </button>
        </div>
      </div>

      {templateCollapsed ? (
        <div className="flex flex-wrap items-center justify-between text-xs text-[var(--rl-text-muted)] pt-2 border-t border-[var(--rl-border)]">
          <span>
            Template:{" "}
            <strong className="text-[var(--rl-text-strong)] font-semibold">
              {publishedTemplates.find((t) => t.template_revision_id === (selectedRevisionId || workspace.pinned.template_revision_id))?.name?.replace(/\.r\d+$/, "") || "Master Template"}
            </strong>
            {" · Extras: "}
            <span className="font-semibold text-[var(--rl-text-strong)]">
              {extrasDisplayMode === "lump_sum" ? "Lump Sum" : extrasDisplayMode === "none" ? "Hidden" : "Itemized"}
            </span>
          </span>
          <span>
            Insurer: <strong className="text-[var(--rl-text-strong)] font-semibold">{companyName || "Standard Motor"}</strong>
          </span>
        </div>
      ) : (
        <>
          <label className="grid gap-1.5 text-xs font-semibold text-[var(--rl-text-strong)]">
            Published template revision
            <Select
              value={selectedRevisionId || workspace.pinned.template_revision_id || (publishedTemplates[0]?.template_revision_id ?? "")}
              disabled={templatesLoading || !publishedTemplates.length}
              onChange={(event) => selectTemplateDirectly(event.target.value)}
            >
              {publishedTemplates.map((option) => (
                <option key={option.template_revision_id} value={option.template_revision_id}>
                  {option.name.replace(/\.r\d+$/, "")}
                  {option.is_default ? " (Default)" : ""}
                </option>
              ))}
            </Select>
          </label>

          {/* Extras Display Mode Segmented Control ("Template as Builder") */}
          {handleExtrasDisplayModeChange && (
            <div className="grid gap-1.5 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[var(--rl-text-strong)]">
                  Quotation Extras Breakdown
                </span>
                <span className="text-[10px] text-[var(--rl-text-muted)]">
                  Template as Builder
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1 p-1 bg-neutral-100 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] text-xs">
                <button
                  type="button"
                  onClick={() => handleExtrasDisplayModeChange("itemized")}
                  className={`py-1 px-2 rounded-[var(--rl-radius-xs)] font-medium text-center transition-all cursor-pointer ${
                    (extrasDisplayMode || "itemized") === "itemized"
                      ? "bg-white text-[var(--rl-text-strong)] font-bold shadow-2xs border border-[var(--rl-border)]"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  Itemized
                </button>
                <button
                  type="button"
                  onClick={() => handleExtrasDisplayModeChange("lump_sum")}
                  className={`py-1 px-2 rounded-[var(--rl-radius-xs)] font-medium text-center transition-all cursor-pointer ${
                    extrasDisplayMode === "lump_sum"
                      ? "bg-white text-[var(--rl-text-strong)] font-bold shadow-2xs border border-[var(--rl-border)]"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  Lump Sum
                </button>
                <button
                  type="button"
                  onClick={() => handleExtrasDisplayModeChange("none")}
                  className={`py-1 px-2 rounded-[var(--rl-radius-xs)] font-medium text-center transition-all cursor-pointer ${
                    extrasDisplayMode === "none"
                      ? "bg-white text-[var(--rl-text-strong)] font-bold shadow-2xs border border-[var(--rl-border)]"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                  }`}
                >
                  Hide Extras
                </button>
              </div>
            </div>
          )}

          {templateError ? (
            <p role="alert" className="text-xs font-semibold text-[var(--rl-red)]">
              {templateError}
            </p>
          ) : null}

          {templateImpact ? (
            <div className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 p-3">
              <p className="text-sm font-bold text-[var(--rl-text-strong)]">
                Change to {templateImpact.target.name} revision {templateImpact.target.revision_number}?
              </p>
              {templateImpact.messages.map((message) => (
                <p key={message} className="text-xs font-semibold text-amber-800">
                  {message}
                </p>
              ))}
              <div className="flex flex-wrap gap-2 pt-1">
                <Button size="sm" onClick={confirmTemplateSelection}>
                  Confirm template change
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setTemplateImpact(null)}>
                  Cancel
                </Button>
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
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </Select>
            </label>

            <label className="grid gap-1 text-xs font-semibold text-[var(--rl-text-strong)]">
              <span className="flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <span>Product / Package</span>
                  {pinLoading ? <span className="text-[10px] text-emerald-600 font-normal animate-pulse">(syncing...)</span> : null}
                </span>
                {syncHighlight && syncHighlight.field === "product_package" && Date.now() - syncHighlight.timestamp < 6000 ? (
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 border border-emerald-300 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 shadow-xs animate-pulse">
                    <span className="text-[10px] text-emerald-600 font-bold uppercase tracking-wider">Auto-selected</span>
                    <span className="line-through text-slate-400 font-normal truncate max-w-[110px]" title={syncHighlight.prev}>
                      {syncHighlight.prev}
                    </span>
                    <span className="text-emerald-500 font-bold">→</span>
                    <span className="bg-emerald-100 text-emerald-900 px-1 rounded font-bold truncate max-w-[140px]" title={syncHighlight.next}>
                      {syncHighlight.next}
                    </span>
                  </span>
                ) : null}
              </span>
              <Select
                value={workspace.pinned.product_id || ""}
                disabled={!productOptions.length}
                onChange={(event) => handlePackageSelect(event.target.value)}
                className={`transition-all duration-300 ${
                  syncHighlight && syncHighlight.field === "product_package" && Date.now() - syncHighlight.timestamp < 6000
                    ? "border-emerald-500 ring-2 ring-emerald-300 bg-emerald-50/20"
                    : ""
                }`}
              >
                <option value="">{productOptions.length ? "Choose package" : "Standard Motor"}</option>
                {categorizedProducts.cars.length > 0 ? (
                  <optgroup label="🚗 Cars (Saloon / Sedan / SUV / MPV / Company)">
                    {categorizedProducts.cars.map((product) => (
                      <option key={product.id} value={product.id}>
                        {formatProductLabel(product.name || "")}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
                {categorizedProducts.motorcycles.length > 0 ? (
                  <optgroup label="🏍️ Motorcycles / Bikes">
                    {categorizedProducts.motorcycles.map((product) => (
                      <option key={product.id} value={product.id}>
                        {formatProductLabel(product.name || "")}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
                {categorizedProducts.lorries.length > 0 ? (
                  <optgroup label="🚛 Commercial Vehicles / Lorries">
                    {categorizedProducts.lorries.map((product) => (
                      <option key={product.id} value={product.id}>
                        {formatProductLabel(product.name || "")}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
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
                      className={`flex flex-col justify-between rounded-[var(--rl-radius-sm)] border p-2.5 text-left transition-all cursor-pointer ${
                        active
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

          {/* Design 2 Dedicated Layout Controls */}
          {isDesign2 ? (
            <div className="grid gap-2.5 pt-2 border-t border-[var(--rl-border)]">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                  <Sparkle size={13} className="text-[var(--rl-red)]" weight="fill" />
                  Design 2 Document Controls
                </label>
                <span className="rounded-full bg-emerald-50 border border-emerald-300 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                  Modern 4-Column Matrix
                </span>
              </div>
            </div>
          ) : (
            /* Legacy Benefits Card Template Switcher (Bilingual v4 only) */
            <div className="grid gap-2 pt-2 border-t border-[var(--rl-border)]">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
                  <Sparkle size={13} className="text-[var(--rl-red)]" weight="fill" />
                  Benefits Card Template (Legacy v4)
                </label>
                <span className="text-[11px] text-[var(--rl-text-muted)] font-medium">
                  {allBenefitPresets.find((p) => p.id === selectedBenefitPreset)?.name || "Masonry Flow"}
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {allBenefitPresets.map((preset) => {
                  const isSelected = selectedBenefitPreset === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => handleSelectBenefitPreset(preset.id)}
                      title={preset.description}
                      className={`flex flex-col items-start rounded-[var(--rl-radius-sm)] border p-2 text-left transition-all cursor-pointer ${
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
          )}
        </>
      )}
    </Card>
  );
}
