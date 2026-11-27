"use client";

import React, { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { Robot } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import { CopilotWorkspace } from "@/components/copilot/CopilotWorkspace";

export function GlobalAiCopilot() {
  const pathname = usePathname() || "/";
  const { user } = useAuth();
  const {
    isOpen,
    setIsOpen,
    drawerMode,
    setDrawerMode,
    drawerWidth,
    setDrawerWidth,
    activeArtifact,
    dockedFromNavigation,
    restoreFromDock,
  } = useCopilot();

  const draggingRef = useRef(false);

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!draggingRef.current) return;
      const nextWidth = window.innerWidth - e.clientX;
      setDrawerWidth(nextWidth);
    }
    function onMouseUp() {
      if (draggingRef.current) {
        draggingRef.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [setDrawerWidth]);

  useEffect(() => {
    if (!isOpen || drawerMode !== "modal") return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setDrawerMode("compact");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, drawerMode, setDrawerMode]);

  const isStaffOrAdmin = !!user && ["super_admin", "admin", "dev", "staff"].includes(user.role);
  if (!isStaffOrAdmin || pathname === "/copilot") {
    return null;
  }

  const effectiveWidth =
    activeArtifact || drawerMode === "wide"
      ? Math.max(drawerWidth, 960)
      : drawerWidth;

  return (
    <>
      {!isOpen && dockedFromNavigation && (
        <button
          type="button"
          onClick={restoreFromDock}
          className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-[var(--rl-black)] hover:bg-[#111111] text-white px-4 py-3 shadow-2xl border border-white/15 text-xs font-bold cursor-pointer transition-transform hover:scale-105"
          title="Return to AI Copilot conversation"
        >
          <Robot size={17} weight="fill" className="text-emerald-400" />
          <span>Return to Copilot</span>
        </button>
      )}

      {!isOpen && !dockedFromNavigation && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="group fixed bottom-6 right-6 z-40 flex items-center h-14 w-14 hover:w-40 rounded-full bg-[var(--rl-black)] hover:bg-[#111111] text-white shadow-2xl transition-all duration-300 ease-out border border-white/10 hover:shadow-[0_8px_32px_rgba(0,0,0,0.35)] overflow-hidden cursor-pointer justify-center hover:justify-start hover:px-3.5"
          aria-label="Open AI Copilot (Ctrl+K)"
          title="Open AI Copilot (Ctrl+K)"
        >
          <div className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center text-white shrink-0 group-hover:scale-105 transition-transform duration-200">
            <Robot size={20} weight="fill" />
          </div>
          <span className="max-w-0 overflow-hidden group-hover:max-w-xs transition-all duration-300 ease-out whitespace-nowrap text-xs font-bold tracking-wide pl-0 group-hover:pl-2.5 opacity-0 group-hover:opacity-100 text-white">
            AI Copilot
          </span>
        </button>
      )}

      {isOpen && drawerMode === "modal" && (
        <div
          className="fixed inset-0 z-50 bg-black/45 backdrop-blur-[2px] flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setDrawerMode("compact");
          }}
        >
          <aside
            aria-label="RiskLocker AI Copilot Expanded Modal"
            className="w-[92vw] max-w-[1400px] h-[90vh] rounded-2xl bg-white text-[var(--rl-text-strong)] shadow-2xl border border-[var(--rl-border)] flex flex-col overflow-hidden"
          >
            <CopilotWorkspace variant="sidecar" onCloseDrawer={() => setIsOpen(false)} />
          </aside>
        </div>
      )}

      {isOpen && drawerMode !== "modal" && (
        <aside
          aria-label="RiskLocker AI Copilot Drawer"
          style={{ width: `min(94vw, ${effectiveWidth}px)` }}
          className="fixed top-0 right-0 z-50 h-screen bg-white text-[var(--rl-text-strong)] shadow-2xl border-l border-[var(--rl-border)] flex flex-col"
        >
          {/* Left-Edge Drag-to-Resize Handle */}
          <div
            role="separator"
            aria-orientation="vertical"
            title="Drag to resize Copilot panel"
            onMouseDown={(e) => {
              e.preventDefault();
              draggingRef.current = true;
              document.body.style.cursor = "col-resize";
              document.body.style.userSelect = "none";
            }}
            className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-emerald-500/50 transition-colors z-50"
          />
          <CopilotWorkspace variant="sidecar" onCloseDrawer={() => setIsOpen(false)} />
        </aside>
      )}
    </>
  );
}
