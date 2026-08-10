"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { NotePencil, Trash } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { PageLoading } from "@/components/ui/page-loading";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

type Session = {
  id: string;
  draft_id: string;
  uploaded_file_id: string;
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
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Session | null>(null);
  const [pendingBulkDelete, setPendingBulkDelete] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  async function load() {
    setLoading(true);
    try {
      const result = await api<{ sessions: Session[] }>("/sessions");
      setSessions(result.sessions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load sessions.");
    } finally {
      setLoading(false);
    }
  }

  async function remove(session: Session) {
    setDeleting(session.id);
    setError("");
    try {
      await api(`/records/${session.uploaded_file_id}`, { method: "DELETE" });
      toast("Session moved to Trash.", "success");
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete session.");
    } finally {
      setDeleting(null);
    }
  }

  async function removeSelected() {
    const ids = sessions.filter((s) => selected.has(s.id)).map((s) => s.uploaded_file_id);
    if (!ids.length) return;
    setDeleting("bulk");
    setError("");
    try {
      await api("/records/bulk-delete", { method: "POST", body: JSON.stringify({ uploaded_file_ids: ids }) });
      toast(`${ids.length} session${ids.length > 1 ? "s" : ""} moved to Trash.`, "success");
      setSelected(new Set());
      setPendingBulkDelete(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete sessions.");
    } finally {
      setDeleting(null);
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
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
  const allSelected = sessions.length > 0 && sessions.every((s) => selected.has(s.id));

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Sessions</h1>
            <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">Reopen past quotation sessions and continue reviewing or generating PDFs.</p>
          </div>
          {selected.size > 0 ? (
            <Button
              variant="danger"
              loading={deleting === "bulk"}
              icon={<Trash aria-hidden="true" size={16} weight="bold" />}
              onClick={() => setPendingBulkDelete(true)}
            >
              Delete selected ({selected.size})
            </Button>
          ) : null}
        </div>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {loading ? (
          <PageLoading />
        ) : Object.keys(grouped).length === 0 && !error ? (
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
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      aria-label={`Select ${s.filename}`}
                      className="mt-1 h-4 w-4 accent-[var(--rl-red)]"
                      checked={selected.has(s.id)}
                      onChange={() => toggleSelect(s.id)}
                    />
                    <div>
                      <div className="text-[14px] font-medium text-[var(--rl-text-strong)]">{s.filename}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <StatusBadge status={s.draft_status} />
                        {s.detected_company ? (
                          <span className="text-[14px] text-[var(--rl-text)]">{s.detected_company}</span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/sessions/${s.id}/review`}
                      className="inline-flex items-center justify-center gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-4 py-2 text-[14px] font-semibold text-[var(--rl-text-strong)] transition-all hover:bg-[var(--rl-bg)] active:scale-[0.98]"
                    >
                      <NotePencil aria-hidden="true" size={18} weight="bold" />
                      Review
                    </Link>
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={deleting === s.id}
                      icon={<Trash aria-hidden="true" size={16} weight="bold" />}
                      onClick={() => setPendingDelete(s)}
                      className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]"
                    >
                      Delete
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          ))
        )}
      </section>

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title={`Delete "${pendingDelete.filename}"?`}
          message="This session moves to Trash and can be restored later."
          loading={deleting === pendingDelete.id}
          onConfirm={() => remove(pendingDelete)}
        />
      ) : null}

      {pendingBulkDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingBulkDelete(false); }}
          title={`Delete ${selected.size} selected session${selected.size > 1 ? "s" : ""}?`}
          message="They move to Trash and can be restored later."
          loading={deleting === "bulk"}
          onConfirm={removeSelected}
        />
      ) : null}
    </AppShell>
  );
}
