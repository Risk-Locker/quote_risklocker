"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
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
      <section className="grid gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold text-rl-textStrong">System Checks</h1>
            <p className="mt-2">Required setup is shown first. Enhanced reading engines are optional.</p>
          </div>
          <button className="rl-button rl-button-secondary" type="button" onClick={load}>
            <RefreshCw aria-hidden="true" size={18} />
            Refresh
          </button>
        </div>
        <SettingsNav />
        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        <CheckGroup title="Required Setup" checks={required} />
        <details className="rl-panel p-5">
          <summary className="cursor-pointer text-xl font-bold text-rl-textStrong">Advanced Enhanced Reading</summary>
          <p className="mt-2 text-sm">These tools improve difficult scanned documents, but normal PDF extraction can run without them.</p>
          <div className="mt-3">
            <CheckRows checks={advanced} />
          </div>
        </details>
      </section>
    </AppShell>
  );
}

function CheckGroup({ title, checks }: { title: string; checks: Check[] }) {
  return (
    <section className="rl-panel p-5">
      <h2 className="text-xl font-bold text-rl-textStrong">{title}</h2>
      <div className="mt-3">
        <CheckRows checks={checks} />
      </div>
    </section>
  );
}

function CheckRows({ checks }: { checks: Check[] }) {
  return (
    <div className="grid gap-2">
      {checks.map((check) => (
        <div key={check.name} className="grid gap-2 border-b border-rl-line py-3 sm:grid-cols-[1fr_auto]">
          <div>
            <div className="font-bold text-rl-textStrong">{check.name}</div>
            <div className="text-sm">{check.message}</div>
          </div>
          <StatusBadge status={check.status} />
        </div>
      ))}
    </div>
  );
}
