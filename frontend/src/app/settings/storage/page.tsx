"use client";

import { useEffect, useState } from "react";
import { Cloud, Archive, ArrowsClockwise, HardDrives } from "@phosphor-icons/react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

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
  const [error, setError] = useState("");
  const { toast } = useToast();

  async function load() {
    setError("");
    setStatus(await api<StorageStatus>("/admin/storage"));
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Storage status could not be loaded."));
  }, []);

  async function purge() {
    setError("");
    try {
      const result = await api<{ deleted: number }>("/admin/storage/purge-expired", { method: "POST" });
      toast(`${result.deleted} expired PDF${result.deleted === 1 ? "" : "s"} removed.`, "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function connectMicrosoft() {
    setError("");
    try {
      await api("/admin/storage/microsoft/connect", { method: "POST" });
      toast("Microsoft 365 connection initiated.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Microsoft 365 connection could not be started.");
    }
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <div>
          <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Storage</h1>
          <p className="text-[14px] text-[var(--rl-text-muted)]">Private PDF storage, retention, and permanent archive status.</p>
        </div>
        <SettingsNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <div className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Cloud size={22} weight="bold" className="text-[var(--rl-text-strong)]" />
                  <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Supabase Storage</h2>
                </div>
                <Badge variant={status?.supabase.status === "ok" ? "success" : "warning"}>
                  {status?.supabase.status || "Checking"}
                </Badge>
              </div>
              <dl className="mt-5 grid grid-cols-[1fr_auto] gap-x-4 gap-y-3 text-[14px]">
                <dt className="text-[var(--rl-text-muted)]">Private bucket</dt>
                <dd className="font-bold text-[var(--rl-text-strong)]">{status?.supabase.bucket || "-"}</dd>
                <dt className="text-[var(--rl-text-muted)]">Rolling retention</dt>
                <dd className="font-bold text-[var(--rl-text-strong)]">{status?.supabase.retention_days ?? "-"} days</dd>
                <dt className="text-[var(--rl-text-muted)]">Tracked source PDFs</dt>
                <dd className="font-bold text-[var(--rl-text-strong)]">{formatBytes(status?.supabase.tracked_source_bytes || 0)}</dd>
              </dl>
              <p className="mt-4 text-[14px] text-[var(--rl-text-muted)]">{status?.supabase.message}</p>
              <div className="mt-5">
                <Button variant="secondary" icon={<ArrowsClockwise size={16} weight="bold" />} onClick={purge}>
                  Purge expired PDFs
                </Button>
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Archive size={22} weight="bold" className="text-[var(--rl-text-strong)]" />
                  <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Microsoft 365 Archive</h2>
                </div>
                <Badge variant={status?.microsoft.status === "Connected" ? "success" : "default"}>
                  {status?.microsoft.status || "Not Connected"}
                </Badge>
              </div>
              <p className="mt-5 text-[14px] text-[var(--rl-text-muted)]">{status?.microsoft.message}</p>
              <div className="mt-5">
                <Button icon={<Archive size={16} weight="bold" />} onClick={connectMicrosoft}>
                  Connect Microsoft 365
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
