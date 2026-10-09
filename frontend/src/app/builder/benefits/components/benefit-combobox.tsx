"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { CaretDown, Check, MagnifyingGlass, X } from "@phosphor-icons/react";
import type { ConceptSummary as Concept } from "@/types/benefits";

interface BenefitComboboxProps {
  concepts: Concept[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function BenefitCombobox({
  concepts,
  value,
  onChange,
  placeholder = "-- Select Benefit --",
  disabled = false,
}: BenefitComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  // Focus search input on open
  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    } else {
      setSearch("");
    }
  }, [open]);

  const selectedConcept = useMemo(() => {
    return concepts.find((c) => c.id === value) || null;
  }, [concepts, value]);

  // Alphabetically sorted and filtered concepts
  const filteredConcepts = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...concepts].sort((a, b) =>
      (a.label || "").localeCompare(b.label || "", undefined, { sensitivity: "base" })
    );
    if (!q) return sorted;
    return sorted.filter((c) => {
      const labelMatch = (c.label || "").toLowerCase().includes(q);
      const keyMatch = (c.concept_key || "").toLowerCase().includes(q);
      const descMatch = (c.description || "").toLowerCase().includes(q);
      return labelMatch || keyMatch || descMatch;
    });
  }, [concepts, search]);

  return (
    <div className="relative w-full" ref={containerRef}>
      {/* Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
        className={`flex w-full items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-3 py-2 text-left text-xs transition-colors hover:border-[var(--rl-border-strong)] focus:outline-none ${
          disabled ? "opacity-60 cursor-not-allowed" : "cursor-pointer"
        } ${open ? "border-[var(--rl-blue,#2563eb)] ring-1 ring-[var(--rl-blue,#2563eb)]" : ""}`}
      >
        <div className="flex-1 min-w-0">
          {selectedConcept ? (
            <div className="flex items-center gap-2 truncate">
              <span className="font-semibold text-[var(--rl-text-strong)] truncate">
                {selectedConcept.label}
              </span>
              <span className="text-[10px] font-mono text-[var(--rl-text-muted)] bg-[var(--rl-surface)] px-1.5 py-0.5 rounded border border-[var(--rl-border)] shrink-0">
                {selectedConcept.concept_key}
              </span>
            </div>
          ) : (
            <span className="text-[var(--rl-text-muted)]">{placeholder}</span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0 text-[var(--rl-text-muted)]">
          {selectedConcept && !disabled && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onChange("");
              }}
              className="p-0.5 hover:text-red-600 rounded"
              title="Clear selection"
            >
              <X size={13} />
            </button>
          )}
          <CaretDown size={14} className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`} />
        </div>
      </button>

      {/* Popover Menu */}
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-lg animate-in fade-in-50 zoom-in-95 duration-100">
          {/* Search Header */}
          <div className="p-2 border-b border-[var(--rl-border)] bg-[var(--rl-bg)]">
            <div className="relative flex items-center">
              <MagnifyingGlass size={14} className="absolute left-2.5 text-[var(--rl-text-muted)]" />
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search benefit name or key..."
                className="w-full rounded-[4px] border border-[var(--rl-border)] bg-[var(--rl-surface)] pl-8 pr-3 py-1.5 text-xs text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:outline-none focus:border-[var(--rl-blue,#2563eb)]"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-2 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Items List */}
          <div className="max-h-60 overflow-y-auto p-1 text-xs">
            {filteredConcepts.length === 0 ? (
              <div className="p-4 text-center text-xs text-[var(--rl-text-muted)]">
                No benefits match &quot;{search}&quot;
              </div>
            ) : (
              filteredConcepts.map((c) => {
                const isSelected = c.id === value;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      onChange(c.id);
                      setOpen(false);
                    }}
                    className={`flex w-full items-center justify-between gap-2 rounded px-2.5 py-1.5 text-left transition-colors ${
                      isSelected
                        ? "bg-blue-50 text-blue-900 font-semibold dark:bg-blue-950 dark:text-blue-100"
                        : "hover:bg-[var(--rl-bg)] text-[var(--rl-text-strong)]"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate">{c.label}</div>
                      <div className="text-[10px] font-mono text-[var(--rl-text-muted)] truncate">
                        {c.concept_key}
                      </div>
                    </div>
                    {isSelected && (
                      <Check size={14} weight="bold" className="text-blue-600 shrink-0" />
                    )}
                  </button>
                );
              })
            )}
          </div>

          {/* Footer with count */}
          <div className="px-3 py-1.5 border-t border-[var(--rl-border)] bg-[var(--rl-bg)] text-[10px] text-[var(--rl-text-muted)] flex items-center justify-between">
            <span>
              {filteredConcepts.length} of {concepts.length} benefits
            </span>
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="hover:underline text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              >
                Clear filter
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
