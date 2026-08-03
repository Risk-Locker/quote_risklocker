"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/status-badge";
import { api } from "@/lib/api";

type RecordItem = {
  id: string;
  draft_id: string | null;
  session_id: string | null;
  filename: string;
  status: string;
  pdf_status: string;
  pdf_expires_at?: string | null;
  created_at: string;
};

function pdfLabel(status: string) {
  if (status === "archived") return "Archived";
  if (status === "expired" || status === "deleted") return "PDF Expired";
  return "Available";
}

export default function HistoryPage() {
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const result = await api<{ records: RecordItem[] }>(
        `/history${search ? `?search=${encodeURIComponent(search)}` : ""}`
      );
      setRecords(result.records);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load history.");
      setRecords([]);
    }
  }

  useEffect(() => {
    load().catch(() => setRecords([]));
  }, []);

  return (
    <AppShell>
      <section className="grid gap-6">
        <div>
          <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Quotation History</h1>
          <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">Search and reopen previously processed quotations.</p>
        </div>

        <div className="flex gap-3">
          <Input
            className="max-w-md"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search vehicle no, customer, insurer, date, status"
            onKeyDown={(event) => { if (event.key === "Enter") load(); }}
          />
          <Button variant="secondary" icon={<MagnifyingGlass aria-hidden="true" size={18} weight="bold" />} onClick={load}>
            Search
          </Button>
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
                <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">PDF</th>
                <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Uploaded</th>
                <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-[14px] text-[var(--rl-text-muted)]">
                    No records found.
                  </td>
                </tr>
              ) : (
                records.map((record) => (
                  <tr key={record.id} className="border-b border-[var(--rl-border)] last:border-0">
                    <td className="px-4 py-3">
                      <StatusBadge status={record.status} />
                    </td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{record.filename}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{pdfLabel(record.pdf_status)}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{new Date(record.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {record.session_id ? (
                        <Link
                          href={`/sessions/${record.session_id}/review`}
                          className="inline-flex items-center justify-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-2 text-[14px] font-semibold text-[var(--rl-text-strong)] transition-all hover:bg-[var(--rl-bg)] active:scale-[0.98]"
                        >
                          Open
                        </Link>
                      ) : record.draft_id ? (
                        <Link
                          href={`/review/${record.draft_id}`}
                          className="inline-flex items-center justify-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-2 text-[14px] font-semibold text-[var(--rl-text-strong)] transition-all hover:bg-[var(--rl-bg)] active:scale-[0.98]"
                        >
                          Open (legacy)
                        </Link>
                      ) : null}
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
