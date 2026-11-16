"use client";

import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  CheckCircle,
  Cpu,
  Lightning,
  Prohibit,
  Sparkle,
  Star,
  WarningCircle,
} from "@phosphor-icons/react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import type { GeminiQuotaStats } from "@/components/gemini-header-meter";

interface EligibleModelItem {
  id: string;
  display_name: string;
  rpd_limit: number;
  rpm_limit: number;
  tpm_limit: number;
  description?: string;
  is_recommended?: boolean;
  is_active?: boolean;
  is_primary?: boolean;
}

interface BannedModelItem {
  id: string;
  display_name: string;
  reason: string;
}

interface EligibleModelsResponse {
  ok: boolean;
  source?: string;
  probe_error?: string | null;
  primary_model: string;
  parallel_models: string[];
  eligible_models: EligibleModelItem[];
  banned_models: BannedModelItem[];
}

const FALLBACK_MODELS: EligibleModelItem[] = [
  {
    id: "gemini-3.1-flash-lite",
    display_name: "Gemini 3.1 Flash-Lite",
    rpd_limit: 480,
    rpm_limit: 13,
    tpm_limit: 200000,
    is_recommended: true,
    description: "Standard high-capacity extraction tier (480 RPD, 13 RPM, 200k TPM).",
  },
  {
    id: "gemini-3.5-flash-lite",
    display_name: "Gemini 3.5 Flash-Lite",
    rpd_limit: 480,
    rpm_limit: 13,
    tpm_limit: 200000,
    is_recommended: true,
    description: "Next-gen high-capacity extraction tier with deeper clause comprehension.",
  },
];

export function GeminiModelSwitcher({ onConfigChanged }: { onConfigChanged?: (stats?: GeminiQuotaStats) => void }) {
  const [primaryModel, setPrimaryModel] = useState<string>("gemini-3.1-flash-lite");
  const [parallelModels, setParallelModels] = useState<string[]>(["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]);
  const [eligibleModels, setEligibleModels] = useState<EligibleModelItem[]>(FALLBACK_MODELS);
  const [bannedModels, setBannedModels] = useState<BannedModelItem[]>([
    {
      id: "gemini-3.8-flash",
      display_name: "Gemini 3.8 Flash",
      reason: "Exhaustion risk: Google AI Studio restricts to 20 RPD cap.",
    },
  ]);
  const [catalogSource, setCatalogSource] = useState<string>("canonical_registry");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  async function loadConfig() {
    setLoading(true);
    try {
      const res = await api<EligibleModelsResponse>("/settings/gemini/eligible-models");
      if (res && res.ok) {
        setPrimaryModel(res.primary_model || "gemini-3.1-flash-lite");
        setParallelModels(res.parallel_models || ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]);
        if (res.eligible_models && res.eligible_models.length > 0) {
          setEligibleModels(res.eligible_models);
        }
        if (res.banned_models) {
          setBannedModels(res.banned_models);
        }
        if (res.source) {
          setCatalogSource(res.source);
        }
      }
    } catch {
      // Keep fallbacks
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConfig();
  }, []);

  async function updateConfig(newPrimary: string, newParallel: string[]) {
    if (newParallel.length === 0) {
      toast("At least one model must remain active in the fleet pool.", "warning");
      return;
    }
    const safePrimary = newParallel.includes(newPrimary) ? newPrimary : newParallel[0];

    setSaving(true);
    try {
      const res = await api<{ ok: boolean; primary_model: string; parallel_models: string[]; gemini?: GeminiQuotaStats }>(
        "/settings/gemini/model-config",
        {
          method: "POST",
          body: JSON.stringify({
            primary_model: safePrimary,
            parallel_models: newParallel,
          }),
        }
      );
      if (res?.ok) {
        setPrimaryModel(res.primary_model);
        setParallelModels(res.parallel_models);
        toast(`AI Fleet Model updated: ${res.primary_model} is Primary. ${res.parallel_models.length} model(s) active.`, "success");
        if (onConfigChanged) onConfigChanged(res.gemini);
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to save model configuration.", "error");
    } finally {
      setSaving(false);
    }
  }

  function handleToggleModel(modelName: string, active: boolean) {
    let nextList: string[];
    if (active) {
      nextList = Array.from(new Set([...parallelModels, modelName]));
    } else {
      nextList = parallelModels.filter((m) => m !== modelName);
    }
    updateConfig(primaryModel, nextList);
  }

  function handleSetPrimary(modelName: string) {
    if (!parallelModels.includes(modelName)) {
      updateConfig(modelName, [...parallelModels, modelName]);
    } else {
      updateConfig(modelName, parallelModels);
    }
  }

  return (
    <Card className="p-5 border border-[var(--rl-border)] bg-white shadow-xs grid gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
        <div>
          <h2 className="text-sm font-bold text-[var(--rl-text-strong)] flex items-center gap-2">
            <Cpu size={16} weight="fill" className="text-emerald-600" />
            Dynamic Gemini Model Discovery & Quota Pool
          </h2>
          <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
            Real-time qualified models matching Google AI Studio throughput standards (≥13 RPM, ≥200k TPM, ≥480 RPD).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge
            variant={catalogSource === "google_ai_studio_live" ? "success" : "info"}
            className="text-[10px] font-mono"
          >
            {catalogSource === "google_ai_studio_live" ? "Google AI Studio Live" : "Verified Registry"}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            loading={loading}
            onClick={loadConfig}
            className="h-7 px-2 text-xs text-gray-600 hover:text-gray-900"
          >
            <ArrowsClockwise size={13} className={loading ? "animate-spin" : ""} />
            <span className="ml-1">Refresh</span>
          </Button>
        </div>
      </div>

      {/* Model Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {eligibleModels.map((m) => {
          const isPrimary = primaryModel === m.id;
          const isParallel = parallelModels.includes(m.id);

          return (
            <div
              key={m.id}
              className={`rounded-lg border p-4 transition-all ${
                isPrimary
                  ? "border-emerald-500 bg-emerald-50/20 shadow-xs ring-1 ring-emerald-500/30"
                  : isParallel
                  ? "border-[var(--rl-border)] bg-white hover:border-gray-300"
                  : "border-dashed border-gray-300 bg-gray-50/60 opacity-75"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-[var(--rl-text-strong)]">{m.display_name}</span>
                    {m.is_recommended && (
                      <Badge variant="success" className="text-[10px]">
                        Production Tier
                      </Badge>
                    )}
                  </div>
                  <span className="text-xs font-mono text-gray-500 block mt-0.5">{m.id}</span>
                </div>

                <div className="flex items-center gap-1.5">
                  {isPrimary && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                      <Star size={12} weight="fill" /> Primary
                    </span>
                  )}
                </div>
              </div>

              <p className="text-xs text-[var(--rl-text-muted)] mt-2 leading-relaxed">
                {m.description || "Qualified Flash-Lite high-throughput quotation extraction model."}
              </p>

              {/* Specs pill */}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] font-mono text-[var(--rl-text-muted)] bg-[var(--rl-bg)] p-2 rounded border border-[var(--rl-border)]">
                <span className="font-bold text-[var(--rl-text-strong)]">{m.rpd_limit} RPD safe cap</span>
                <span>&bull;</span>
                <span>{m.rpm_limit} RPM burst</span>
                <span>&bull;</span>
                <span>{Math.round(m.tpm_limit / 1000)}k TPM token ceiling</span>
              </div>

              {/* Controls */}
              <div className="mt-4 pt-3 border-t border-[var(--rl-border)] flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Toggle
                    checked={isParallel}
                    onChange={(checked) => handleToggleModel(m.id, checked)}
                    label={isParallel ? "Active in Pool" : "Inactive (Off)"}
                    description="Include in round-robin worker requests"
                  />
                </div>

                {!isPrimary && isParallel && (
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={saving}
                    onClick={() => handleSetPrimary(m.id)}
                    className="text-xs text-gray-700 hover:text-emerald-700"
                  >
                    Set as Primary
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Safety Notice on Banned Preview / High-Risk Models */}
      <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 grid gap-2 text-xs text-gray-600">
        <div className="flex items-start gap-2.5">
          <Prohibit size={16} weight="bold" className="text-gray-500 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-gray-800">Enforced Quota Isolation:</span>{" "}
            Models below 480 RPD or unverified preview branches are blocked from the automated pipeline to protect multi-vehicle fleet batches from rate-limit exhaustion.
          </div>
        </div>

        {bannedModels.length > 0 && (
          <div className="ml-6 space-y-1">
            {bannedModels.map((b) => (
              <div key={b.id} className="flex items-center gap-2 font-mono text-[11px]">
                <code className="bg-red-50 text-red-700 border border-red-200 px-1.5 py-0.5 rounded">{b.id}</code>
                <span className="text-gray-500">&mdash; {b.reason}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
