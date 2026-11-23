"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
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

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 2.5;

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
  const expandedScrollRef = useRef<HTMLDivElement | null>(null);
  const zoomRef = useRef(previewZoom);
  zoomRef.current = previewZoom;

  const [isPanning, setIsPanning] = useState(false);
  const panStateRef = useRef<{
    active: boolean;
    el: HTMLDivElement | null;
    startX: number;
    startY: number;
    startLeft: number;
    startTop: number;
  }>({ active: false, el: null, startX: 0, startY: 0, startLeft: 0, startTop: 0 });

  const activeViewportRef = previewExpanded ? expandedScrollRef : previewScrollRef;

  const canvasWidth = Number(previewTemplate?.config?.canvas?.width || 794);

  const clampZoom = useCallback((z: number) => {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(z.toFixed(2))));
  }, []);

  const handleFitToWidth = useCallback(() => {
    const el = activeViewportRef.current;
    if (!el || canvasWidth <= 0) return;
    const availW = Math.max(240, el.clientWidth - 28);
    const fit = Math.min(1.5, Math.max(0.3, Number((availW / canvasWidth).toFixed(2))));
    setPreviewZoom(fit);
  }, [activeViewportRef, canvasWidth, setPreviewZoom]);

  const handleToggleExpand = useCallback(() => {
    const next = !previewExpanded;
    setPreviewExpanded(next);
    if (next && zoomRef.current < 0.9) {
      setPreviewZoom(1.0);
    }
  }, [previewExpanded, setPreviewExpanded, setPreviewZoom]);

  // Escape closes full-viewport expanded preview
  useEffect(() => {
    if (!previewExpanded) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPreviewExpanded(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [previewExpanded, setPreviewExpanded]);

  // Native non-passive Ctrl/Cmd + Scroll wheel zoom anchored around cursor position
  useEffect(() => {
    if (previewCollapsed && !previewExpanded) return;
    const el = previewExpanded ? expandedScrollRef.current : previewScrollRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      e.stopPropagation();

      const prevZoom = zoomRef.current;
      const absDelta = Math.abs(e.deltaY);
      const step = absDelta >= 40 ? (e.deltaY < 0 ? 0.1 : -0.1) : Math.max(-0.12, Math.min(0.12, -e.deltaY * 0.005));
      const nextZoom = clampZoom(prevZoom + step);
      if (nextZoom === prevZoom) return;

      const rect = el.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const contentX = (el.scrollLeft + mouseX) / prevZoom;
      const contentY = (el.scrollTop + mouseY) / prevZoom;

      zoomRef.current = nextZoom;
      setPreviewZoom(nextZoom);

      requestAnimationFrame(() => {
        el.scrollLeft = Math.max(0, contentX * nextZoom - mouseX);
        el.scrollTop = Math.max(0, contentY * nextZoom - mouseY);
      });
    };

    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, [previewCollapsed, previewExpanded, previewScrollRef, clampZoom, setPreviewZoom]);

  // Window mouse listeners for right-click / middle-click drag panning
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const p = panStateRef.current;
      if (!p.active || !p.el) return;
      const dx = e.clientX - p.startX;
      const dy = e.clientY - p.startY;
      p.el.scrollLeft = p.startLeft - dx;
      p.el.scrollTop = p.startTop - dy;
    };

    const handleMouseUp = () => {
      if (!panStateRef.current.active) return;
      panStateRef.current.active = false;
      panStateRef.current.el = null;
      setIsPanning(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  const handleViewportMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    // Right mouse button (2) or middle mouse button (1) pans the preview canvas
    if (e.button !== 2 && e.button !== 1) return;
    e.preventDefault();
    const el = e.currentTarget;
    panStateRef.current = {
      active: true,
      el,
      startX: e.clientX,
      startY: e.clientY,
      startLeft: el.scrollLeft,
      startTop: el.scrollTop,
    };
    setIsPanning(true);
  };

  const handleViewportContextMenu = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const insurerLogoUrl = (() => {
    const logoId =
      companyWorkspace?.company?.logo_asset_id ||
      companies.find(
        (c) =>
          c.id === workspace?.pinned.company_id ||
          (companyName && c.name.toLowerCase() === companyName.toLowerCase())
      )?.logo_asset_id;
    return logoId ? `/business/assets/${logoId}/content?profile=print` : undefined;
  })();

  const renderCanvasContent = () => {
    if (previewLoading && !previewTemplate) {
      return (
        <div className="flex h-full items-center justify-center text-xs text-[var(--rl-text-muted)]">
          Loading preview template...
        </div>
      );
    }
    if (!previewTemplate) {
      return (
        <div className="flex h-full items-center justify-center text-xs text-[var(--rl-text-muted)]">
          Select a template to generate live preview
        </div>
      );
    }
    return (
      <div className="inline-block min-w-full text-center">
        <div
          className="inline-block text-left shrink-0"
          style={{
            width: canvasWidth * previewZoom,
            height: canvasH * previewZoom,
            position: "relative",
            backgroundColor: "#ffffff",
            boxShadow: "0 4px 18px rgba(0,0,0,0.10)",
            borderRadius: "4px",
            overflow: "hidden",
          }}
        >
          <div
            id="rl-live-canvas-inner"
            style={{
              width: canvasWidth,
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
                insurerLogoUrl={insurerLogoUrl}
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
    );
  };

  const renderZoomControls = (inExpandedModal: boolean) => (
    <div className="flex items-center gap-1 bg-gray-100/90 rounded px-1.5 py-0.5 border border-gray-200 text-[10px]">
      <span className="font-bold text-[var(--rl-text-muted)] text-[9px] uppercase tracking-wider">Zoom</span>
      <button
        type="button"
        onClick={() => setPreviewZoom((z) => clampZoom(z - 0.1))}
        className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-gray-200 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
        title="Zoom Out (or Ctrl + Scroll Down)"
      >
        <MagnifyingGlassMinus size={13} weight="bold" />
      </button>
      <input
        type="range"
        min={MIN_ZOOM}
        max={MAX_ZOOM}
        step="0.05"
        value={previewZoom}
        onChange={(e) => setPreviewZoom(parseFloat(e.target.value))}
        className="w-14 h-1 cursor-pointer accent-[var(--rl-red)]"
        title="Zoom slider (25% - 250%)"
      />
      <button
        type="button"
        onClick={() => setPreviewZoom((z) => clampZoom(z + 0.1))}
        className="rounded p-0.5 text-[var(--rl-text-muted)] hover:bg-gray-200 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
        title="Zoom In (or Ctrl + Scroll Up)"
      >
        <MagnifyingGlassPlus size={13} weight="bold" />
      </button>
      <div className="hidden md:flex items-center gap-0.5 ml-0.5 border-l border-gray-300 pl-1">
        <button
          type="button"
          onClick={handleFitToWidth}
          className="px-1 py-0.2 rounded text-[9px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-white transition-colors cursor-pointer"
          title="Fit quotation width to viewport"
        >
          Fit
        </button>
        {(inExpandedModal ? [0.5, 0.8, 1.0, 1.25, 1.5] : [0.5, 0.8, 1.0]).map((preset) => (
          <button
            key={preset}
            type="button"
            onClick={() => setPreviewZoom(preset)}
            className={`px-1 py-0.2 rounded text-[9px] font-semibold transition-colors cursor-pointer ${
              Math.abs(previewZoom - preset) < 0.03
                ? "bg-white shadow-2xs text-[var(--rl-red)] font-bold"
                : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
            title={`${Math.round(preset * 100)}%`}
          >
            {Math.round(preset * 100)}%
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <>
      <Card className="rl-tour-preview flex flex-col gap-2 p-2.5 h-full min-h-[480px] overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-1.5 shrink-0">
          <div className="flex items-center gap-1.5">
            <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Live Quotation Preview</h2>
            <span className="flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Live
            </span>
            <button
              type="button"
              onClick={() => setPreviewZoom(0.8)}
              className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] bg-gray-100 hover:bg-gray-200 px-1.5 py-0.5 rounded border border-gray-200 cursor-pointer transition-colors"
              title="Click to reset zoom (Default 80%). Ctrl+Scroll to zoom, Right-Click drag to pan."
            >
              <span>{Math.round(previewZoom * 100)}%</span>
              <ArrowCounterClockwise size={10} className="text-gray-400" />
            </button>
          </div>
          <div className="flex items-center gap-1 flex-wrap">
            {!previewCollapsed ? (
              <>
                {renderZoomControls(false)}
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
                    title="Open rendered quotation in a full browser tab"
                  >
                    <ArrowSquareOut size={12} weight="bold" />
                    <span>{openingPreviewTab ? "Opening..." : "New Tab"}</span>
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={handleToggleExpand}
                  className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors border border-gray-200 shadow-2xs cursor-pointer"
                  title="Expand live preview full screen"
                >
                  <ArrowsOutSimple size={12} weight="bold" />
                  <span>Expand</span>
                </button>
              </>
            ) : null}
            <button
              type="button"
              onClick={() => setPreviewCollapsed((v) => !v)}
              className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold text-[var(--rl-text-muted)] hover:bg-gray-100 hover:text-[var(--rl-text-strong)] transition-colors border border-gray-200 shadow-2xs cursor-pointer"
              title={previewCollapsed ? "Expand live preview canvas" : "Collapse live preview canvas"}
            >
              {previewCollapsed ? <CaretDown size={12} weight="bold" /> : <CaretUp size={12} weight="bold" />}
              <span>{previewCollapsed ? "Show" : "Collapse"}</span>
            </button>
            <button
              type="button"
              onClick={() => setPreviewColCollapsed(true)}
              className="hidden lg:flex items-center justify-center p-1 text-[11px] font-semibold text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded border border-transparent hover:border-gray-200 transition-all cursor-pointer"
              title="Close Preview Panel"
              aria-label="Close Preview Panel"
            >
              <X size={13} weight="bold" />
            </button>
          </div>
        </div>

        {previewCollapsed ? (
          <div className="flex items-center justify-center p-3 text-xs text-[var(--rl-text-muted)] italic bg-gray-50/70 rounded">
            Live quotation preview canvas is collapsed. Click Show to preview document.
          </div>
        ) : previewExpanded ? (
          <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-2.5 rounded-[var(--rl-radius-sm)] border border-dashed border-[var(--rl-border)] bg-gray-50/80 p-6 text-center">
            <p className="text-xs font-medium text-[var(--rl-text-muted)]">
              Live quotation preview is open in full-screen view.
            </p>
            <button
              type="button"
              onClick={() => setPreviewExpanded(false)}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--rl-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--rl-text-strong)] hover:bg-gray-50 shadow-2xs cursor-pointer"
            >
              <ArrowsInSimple size={14} weight="bold" />
              <span>Return to Docked Preview</span>
            </button>
          </div>
        ) : (
          <div className="flex flex-col flex-1 min-h-0 gap-1">
            <div
              ref={previewScrollRef}
              onMouseDown={handleViewportMouseDown}
              onContextMenu={handleViewportContextMenu}
              className={`relative flex-1 min-h-0 w-full overflow-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-gray-100/80 p-3 ${
                isPanning ? "cursor-grabbing select-none" : ""
              }`}
            >
              {renderCanvasContent()}
            </div>
            <div className="flex items-center justify-between text-[10px] text-[var(--rl-text-muted)] px-0.5 shrink-0">
              <span>Ctrl+Scroll to zoom · Right-click drag to pan</span>
              <span className="font-mono">{Math.round(previewZoom * 100)}%</span>
            </div>
          </div>
        )}
      </Card>

      {/* Full-Viewport Expanded Preview Overlay */}
      {previewExpanded && !previewCollapsed && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-xs p-2 sm:p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
          aria-label="Expanded Live Quotation Preview"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setPreviewExpanded(false);
          }}
        >
          <div className="w-full h-full max-w-[98vw] max-h-[96dvh] flex flex-col rounded-xl bg-white shadow-2xl border border-[var(--rl-border)] overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-[var(--rl-border)] bg-[var(--rl-surface)] shrink-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Live Quotation Preview</h2>
                <span className="rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                  Full View · {Math.round(previewZoom * 100)}%
                </span>
                <span className="hidden md:inline text-[11px] text-[var(--rl-text-muted)]">
                  Ctrl+Scroll to zoom · Right-click drag to pan · Esc to exit
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {renderZoomControls(true)}
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
                    className="flex items-center gap-1 rounded px-2.5 py-1 text-xs font-bold bg-[var(--rl-black)] text-white hover:bg-black transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
                  >
                    <ArrowSquareOut size={13} weight="bold" />
                    <span>{openingPreviewTab ? "Opening..." : "Open in New Tab"}</span>
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => setPreviewExpanded(false)}
                  className="flex items-center gap-1 rounded px-2.5 py-1 text-xs font-semibold text-[var(--rl-text-strong)] bg-white hover:bg-gray-100 transition-colors border border-[var(--rl-border)] shadow-2xs cursor-pointer"
                  title="Compress back to workspace panel (Esc)"
                >
                  <ArrowsInSimple size={13} weight="bold" />
                  <span>Compress</span>
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewExpanded(false)}
                  aria-label="Close expanded preview"
                  className="p-1.5 rounded text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors cursor-pointer"
                >
                  <X size={16} weight="bold" />
                </button>
              </div>
            </div>

            <div
              ref={expandedScrollRef}
              onMouseDown={handleViewportMouseDown}
              onContextMenu={handleViewportContextMenu}
              className={`relative flex-1 min-h-0 w-full overflow-auto bg-neutral-200/75 p-6 ${
                isPanning ? "cursor-grabbing select-none" : ""
              }`}
            >
              {renderCanvasContent()}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
