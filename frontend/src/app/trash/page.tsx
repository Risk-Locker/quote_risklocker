"use client";

import { useEffect, useState } from "react";
import { ArrowCounterClockwise } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

type TrashRecord = { id: string; filename: string; status: string; created_at: string };

export default function TrashPage() {
  const [records, setRecords] = useState<TrashRecord[]>([]);
  const [retentionDays, setRetentionDays] = useState(14);
  const [error, setError] = useState("");
  const [restoring, setRestoring] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  async function load() {
    setError("");
    try {
      const result = await api<{ records: TrashRecord[]; retention_days: number }>("/trash");
      setRecords(result.records);
      if (typeof result.retention_days === "number") {
        setRetentionDays(result.retention_days);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load trash.");
      setRecords([]);
    }
  }

  async function restore(id: string) {
    setRestoring((prev) => new Set(prev).add(id));
    setError("");
    try {
      await api(`/trash/${id}/restore`, { method: "POST", body: JSON.stringify({}) });
      toast("Record restored.", "success");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not restore record.");
    } finally {
      setRestoring((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  useEffect(() => {
    load().catch(() => setRecords([]));
  }, []);

  return (
    <AppShell>
      <section className="grid gap-6">
        <div>
          <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Trash</h1>
          <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">
            Records are recoverable for {retentionDays} days before permanent deletion.
          </p>
        </div>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        <Card className="overflow-x-auto">
          <table className="min-w-[720px] w-full">
            <thead>
              <tr className="border-b border-[var(--rl-border)]">
                <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">File</th>
                <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Deleted</th>
                <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-[14px] text-[var(--rl-text-muted)]">
                    No records in trash.
                  </td>
                </tr>
              ) : (
                records.map((record) => (
                  <tr key={record.id} className="border-b border-[var(--rl-border)] last:border-0">
                    <td className="px-4 py-3">
                      <StatusBadge status="Deleted" />
                    </td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{record.filename}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{new Date(record.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3">
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={<ArrowCounterClockwise aria-hidden="true" size={16} weight="bold" />}
                        onClick={() => restore(record.id)}
                        loading={restoring.has(record.id)}
                      >
                        Restore
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      </section>
    </AppShell>
  );
}
