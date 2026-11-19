"use client";

import { useEffect, useRef, useState } from "react";
import { CaretDown, Check, Plus, X } from "@phosphor-icons/react";
import type { DynamicAddonDefinition } from "../types";

export const DEFAULT_DYNAMIC_ADDON_CATALOG: DynamicAddonDefinition[] = [
  { key: "ehailing", label: "E-Hailing" },
  { key: "srcc", label: "Strike & Riot" },
  { key: "child_safety", label: "Child Safety" },
  { key: "respray", label: "Full Respray" },
  { key: "ev_battery", label: "EV Battery" },
  { key: "ev_protection", label: "EV Protection" },
];

export interface DynamicAddonsControlProps {
  currentExtraAddons?: Record<string, string> | null;
  catalog?: DynamicAddonDefinition[];
  onSetAddon: (key: string, val: "Yes" | "No") => Promise<void> | void;
  disabled?: boolean;
  label?: string;
}

/**
 * Compact manual '+ Add-on' selector letting staff manually attach any of the
 * conditional add-ons (E-Hailing, Strike & Riot, Child Safety, Full Respray,
 * EV Battery, EV Protection) with explicit Yes / No selection.
 */
export function DynamicAddonsControl({
  currentExtraAddons,
  catalog = DEFAULT_DYNAMIC_ADDON_CATALOG,
  onSetAddon,
  disabled = false,
  label = "+ Add-on",
}: DynamicAddonsControlProps) {
  const [open, setOpen] = useState(false);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleOutside = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  const activeMap = currentExtraAddons || {};

  const handleChoose = async (key: string, val: "Yes" | "No") => {
    setSavingKey(key);
    try {
      await onSetAddon(key, val);
      setOpen(false);
    } finally {
      setSavingKey(null);
    }
  };

  return (
    <div ref={rootRef} className="relative inline-block">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[#e5e5ea] bg-[#f5f5f7] hover:bg-[#ebebef] hover:border-[#d1d1d6] px-2 py-1 text-[11px] font-semibold text-[#1b1717] transition-colors cursor-pointer disabled:opacity-50"
      >
        <Plus size={11} weight="bold" />
        <span>{label.replace(/^\+\s*/, "")}</span>
        <CaretDown size={10} weight="bold" className="text-[#6e6e73]" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 w-64 rounded-[var(--rl-radius)] border border-[#e5e5ea] bg-[#ffffff] shadow-xl p-2 space-y-1">
          <div className="flex items-center justify-between px-1 pb-1 border-b border-[#e5e5ea]">
            <span className="text-[11px] font-bold text-[#1b1717]">Add / Toggle Extra Add-on</span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="p-0.5 text-[#6e6e73] hover:text-[#1b1717] rounded-[var(--rl-radius-sm)] cursor-pointer"
              aria-label="Close add-on menu"
            >
              <X size={12} weight="bold" />
            </button>
          </div>
          {catalog.map((def) => {
            const cur = activeMap[def.key];
            const isYes = cur === "Yes";
            const isNo = cur === "No";
            const busy = savingKey === def.key;
            return (
              <div
                key={def.key}
                className="flex items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] px-1.5 py-1 hover:bg-[#f5f5f7]"
              >
                <span className="text-[11px] font-semibold text-[#1b1717] truncate">
                  {def.label}
                </span>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleChoose(def.key, "Yes")}
                    className={`inline-flex items-center gap-0.5 rounded-[var(--rl-radius-sm)] border px-2 py-0.5 text-[10px] font-semibold cursor-pointer transition-colors ${
                      isYes
                        ? "bg-emerald-700 text-white border-emerald-700"
                        : "bg-white text-[#1b1717] border-[#e5e5ea] hover:bg-emerald-50"
                    }`}
                  >
                    {isYes && <Check size={9} weight="bold" />}
                    Yes
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleChoose(def.key, "No")}
                    className={`rounded-[var(--rl-radius-sm)] border px-2 py-0.5 text-[10px] font-semibold cursor-pointer transition-colors ${
                      isNo
                        ? "bg-[#1b1717] text-white border-[#1b1717]"
                        : "bg-white text-[#6e6e73] border-[#e5e5ea] hover:bg-neutral-100"
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
