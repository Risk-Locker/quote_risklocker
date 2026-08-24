"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MagnifyingGlass, NotePencil, Trash, X } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { PageLoading } from "@/components/ui/page-loading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

const PAGE_SIZE = 25;

type Session = {
  id: string;
  draft_id: string;
  uploaded_file_id: string;
  filename: string;
  detected_company?: string | null;
  status: string;
  draft_status: string;
  insured_name?: string | null;
  vehicle_plate?: string | null;
  vehicle_model?: string | null;
  total_premium?: string | null;
  created_at: string;
};

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-MY", { day: "2-digit", month: "short", year: "numeric" });
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Session | null>(null);
  const [pendingBulkDelete, setPendingBulkDelete] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  async function load(reset: boolean, term = appliedSearch) {
    if (reset) setLoading(true);
    else setLoadingMore(true);
    setError("");
    try {
      const offset = reset ? 0 : sessions.length;
      const result = await api<{ sessions: Session[]; total: number }>(
        `/sessions?limit=${PAGE_SIZE}&offset=${offset}${term ? `&search=${encodeURIComponent(term)}` : ""}`
      );
      setSessions((current) => (reset ? result.sessions : [...current, ...result.sessions]));
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load sessions.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  function applySearch(event: React.FormEvent) {
    event.preventDefault();
    setSelected(new Set());
    load(true, search.trim());
    setAppliedSearch(search.trim());
  }

  async function remove(session: Session) {
    setDeleting(session.id);
    setError("");
    try {
      await api(`/records/${session.uploaded_file_id}`, { method: "DELETE" });
      toast("Session moved to Trash.", "success");
      setPendingDelete(null);
      await load(true);
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
      await load(true);
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
    load(true).catch((err) => setError(err instanceof Error ? err.message : "Could not load sessions."));
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

        <form onSubmit={applySearch} className="flex flex-wrap items-center gap-2">
          <Input
            className="max-w-sm flex-1 min-w-[200px]"
            placeholder="Search by file name or company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button type="submit" variant="secondary" icon={<MagnifyingGlass weight="bold" size={16} />}>Search</Button>
          {appliedSearch ? (
            <Button
              variant="ghost"
              size="sm"
              icon={<X weight="bold" size={14} />}
              onClick={() => { setSearch(""); setAppliedSearch(""); load(true, ""); }}
            >
              Clear
            </Button>
          ) : null}
          {!loading ? <span className="text-[13px] text-[var(--rl-text-muted)]">{total} session{total === 1 ? "" : "s"}</span> : null}
        </form>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {loading ? (
          <PageLoading />
        ) : sessions.length === 0 && !error ? (
          <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-10 text-center">
            <p className="font-semibold text-[var(--rl-text-strong)]">{appliedSearch ? "No sessions match your search." : "No sessions yet."}</p>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              {appliedSearch ? "Try a different file name or company." : "Upload a quotation PDF to start one."}
            </p>
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
                      {s.insured_name || s.vehicle_plate ? (
                        <div className="mt-1 text-[13px] text-[var(--rl-text)]">
                          {[
                            s.insured_name,
                            s.vehicle_plate,
                            s.vehicle_model,
                            s.total_premium ? `RM ${s.total_premium}` : null,
                          ]
                            .filter(Boolean)
                            .join(" • ")}
                        </div>
                      ) : null}
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <StatusBadge status={s.draft_status} />
                        {s.detected_company ? (
                          <span className="text-[13px] font-medium text-[var(--rl-text)]">{s.detected_company}</span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/sessions/${s.id}`}
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
        {!loading && sessions.length < total ? (
          <div className="flex justify-center">
            <Button variant="secondary" loading={loadingMore} onClick={() => load(false)}>
              Load more ({sessions.length} of {total})
            </Button>
          </div>
        ) : null}
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
