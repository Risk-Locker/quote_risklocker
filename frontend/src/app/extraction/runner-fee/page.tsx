"use client";

import { useEffect, useState } from "react";
import { FloppyDisk, CurrencyDollar, CheckCircle, Info } from "@phosphor-icons/react";
import { ExtractionNav } from "@/components/extraction-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

export default function RunnerFeePage() {
  const [runnerFee, setRunnerFee] = useState("20.00");
  const [currency, setCurrency] = useState("MYR");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { toast } = useToast();

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{ amount: number }>("/admin/settings/runner-fee");
      if (data && typeof data.amount === "number") {
        setRunnerFee(data.amount.toFixed(2));
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
    setSaving(true);
    setError("");
    try {
      const numVal = parseFloat(runnerFee) || 20.0;
      await api("/admin/settings/runner-fee", {
        method: "POST",
        body: JSON.stringify({ amount: numVal, currency: currency || "MYR" }),
      });
      setRunnerFee(numVal.toFixed(2));
      toast("Runner fee setting updated.", "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <section className="grid gap-6 max-w-4xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">
              Runner Fee
            </h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">
              Configure the default service / runner fee applied to quotation drafts.
            </p>
          </div>
        </div>

        <ExtractionNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        <div className="grid gap-6 sm:grid-cols-3">
          {/* Main Setting Card */}
          <Card className="p-5 grid gap-4 border border-[var(--rl-border)] bg-white shadow-xs sm:col-span-2">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-emerald-800">
                  <CurrencyDollar size={20} weight="bold" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">Standard Runner Fee</h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">Default service amount for new motor quotations</p>
                </div>
              </div>
              <Badge variant="success">Active</Badge>
            </div>

            <form onSubmit={handleSave} className="grid gap-4">
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">
                    Default Amount (RM)
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-[var(--rl-text-muted)]">
                      RM
                    </span>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={runnerFee}
                      onChange={(e) => setRunnerFee(e.target.value)}
                      className="pl-9 font-mono font-medium text-sm"
                      placeholder="20.00"
                      disabled={loading || saving}
                    />
                  </div>
                </div>

                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">
                    Currency
                  </label>
                  <Input
                    type="text"
                    value={currency}
                    disabled
                    className="font-mono text-sm bg-gray-50"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-[var(--rl-border)]">
                <p className="text-xs text-[var(--rl-text-muted)]">
                  Applies to all new uploaded quotations where runner fee is omitted.
                </p>
                <Button
                  type="submit"
                  size="sm"
                  disabled={loading || saving}
                  icon={<FloppyDisk size={14} weight="bold" />}
                >
                  {saving ? "Saving..." : "Save Runner Fee"}
                </Button>
              </div>
            </form>
          </Card>

          {/* Quick Summary Info */}
          <Card className="p-4 grid gap-3 border border-[var(--rl-border)] bg-gray-50/70 text-xs text-[var(--rl-text-muted)]">
            <div className="flex items-center gap-1.5 font-bold text-[var(--rl-text-strong)]">
              <Info size={16} weight="bold" className="text-blue-600" />
              <span>How It Works</span>
            </div>
            <p>
              When a quotation is uploaded and processed, RiskLocker checks if a runner fee was detected from the PDF.
            </p>
            <p>
              If absent, it automatically defaults to <strong>RM {parseFloat(runnerFee || "20").toFixed(2)}</strong>, ensuring quotations always calculate full total amounts reliably.
            </p>
            <div className="mt-2 rounded bg-white p-2.5 border border-[var(--rl-border)]">
              <span className="font-semibold text-[var(--rl-text-strong)]">Total Calculation:</span>
              <p className="font-mono text-[11px] mt-1 text-emerald-800">
                Total = Premium + Roadtax + Runner Fee (RM {parseFloat(runnerFee || "20").toFixed(2)})
              </p>
            </div>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
