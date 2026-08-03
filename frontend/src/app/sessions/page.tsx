"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { NotePencil } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { api } from "@/lib/api";

type Session = {
  id: string;
  draft_id: string;
  filename: string;
  detected_company?: string | null;
  status: string;
  draft_status: string;
  created_at: string;
};

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-MY", { day: "2-digit", month: "short", year: "numeric" });
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");

  async function load() {
    const result = await api<{ sessions: Session[] }>("/sessions");
    setSessions(result.sessions);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load sessions."));
  }, []);

  const grouped: Record<string, Session[]> = {};
  for (const s of sessions) {
    const label = formatDate(s.created_at);
    if (!grouped[label]) grouped[label] = [];
    grouped[label].push(s);
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <div>
          <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Sessions</h1>
          <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">Reopen past quotation sessions and continue reviewing or generating PDFs.</p>
        </div>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {Object.keys(grouped).length === 0 && !error ? (
          <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-10 text-center">
            <p className="font-semibold text-[var(--rl-text-strong)]">No sessions yet.</p>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Upload a quotation PDF to start one.</p>
          </div>
        ) : (
          Object.entries(grouped).map(([date, items]) => (
            <div key={date} className="grid gap-2">
              <h2 className="text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">{date}</h2>
              {items.map((s) => (
                <Card key={s.id} className="grid gap-2 p-4 sm:grid-cols-[1fr_auto] sm:items-center">
                  <div>
                    <div className="text-[14px] font-medium text-[var(--rl-text-strong)]">{s.filename}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <StatusBadge status={s.draft_status} />
                      {s.detected_company ? (
                        <span className="text-[14px] text-[var(--rl-text)]">{s.detected_company}</span>
                      ) : null}
                    </div>
                  </div>
                  <Link
                    href={`/sessions/${s.id}/review`}
                    className="inline-flex items-center justify-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-2 text-[14px] font-semibold text-[var(--rl-text-strong)] transition-all hover:bg-[var(--rl-bg)] active:scale-[0.98]"
                  >
                    <NotePencil aria-hidden="true" size={18} weight="bold" />
                    Review
                  </Link>
                </Card>
              ))}
            </div>
          ))
        )}
      </section>
    </AppShell>
  );
}
