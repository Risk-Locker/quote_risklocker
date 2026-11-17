"use client";

import { useEffect, useState } from "react";
import { Files, FloppyDisk, Info, ShieldCheck, Sparkle } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

export default function BuilderUploadsPage() {
  const [maxBulkFiles, setMaxBulkFiles] = useState("5");
  const [comparisonUnlimited, setComparisonUnlimited] = useState(true);
  const [comparisonLimit, setComparisonLimit] = useState("30");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { toast } = useToast();

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{
        max_bulk_upload_files: number;
        comparison_upload_limit?: number | null;
        min_allowed: number;
      }>("/admin/settings/upload-limits");
      if (data && typeof data.max_bulk_upload_files === "number") {
        setMaxBulkFiles(String(data.max_bulk_upload_files));
      }
      if (data && typeof data.comparison_upload_limit === "number" && data.comparison_upload_limit >= 1) {
        setComparisonUnlimited(false);
        setComparisonLimit(String(data.comparison_upload_limit));
      } else {
        setComparisonUnlimited(true);
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    const val = parseInt(maxBulkFiles, 10);
    if (isNaN(val) || val < 3) {
      setError("Bulk upload limit cannot be less than 3 PDFs.");
      return;
    }

    let compVal: number | null = null;
    if (!comparisonUnlimited) {
      const parsedComp = parseInt(comparisonLimit, 10);
      if (isNaN(parsedComp) || parsedComp < 1) {
        setError("Marketing Comparison upload limit must be at least 1 PDF, or set to Unlimited.");
        return;
      }
      compVal = parsedComp;
    }

    setSaving(true);
    setError("");
    try {
      const res = await api<{
        max_bulk_upload_files: number;
        comparison_upload_limit?: number | null;
      }>("/admin/settings/upload-limits", {
        method: "POST",
        body: JSON.stringify({
          max_bulk_upload_files: val,
          comparison_upload_limit: compVal,
        }),
      });
      setMaxBulkFiles(String(res.max_bulk_upload_files));
      if (typeof res.comparison_upload_limit === "number" && res.comparison_upload_limit >= 1) {
        setComparisonUnlimited(false);
        setComparisonLimit(String(res.comparison_upload_limit));
      } else {
        setComparisonUnlimited(true);
      }
      toast("Upload limits updated successfully.", "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <section className="grid w-full gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">
              Upload Limits & Settings
            </h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">
              Configure agency intake thresholds and bulk upload batch limits.
            </p>
          </div>
        </div>

        <BuilderNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        <div className="grid gap-6 sm:grid-cols-3">
          {/* Main Setting Card */}
          <Card className="grid gap-4 border border-[var(--rl-border)] bg-white p-5 shadow-xs sm:col-span-2">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--rl-red-light)] text-[var(--rl-red)]">
                  <Files size={20} weight="bold" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Bulk Upload Limit</h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">Maximum PDFs allowed per batch drag-and-drop</p>
                </div>
              </div>
              <Badge variant="success">Active</Badge>
            </div>

            <form onSubmit={handleSave} className="grid gap-4">
              <div className="grid gap-2">
                <label htmlFor="maxBulkFiles" className="text-xs font-semibold text-[var(--rl-text-strong)]">
                  Maximum PDFs per Bulk Upload
                </label>
                <div className="flex max-w-xs items-center gap-2">
                  <Input
                    id="maxBulkFiles"
                    type="number"
                    min={3}
                    step={1}
                    value={maxBulkFiles}
                    disabled={loading || saving}
                    onChange={(e) => setMaxBulkFiles(e.target.value)}
                    className="font-mono text-sm"
                  />
                  <span className="text-xs font-medium text-[var(--rl-text-muted)]">PDFs</span>
                </div>
                <p className="text-[12px] text-[var(--rl-text-muted)]">
                  Agency staff can drag and drop up to this number of quotation PDFs simultaneously on the Corporate Fleet Upload page. Minimum allowed limit is <strong>3</strong>.
                </p>
              </div>

              <div className="grid gap-2 border-t border-[var(--rl-border)] pt-4">
                <label className="text-xs font-semibold text-[var(--rl-text-strong)]">
                  Marketing Comparison Queue Limit
                </label>
                <label className="inline-flex items-center gap-2 text-xs font-medium text-[var(--rl-text-strong)] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={comparisonUnlimited}
                    disabled={loading || saving}
                    onChange={(e) => setComparisonUnlimited(e.target.checked)}
                    className="h-4 w-4 rounded border-[var(--rl-border)] accent-[#1b1717]"
                  />
                  <span>Unlimited Marketing Comparison Queue (Default — processed via server fair-share queue)</span>
                </label>
                {!comparisonUnlimited && (
                  <div className="flex max-w-xs items-center gap-2 mt-1">
                    <Input
                      id="comparisonLimit"
                      type="number"
                      min={1}
                      step={1}
                      value={comparisonLimit}
                      disabled={loading || saving}
                      onChange={(e) => setComparisonLimit(e.target.value)}
                      className="font-mono text-sm"
                    />
                    <span className="text-xs font-medium text-[var(--rl-text-muted)]">PDFs Max</span>
                  </div>
                )}
                <p className="text-[12px] text-[var(--rl-text-muted)]">
                  When set to <strong>Unlimited</strong>, staff can stage any number of insurer quotation PDFs for a vehicle without a 30-PDF cap; the server fair-share queue paces extraction automatically.
                </p>
              </div>

              <div className="flex items-center justify-start pt-2">
                <Button type="submit" loading={saving} disabled={loading} className="gap-2">
                  <FloppyDisk size={16} weight="bold" />
                  Save Settings
                </Button>
              </div>
            </form>
          </Card>

          {/* Rate Limit & AI Safeguard Info */}
          <Card className="grid gap-3.5 border border-[var(--rl-border)] bg-[var(--rl-bg-surface)] p-5 shadow-xs">
            <div className="flex items-center gap-2 text-[var(--rl-text-strong)]">
              <ShieldCheck size={18} weight="bold" className="text-emerald-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider">Quota Safeguards</h3>
            </div>

            <p className="text-xs leading-relaxed text-[var(--rl-text-muted)]">
              The backend background worker processes extraction jobs sequentially, ensuring steady rate control that stays safely under Gemini AI limits.
            </p>

            <div className="rounded border border-[var(--rl-border)] bg-white p-3 text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-[var(--rl-text-strong)]">
                <Sparkle size={14} weight="bold" className="text-amber-500" />
                Gemini Rate Baseline
              </div>
              <div className="mt-1 text-[11px] text-[var(--rl-text-muted)]">
                15 RPM standard quota. A batch of 5–8 PDFs executes sequentially across ~40–50s with zero concurrency spikes.
              </div>
            </div>

            <div className="flex items-start gap-1.5 text-[11px] text-[var(--rl-text-muted)]">
              <Info size={14} className="mt-0.5 shrink-0 text-[var(--rl-text-muted)]" />
              <span>Settings apply immediately to all staff upload sessions.</span>
            </div>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
