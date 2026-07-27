"use client";

import { useEffect, useState } from "react";
import { Archive, Cloud, RefreshCw } from "lucide-react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";

type StorageStatus = {
  supabase: {
    status: string;
    message: string;
    bucket: string;
    retention_days: number;
    tracked_source_bytes: number;
  };
  microsoft: {
    status: string;
    message: string;
    connections: Array<{ id: string; name: string; status: string }>;
  };
};

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(0, value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export default function SettingsStoragePage() {
  const [status, setStatus] = useState<StorageStatus | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setError("");
    setStatus(await api<StorageStatus>("/admin/storage"));
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Storage status could not be loaded."));
  }, []);

  async function purge() {
    setError("");
    const result = await api<{ deleted: number }>("/admin/storage/purge-expired", { method: "POST" });
    setMessage(`${result.deleted} expired PDF${result.deleted === 1 ? "" : "s"} removed.`);
    await load();
  }

  async function connectMicrosoft() {
    setError("");
    try {
      await api("/admin/storage/microsoft/connect", { method: "POST" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Microsoft 365 connection could not be started.");
    }
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-3xl font-bold text-rl-textStrong">Storage</h1>
          <p className="mt-2">Private PDF storage, retention, and permanent archive status.</p>
        </div>
        <SettingsNav />
        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        {message ? <p className="rounded-md border border-rl-success bg-green-50 p-3 font-bold text-rl-success">{message}</p> : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rl-panel p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Cloud aria-hidden="true" size={22} />
                <h2 className="text-xl font-bold text-rl-textStrong">Supabase Storage</h2>
              </div>
              <strong>{status?.supabase.status || "Checking"}</strong>
            </div>
            <dl className="mt-5 grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 text-sm">
              <dt>Private bucket</dt><dd className="font-bold text-rl-textStrong">{status?.supabase.bucket || "-"}</dd>
              <dt>Rolling retention</dt><dd className="font-bold text-rl-textStrong">{status?.supabase.retention_days ?? 30} days</dd>
              <dt>Tracked source PDFs</dt><dd className="font-bold text-rl-textStrong">{formatBytes(status?.supabase.tracked_source_bytes || 0)}</dd>
            </dl>
            <p className="mt-4 text-sm">{status?.supabase.message}</p>
            <button className="rl-button rl-button-secondary mt-5" type="button" onClick={purge}>
              <RefreshCw aria-hidden="true" size={18} />
              Purge expired PDFs
            </button>
          </section>

          <section className="rl-panel p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Archive aria-hidden="true" size={22} />
                <h2 className="text-xl font-bold text-rl-textStrong">Microsoft 365 Archive</h2>
              </div>
              <strong>{status?.microsoft.status || "Not Connected"}</strong>
            </div>
            <p className="mt-5 text-sm">{status?.microsoft.message}</p>
            <button className="rl-button mt-5" type="button" onClick={connectMicrosoft}>
              <Archive aria-hidden="true" size={18} />
              Connect Microsoft 365
            </button>
          </section>
        </div>
      </section>
    </AppShell>
  );
}
