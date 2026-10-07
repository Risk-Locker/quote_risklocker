"use client";

import { useState } from "react";
import {
  ArrowsClockwise,
  ArrowSquareOut,
  CheckCircle,
  Info,
  Sparkle,
  Warning,
  WarningCircle,
  WarningOctagon,
} from "@phosphor-icons/react";
import { Tooltip } from "@/components/ui/tooltip";
import { api } from "@/lib/api";

export type GeminiQuota = {
  active?: boolean;
  status?: "ready" | "denied" | "rate_limited" | "invalid_key" | "model_not_found" | "error" | "offline" | "untested";
  status_label?: string;
  status_color?: "green" | "red" | "amber" | "gray";
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
  tokens_total?: number;
  tokens_prompt?: number;
  tokens_candidate?: number;
  successful_calls?: number;
  failed_calls?: number;
  last_error?: string;
  last_error_code?: number;
  last_error_at?: string;
  last_success_at?: string;
  last_probed_at?: string;
  message?: string;
  troubleshooting?: {
    title?: string;
    description?: string;
    cause?: string;
    action?: string;
    steps?: string[];
    recharge_url?: string;
    cloud_billing_url?: string;
  };
};

export function GeminiQuotaTooltipContent({
  quota,
  onProbeResult,
}: {
  quota?: GeminiQuota | null;
  onProbeResult?: (updated: GeminiQuota) => void;
}) {
  const [probing, setProbing] = useState(false);
  const [probeMessage, setProbeMessage] = useState<string | null>(null);

  const status = quota?.status || (quota?.active ? "ready" : "offline");
  const count = quota?.key_count ?? quota?.keys_count ?? 0;
  const model = quota?.model || "gemini-3.1-flash-lite-preview";
  const rpdRemaining = quota?.rpd_remaining ?? (count * 1500);
  const rpdLimit = quota?.rpd_limit ?? quota?.total_rpd ?? (count * 1500);
  const tokensTotal = quota?.tokens_total ?? 0;

  async function handleProbe() {
    setProbing(true);
    setProbeMessage(null);
    try {
      const res = await api<{ gemini: GeminiQuota }>("/settings/gemini/probe", { method: "POST" });
      if (res?.gemini) {
        onProbeResult?.(res.gemini);
        setProbeMessage(res.gemini.status === "ready" ? "Live Verified: HTTP 200 OK" : `Status: ${res.gemini.status_label || res.gemini.status}`);
      }
    } catch (err) {
      setProbeMessage(err instanceof Error ? err.message : "Probe failed");
    } finally {
      setProbing(false);
    }
  }

  if (status === "offline" || count === 0) {
    return (
      <div className="w-72 p-2 text-xs grid gap-2">
        <div className="flex items-center justify-between border-b border-gray-700 pb-1.5">
          <span className="font-bold text-white flex items-center gap-1.5">
            <Sparkle size={13} weight="fill" className="text-gray-400" />
            Gemini AI Engine
          </span>
          <span className="text-[10px] font-mono bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded-[4px] border border-gray-700">
            Offline
          </span>
        </div>
        <p className="text-gray-300 text-[11px] leading-relaxed">
          No <code className="font-mono text-amber-300">GEMINI_API_KEY</code> set in <code className="font-mono text-gray-200">.env</code>. Uploads will use offline deterministic regex fallback.
        </p>
        <a
          href="https://aistudio.google.com/apikey"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-1 text-[11px] font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded px-2 py-1 transition-colors mt-1"
        >
          Get Free Key at Google AI Studio
          <ArrowSquareOut size={12} />
        </a>
      </div>
    );
  }

  if (status === "denied" || quota?.last_error_code === 403) {
    return (
      <div className="w-80 p-2 text-xs grid gap-2">
        <div className="flex items-center justify-between border-b border-rose-900/60 pb-1.5">
          <span className="font-bold text-rose-300 flex items-center gap-1.5">
            <WarningOctagon size={14} weight="fill" className="text-rose-400" />
            Google AI Project Access Denied
          </span>
          <span className="text-[10px] font-mono bg-rose-950 text-rose-300 px-1.5 py-0.5 rounded-[4px] border border-rose-800 font-semibold">
            HTTP 403
          </span>
        </div>

        <div className="bg-rose-950/40 border border-rose-900/80 rounded p-2 text-[11px] text-rose-200">
          <p className="font-mono text-[10px] text-rose-300 break-words font-semibold">
            {quota?.last_error || "Your project has been denied access. Please contact support."}
          </p>
          <p className="mt-1.5 text-gray-300 text-[10px] leading-snug">
            Google has restricted or suspended this Google Cloud project. This is not a PDF format issue. Quotation uploads are temporarily using offline regex fallback.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-1.5 pt-1">
          <a
            href="https://aistudio.google.com/apikey"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1 text-[10px] font-semibold bg-white/10 hover:bg-white/20 text-white rounded px-2 py-1 transition-colors text-center"
          >
            Create New Key
            <ArrowSquareOut size={11} />
          </a>
          <a
            href="https://console.cloud.google.com/billing"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1 text-[10px] font-semibold bg-white/10 hover:bg-white/20 text-white rounded px-2 py-1 transition-colors text-center"
          >
            Check Billing
            <ArrowSquareOut size={11} />
          </a>
        </div>

        <button
          type="button"
          onClick={handleProbe}
          disabled={probing}
          className="inline-flex items-center justify-center gap-1 text-[11px] font-medium bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white rounded px-2 py-1 transition-colors mt-0.5 cursor-pointer"
        >
          <ArrowsClockwise size={12} className={probing ? "animate-spin" : ""} />
          {probing ? "Testing live key..." : "Test Key Connection"}
        </button>
        {probeMessage && <p className="text-[10px] font-mono text-rose-300 text-center">{probeMessage}</p>}
      </div>
    );
  }

  if (status === "rate_limited" || quota?.last_error_code === 429) {
    return (
      <div className="w-80 p-2 text-xs grid gap-2">
        <div className="flex items-center justify-between border-b border-amber-900/60 pb-1.5">
          <span className="font-bold text-amber-300 flex items-center gap-1.5">
            <Warning size={14} weight="fill" className="text-amber-400" />
            Gemini Rate Limited
          </span>
          <span className="text-[10px] font-mono bg-amber-950 text-amber-300 px-1.5 py-0.5 rounded-[4px] border border-amber-800 font-semibold">
            HTTP 429
          </span>
        </div>

        <div className="bg-amber-950/40 border border-amber-900/80 rounded p-2 text-[11px] text-amber-200">
          <p className="text-[10px] text-amber-300 leading-snug">
            Free tier rate limit reached (15 RPM or 1,500 requests/day). Add a secondary key to GEMINI_API_KEYS for automatic failover.
          </p>
        </div>

        <button
          type="button"
          onClick={handleProbe}
          disabled={probing}
          className="inline-flex items-center justify-center gap-1 text-[11px] font-medium bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded px-2 py-1 transition-colors mt-0.5 cursor-pointer"
        >
          <ArrowsClockwise size={12} className={probing ? "animate-spin" : ""} />
          {probing ? "Probing quota..." : "Re-Check Quota"}
        </button>
      </div>
    );
  }

  return (
    <div className="w-72 p-2 text-xs grid gap-2">
      <div className="flex items-center justify-between border-b border-gray-700 pb-1.5">
        <span className="font-bold text-white flex items-center gap-1.5">
          <Sparkle size={13} weight="fill" className="text-amber-400" />
          Gemini Multimodal AI
        </span>
        <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-1.5 py-0.5 rounded-[4px] border border-emerald-800 flex items-center gap-1 font-semibold">
          <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Live Verified
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[11px] bg-gray-900/60 rounded-[var(--rl-radius-sm)] p-2 border border-gray-800">
        <div>
          <span className="text-gray-400 block text-[10px]">Active Keys</span>
          <span className="font-mono text-gray-200 font-semibold">{count} Key{count > 1 ? "s" : ""} Loaded</span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">Daily Free Quota</span>
          <span className="font-mono text-emerald-400 font-semibold">{rpdRemaining.toLocaleString()} / {rpdLimit.toLocaleString()} RPD</span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">Tokens Consumed</span>
          <span className="font-mono text-gray-200 font-semibold">{tokensTotal.toLocaleString()} tokens</span>
        </div>
        <div>
          <span className="text-gray-400 block text-[10px]">Minute Rate</span>
          <span className="font-mono text-emerald-400 font-semibold">15 RPM / Key</span>
        </div>
        <div className="col-span-2">
          <span className="text-gray-400 block text-[10px]">Active Engine Model</span>
          <span className="font-mono text-gray-100 font-medium truncate block">{model}</span>
        </div>
      </div>

      <button
        type="button"
        onClick={handleProbe}
        disabled={probing}
        className="inline-flex items-center justify-center gap-1 text-[11px] font-medium bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 rounded px-2 py-1 transition-colors mt-0.5 cursor-pointer border border-gray-700"
      >
        <ArrowsClockwise size={12} className={probing ? "animate-spin" : ""} />
        {probing ? "Testing live key..." : "Test Connection"}
      </button>
      {probeMessage && <p className="text-[10px] font-mono text-emerald-400 text-center">{probeMessage}</p>}
    </div>
  );
}

export function GeminiQuotaInfoButton({
  quota,
  onProbeResult,
}: {
  quota?: GeminiQuota | null;
  onProbeResult?: (updated: GeminiQuota) => void;
}) {
  const isError = quota?.status === "denied" || (quota?.last_error_code && quota.last_error_code >= 400);

  return (
    <Tooltip content={<GeminiQuotaTooltipContent quota={quota} onProbeResult={onProbeResult} />}>
      <button
        type="button"
        aria-label="View Gemini AI connection status and active model"
        className={`inline-flex size-5 items-center justify-center rounded-[var(--rl-radius-sm)] transition-colors cursor-pointer ${
          isError
            ? "text-rose-500 hover:bg-rose-50 hover:text-rose-600"
            : "text-[var(--rl-text-muted)] hover:bg-black/5 hover:text-[var(--rl-text-strong)]"
        }`}
      >
        {isError ? <WarningCircle size={16} weight="bold" /> : <Info size={15} weight="bold" />}
      </button>
    </Tooltip>
  );
}

