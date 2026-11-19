"use client";

import { useEffect, useState } from "react";
import { CurrencyDollar, FloppyDisk, Info, ShieldCheck } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

const PRESET_AMOUNTS = [0, 10, 20, 25, 30];

export default function BuilderRunnerFeePage() {
  const [amountInput, setAmountInput] = useState("20.00");
  const [savedAmount, setSavedAmount] = useState<number>(20);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { toast } = useToast();

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{ amount: number }>("/admin/settings/runner-fee");
      const val = typeof data?.amount === "number" && !Number.isNaN(data.amount) ? data.amount : 20;
      setSavedAmount(val);
      setAmountInput(val.toFixed(2));
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    const parsed = Number(amountInput);
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > 10000) {
      setError("Runner fee (default) must be between RM 0.00 and RM 10,000.00.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const res = await api<{ amount: number }>("/admin/settings/runner-fee", {
        method: "POST",
        body: JSON.stringify({ amount: Number(parsed.toFixed(2)) }),
      });
      const nextVal = typeof res?.amount === "number" ? res.amount : Number(parsed.toFixed(2));
      setSavedAmount(nextVal);
      setAmountInput(nextVal.toFixed(2));
      toast(`Runner fee (default) updated to RM ${nextVal.toFixed(2)} for all future quotations.`, "success");
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
              Runner Fee (Default)
            </h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">
              Configure the system-wide default runner fee applied to all future quotations and renewals (editable per quote).
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
          <Card className="grid gap-4 border border-[var(--rl-border)] bg-white p-5 shadow-xs sm:col-span-2">
            <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--rl-red-light)] text-[var(--rl-red)]">
                  <CurrencyDollar size={20} weight="bold" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-[var(--rl-text-strong)]">
                    Runner fee (default) : RM {savedAmount.toFixed(2)}
                  </h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Applies automatically to every future quotation &amp; tenure regardless of MyKad or Passport
                  </p>
                </div>
              </div>
              <Badge variant="success">Active</Badge>
            </div>

            <form onSubmit={handleSave} className="grid gap-4">
              <div className="grid gap-2">
                <label htmlFor="runnerFeeDefault" className="text-xs font-semibold text-[var(--rl-text-strong)]">
                  Default Runner Fee Amount (MYR)
                </label>
                <div className="flex max-w-xs items-center gap-2">
                  <span className="text-xs font-bold text-[var(--rl-text-muted)]">RM</span>
                  <Input
                    id="runnerFeeDefault"
                    type="number"
                    min={0}
                    max={10000}
                    step="0.01"
                    value={amountInput}
                    disabled={loading || saving}
                    onChange={(e) => setAmountInput(e.target.value)}
                    className="font-mono text-sm"
                  />
                </div>
              </div>

              <div className="grid gap-1.5">
                <span className="text-xs font-semibold text-[var(--rl-text-muted)]">Quick Select</span>
                <div className="flex flex-wrap items-center gap-2">
                  {PRESET_AMOUNTS.map((preset) => {
                    const isCurrent = Math.abs(Number(amountInput) - preset) < 0.005;
                    return (
                      <Button
                        key={preset}
                        type="button"
                        size="sm"
                        variant={isCurrent ? "primary" : "secondary"}
                        disabled={loading || saving}
                        onClick={() => setAmountInput(preset.toFixed(2))}
                        className="font-mono"
                      >
                        RM {preset.toFixed(2)}
                      </Button>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center justify-start pt-2">
                <Button type="submit" loading={saving} disabled={loading} className="gap-2">
                  <FloppyDisk size={16} weight="bold" />
                  Save Runner Fee Default
                </Button>
              </div>
            </form>
          </Card>

          <Card className="grid gap-3.5 border border-[var(--rl-border)] bg-[var(--rl-bg-surface)] p-5 shadow-xs">
            <div className="flex items-center gap-2 text-[var(--rl-text-strong)]">
              <ShieldCheck size={18} weight="bold" className="text-emerald-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider">Calculation Rules</h3>
            </div>

            <p className="text-xs leading-relaxed text-[var(--rl-text-muted)]">
              Runner fee and road tax are never extracted from insurer quotation PDFs. Road tax is calculated via the JPJ Road Tax Engine, and runner fee defaults to this Studio setting.
            </p>

            <div className="flex items-start gap-1.5 text-[11px] text-[var(--rl-text-muted)]">
              <Info size={14} className="mt-0.5 shrink-0 text-[var(--rl-text-muted)]" />
              <span>
                Only future quotations and renewals created after saving use the new default. Existing quotations keep their saved values, and staff can still manually edit runner fee on any individual quotation.
              </span>
            </div>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
