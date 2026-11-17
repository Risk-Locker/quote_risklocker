"use client";

import React, { useState, useRef, useEffect } from "react";
import { PencilSimple, Check, X, ArrowCounterClockwise } from "@phosphor-icons/react";

export type InlineEditableFieldKey =
  | "towing_limit"
  | "special_perils"
  | "llp_llop"
  | "excess"
  | "windscreen_sum_insured"
  | "notes";

interface InlineComparisonFieldEditorProps {
  field: InlineEditableFieldKey;
  label: string;
  currentValue: string | number | null | undefined;
  isOverridden?: boolean;
  disabled?: boolean;
  onSave: (patch: Record<string, any>) => Promise<void>;
  children: React.ReactNode;
}

const TOWING_PRESETS = ["Unlimited", "200 KM", "150 KM", "RM 500", "RM 400", "RM 300", "No Towing"];
const TOGGLE_PRESETS = ["Included", "Not Included"];

export function InlineComparisonFieldEditor({
  field,
  label,
  currentValue,
  isOverridden = false,
  disabled = false,
  onSave,
  children,
}: InlineComparisonFieldEditorProps) {
  const [open, setOpen] = useState(false);
  const [draftValue, setDraftValue] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (open) {
      const initStr =
        currentValue === null || currentValue === undefined
          ? field === "special_perils" || field === "llp_llop"
            ? "Not Included"
            : ""
          : String(currentValue);
      setDraftValue(initStr);
      setError(null);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 20);
    }
  }, [open, currentValue, field]);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const handleCommit = async (overrideVal?: string) => {
    const raw = (overrideVal !== undefined ? overrideVal : draftValue).trim();
    setError(null);

    if (field === "notes" && raw.length > 160) {
      setError("Notes must be 160 characters or fewer.");
      return;
    }
    if ((field === "special_perils" || field === "llp_llop") && raw.length > 50) {
      setError("Value must be 50 characters or fewer.");
      return;
    }
    if (field === "towing_limit" && raw.length > 100) {
      setError("Towing limit must be 100 characters or fewer.");
      return;
    }

    let payloadVal: string | number | null = raw;
    if (field === "excess" || field === "windscreen_sum_insured") {
      if (!raw || raw.toLowerCase() === "not included") {
        payloadVal = 0;
      } else {
        const parsed = parseFloat(raw.replace(/[^0-9.-]/g, ""));
        if (isNaN(parsed) || parsed < 0) {
          setError("Enter a valid non-negative amount.");
          return;
        }
        payloadVal = parsed;
      }
    }

    try {
      setSaving(true);
      await onSave({ [field]: payloadVal });
      setOpen(false);
    } catch (err: any) {
      setError(err?.message || "Failed to save override");
    } finally {
      setSaving(false);
    }
  };

  const handleRevert = async () => {
    try {
      setSaving(true);
      setError(null);
      await onSave({ clear_override_field: field });
      setOpen(false);
    } catch (err: any) {
      setError(err?.message || "Failed to revert override");
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleCommit();
    }
  };

  const isNumericField = field === "excess" || field === "windscreen_sum_insured";
  const isToggleField = field === "special_perils" || field === "llp_llop";
  const isTowingField = field === "towing_limit";

  return (
    <div className="relative inline-flex items-center gap-1 group max-w-full" ref={popoverRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        title={`Edit ${label}${isOverridden ? " (Manual override active)" : ""}`}
        className="inline-flex items-center gap-1 rounded px-1 -mx-1 py-0.5 hover:bg-[#f5f5f7] focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#1b1717] transition-colors cursor-pointer text-right"
      >
        {children}
        {isOverridden ? (
          <span className="ml-0.5 rounded-[4px] bg-amber-100 text-amber-900 border border-amber-300 px-1 py-0 text-[9px] font-bold uppercase tracking-tight shrink-0">
            Manual
          </span>
        ) : (
          <PencilSimple
            size={11}
            weight="bold"
            className="text-[#6e6e73] opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity shrink-0 no-print"
          />
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={`Edit ${label}`}
          onKeyDown={handleKeyDown}
          className="absolute right-0 top-full mt-1 z-50 w-60 rounded-[8px] border border-[#e5e5ea] bg-white p-2.5 shadow-lg text-left space-y-2 no-print"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-bold text-[#1b1717]">{label}</span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-[#6e6e73] hover:text-[#1b1717] p-0.5 rounded cursor-pointer"
              aria-label="Close inline editor"
            >
              <X size={12} weight="bold" />
            </button>
          </div>

          {isToggleField && (
            <div className="grid grid-cols-2 gap-1">
              {TOGGLE_PRESETS.map((opt) => {
                const active = draftValue.toLowerCase() === opt.toLowerCase();
                return (
                  <button
                    key={opt}
                    type="button"
                    disabled={saving}
                    onClick={() => handleCommit(opt)}
                    className={`px-2 py-1 rounded-[6px] text-[11px] font-semibold border transition-colors cursor-pointer ${
                      active
                        ? "bg-[#1b1717] text-white border-[#1b1717]"
                        : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea] hover:bg-[#e5e5ea]"
                    }`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          )}

          {isTowingField && (
            <div className="flex flex-wrap gap-1">
              {TOWING_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  disabled={saving}
                  onClick={() => handleCommit(preset)}
                  className={`px-1.5 py-0.5 rounded-[6px] text-[10px] font-semibold border transition-colors cursor-pointer ${
                    draftValue.toLowerCase() === preset.toLowerCase()
                      ? "bg-[#1b1717] text-white border-[#1b1717]"
                      : "bg-[#f5f5f7] text-[#1b1717] border-[#e5e5ea] hover:bg-[#e5e5ea]"
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-1">
            {field === "notes" ? (
              <textarea
                ref={(el) => {
                  inputRef.current = el;
                }}
                rows={2}
                maxLength={160}
                value={draftValue}
                onChange={(e) => setDraftValue(e.target.value)}
                placeholder="Enter note (max 160 chars)..."
                className="w-full rounded-[6px] border border-[#e5e5ea] bg-white px-2 py-1 text-xs text-[#1b1717] focus:border-[#1b1717] focus:outline-none"
              />
            ) : (
              <input
                ref={(el) => {
                  inputRef.current = el;
                }}
                type={isNumericField ? "number" : "text"}
                step={isNumericField ? "0.01" : undefined}
                min={isNumericField ? "0" : undefined}
                value={draftValue}
                onChange={(e) => setDraftValue(e.target.value)}
                placeholder={isNumericField ? "0.00" : `Custom ${label.toLowerCase()}...`}
                className="w-full rounded-[6px] border border-[#e5e5ea] bg-white px-2 py-1 text-xs text-[#1b1717] focus:border-[#1b1717] focus:outline-none"
              />
            )}
            <button
              type="button"
              disabled={saving}
              onClick={() => handleCommit()}
              title="Save (Enter)"
              className="shrink-0 rounded-[6px] bg-[#1b1717] text-white p-1.5 hover:bg-black disabled:opacity-50 cursor-pointer"
            >
              <Check size={12} weight="bold" />
            </button>
          </div>

          {error && <p className="text-[10px] font-semibold text-[#ed1c24]">{error}</p>}

          {isOverridden && (
            <button
              type="button"
              disabled={saving}
              onClick={handleRevert}
              className="w-full inline-flex items-center justify-center gap-1 rounded-[6px] border border-[#e5e5ea] bg-[#f5f5f7] px-2 py-1 text-[10px] font-semibold text-[#6e6e73] hover:text-[#1b1717] hover:bg-[#e5e5ea] cursor-pointer"
            >
              <ArrowCounterClockwise size={11} weight="bold" />
              <span>Revert to extracted</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
