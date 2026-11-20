"use client";

import { useEffect, useState } from "react";
import { Check, Infinity as InfinityIcon, MapPin, Money, Prohibit } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type TowingMode = "rm" | "km" | "unlimited" | "none";

const RM_PRESETS = ["RM 100", "RM 200", "RM 300", "RM 400", "RM 500", "RM 600"];
const KM_PRESETS = ["50 km", "100 km", "150 km", "200 km", "300 km", "365 km"];

export interface TowingLimitSelectorProps {
  value: string;
  onChange: (nextValue: string) => void;
  disabled?: boolean;
  compact?: boolean;
}

function parseTowingMode(raw: string): { mode: TowingMode; numberStr: string } {
  const s = (raw || "").trim();
  if (/^(?:0(?:\.0+)?|(?:rm|myr)\s*0(?:\.0+)?|0(?:\.0+)?\s*km|no\s*towing|without\s*towing|not\s*included|none|no|tiada|nil)$/i.test(s)) {
    return { mode: "none", numberStr: "0" };
  }
  const rmMatch = s.match(/^(?:rm|myr)\s*([\d,]+)/i);
  if (rmMatch) {
    const cleanNum = rmMatch[1].replace(/,/g, "");
    if (Number(cleanNum) <= 0) return { mode: "none", numberStr: "0" };
    return { mode: "rm", numberStr: cleanNum };
  }
  const kmMatch = s.match(/^(\d+)\s*km\b/i);
  if (kmMatch) {
    if (Number(kmMatch[1]) <= 0) return { mode: "none", numberStr: "0" };
    return { mode: "km", numberStr: kmMatch[1] };
  }
  return { mode: "unlimited", numberStr: "" };
}

/**
 * 3-mode towing limit picker: RM (cash), KM (distance), or Unlimited.
 * Uses uniform --rl-radius-sm controls without forcing underwriter defaults.
 */
export function TowingLimitSelector({
  value,
  onChange,
  disabled = false,
  compact = false,
}: TowingLimitSelectorProps) {
  const parsed = parseTowingMode(value);
  const [mode, setMode] = useState<TowingMode>(parsed.mode);
  const [customNum, setCustomNum] = useState<string>(parsed.numberStr);

  useEffect(() => {
    const next = parseTowingMode(value);
    setMode(next.mode);
    setCustomNum(next.numberStr);
  }, [value]);

  const handleModeSwitch = (nextMode: TowingMode) => {
    if (disabled) return;
    setMode(nextMode);
    if (nextMode === "none") {
      setCustomNum("0");
      onChange("No towing");
      return;
    }
    if (nextMode === "unlimited") {
      setCustomNum("");
      onChange("Unlimited");
      return;
    }
    if (nextMode === "rm") {
      const seed = parseTowingMode(value).mode === "rm" && customNum && Number(customNum) > 0 ? customNum : "200";
      setCustomNum(seed);
      onChange(`RM ${seed}`);
      return;
    }
    const seed = parseTowingMode(value).mode === "km" && customNum && Number(customNum) > 0 ? customNum : "100";
    setCustomNum(seed);
    onChange(`${seed} km`);
  };

  const handleCustomSubmit = () => {
    const digits = customNum.replace(/[^\d]/g, "");
    if (!digits) return;
    if (Number(digits) === 0) {
      setMode("none");
      onChange("No towing");
      return;
    }
    if (mode === "rm") {
      onChange(`RM ${digits}`);
    } else if (mode === "km") {
      onChange(`${digits} km`);
    }
  };

  const tabBtnClass = (active: boolean) =>
    `flex-1 inline-flex items-center justify-center gap-1.5 rounded-[var(--rl-radius-sm)] border px-2.5 ${
      compact ? "min-h-[28px] text-[11px]" : "min-h-[32px] text-[12px]"
    } font-semibold transition-colors cursor-pointer ${
      active
        ? "bg-[#1b1717] text-white border-[#1b1717]"
        : "bg-[#ffffff] text-[#1b1717] border-[#e5e5ea] hover:bg-[#f5f5f7]"
    }`;

  const presetBtnClass = (active: boolean) =>
    `rounded-[var(--rl-radius-sm)] border px-2.5 ${
      compact ? "min-h-[26px] text-[11px]" : "min-h-[30px] text-[12px]"
    } font-semibold transition-colors cursor-pointer ${
      active
        ? "bg-[#1b1717] text-white border-[#1b1717]"
        : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea] hover:bg-[#ebebef]"
    }`;

  return (
    <div className="space-y-2">
      {/* Mode selector: strictly RM / KM / Unlimited */}
      <div className="flex items-center gap-1.5" role="tablist" aria-label="Towing limit format">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "rm"}
          disabled={disabled}
          onClick={() => handleModeSwitch("rm")}
          className={tabBtnClass(mode === "rm")}
        >
          <Money size={13} weight="bold" />
          RM (Cash)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "km"}
          disabled={disabled}
          onClick={() => handleModeSwitch("km")}
          className={tabBtnClass(mode === "km")}
        >
          <MapPin size={13} weight="bold" />
          KM (Dist.)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "unlimited"}
          disabled={disabled}
          onClick={() => handleModeSwitch("unlimited")}
          className={tabBtnClass(mode === "unlimited")}
        >
          <InfinityIcon size={13} weight="bold" />
          Unlimited
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "none"}
          disabled={disabled}
          onClick={() => handleModeSwitch("none")}
          className={tabBtnClass(mode === "none")}
          title="No towing / 0 coverage"
        >
          <Prohibit size={13} weight="bold" />
          No (0)
        </button>
      </div>

      {mode === "rm" && (
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-1.5">
            {RM_PRESETS.map((preset) => {
              const normPreset = preset.toLowerCase();
              const isSelected = (value || "").trim().toLowerCase() === normPreset;
              return (
                <button
                  key={preset}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    setCustomNum(preset.replace(/[^\d]/g, ""));
                    onChange(preset);
                  }}
                  className={presetBtnClass(isSelected)}
                >
                  {preset}
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold text-[#6e6e73] shrink-0">RM</span>
            <Input
              type="number"
              min={0}
              step={50}
              disabled={disabled}
              placeholder="Custom RM (0 = No towing)"
              value={customNum}
              onChange={(e) => {
                setCustomNum(e.target.value);
                const digits = e.target.value.replace(/[^\d]/g, "");
                if (digits && Number(digits) > 0) {
                  onChange(`RM ${digits}`);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleCustomSubmit();
                }
              }}
              className="h-8 text-[12px] font-mono rounded-[var(--rl-radius-sm)]"
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled || !customNum}
              onClick={handleCustomSubmit}
              className="shrink-0"
            >
              Set
            </Button>
          </div>
        </div>
      )}

      {mode === "km" && (
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-1.5">
            {KM_PRESETS.map((preset) => {
              const normPreset = preset.toLowerCase();
              const isSelected = (value || "").trim().toLowerCase() === normPreset;
              return (
                <button
                  key={preset}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    setCustomNum(preset.replace(/[^\d]/g, ""));
                    onChange(preset);
                  }}
                  className={presetBtnClass(isSelected)}
                >
                  {preset}
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-1.5">
            <Input
              type="number"
              min={0}
              step={10}
              disabled={disabled}
              placeholder="Custom KM (0 = No towing)"
              value={customNum}
              onChange={(e) => {
                setCustomNum(e.target.value);
                const digits = e.target.value.replace(/[^\d]/g, "");
                if (digits && Number(digits) > 0) {
                  onChange(`${digits} km`);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleCustomSubmit();
                }
              }}
              className="h-8 text-[12px] font-mono rounded-[var(--rl-radius-sm)]"
            />
            <span className="text-[11px] font-bold text-[#6e6e73] shrink-0">KM</span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled || !customNum}
              onClick={handleCustomSubmit}
              className="shrink-0"
            >
              Set
            </Button>
          </div>
        </div>
      )}

      {mode === "unlimited" && (
        <div className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-emerald-200 bg-emerald-50/70 px-2.5 py-2 text-[11px] font-semibold text-emerald-800">
          <Check size={13} weight="bold" className="shrink-0" />
          <span>Unlimited emergency towing coverage selected</span>
        </div>
      )}

      {mode === "none" && (
        <div className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-amber-200 bg-amber-50/70 px-2.5 py-2 text-[11px] font-semibold text-amber-900">
          <Prohibit size={13} weight="bold" className="shrink-0" />
          <span>No towing coverage (0 / Not Included)</span>
        </div>
      )}
    </div>
  );
}
