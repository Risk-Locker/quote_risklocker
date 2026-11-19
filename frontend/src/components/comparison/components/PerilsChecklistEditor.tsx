"use client";

import { Check, Minus } from "@phosphor-icons/react";

export type CanonicalPerilDef = {
  code: string;
  label: string;
  group: "core" | "addon";
};

export const CANONICAL_PERIL_CATALOG: CanonicalPerilDef[] = [
  { code: "TOWING", label: "Towing", group: "core" },
  { code: "WINDSCREEN", label: "Windscreen", group: "core" },
  { code: "FLOOD", label: "Special Perils", group: "core" },
  { code: "LLP", label: "LLP (Passengers)", group: "core" },
  { code: "LLOP", label: "LLOP (Acts)", group: "core" },
  { code: "BETTERMENT", label: "Betterment Waiver", group: "core" },
  { code: "ALL DRIVERS", label: "All Drivers", group: "core" },
  { code: "PA", label: "Personal Accident", group: "core" },
  { code: "CART", label: "CART (Loss of Use)", group: "addon" },
  { code: "SRCC", label: "Strike & Riot", group: "addon" },
  { code: "KEY CARE", label: "Key Care", group: "addon" },
  { code: "NCD RELIEF", label: "NCD Protection", group: "addon" },
  { code: "E-HAILING", label: "E-Hailing", group: "addon" },
  { code: "CHILD SEAT", label: "Child Safety", group: "addon" },
  { code: "RESPRAY", label: "Full Respray", group: "addon" },
  { code: "EV BATTERY", label: "EV Battery", group: "addon" },
  { code: "EV CHARGE", label: "EV Protection", group: "addon" },
];

export interface PerilsChecklistEditorProps {
  selectedPerils: string[];
  onChange?: (nextPerils: string[]) => void;
  readOnly?: boolean;
  compact?: boolean;
}

/**
 * Interactive or read-only Included Perils checklist clearly showing
 * Added (emerald check) vs Not Added states across all canonical perils.
 */
export function PerilsChecklistEditor({
  selectedPerils,
  onChange,
  readOnly = false,
  compact = false,
}: PerilsChecklistEditorProps) {
  const normalizedSet = new Set(
    (selectedPerils || []).map((p) => String(p).trim().toUpperCase())
  );

  // Include any non-standard custom tokens at the end cleanly
  const knownCodes = new Set(CANONICAL_PERIL_CATALOG.map((c) => c.code));
  const extraTokens = Array.from(normalizedSet).filter((p) => p && !knownCodes.has(p));

  const items: CanonicalPerilDef[] = [
    ...CANONICAL_PERIL_CATALOG,
    ...extraTokens.map((code) => ({ code, label: code, group: "addon" as const })),
  ];

  const handleToggle = (code: string) => {
    if (readOnly || !onChange) return;
    const next = new Set(normalizedSet);
    if (next.has(code)) {
      next.delete(code);
    } else {
      next.add(code);
    }
    onChange(Array.from(next));
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => {
        const isAdded = normalizedSet.has(item.code);
        // In read-only compact mode show core perils always (Added vs Not Added) + only active addon perils
        if (readOnly && compact && item.group === "addon" && !isAdded) {
          return null;
        }
        const sharedStyle = `inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] border ${
          compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]"
        } font-semibold transition-colors ${
          isAdded
            ? "bg-emerald-50 text-emerald-800 border-emerald-300"
            : "bg-[#f5f5f7] text-[#6e6e73] border-[#e5e5ea]"
        }`;

        if (readOnly) {
          return (
            <span
              key={item.code}
              className={sharedStyle}
              title={isAdded ? `${item.label}: Added` : `${item.label}: Not Included`}
            >
              {isAdded ? (
                <Check size={10} weight="bold" className="text-emerald-700 shrink-0" />
              ) : (
                <Minus size={10} weight="bold" className="text-[#8e8e93] shrink-0" />
              )}
              <span>{item.label}</span>
            </span>
          );
        }

        return (
          <button
            key={item.code}
            type="button"
            onClick={() => handleToggle(item.code)}
            aria-pressed={isAdded}
            className={`${sharedStyle} cursor-pointer hover:border-[#1b1717]`}
          >
            {isAdded ? (
              <Check size={11} weight="bold" className="text-emerald-700 shrink-0" />
            ) : (
              <Minus size={11} weight="bold" className="text-[#8e8e93] shrink-0" />
            )}
            <span>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
