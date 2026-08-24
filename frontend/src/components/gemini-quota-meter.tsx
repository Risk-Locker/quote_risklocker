"use client";

import { Info, Sparkle } from "@phosphor-icons/react";
import { Tooltip } from "@/components/ui/tooltip";

export type GeminiQuota = {
  active?: boolean;
  model?: string;
  key_count?: number;
  keys_count?: number;
  rpm_limit?: number;
  rpm_used?: number;
  rpm_remaining?: number;
  rpd_limit?: number;
  rpd_used?: number;
  rpd_remaining?: number;
  percent_rpd_remaining?: number;
  rpm_per_key?: number;
  rpd_per_key?: number;
  total_rpd?: number;
  message?: string;
};

export function GeminiQuotaTooltipContent({ quota }: { quota?: GeminiQuota | null }) {
  if (!quota || !quota.active) {
    return (
      <div className="w-56 p-1 text-xs">
        <p className="font-bold text-white flex items-center gap-1.5">
          <Sparkle size={13} weight="fill" className="text-amber-400" />
          Gemini AI Engine
        </p>
        <p className="mt-1 text-gray-300 text-[11px]">
          No GEMINI_API_KEY configured in .env. Add your Google AI Studio API key to activate deep AI extraction.
        </p>
      </div>
    );
  }

  const count = quota.key_count ?? quota.keys_count ?? 1;
  const model = quota.model || "gemini-3.1-flash-lite-preview";

  return (
    <div className="w-64 p-1.5 text-xs grid gap-2">
      <div className="flex items-center justify-between border-b border-gray-700 pb-1.5">
        <span className="font-bold text-white flex items-center gap-1.5">
          <Sparkle size={13} weight="fill" className="text-amber-400" />
          Gemini Multimodal AI
        </span>
        <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-1.5 py-0.5 rounded-[4px] border border-emerald-800 flex items-center gap-1">
          <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Connected
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px] bg-gray-900/60 rounded-[var(--rl-radius-sm)] p-2 border border-gray-800">
        <div>
          <span className="text-gray-400 block text-[10px]">Active Keys</span>
          <span className="font-mono text-gray-200 font-semibold">{count} Key{count > 1 ? "s" : ""} Loaded</span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">Key Rotation</span>
          <span className="font-mono text-emerald-400 font-semibold">Round-Robin</span>
        </div>
        <div className="col-span-2">
          <span className="text-gray-400 block text-[10px]">Active Engine Model</span>
          <span className="font-mono text-gray-100 font-medium truncate block">{model}</span>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 leading-tight">
        Authoritative extraction with live database grounding (insurers, catalogs, benefit concepts).
      </p>
    </div>
  );
}

export function GeminiQuotaInfoButton({ quota }: { quota?: GeminiQuota | null }) {
  return (
    <Tooltip content={<GeminiQuotaTooltipContent quota={quota} />}>
      <button
        type="button"
        aria-label="View Gemini AI connection status and active model"
        className="inline-flex size-5 items-center justify-center rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:bg-black/5 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
      >
        <Info size={15} weight="bold" />
      </button>
    </Tooltip>
  );
}
