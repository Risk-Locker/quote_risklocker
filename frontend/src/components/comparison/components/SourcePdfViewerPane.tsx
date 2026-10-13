"use client";

import React from "react";
import { FilePdf, SidebarSimple, X } from "@phosphor-icons/react";

interface SourcePdfViewerPaneProps {
  activePdfSession: {
    sessionId: string;
    companyName: string;
  } | null;
  dockMode: "docked" | "floating";
  panelWidth: number;
  onSetDockMode: (mode: "docked" | "floating") => void;
  onClose: () => void;
  onStartResizing: () => void;
}

export function SourcePdfViewerPane({
  activePdfSession,
  dockMode,
  panelWidth,
  onSetDockMode,
  onClose,
  onStartResizing,
}: SourcePdfViewerPaneProps) {
  if (!activePdfSession) return null;

  if (dockMode === "docked") {
    return (
      <div
        style={{ width: panelWidth }}
        className="shrink-0 sticky top-4 h-[calc(100vh-2rem)] border border-[#e5e5ea] bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden relative transition-all no-print print:hidden"
      >
        {/* Draggable Resize Divider on Left Edge */}
        <div
          onMouseDown={onStartResizing}
          className="absolute top-0 bottom-0 -left-1.5 w-3 cursor-col-resize hover:bg-[#1b1717]/40 z-30 flex items-center justify-center group"
          title="Click & drag to resize PDF viewer"
        >
          <div className="w-1 h-12 rounded-full bg-neutral-300 group-hover:bg-[#1b1717] transition-colors" />
        </div>

        <div className="flex items-center justify-between p-3.5 border-b border-[#e5e5ea] bg-[#f5f5f7]">
          <div className="flex items-center gap-2.5 min-w-0">
            <FilePdf size={22} className="text-[#ed1c24] shrink-0" weight="bold" />
            <div className="min-w-0">
              <h4 className="text-xs font-bold text-[#1b1717] truncate">
                {activePdfSession.companyName} Source PDF
              </h4>
              <p className="text-[11px] text-[#6e6e73] truncate">
                Verify extracted values directly against source document
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => onSetDockMode("floating")}
              className="px-2 py-1 text-[11px] font-semibold rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#454545] flex items-center gap-1 transition-colors cursor-pointer"
              title="Switch to floating overlay drawer"
            >
              <SidebarSimple size={13} weight="bold" />
              <span>Float</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#454545] transition-colors cursor-pointer"
              title="Close PDF Panel"
            >
              <X size={15} weight="bold" />
            </button>
          </div>
        </div>
        <div className="flex-1 bg-neutral-100 p-2 overflow-hidden">
          <iframe
            key={activePdfSession.sessionId}
            src={`/api/sessions/${activePdfSession.sessionId}/pdf`}
            className="w-full h-full rounded-lg border border-[#e5e5ea] bg-white"
            title="Underwriter Source PDF"
          />
        </div>
      </div>
    );
  }

  return (
    <div
      style={{ width: panelWidth }}
      className="fixed inset-y-0 right-0 z-50 bg-white border-l border-[#e5e5ea] shadow-2xl flex flex-col animate-in slide-in-from-right duration-150 no-print print:hidden"
    >
      {/* Draggable Resize Divider on Left Edge */}
      <div
        onMouseDown={onStartResizing}
        className="absolute top-0 bottom-0 -left-1.5 w-3 cursor-col-resize hover:bg-[#1b1717]/40 z-30 flex items-center justify-center group"
        title="Click & drag to resize PDF viewer"
      >
        <div className="w-1 h-16 rounded-full bg-neutral-300 group-hover:bg-[#1b1717] transition-colors" />
      </div>

      <div className="flex items-center justify-between p-4 border-b border-[#e5e5ea] bg-[#f5f5f7]">
        <div className="flex items-center gap-2.5 min-w-0">
          <FilePdf size={22} className="text-[#ed1c24] shrink-0" weight="bold" />
          <div className="min-w-0">
            <h4 className="text-sm font-bold text-[#1b1717] truncate">
              {activePdfSession.companyName} Source PDF
            </h4>
            <p className="text-xs text-[#6e6e73] truncate">
              Verify extracted values directly against source document
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => onSetDockMode("docked")}
            className="px-2.5 py-1 text-xs font-semibold rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#1b1717] flex items-center gap-1.5 transition-colors cursor-pointer"
            title="Dock side-by-side with matrix table"
          >
            <SidebarSimple size={14} weight="bold" />
            <span>Dock to Window</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg border border-[#e5e5ea] bg-white hover:bg-neutral-100 text-[#454545] transition-colors cursor-pointer"
            title="Close PDF Panel"
          >
            <X size={16} weight="bold" />
          </button>
        </div>
      </div>
      <div className="flex-1 bg-neutral-100 p-2 overflow-hidden">
        <iframe
          key={activePdfSession.sessionId}
          src={`/api/sessions/${activePdfSession.sessionId}/pdf`}
          className="w-full h-full rounded-lg border border-[#e5e5ea] bg-white"
          title="Underwriter Source PDF"
        />
      </div>
    </div>
  );
}
