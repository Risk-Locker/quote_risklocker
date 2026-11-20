"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import {
  ArrowCounterClockwise,
  ArrowsInSimple,
  ArrowsOutSimple,
  ArrowSquareOut,
  CaretDown,
  CaretUp,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  X,
} from "@phosphor-icons/react";
import { CanvasElementView, type CanvasElement } from "@/components/template-canvas/shared";
import { Design2CanvasView } from "@/components/template-canvas/design2-canvas";
import type { BenefitCardStyle } from "@/lib/benefit-presets";
import type { WorkspaceSnapshot } from "../types";

export interface LivePreviewCardProps {
  previewCollapsed: boolean;
  setPreviewCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  previewExpanded: boolean;
  setPreviewExpanded: React.Dispatch<React.SetStateAction<boolean>>;
  setPreviewColCollapsed: (collapsed: boolean) => void;
  previewZoom: number;
  setPreviewZoom: React.Dispatch<React.SetStateAction<number>>;
  isDesign2: boolean;
  showDesign2Schedule: boolean;
  toggleDesign2Schedule: () => void;
  design2CardCount: number;
  selectedBenefitPreset: string;
  handleSelectBenefitPreset: (presetId: string) => void;
  allBenefitPresets: BenefitCardStyle[];
  previewScrollRef: React.RefObject<HTMLDivElement | null>;
  previewLoading: boolean;
  previewTemplate: any;
  canvasH: number;
  previewFields: Record<string, string>;
  currentCards: any[];
  addonCards: any[];
  companyName: string | null | undefined;
  previewTemplateAssets: Array<{ id: string; label: string; url: string }>;
  companyWorkspace: any;
  companies: Array<{ id: string; name: string; logo_asset_id?: string | null }>;
  workspace: WorkspaceSnapshot;
  balancedElements: CanvasElement[];
  displayOptions: any;
  conceptAssets: Record<string, string>;
  handleOpenNewQuotationTab?: () => void;
  openingPreviewTab?: boolean;
}

export function LivePreviewCard({
  previewCollapsed,
  setPreviewCollapsed,
  previewExpanded,
  setPreviewExpanded,
  setPreviewColCollapsed,
  previewZoom,
  setPreviewZoom,
  isDesign2,
  showDesign2Schedule,
  toggleDesign2Schedule,
  design2CardCount,
  selectedBenefitPreset,
  handleSelectBenefitPreset,
  allBenefitPresets,
  previewScrollRef,
  previewLoading,
  previewTemplate,
  canvasH,
  previewFields,
  currentCards,
  addonCards,
  companyName,
  previewTemplateAssets,
  companyWorkspace,
  companies,
  workspace,
  balancedElements,
  displayOptions,
  conceptAssets,
  handleOpenNewQuotationTab,
  openingPreviewTab = false,
}: LivePreviewCardProps) {
  return (
    <Card className="rl-tour-preview grid gap-2.5 p-3.5 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Live Quotation Preview</h2>
          <span className="flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Real-time
          </span>
          <button
            type="button"
            onClick={() => setPreviewZoom(0.80)}
            className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] bg-gray-100 hover:bg-gray-200 px-1.5 py-0.5 rounded border border-gray-200 cursor-pointer transition-colors"
            title="Click to reset zoom (Default 80%). Or hold Ctrl and scroll mouse wheel inside canvas to zoom in/out"
          >
            <span>{Math.round(previewZoom * 100)}%</span>
            <ArrowCounterClockwise size={10} className="text-gray-400" />
          </button>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {!previewCollapsed ? (
            <>
              <div className="flex items-center gap-1 bg-gray-100/90 rounded px-1.5 py-0.5 border border-gray-200 text-[10px]">
                <span className="font-bold text-[var(--rl-text-muted)] text-[9px] uppercase tracking-wider">Zoom</span>
                <button
                  type="button"
                  onClick={() => setPreviewZoom((z) => Math.max(0.25, Number((z - 0.1).toFixed(2))))}
                  className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-gray-200 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
                  title="Zoom Out (or Ctrl + Wheel Down)"
                >
                  <MagnifyingGlassMinus size={13} weight="bold" />
                </button>
                <input
                  type="range"
                  min="0.25"
                  max="2.5"
                  step="0.05"
                  value={previewZoom}
                  onChange={(e) => setPreviewZoom(parseFloat(e.target.value))}
                  className="w-14 h-1 cursor-pointer accent-[var(--rl-red)]"
                  title="Zoom slider (25% - 250%)"
                />
                <button
                  type="button"
                  onClick={() => setPreviewZoom((z) => Math.min(2.5, Number((z + 0.1).toFixed(2))))}
                  className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-gray-200 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
                  title="Zoom In (or Ctrl + Wheel Up)"
                >
                  <MagnifyingGlassPlus size={13} weight="bold" />
                </button>
                <div className="hidden md:flex items-center gap-0.5 ml-0.5 border-l border-gray-300 pl-1">
                  <button
                    type="button"
                    onClick={() => setPreviewZoom(0.50)}
                    className={`px-1 py-0.2 rounded text-[9px] font-semibold transition-colors cursor-pointer ${
                      Math.abs(previewZoom - 0.50) < 0.03 ? "bg-white shadow-2xs text-[var(--rl-red)] font-bold" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                    title="Fit (50%)"
                  >
                    50%
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewZoom(0.80)}
                    className={`px-1 py-0.2 rounded text-[9px] font-semibold transition-colors cursor-pointer ${
                      Math.abs(previewZoom - 0.80) < 0.03 ? "bg-white shadow-2xs text-[var(--rl-red)] font-bold" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                    title="Readable (80%)"
                  >
                    80%
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewZoom(1.00)}
                    className={`px-1 py-0.2 rounded text-[9px] font-semibold transition-colors cursor-pointer ${
                      Math.abs(previewZoom - 1.00) < 0.03 ? "bg-white shadow-2xs text-[var(--rl-red)] font-bold" : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                    title="1:1 Full Scale (100%)"
                  >
                    100%
                  </button>
                </div>
              </div>
              {!isDesign2 ? (
                <div className="flex items-center gap-1 bg-gray-100/90 rounded px-1.5 py-0.5 border border-gray-200 text-[10px]">
                  <span className="font-bold text-[var(--rl-text-muted)]">Style:</span>
                  <select
                    value={selectedBenefitPreset}
                    onChange={(e) => handleSelectBenefitPreset(e.target.value)}
                    className="bg-transparent font-semibold text-[var(--rl-text-strong)] cursor-pointer outline-hidden text-[10px]"
                  >
                    {allBenefitPresets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.shortName}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              {handleOpenNewQuotationTab ? (
                <button
                  type="button"
                  onClick={handleOpenNewQuotationTab}
                  disabled={openingPreviewTab}
                  className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-bold bg-[var(--rl-black)] text-white hover:bg-black transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
                  title="Open this new rendered quotation in a full browser tab"
                >
                  <ArrowSquareOut size={13} weight="bold" />
                  <span>{openingPreviewTab ? "Opening..." : "Open in New Tab"}</span>
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setPreviewExpanded((v) => !v)}
                className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors border border-gray-200 shadow-2xs cursor-pointer"
                title={previewExpanded ? "Compress live preview" : "Expand live preview"}
              >
                {previewExpanded ? <ArrowsInSimple size={13} weight="bold" /> : <ArrowsOutSimple size={13} weight="bold" />}
                <span>{previewExpanded ? "Compress" : "Expand"}</span>
              </button>
            </>
          ) : null}
          <button
            type="button"
            onClick={() => setPreviewCollapsed((v) => !v)}
            className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors border border-gray-200 shadow-2xs cursor-pointer"
            title={previewCollapsed ? "Expand live preview canvas" : "Collapse live preview canvas"}
          >
            {previewCollapsed ? <CaretDown size={13} weight="bold" /> : <CaretUp size={13} weight="bold" />}
            <span>{previewCollapsed ? "Expand" : "Collapse"}</span>
          </button>
          <button
            type="button"
            onClick={() => setPreviewColCollapsed(true)}
            className="hidden lg:flex items-center justify-center p-1 text-[11px] font-semibold text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded border border-transparent hover:border-gray-200 transition-all cursor-pointer ml-1"
            title="Close Preview Panel"
          >
            <X size={14} weight="bold" />
          </button>
        </div>
      </div>

      {previewCollapsed ? (
        <div className="flex items-center justify-center p-3.5 text-xs text-[var(--rl-text-muted)] italic bg-gray-50/70 rounded">
          Live quotation preview canvas is collapsed. Click Expand to preview document.
        </div>
      ) : (
        <div
          ref={previewScrollRef}
          className={`relative ${previewExpanded ? "h-[680px]" : "h-[450px]"} w-full overflow-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-50/80 p-4 transition-all duration-200`}
        >
          {previewLoading && !previewTemplate ? (
            <div className="flex h-full items-center justify-center text-xs text-[var(--rl-text-muted)]">
              Loading preview template...
            </div>
          ) : previewTemplate ? (
            <div className="inline-block min-w-full text-center">
              <div
                className="inline-block text-left shrink-0"
                style={{
                  width: (previewTemplate.config.canvas?.width || 794) * previewZoom,
                  height: canvasH * previewZoom,
                  position: "relative",
                  backgroundColor: "#ffffff",
                  boxShadow: "0 4px 14px rgba(0,0,0,0.08)",
                  borderRadius: "4px",
                  overflow: "hidden",
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
                    textRendering: "geometricPrecision",
                    WebkitFontSmoothing: "antialiased",
                    imageRendering: "auto",
                  }}
                >
                  {isDesign2 ? (
                    <Design2CanvasView
                      fields={previewFields}
                      config={previewTemplate.config}
                      height={canvasH}
                      currentBenefits={currentCards}
                      availableAddons={addonCards}
                      companyName={companyName || undefined}
                      assets={previewTemplateAssets}
                      includeSchedule={showDesign2Schedule}
                      insurerLogoUrl={(() => {
                        const logoId =
                          companyWorkspace?.company?.logo_asset_id ||
                          companies.find(
                            (c) =>
                              c.id === workspace?.pinned.company_id ||
                              (companyName && c.name.toLowerCase() === companyName.toLowerCase())
                          )?.logo_asset_id;
                        return logoId ? `/business/assets/${logoId}/content?profile=print` : undefined;
                      })()}
                    />
                  ) : (
                    balancedElements.map((element: CanvasElement) => (
                      <CanvasElementView
                        key={element.id}
                        element={element}
                        selected={false}
                        readOnly={true}
                        onPointerDown={() => {}}
                        config={previewTemplate.config}
                        variableValues={previewFields}
                        benefitData={{
                          ...workspace.benefit_cards,
                          current_benefits: currentCards,
                          available_addons: addonCards,
                          extras: workspace.extras,
                          displayOptions,
                        }}
                        conceptAssets={conceptAssets}
                        assets={previewTemplateAssets}
                      />
                    ))
                  )}
                </div>
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
  );
}
