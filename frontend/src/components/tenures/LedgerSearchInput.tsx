"use client";

import React, { useState, useRef, useEffect } from "react";
import { MagnifyingGlass, X, Sparkle } from "@phosphor-icons/react";

export interface LedgerSearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

/**
 * Interactive expanding search capsule for the Motor Renewal Ledger.
 * - Smooth horizontal expansion animation on click / focus
 * - Instant clear button (✕) when text is present
 * - Keyboard shortcut listener: `/` or `⌘K` / `Ctrl+K` to focus
 * - Clear active / filtering indicators with zero server pressure
 * - Enforces minimum width so it is never squashed into a tiny button
 */
export function LedgerSearchInput({
  value,
  onChange,
  placeholder = "Search plate (e.g. JRC 3838), client, IC...",
  className = "",
}: LedgerSearchInputProps) {
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Global keyboard shortcut: `/` or `⌘K` / `Ctrl+K` to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement &&
        (document.activeElement.tagName === "INPUT" ||
          document.activeElement.tagName === "TEXTAREA" ||
          (document.activeElement as HTMLElement).isContentEditable)
      ) {
        return;
      }
      if (e.key === "/" || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k")) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const isExpanded = isFocused || Boolean(value.trim());

  const handleClear = () => {
    onChange("");
    inputRef.current?.focus();
  };

  return (
    <div
      role="search"
      className={`relative flex items-center transition-[width,box-shadow,border-color] duration-300 ease-out shrink-0 ${
        isExpanded
          ? "w-64 sm:w-80 md:w-96 ring-2 ring-neutral-900/10 border-neutral-900 bg-white shadow-xs"
          : "w-44 sm:w-56 md:w-64 border-neutral-200/90 hover:border-neutral-400 bg-white shadow-2xs"
      } h-9 rounded-[var(--rl-radius-sm)] border ${className}`}
    >
      {/* Search Icon */}
      <label
        htmlFor="ledger-search-input"
        className="pl-2.5 pr-1.5 flex items-center justify-center cursor-pointer text-neutral-400 hover:text-neutral-900 transition-colors shrink-0"
        title="Search ledger records"
      >
        <MagnifyingGlass
          size={15}
          weight={isExpanded ? "bold" : "regular"}
          className={`transition-colors ${isExpanded ? "text-neutral-900" : "text-neutral-400"}`}
        />
      </label>

      {/* Input Field */}
      <input
        ref={inputRef}
        id="ledger-search-input"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            if (value) {
              onChange("");
            } else {
              inputRef.current?.blur();
            }
          }
        }}
        placeholder={isExpanded ? placeholder : "Search plate, client..."}
        className="w-full h-full bg-transparent text-xs font-medium text-neutral-900 placeholder:text-neutral-400 outline-none pr-1.5"
        autoComplete="off"
        spellCheck="false"
      />

      {/* Right controls: Clear button OR Keyboard shortcut badge */}
      <div className="pr-2 flex items-center gap-1 shrink-0">
        {value ? (
          <button
            type="button"
            onClick={handleClear}
            className="p-1 rounded-full text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100 transition-colors cursor-pointer"
            title="Clear search (Esc)"
            aria-label="Clear search"
          >
            <X size={12} weight="bold" />
          </button>
        ) : (
          !isFocused && (
            <kbd
              onClick={() => inputRef.current?.focus()}
              className="hidden sm:inline-flex items-center justify-center text-[10px] font-mono text-neutral-400 bg-neutral-100/90 border border-neutral-200 px-1.5 py-0.5 rounded cursor-pointer hover:bg-neutral-200/80 transition-colors"
              title="Press / to search"
            >
              /
            </kbd>
          )
        )}
      </div>

      {/* Subtle indicator bar when active search is filtering */}
      {value.trim() && (
        <span
          className="absolute -bottom-px left-2 right-2 h-[2px] bg-amber-500 rounded-full animate-fade-in"
          title="Search filter active"
        />
      )}
    </div>
  );
}
