"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ArrowSquareOut } from "@phosphor-icons/react";

const STORAGE_KEY = "rl_pref_open_in_new_tab";
const CUSTOM_EVENT = "rl-open-new-tab-pref";

export function useOpenInNewTabPreference() {
  const [openInNewTab, setOpenInNewTabState] = useState<boolean>(false);

  useEffect(() => {
    try {
      setOpenInNewTabState(window.localStorage.getItem(STORAGE_KEY) === "true");
    } catch {
      // Ignore storage restrictions
    }
    const sync = () => {
      try {
        setOpenInNewTabState(window.localStorage.getItem(STORAGE_KEY) === "true");
      } catch {
        // Ignore
      }
    };
    window.addEventListener("storage", sync);
    window.addEventListener(CUSTOM_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(CUSTOM_EVENT, sync);
    };
  }, []);

  const setOpenInNewTab = useCallback((next: boolean) => {
    setOpenInNewTabState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "true" : "false");
      window.dispatchEvent(new Event(CUSTOM_EVENT));
    } catch {
      // Ignore storage restrictions
    }
  }, []);

  return { openInNewTab, setOpenInNewTab };
}

export function openTargetRoute(
  url: string,
  options: {
    openInNewTab: boolean;
    router?: { push: (href: any) => void };
    onBlocked?: (blockedUrl: string) => void;
  }
): boolean {
  if (options.openInNewTab) {
    const win = window.open(url, "_blank", "noopener,noreferrer");
    if (!win) {
      options.onBlocked?.(url);
      return false;
    }
    return true;
  }
  if (options.router) {
    options.router.push(url);
  } else {
    window.location.assign(url);
  }
  return true;
}

export function OpenInNewTabToggle({
  checked,
  onChange,
  label = "Open in new tab",
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: string;
}) {
  return (
    <label
      className={`inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[var(--rl-radius-sm)] border text-xs font-semibold transition-colors cursor-pointer select-none ${
        checked
          ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white"
          : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:bg-neutral-50"
      }`}
      title="Automatically open sessions & comparison pages in a new browser tab"
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="sr-only"
      />
      <ArrowSquareOut size={13} weight="bold" />
      <span>{label}</span>
    </label>
  );
}
