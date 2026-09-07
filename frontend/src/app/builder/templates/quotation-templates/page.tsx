"use client";

import Link from "next/link";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CopySimple,
  Eye,
  FilePdf,
  FilePlus,
  Lock,
  MagnifyingGlass,
  PencilSimple,
  ShieldCheck,
  Star,
  Trash,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Revision = {
  id: string;
  revision_number: number;
  state: "draft" | "published" | "retired" | "compatibility";
  published_at?: string | null;
  page_profile?: { name: string; width: number; height: number; unit: string } | null;
};

type CanvasNode = {
  id: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
  text?: string;
  variableId?: string;
  gridKind?: string;
  shapeKind?: string;
  style?: { background?: string; color?: string; borderColor?: string; borderWidth?: number; fontSize?: number };
};

type TemplateRecord = {
  id: string;
  revision: number;
  name: string;
  status: string;
  locked: boolean;
  is_default: boolean;
  fixed_fields: {
    version?: number;
    canvas?: { width?: number; height?: number; elements?: CanvasNode[] };
    page_profile?: { name?: string; width?: number; height?: number; unit?: string };
  };
  template_revisions: Revision[];
  latest_published_revision?: Revision | null;
};

function templateState(template: TemplateRecord) {
  if (template.status === "retired") return "retired";
  return template.latest_published_revision?.state || (template.fixed_fields.version === 7 ? "draft" : "compatibility");
}

function pageProfile(template: TemplateRecord) {
  const published = template.latest_published_revision?.page_profile;
  if (published) return published;
  const page = template.fixed_fields.page_profile;
  const canvas = template.fixed_fields.canvas;
  return {
    name: page?.name || (Number(canvas?.height || 1123) > 1200 ? "Custom portrait" : "A4"),
    width: Number(page?.width || canvas?.width || 794),
    height: Number(page?.height || canvas?.height || 1123),
    unit: page?.unit || "px",
  };
}

function resolveNodeImageUrl(node: CanvasNode, template: TemplateRecord): string | null {
  const isImageOrLogo =
    node.type === "image" ||
    ["pay_holder", "text_ltaa394", "pay_bank_sub", "text_ul2w5ka", "pay_bank_logo", "bank_logo", "risklocker_logo"].includes(node.id);
  if (!isImageOrLogo) return null;

  const slot =
    (node as any).assetSlot ||
    (node.id === "risklocker_logo" || node.id === "pay_holder" || node.id === "text_ltaa394"
      ? "risklocker_logo"
      : node.id === "bank_logo" || node.id === "pay_bank_logo" || node.id === "pay_bank_sub" || node.id === "text_ul2w5ka"
        ? "bank_logo"
        : node.id === "driver_icon"
          ? "all_driver_icon"
          : "");
  const assetId = (node as any).assetId || (template.fixed_fields as any)?.assets?.[slot];
  if (slot === "risklocker_logo" || assetId === "e9685e1f-ac95-410c-a2e9-eccb7ca35d5f") {
    return "/api/business/assets/e9685e1f-ac95-410c-a2e9-eccb7ca35d5f/content?profile=ui";
  }
  if (slot === "bank_logo" || assetId === "2168eaee-3e56-4903-8c4f-841f01ff2407") {
    return "/api/business/assets/2168eaee-3e56-4903-8c4f-841f01ff2407/content?profile=ui";
  }
  if (slot === "all_driver_icon" || assetId === "91116a7dc3540d62") {
    return "/api/template-assets/91116a7dc3540d62";
  }
  if (slot === "background") {
    return null;
  }
  if (assetId) {
    return String(assetId).includes("-") ? `/api/business/assets/${assetId}/content?profile=ui` : `/api/template-assets/${assetId}`;
  }
  return null;
}

const LOGO_TEXT_IDS = new Set(["pay_holder", "text_ltaa394", "pay_bank_sub", "text_ul2w5ka"]);

function TemplateThumbnail({ template, large = false }: { template: TemplateRecord; large?: boolean }) {
  const page = pageProfile(template);
  const elements = (template.fixed_fields.canvas?.elements || []).filter((item) => item.type !== "layer-group");
  const textNodes = elements.filter((item) => (item.type === "text" || item.type === "variable") && !LOGO_TEXT_IDS.has(item.id)).slice(0, large ? 80 : 42);
  const shapeNodes = elements.filter((item) => !["text", "variable", "layer-group"].includes(item.type) || LOGO_TEXT_IDS.has(item.id)).slice(0, large ? 100 : 60);
  return (
    <div className={`grid place-items-center bg-[#ececee] ${large ? "h-[68vh] p-8" : "h-[300px] p-6"}`}>
      <svg viewBox={`0 0 ${page.width} ${page.height}`} className="h-full max-w-full bg-white shadow-card" role="img" aria-label={`Preview of ${template.name}`}>
        <rect x="0" y="0" width={page.width} height={page.height} fill="white" />
        {shapeNodes.map((node) => {
          const imgUrl = resolveNodeImageUrl(node, template);
          if (imgUrl) {
            return (
              <image
                key={node.id}
                x={node.x}
                y={node.y}
                width={node.w}
                height={node.h}
                href={imgUrl}
                xlinkHref={imgUrl}
                preserveAspectRatio="xMidYMid meet"
              />
            );
          }
          if (node.type === "image") {
            if ((node as any).assetSlot === "background") return null;
          }
          const fill = node.style?.background || (node.type === "benefit-grid" ? "#fff7f7" : "#f0f0f1");
          const stroke = node.type === "benefit-grid" ? "#ed1c24" : (node.style?.borderColor || "#d1d1d4");
          const strokeWidth = Math.max(1, Number(node.style?.borderWidth || 1));
          if (node.type === "line") return <line key={node.id} x1={node.x} y1={node.y} x2={node.x + node.w} y2={node.y + node.h} stroke={node.style?.color || "#171717"} strokeWidth={strokeWidth} />;
          if (node.type === "ellipse" || node.shapeKind === "circle") return <ellipse key={node.id} cx={node.x + node.w / 2} cy={node.y + node.h / 2} rx={node.w / 2} ry={node.h / 2} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
          if (node.type === "triangle" || node.shapeKind === "triangle") return <polygon key={node.id} points={`${node.x + node.w / 2},${node.y} ${node.x + node.w},${node.y + node.h} ${node.x},${node.y + node.h}`} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
          if (node.type === "diamond" || node.shapeKind === "diamond") return <polygon key={node.id} points={`${node.x + node.w / 2},${node.y} ${node.x + node.w / 2},${node.y + node.h / 2} ${node.x + node.w / 2},${node.y + node.h} ${node.x},${node.y + node.h / 2}`} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
          return <rect key={node.id} x={node.x} y={node.y} width={node.w} height={node.h} fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeDasharray={node.type === "benefit-grid" ? "7 5" : undefined} />;
        })}
        {textNodes.map((node) => (
          <text key={node.id} x={node.x} y={node.y + Math.min(node.h, Number(node.style?.fontSize || 14))} fill={node.type === "variable" ? "#ed1c24" : (node.style?.color || "#171717")} fontSize={Math.max(7, Number(node.style?.fontSize || 14))} fontWeight={node.type === "variable" ? 600 : 400}>
            {(node.type === "variable" ? `{${node.variableId || "variable"}}` : (node.text || "Text")).slice(0, 70)}
          </text>
        ))}
      </svg>
    </div>
  );
}

export default function QuotationTemplatesPage() {
  const router = useRouter();

  // Quotation Templates State
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [profileFilter, setProfileFilter] = useState("all");
  const [newName, setNewName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [preview, setPreview] = useState<TemplateRecord | null>(null);
  const [pendingRetire, setPendingRetire] = useState<TemplateRecord | null>(null);
  const [pendingRename, setPendingRename] = useState<TemplateRecord | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<TemplateRecord | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api<{ templates: TemplateRecord[] }>("/admin/templates");
      setTemplates(result.templates);
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const profiles = useMemo(() => [...new Set(templates.map((item) => pageProfile(item).name))].sort(), [templates]);
  const visibleTemplates = useMemo(() => {
    return templates.filter((template) => {
      const matchesText = !search.trim() || template.name.toLowerCase().includes(search.trim().toLowerCase());
      const matchesStatus = statusFilter === "all" || templateState(template) === statusFilter;
      const matchesProfile = profileFilter === "all" || pageProfile(template).name === profileFilter;
      return matchesText && matchesStatus && matchesProfile;
    });
  }, [profileFilter, search, statusFilter, templates]);

  async function createTemplate(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      const result = await api<{ template: TemplateRecord }>("/admin/templates", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), insurance_type: "Motor" }),
      });
      window.location.assign(`/builder/templates/${result.template.id}/builder`);
    } catch (reason) {
      setError(apiErrorMessage(reason));
      setCreating(false);
    }
  }

  async function cloneTemplate(template: TemplateRecord) {
    setError("");
    try {
      const result = await api<{ template: TemplateRecord }>(`/admin/templates/${template.id}/copy`, { method: "POST", body: "{}" });
      toast("Template cloned as a new editable draft.", "success");
      window.location.assign(`/builder/templates/${result.template.id}/builder`);
    } catch (reason) {
      setError(apiErrorMessage(reason));
    }
  }

  async function handleMakeDefault(template: TemplateRecord) {
    if (template.is_default) return;
    setError("");
    try {
      await api(`/admin/templates/${template.id}/make-master`, { method: "POST", body: "{}" });
      toast(`"${template.name}" is now the default template for quotations.`, "success");
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    }
  }

  async function handleRenameSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingRename || !renameValue.trim()) return;
    setRenaming(true);
    setError("");
    try {
      await api(`/admin/templates/${pendingRename.id}`, {
        method: "PATCH",
        body: JSON.stringify({ base_revision: pendingRename.revision, name: renameValue.trim() }),
      });
      toast("Template renamed successfully.", "success");
      setPendingRename(null);
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setRenaming(false);
    }
  }

  async function handleDeleteTemplate() {
    if (!pendingDelete) return;
    setDeleting(true);
    setError("");
    try {
      await api(`/admin/templates/${pendingDelete.id}`, { method: "DELETE" });
      toast("Template deleted successfully.", "success");
      setPendingDelete(null);
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setDeleting(false);
    }
  }

  async function retireTemplate() {
    if (!pendingRetire) return;
    setError("");
    try {
      await api(`/admin/templates/${pendingRetire.id}`, {
        method: "PATCH",
        body: JSON.stringify({ base_revision: pendingRetire.revision, status: "retired" }),
      });
      setPendingRetire(null);
      toast("Template retired. Published revisions remain available to pinned quotations.", "success");
      await load();
    } catch (reason) {
      setError(apiErrorMessage(reason));
    }
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        {/* Top Header */}
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--rl-red)]">Builder</p>
            <h1 className="m-0 font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">Quotation Templates</h1>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
              Design and configure master quotation page templates for PDF export.
            </p>
          </div>
          <Button icon={<FilePlus size={16} weight="bold" />} onClick={() => { setNewName(""); setShowCreate(true); }}>New template</Button>
        </header>

        <BuilderNav />

        {/* Top Subtabs Navigation: Quotation Templates vs Benefit Templates */}
        <div className="flex items-center gap-2 border-b border-[var(--rl-border)] pb-2">
          <Link
            href={"/builder/templates/quotation-templates" as Route}
            className="flex items-center gap-2 rounded-t-[var(--rl-radius-sm)] bg-[var(--rl-black)] px-4 py-2 text-xs font-bold text-white shadow-sm transition-all"
          >
            <FilePdf size={16} weight="bold" />
            <span>Quotation Templates</span>
            {templates.length > 0 && (
              <span className="ml-1 rounded-full bg-white/20 px-1.5 py-0.5 text-[10px] font-bold text-white">
                {templates.length}
              </span>
            )}
          </Link>

          <Link
            href={"/builder/templates/benefit-templates" as Route}
            className="flex items-center gap-2 rounded-t-[var(--rl-radius-sm)] border border-transparent bg-transparent px-4 py-2 text-xs font-bold text-[var(--rl-text-muted)] transition-all hover:bg-neutral-100 hover:text-[var(--rl-text-strong)]"
          >
            <ShieldCheck size={16} weight="bold" />
            <span>Benefit Templates</span>
          </Link>
        </div>

        {error ? <div role="alert" className="border-l-2 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div> : null}

        {/* QUOTATION MASTER TEMPLATES LIST */}
        <div className="space-y-6">
          <div className="grid gap-3 border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 shadow-card md:grid-cols-[minmax(260px,1fr)_190px_190px_auto] md:items-center">
            <label className="relative block">
              <MagnifyingGlass size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
              <Input aria-label="Search templates" className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search templates" />
            </label>
            <Select aria-label="Filter by publication status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All statuses</option><option value="published">Published</option><option value="draft">Draft</option><option value="compatibility">Legacy compatibility</option><option value="retired">Retired</option>
            </Select>
            <Select aria-label="Filter by page profile" value={profileFilter} onChange={(event) => setProfileFilter(event.target.value)}><option value="all">All page profiles</option>{profiles.map((profile) => <option key={profile} value={profile}>{profile}</option>)}</Select>
            <span className="text-right text-[12px] font-semibold text-[var(--rl-text-muted)]">{visibleTemplates.length} template{visibleTemplates.length === 1 ? "" : "s"}</span>
          </div>

          {loading ? <p role="status" className="border border-[var(--rl-border)] bg-white p-8 text-center text-[14px] text-[var(--rl-text-muted)]">Loading template previews…</p> : null}
          {!loading && visibleTemplates.length ? (
            <div className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
              {visibleTemplates.map((template) => {
                const state = templateState(template);
                const page = pageProfile(template);
                const published = template.latest_published_revision;
                return (
                  <article key={template.id} className="group overflow-hidden border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card">
                    <button type="button" className="block w-full text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rl-red)]" onClick={() => setPreview(template)} aria-label={`Preview ${template.name}`}>
                      <TemplateThumbnail template={template} />
                    </button>
                    <div className="grid gap-4 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h2 className="m-0 truncate text-[17px] font-bold text-[var(--rl-text-strong)]">{template.name}</h2>
                            {template.is_default ? (
                              <span className="inline-flex items-center gap-1 rounded bg-amber-50 border border-amber-300 px-1.5 py-0.5 text-[10px] font-bold text-amber-900 uppercase">
                                <Star size={11} weight="fill" className="text-amber-500" /> Default
                              </span>
                            ) : null}
                            {template.locked ? (
                              <span className="inline-flex items-center gap-1 rounded bg-slate-50 border border-slate-300 px-1.5 py-0.5 text-[10px] font-bold text-slate-700 uppercase">
                                <Lock size={11} weight="bold" /> Locked Master
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-1 text-[12px] text-[var(--rl-text-muted)]">{page.name} · {Math.round(page.width)} × {Math.round(page.height)} {page.unit}</p>
                        </div>
                        <span className={`border-l-2 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] ${state === "published" ? "border-emerald-600 text-emerald-700" : state === "draft" ? "border-amber-500 text-amber-700" : "border-[var(--rl-border-strong)] text-[var(--rl-text-muted)]"}`}>{state}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3 border-t border-[var(--rl-border)] pt-3">
                        <p className="m-0 text-[11px] text-[var(--rl-text-muted)]">{published ? `Published revision ${published.revision_number}` : `Working revision ${template.revision}`}</p>
                        <div className="flex flex-wrap gap-1 items-center">
                          <Button
                            variant={template.is_default ? "secondary" : "ghost"}
                            size="sm"
                            icon={<Star size={14} weight={template.is_default ? "fill" : "regular"} className={template.is_default ? "text-amber-500" : ""} />}
                            onClick={() => handleMakeDefault(template)}
                            disabled={template.is_default}
                            title={template.is_default ? "Currently default template" : "Set as default quotation template"}
                          >
                            {template.is_default ? "Default" : "Set Default"}
                          </Button>
                          <Button variant="ghost" size="sm" icon={<Eye size={14} />} onClick={() => setPreview(template)}>Preview</Button>
                          <Button variant="secondary" size="sm" icon={<PencilSimple size={14} />} onClick={() => { setPendingRename(template); setRenameValue(template.name); }}>Rename</Button>
                          {template.locked ? (
                            <Button size="sm" icon={<CopySimple size={14} />} onClick={() => cloneTemplate(template)}>Clone to Edit</Button>
                          ) : (
                            <Button variant="secondary" size="sm" icon={<CopySimple size={14} />} onClick={() => cloneTemplate(template)}>Clone</Button>
                          )}
                          {!template.locked && template.status !== "retired" ? (
                            <Link href={`/builder/templates/${template.id}/builder` as Route}>
                              <Button size="sm" icon={<PencilSimple size={14} />}>Open</Button>
                            </Link>
                          ) : null}
                          {!template.locked && template.status !== "retired" ? (
                            <Button variant="ghost" size="sm" aria-label={`Delete ${template.name}`} icon={<Trash size={14} />} className="text-[var(--rl-red)]" onClick={() => setPendingDelete(template)}>
                              <span className="sr-only">Delete</span>
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
          {!loading && !visibleTemplates.length ? <p className="border border-dashed border-[var(--rl-border)] p-12 text-center text-[14px] text-[var(--rl-text-muted)]">No templates match these filters.</p> : null}
        </div>
      </section>

      {/* Dialogs for Quotation Templates */}
      <Dialog open={showCreate} onOpenChange={setShowCreate} title="Create an insurer-independent template" description="Start with a clean Standard A4 draft. Page profile and layout can be changed inside the Builder.">
        <form onSubmit={createTemplate} className="grid gap-4"><label className="grid gap-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">Template name<Input autoFocus value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="e.g. Standard A4" required /></label><div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button><Button type="submit" loading={creating}>Create and open</Button></div></form>
      </Dialog>

      <Dialog open={Boolean(pendingRename)} onOpenChange={(open) => { if (!open) setPendingRename(null); }} title={`Rename “${pendingRename?.name || ""}”`} description="Update the display name of this quotation template.">
        <form onSubmit={handleRenameSubmit} className="grid gap-4">
          <label className="grid gap-1.5 text-[12px] font-semibold text-[var(--rl-text-strong)]">
            New Template Name
            <Input autoFocus value={renameValue} onChange={(e) => setRenameValue(e.target.value)} placeholder="e.g. AmAssurance Custom Quotation" required />
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setPendingRename(null)}>Cancel</Button>
            <Button type="submit" loading={renaming}>Rename Template</Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={Boolean(preview)} onOpenChange={(open) => { if (!open) setPreview(null); }} title={preview?.name || "Template preview"} description={preview ? `${pageProfile(preview).name} · ${templateState(preview)}` : undefined}>{preview ? <TemplateThumbnail template={preview} large /> : null}</Dialog>

      {pendingRetire ? <ConfirmDialog open onOpenChange={(open) => { if (!open) setPendingRetire(null); }} title={`Retire “${pendingRetire.name}”?`} message="Pinned quotations keep their immutable published revision. This working template disappears from new selection." confirmLabel="Retire template" onConfirm={retireTemplate} /> : null}

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title={`Delete Template “${pendingDelete.name}”?`}
          message="Are you sure you want to delete this template? Any quotations that have pinned published revisions will continue to work, but this working template will be removed."
          confirmLabel="Delete Template"
          onConfirm={handleDeleteTemplate}
        />
      ) : null}
    </AppShell>
  );
}
