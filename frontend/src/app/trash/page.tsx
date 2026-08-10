"use client";

import { useEffect, useState } from "react";
import { ArrowCounterClockwise, Trash } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

type SessionItem = { id: string; filename: string; created_at?: string; deleted_at?: string | null };
type TemplateItem = { id: string; name: string; deleted_at?: string | null };
type SpecialItem = { id: string; label: string; category: string; variant_count: number; deleted_at?: string | null };
type VariantItem = { id: string; label: string; special_label: string; deleted_at?: string | null };
type RecordItem = { id: string; insurer_no: string; customer_name?: string | null; vehicle_no?: string | null; deleted_at?: string | null };
type AssetItem = { id: string; label: string; filename: string; folder?: string | null; deleted_at?: string | null };

type TrashData = {
  retention_days: number;
  sessions: SessionItem[];
  templates: TemplateItem[];
  our_specials: SpecialItem[];
  our_special_variants: VariantItem[];
  client_records: RecordItem[];
  assets: AssetItem[];
};

type TabKey = "sessions" | "templates" | "specials" | "records" | "assets";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "sessions", label: "Sessions" },
  { key: "templates", label: "Templates" },
  { key: "specials", label: "Specials & Benefits" },
  { key: "records", label: "Records" },
  { key: "assets", label: "Assets" },
];

export default function TrashPage() {
  const [data, setData] = useState<TrashData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("sessions");
  const [restoring, setRestoring] = useState<Set<string>>(new Set());
  const [confirmEmpty, setConfirmEmpty] = useState(false);
  const [confirmForever, setConfirmForever] = useState<{ entityType: string; entityId: string; label: string } | null>(null);
  const [emptying, setEmptying] = useState(false);
  const { toast } = useToast();

  async function load() {
    setError("");
    setLoading(true);
    try {
      const result = await api<TrashData>("/trash");
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load trash.");
    } finally {
      setLoading(false);
    }
  }

  async function restore(path: string, id: string) {
    setRestoring((prev) => new Set(prev).add(id));
    setError("");
    try {
      await api(`/trash${path ? `/${path}` : ""}/${id}/restore`, { method: "POST", body: JSON.stringify({}) });
      toast("Item restored.", "success");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not restore item.");
    } finally {
      setRestoring((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  async function emptyTrash() {
    setEmptying(true);
    setError("");
    try {
      const result = await api<{ emptied: Record<string, number> }>("/trash/empty", { method: "POST", body: JSON.stringify({}) });
      const total = Object.values(result.emptied).reduce((a, b) => a + b, 0);
      toast(`${total} item${total !== 1 ? "s" : ""} permanently deleted.`, "success");
      setConfirmEmpty(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not empty trash.");
    } finally {
      setEmptying(false);
    }
  }

  async function deleteForever() {
    if (!confirmForever) return;
    setError("");
    try {
      await api("/trash/delete-forever", { method: "POST", body: JSON.stringify({ entity_type: confirmForever.entityType, entity_id: confirmForever.entityId }) });
      toast("Item permanently deleted.", "success");
      setConfirmForever(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete item.");
    }
  }

  useEffect(() => {
    load().catch(() => setData(null));
  }, []);

  const counts: Record<TabKey, number> = {
    sessions: data?.sessions.length ?? 0,
    templates: data?.templates.length ?? 0,
    specials: (data?.our_specials.length ?? 0) + (data?.our_special_variants.length ?? 0),
    records: data?.client_records.length ?? 0,
    assets: data?.assets.length ?? 0,
  };

  return (
    <AppShell>
      <section className="grid gap-6">
        <div>
          <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Trash</h1>
          <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">
            Deleted items are recoverable for {data?.retention_days ?? 14} days before permanent deletion.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-1.5">
            {TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                className={`rounded-[var(--rl-radius-sm)] px-3.5 py-2 text-[13px] font-semibold transition-all
                  ${tab === t.key
                    ? "bg-[var(--rl-black)] text-white shadow-card"
                    : "bg-[var(--rl-surface)] text-[var(--rl-text)] border border-[var(--rl-border)] hover:bg-[var(--rl-bg)]"}`}
              >
                {t.label} ({counts[t.key]})
              </button>
            ))}
          </div>
          {counts.sessions + counts.templates + counts.specials + counts.records + counts.assets > 0 ? (
            <Button
              variant="danger"
              loading={emptying}
              icon={<Trash size={16} weight="bold" />}
              onClick={() => setConfirmEmpty(true)}
            >
              Empty trash
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
        ) : tab === "sessions" ? (
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[560px]">
              <thead>
                <tr className="border-b border-[var(--rl-border)]">
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">File</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Deleted</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {data?.sessions.length === 0 ? (
                  <tr><td colSpan={3} className="px-4 py-10 text-center text-[14px] text-[var(--rl-text-muted)]">No sessions in trash.</td></tr>
                ) : data?.sessions.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--rl-border)] last:border-0">
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.filename}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.deleted_at ? new Date(item.deleted_at).toLocaleString() : item.created_at ? new Date(item.created_at).toLocaleString() : "-"}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={16} weight="bold" />} loading={restoring.has(item.id)} onClick={() => restore("", item.id)}>
                          Restore
                        </Button>
                        <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setConfirmForever({ entityType: "session", entityId: item.id, label: item.filename })} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]" title="Delete forever" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : tab === "templates" ? (
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[560px]">
              <thead>
                <tr className="border-b border-[var(--rl-border)]">
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Template</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Deleted</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {data?.templates.length === 0 ? (
                  <tr><td colSpan={3} className="px-4 py-10 text-center text-[14px] text-[var(--rl-text-muted)]">No templates in trash.</td></tr>
                ) : data?.templates.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--rl-border)] last:border-0">
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.name}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.deleted_at ? new Date(item.deleted_at).toLocaleString() : "-"}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={16} weight="bold" />} loading={restoring.has(item.id)} onClick={() => restore("templates", item.id)}>
                          Restore
                        </Button>
                        <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setConfirmForever({ entityType: "template", entityId: item.id, label: item.name })} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]" title="Delete forever" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : tab === "specials" ? (
          <div className="grid gap-4">
            <Card className="overflow-x-auto">
              <h2 className="border-b border-[var(--rl-border)] px-4 py-3 text-[13px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">Our Specials</h2>
              <table className="w-full min-w-[560px]">
                <tbody>
                  {data?.our_specials.length === 0 ? (
                    <tr><td colSpan={3} className="px-4 py-8 text-center text-[14px] text-[var(--rl-text-muted)]">No specials in trash.</td></tr>
                  ) : data?.our_specials.map((item) => (
                    <tr key={item.id} className="border-b border-[var(--rl-border)] last:border-0">
                      <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.label}</td>
                      <td className="px-4 py-3 text-[13px] text-[var(--rl-text-muted)]">{item.category} · {item.variant_count} variants</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={16} weight="bold" />} loading={restoring.has(item.id)} onClick={() => restore("our-specials", item.id)}>
                            Restore
                          </Button>
                          <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setConfirmForever({ entityType: "our_special", entityId: item.id, label: item.label })} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]" title="Delete forever" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <Card className="overflow-x-auto">
              <h2 className="border-b border-[var(--rl-border)] px-4 py-3 text-[13px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">Variants</h2>
              <table className="w-full min-w-[560px]">
                <tbody>
                  {data?.our_special_variants.length === 0 ? (
                    <tr><td colSpan={3} className="px-4 py-8 text-center text-[14px] text-[var(--rl-text-muted)]">No variants in trash.</td></tr>
                  ) : data?.our_special_variants.map((item) => (
                    <tr key={item.id} className="border-b border-[var(--rl-border)] last:border-0">
                      <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.label}</td>
                      <td className="px-4 py-3 text-[13px] text-[var(--rl-text-muted)]">in {item.special_label}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={16} weight="bold" />} loading={restoring.has(item.id)} onClick={() => restore("our-special-variants", item.id)}>
                            Restore
                          </Button>
                          <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setConfirmForever({ entityType: "our_special_variant", entityId: item.id, label: item.label })} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]" title="Delete forever" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
        ) : tab === "assets" ? (
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[560px]">
              <thead>
                <tr className="border-b border-[var(--rl-border)]">
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Asset</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Folder</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Deleted</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {data?.assets.length === 0 ? (
                  <tr><td colSpan={4} className="px-4 py-10 text-center text-[14px] text-[var(--rl-text-muted)]">No assets in trash.</td></tr>
                ) : data?.assets.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--rl-border)] last:border-0">
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.label}</td>
                    <td className="px-4 py-3 text-[13px] text-[var(--rl-text-muted)]">{item.folder || "Uncategorized"}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.deleted_at ? new Date(item.deleted_at).toLocaleString() : "-"}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={16} weight="bold" />} loading={restoring.has(item.id)} onClick={() => restore("template-assets", item.id)}>
                          Restore
                        </Button>
                        <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setConfirmForever({ entityType: "template_asset", entityId: item.id, label: item.label })} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]" title="Delete forever" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : (
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[560px]">
              <thead>
                <tr className="border-b border-[var(--rl-border)]">
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Insurer No.</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Customer</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Vehicle</th>
                  <th className="px-4 py-3 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {data?.client_records.length === 0 ? (
                  <tr><td colSpan={4} className="px-4 py-10 text-center text-[14px] text-[var(--rl-text-muted)]">No records in trash.</td></tr>
                ) : data?.client_records.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--rl-border)] last:border-0">
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.insurer_no}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)]">{item.customer_name || "-"}</td>
                    <td className="px-4 py-3 text-[14px] font-medium text-[var(--rl-text-strong)] font-mono">{item.vehicle_no || "-"}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={16} weight="bold" />} loading={restoring.has(item.id)} onClick={() => restore("client-records", item.id)}>
                          Restore
                        </Button>
                        <Button variant="ghost" size="sm" icon={<Trash size={14} weight="bold" />} onClick={() => setConfirmForever({ entityType: "client_record", entityId: item.id, label: item.insurer_no })} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]" title="Delete forever" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </section>

      {confirmEmpty ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setConfirmEmpty(false); }}
          title="Empty the Trash?"
          message="Everything in the Trash will be permanently deleted. This cannot be undone."
          confirmLabel="Delete everything"
          loading={emptying}
          onConfirm={emptyTrash}
        />
      ) : null}

      {confirmForever ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setConfirmForever(null); }}
          title={`Permanently delete "${confirmForever.label}"?`}
          message="This cannot be undone."
          confirmLabel="Delete forever"
          onConfirm={deleteForever}
        />
      ) : null}
    </AppShell>
  );
}
