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
          No GEMINI_API_KEY configured in .env. Add your free Google AI Studio key to activate multimodal extraction.
        </p>
      </div>
    );
  }

  const count = quota.key_count ?? quota.keys_count ?? 1;
  const model = quota.model || "gemini-3.1-flash-lite-preview";
  const rpdLimit = quota.rpd_limit ?? (count * 1500);
  const rpdUsed = quota.rpd_used ?? 0;
  const rpdRemaining = quota.rpd_remaining ?? Math.max(0, rpdLimit - rpdUsed);
  const pctRemaining = quota.percent_rpd_remaining ?? (rpdLimit > 0 ? Math.round((rpdRemaining / rpdLimit) * 100) : 100);
  const rpmLimit = quota.rpm_limit ?? (count * 15);

  return (
    <div className="w-64 p-1.5 text-xs grid gap-2.5">
      <div className="flex items-center justify-between border-b border-gray-700 pb-1.5">
        <span className="font-bold text-white flex items-center gap-1.5">
          <Sparkle size={13} weight="fill" className="text-amber-400" />
          Google Gemini AI Quota
        </span>
        <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-1.5 py-0.5 rounded-[4px] border border-emerald-800">
          Free Tier
        </span>
      </div>

      <div className="grid gap-1">
        <div className="flex justify-between text-[11px]">
          <span className="text-gray-400">Daily Requests (RPD):</span>
          <span className="font-mono font-bold text-white">
            {rpdRemaining.toLocaleString()} / {rpdLimit.toLocaleString()} left
          </span>
        </div>
        <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-400 rounded-full transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, pctRemaining))}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px] bg-gray-900/60 rounded-[var(--rl-radius-sm)] p-2 border border-gray-800">
        <div>
          <span className="text-gray-400 block text-[10px]">Speed / Rate Limit</span>
          <span className="font-mono text-gray-200 font-semibold">{rpmLimit} RPM</span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">Key Pool</span>
          <span className="font-mono text-gray-200 font-semibold">{count} Key{count > 1 ? "s" : ""} Active</span>
        </div>
        <div className="col-span-2">
          <span className="text-gray-400 block text-[10px]">Active Model</span>
          <span className="font-mono text-emerald-400 font-medium truncate block">{model}</span>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 leading-tight">
        Quota automatically resets every 24 hours at 00:00 UTC. Multi-key pool distributes requests evenly.
      </p>
    </div>
  );
}

export function GeminiQuotaInfoButton({ quota }: { quota?: GeminiQuota | null }) {
  return (
    <Tooltip content={<GeminiQuotaTooltipContent quota={quota} />}>
      <button
        type="button"
        aria-label="View Gemini AI quota status and remaining requests"
        className="inline-flex size-5 items-center justify-center rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:bg-black/5 hover:text-[var(--rl-text-strong)] transition-colors cursor-pointer"
      >
        <Info size={15} weight="bold" />
      </button>
    </Tooltip>
  );
}
