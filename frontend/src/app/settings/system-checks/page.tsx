"use client";

import { useEffect, useState } from "react";
import { ArrowsClockwise, Circle, CheckCircle, WarningCircle, ShieldCheck } from "@phosphor-icons/react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

type Check = { name: string; status: string; message: string; group?: string };

export default function SettingsSystemChecksPage() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [error, setError] = useState("");

  async function load() {
    const result = await api<{ checks: Check[] }>("/system/checks");
    setChecks(result.checks);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load system checks."));
  }, []);

  const required = checks.filter((check) => (check.group || "Required Setup") === "Required Setup");
  const advanced = checks.filter((check) => check.group === "Advanced Enhanced Reading");

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">System Checks</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Required setup is shown first. Enhanced reading engines are optional.</p>
          </div>
          <Button variant="secondary" icon={<ArrowsClockwise size={16} weight="bold" />} onClick={load}>
            Refresh
          </Button>
        </div>
        <SettingsNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        <CheckGroup title="Required Setup" checks={required} />
        <Card>
          <details className="p-5">
            <summary className="cursor-pointer text-lg font-bold text-[var(--rl-text-strong)]">Advanced Enhanced Reading</summary>
            <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">These tools improve difficult scanned documents, but normal PDF extraction can run without them.</p>
            <div className="mt-3">
              <CheckRows checks={advanced} />
            </div>
          </details>
        </Card>
      </section>
    </AppShell>
  );
}

function CheckGroup({ title, checks }: { title: string; checks: Check[] }) {
  const okCount = checks.filter((c) => c.status === "ok" || c.status === "available").length;
  return (
    <Card>
      <div className="p-5">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{title}</h2>
          <Badge variant={okCount === checks.length ? "success" : "warning"}>
            {okCount}/{checks.length}
          </Badge>
        </div>
        <div className="mt-3">
          <CheckRows checks={checks} />
        </div>
      </div>
    </Card>
  );
}

function CheckRows({ checks }: { checks: Check[] }) {
  return (
    <div className="grid gap-2">
      {checks.map((check) => (
        <div key={check.name} className="grid gap-2 border-b border-[var(--rl-border)] py-3 sm:grid-cols-[1fr_auto]">
          <div>
            <div className="font-bold text-[var(--rl-text-strong)]">{check.name}</div>
            <div className="text-[14px] text-[var(--rl-text-muted)]">{check.message}</div>
          </div>
          <StatusBadge status={check.status} />
        </div>
      ))}
    </div>
  );
}
