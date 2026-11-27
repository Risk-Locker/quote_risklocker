"use client";

import { usePathname } from "next/navigation";
import { Robot } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import { CopilotWorkspace } from "@/components/copilot/CopilotWorkspace";

export function GlobalAiCopilot() {
  const pathname = usePathname() || "/";
  const { user } = useAuth();
  const { isOpen, setIsOpen, drawerMode, activeArtifact } = useCopilot();

  const isStaffOrAdmin = !!user && ["super_admin", "admin", "dev", "staff"].includes(user.role);
  if (!isStaffOrAdmin || pathname === "/copilot") {
    return null;
  }

  return (
    <>
      {!isOpen && (
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

      {isOpen && (
        <aside
          aria-label="RiskLocker AI Copilot Drawer"
          className={`fixed top-0 right-0 z-50 h-screen bg-white text-[var(--rl-text-strong)] shadow-2xl border-l border-[var(--rl-border)] flex flex-col transition-all duration-200 ease-out ${
            activeArtifact || drawerMode === "wide"
              ? "w-[960px] max-w-[96vw]"
              : "w-[500px] max-w-[95vw]"
          }`}
        >
          <CopilotWorkspace variant="sidecar" onCloseDrawer={() => setIsOpen(false)} />
        </aside>
      )}
    </>
  );
}
