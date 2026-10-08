"use client";

import { useEffect, useMemo, useState } from "react";
import {
  FilePdf,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
} from "@phosphor-icons/react";
import type { BlockTree, CustomerSessionPreview } from "./types";
import { compileBlockTreeToCanvasElements } from "@/lib/template-block-engine";
import { api } from "@/lib/api";

interface LiveA4PreviewProps {
  tree: BlockTree;
  sessions: CustomerSessionPreview[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  lastUpdated: number;
}

export function LiveA4Preview({
  tree,
  sessions,
  activeSessionId,
  onSelectSession,
  lastUpdated,
}: LiveA4PreviewProps) {
  const [zoomScale, setZoomScale] = useState(0.48); // Fit A4 nicely in 400-500px column
  const [debouncedTree, setDebouncedTree] = useState<BlockTree>(tree);
  const [syncing, setSyncing] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const [loadProfile, setLoadProfile] = useState<"minimum" | "medium" | "high">("medium");

  const [previewHtml, setPreviewHtml] = useState<string>("");
  const [renderLoading, setRenderLoading] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  // Debounce tree update by 5 seconds with visible countdown
  useEffect(() => {
    setSyncing(true);
    setSecondsRemaining(5);

    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setDebouncedTree(tree);
          setSyncing(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [tree, lastUpdated]);

  function handleInstantSync() {
    setDebouncedTree(tree);
    setSyncing(false);
    setSecondsRemaining(0);
  }

  const activeSession = useMemo(() => {
    if (!sessions.length) return null;
    return sessions.find((s) => s.id === activeSessionId) || sessions[0];
  }, [sessions, activeSessionId]);

  // Synchronize 1:1 Live Preview with Backend PDF Renderer
  useEffect(() => {
    let cancelled = false;

    async function fetchPreview() {
      setRenderLoading(true);
      setRenderError(null);
      try {
        const elements = compileBlockTreeToCanvasElements(debouncedTree);
        const res = await api<{ html: string }>("/admin/templates/preview-render", {
          method: "POST",
          body: JSON.stringify({
            template_config: {
              canvas: {
                width: debouncedTree.pageWidth || 794,
                height: debouncedTree.pageHeight || 1123,
                elements,
              },
            },
            session_id: activeSessionId || undefined,
            load_profile: loadProfile,
          }),
        });
        if (!cancelled) {
          setPreviewHtml(res.html);
        }
      } catch (err: any) {
        if (!cancelled) {
          setRenderError(err.message || "Failed to render preview");
        }
      } finally {
        if (!cancelled) {
          setRenderLoading(false);
        }
      }
    }

    fetchPreview();
    return () => {
      cancelled = true;
    };
  }, [debouncedTree, loadProfile, activeSessionId]);

  return (
    <div className="w-[480px] shrink-0 border-r border-slate-200 bg-slate-900 flex flex-col h-full overflow-hidden select-none">
      {/* Top Controls Toolbar */}
      <div className="p-2.5 border-b border-slate-800 bg-slate-950 shrink-0 flex items-center justify-between text-white">
        <div className="flex items-center gap-2 min-w-0">
          <FilePdf size={16} weight="bold" className="text-emerald-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[11px] font-bold tracking-tight truncate">
              Live Quotation (A4 Preview)
            </div>
            <div className="text-[9.5px] text-slate-400 flex items-center gap-2">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  syncing ? "bg-amber-400 animate-ping" : "bg-emerald-400"
                }`}
              />
              <span>{syncing ? `Updating in ${secondsRemaining}s...` : renderLoading ? "Rendering..." : "Live Synced"}</span>
              {syncing && (
                <button
                  type="button"
                  onClick={handleInstantSync}
                  className="px-1.5 py-0.5 rounded bg-blue-600 hover:bg-blue-500 text-[9px] text-white font-bold ml-1 transition-colors"
                >
                  Update Now
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1 bg-slate-800 rounded p-0.5">
          <button
            type="button"
            onClick={() => setZoomScale((z) => Math.max(0.3, z - 0.05))}
            className="p-1 rounded text-slate-400 hover:text-white"
            title="Zoom Out"
          >
            <MagnifyingGlassMinus size={13} weight="bold" />
          </button>
          <span className="text-[10px] font-mono px-1 text-slate-300">
            {Math.round(zoomScale * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoomScale((z) => Math.min(0.8, z + 0.05))}
            className="p-1 rounded text-slate-400 hover:text-white"
            title="Zoom In"
          >
            <MagnifyingGlassPlus size={13} weight="bold" />
          </button>
        </div>
      </div>

      {/* Real Customer Session Picker & Load Profile Dropdown */}
      <div className="px-3 py-1.5 bg-slate-800/90 border-b border-slate-700/80 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[10px] text-slate-300 font-semibold shrink-0">Session:</span>
          <select
            value={activeSession?.id || ""}
            onChange={(e) => onSelectSession(e.target.value)}
            className="bg-slate-900 text-white text-[11px] font-medium rounded border border-slate-700 px-2 py-0.5 max-w-[200px] truncate focus:outline-hidden"
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.vehicle_no || "Blank"} · {s.insurance_company || "Insurer"}
              </option>
            ))}
            {!sessions.length && <option value="">ANY 368 · Berjaya Sompo</option>}
          </select>
        </div>
        
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-slate-300 font-semibold">Stress Test:</span>
          <select
            value={loadProfile}
            onChange={(e) => setLoadProfile(e.target.value as "minimum" | "medium" | "high")}
            className="bg-slate-900 text-white text-[11px] font-medium rounded border border-slate-700 px-2 py-0.5 focus:outline-hidden"
          >
            <option value="minimum">Min Load (2/2/2)</option>
            <option value="medium">Med Load (4/2/5)</option>
            <option value="high">High Load (6/6/9)</option>
          </select>
        </div>
      </div>

      {/* Scaled A4 Document View Container */}
      <div className="flex-1 overflow-auto p-4 flex justify-center items-start">
        <div
          style={{
            width: "794px",
            height: "1123px",
            transform: `scale(${zoomScale})`,
            transformOrigin: "top center",
          }}
          className="bg-white shadow-2xl relative shrink-0 overflow-hidden"
        >
          {renderLoading && !previewHtml && (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-white/90 gap-2">
              <div className="w-8 h-8 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin" />
              <span className="text-xs font-semibold text-slate-600">Rendering authentic A4 quotation...</span>
            </div>
          )}

          {renderError && !previewHtml && (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-white p-6 text-center">
              <span className="text-sm font-bold text-red-600 mb-1">Preview Generation Failed</span>
              <span className="text-xs text-slate-500 mb-3">{renderError}</span>
              <button
                type="button"
                onClick={handleInstantSync}
                className="px-3 py-1 bg-slate-900 text-white rounded text-xs font-medium hover:bg-slate-800"
              >
                Retry
              </button>
            </div>
          )}

          {previewHtml && (
            <iframe
              srcDoc={previewHtml}
              title="Live Quotation A4 Preview"
              className="w-[794px] h-[1123px] border-0 select-auto pointer-events-auto"
            />
          )}
        </div>
      </div>
    </div>
  );
}
