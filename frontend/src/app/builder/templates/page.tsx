"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { CaretDown, CopySimple, Crown, DotsThreeVertical, FloppyDisk, FolderPlus, LockKey, PencilSimple, Plus, Trash, X } from "@phosphor-icons/react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type TemplateRecord = {
  id: string;
  name: string;
  insurance_type: string;
  insurance_company_id?: string | null;
  insurance_company_name?: string | null;
  group_id?: string | null;
  group_name?: string | null;
  status: string;
  locked: boolean;
  is_default: boolean;
};

type Company = { id: string; name: string; status: string };
type TemplateGroup = { id: string; name: string; company_id?: string | null; company_name?: string | null; template_count: number };

export default function BuilderTemplatesPage() {
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [groups, setGroups] = useState<TemplateGroup[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCompanyId, setNewCompanyId] = useState("");
  const [newGroupId, setNewGroupId] = useState("");
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupCompanyId, setNewGroupCompanyId] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<TemplateRecord | null>(null);
  const [pendingGroupDelete, setPendingGroupDelete] = useState<TemplateGroup | null>(null);
  const [pendingMaster, setPendingMaster] = useState<TemplateRecord | null>(null);
  const [editingGroup, setEditingGroup] = useState<TemplateGroup | null>(null);
  const { toast } = useToast();

  async function load() {
    const [tResult, cResult, gResult] = await Promise.all([
      api<{ templates: TemplateRecord[] }>("/admin/templates"),
      api<{ companies: Company[] }>("/admin/companies"),
      api<{ groups: TemplateGroup[] }>("/admin/template-groups"),
    ]);
    setTemplates(tResult.templates);
    setCompanies(cResult.companies);
    setGroups(gResult.groups);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load templates."));
  }, []);

  async function createTemplate(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const result = await api<{ template: TemplateRecord }>("/admin/templates", {
        method: "POST",
        body: JSON.stringify({
          name: newName,
          insurance_type: "Motor",
          insurance_company_id: newCompanyId || null,
          group_id: newGroupId || null,
        }),
      });
      setShowCreate(false);
      setNewName("");
      setNewCompanyId("");
      setNewGroupId("");
      window.location.href = `/builder/templates/${result.template.id}/builder`;
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function moveToGroup(templateId: string, groupId: string) {
    setError("");
    try {
      await api(`/admin/templates/${templateId}`, {
        method: "PATCH",
        body: JSON.stringify({ group_id: groupId || null }),
      });
      toast("Template moved.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function saveGroup(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/admin/template-groups", {
        method: "POST",
        body: JSON.stringify({
          id: editingGroup?.id || undefined,
          name: editingGroup ? editingGroup.name : newGroupName,
          company_id: editingGroup ? editingGroup.company_id || null : newGroupCompanyId || null,
        }),
      });
      toast(editingGroup ? "Group updated." : "Group created.", "success");
      setShowNewGroup(false);
      setEditingGroup(null);
      setNewGroupName("");
      setNewGroupCompanyId("");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function deleteGroup() {
    if (!pendingGroupDelete) return;
    setError("");
    try {
      await api(`/admin/template-groups/${pendingGroupDelete.id}`, { method: "DELETE" });
      toast("Group deleted. Templates moved to Ungrouped.", "success");
      setPendingGroupDelete(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function makeMaster() {
    if (!pendingMaster) return;
    setError("");
    try {
      await api(`/admin/templates/${pendingMaster.id}/make-master`, { method: "POST", body: JSON.stringify({}) });
      toast(`"${pendingMaster.name}" is now the master template.`, "success");
      setPendingMaster(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function copyTemplate(templateId: string) {
    setError("");
    try {
      const result = await api<{ template: TemplateRecord }>(`/admin/templates/${templateId}/copy`, { method: "POST", body: JSON.stringify({}) });
      toast("Template copied.", "success");
      await load();
      window.location.href = `/builder/templates/${result.template.id}/builder`;
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function deleteTemplate() {
    if (!pendingDelete) return;
    setError("");
    try {
      await api(`/admin/templates/${pendingDelete.id}`, { method: "DELETE" });
      toast("Template moved to Trash.", "success");
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  function toggleCollapsed(groupId: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }

  const byGroup = (groupId: string | null) => templates.filter((t) => (t.group_id || null) === groupId);

  const renderCard = (template: TemplateRecord) => (
    <Card key={template.id} className="group">
      <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {template.is_default ? (
              <Badge variant="info">
                <Crown weight="bold" size={11} className="-ml-0.5 mr-1" />
                Master
              </Badge>
            ) : null}
            {template.locked ? (
              <Badge>
                <LockKey weight="bold" size={11} className="-ml-0.5 mr-1" />
                Locked
              </Badge>
            ) : null}
            <h3 className="truncate text-lg font-bold text-[var(--rl-text-strong)]">{template.name}</h3>
          </div>
          <p className="mt-1 text-[14px] font-medium text-[var(--rl-text-muted)]">
            {template.is_default
              ? "Master template — copy before editing, cannot be deleted."
              : template.locked
                ? "Default template — copy before editing."
                : "Editable template."}
            {template.insurance_company_name ? ` · ${template.insurance_company_name}` : ""}
            {template.status !== "active" ? ` · Status: ${template.status}` : ""}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-semibold text-[var(--rl-text-muted)]">Folder:</span>
            <Select
              className="w-48"
              value={template.group_id || ""}
              onChange={(e) => moveToGroup(template.id, e.target.value)}
              disabled={template.locked}
              aria-label={`Folder for ${template.name}`}
            >
              <option value="">Ungrouped</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!template.locked ? (
            <Link href={`/builder/templates/${template.id}/builder`}>
              <Button icon={<PencilSimple weight="bold" size={16} />}>
                Open builder
              </Button>
            </Link>
          ) : null}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button variant="secondary" size="sm" icon={<DotsThreeVertical weight="bold" size={16} />} aria-label={`Actions for ${template.name}`}>
                <span className="sr-only">Actions</span>
              </Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={6}
                className="z-50 min-w-[180px] rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-1 shadow-card"
              >
                {!template.is_default ? (
                  <DropdownMenu.Item
                    onSelect={() => setPendingMaster(template)}
                    className="flex cursor-pointer items-center gap-2 rounded-[var(--rl-radius-sm)] px-2.5 py-2 text-[13px] font-medium text-[var(--rl-text-strong)] outline-none hover:bg-[var(--rl-bg)]"
                  >
                    <Crown size={14} weight="bold" className="text-[var(--rl-text-muted)]" />
                    Set as master
                  </DropdownMenu.Item>
                ) : null}
                {template.locked ? (
                  <DropdownMenu.Item
                    onSelect={() => copyTemplate(template.id)}
                    className="flex cursor-pointer items-center gap-2 rounded-[var(--rl-radius-sm)] px-2.5 py-2 text-[13px] font-medium text-[var(--rl-text-strong)] outline-none hover:bg-[var(--rl-bg)]"
                  >
                    <CopySimple size={14} weight="bold" className="text-[var(--rl-text-muted)]" />
                    Copy
                  </DropdownMenu.Item>
                ) : null}
                {!template.is_default ? (
                  <DropdownMenu.Item
                    onSelect={() => setPendingDelete(template)}
                    className="flex cursor-pointer items-center gap-2 rounded-[var(--rl-radius-sm)] px-2.5 py-2 text-[13px] font-medium text-[var(--rl-red)] outline-none hover:bg-[var(--rl-red-light)]"
                  >
                    <Trash size={14} weight="bold" />
                    Delete
                  </DropdownMenu.Item>
                ) : null}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </div>
    </Card>
  );

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] mt-0">Templates</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Locked defaults must be copied before editing. Group templates by company to find them faster.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<FolderPlus weight="bold" size={16} />} onClick={() => { setEditingGroup(null); setShowNewGroup((v) => !v); }}>
              New group
            </Button>
            <Button icon={<Plus weight="bold" size={16} />} onClick={() => setShowCreate((v) => !v)}>
              New template
            </Button>
          </div>
        </div>
        <BuilderNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        {showCreate ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={createTemplate}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">New template</h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Name</label>
                  <Input placeholder="e.g. QBE Motor Template" value={newName} onChange={(e) => setNewName(e.target.value)} required />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Company (optional)</label>
                  <Select value={newCompanyId} onChange={(e) => setNewCompanyId(e.target.value)}>
                    <option value="">None</option>
                    {companies.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Group (optional)</label>
                  <Select value={newGroupId} onChange={(e) => setNewGroupId(e.target.value)}>
                    <option value="">Ungrouped</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </Select>
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" icon={<FloppyDisk weight="bold" size={16} />}>Create &amp; open builder</Button>
                <Button variant="secondary" icon={<X weight="bold" size={16} />} onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        {showNewGroup ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={saveGroup}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{editingGroup ? `Edit group "${editingGroup.name}"` : "New template group"}</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Group name</label>
                  <Input
                    value={editingGroup ? editingGroup.name : newGroupName}
                    onChange={(e) => editingGroup ? setEditingGroup({ ...editingGroup, name: e.target.value }) : setNewGroupName(e.target.value)}
                    required
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Company (optional)</label>
                  <Select
                    value={editingGroup ? editingGroup.company_id || "" : newGroupCompanyId}
                    onChange={(e) => editingGroup ? setEditingGroup({ ...editingGroup, company_id: e.target.value }) : setNewGroupCompanyId(e.target.value)}
                  >
                    <option value="">None</option>
                    {companies.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </Select>
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" icon={<FloppyDisk weight="bold" size={16} />}>{editingGroup ? "Save group" : "Create group"}</Button>
                <Button variant="secondary" icon={<X weight="bold" size={16} />} onClick={() => { setShowNewGroup(false); setEditingGroup(null); }}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        {templates.length === 0 && groups.length === 0 ? (
          <p className="text-[14px] text-[var(--rl-text-muted)]">No templates yet.</p>
        ) : (
          <>
            {groups.map((group) => {
              const items = byGroup(group.id);
              const open = !collapsed.has(group.id);
              return (
                <div key={group.id} className="grid gap-3">
                  <div className="flex items-center gap-2">
                    <button type="button" className="flex items-center gap-2" onClick={() => toggleCollapsed(group.id)}>
                      <CaretDown size={14} weight="bold" className={`text-[var(--rl-text-muted)] transition-transform ${open ? "" : "-rotate-90"}`} />
                      <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{group.name}</h2>
                      <span className="text-[13px] font-medium text-[var(--rl-text-muted)]">
                        {group.company_name ? `· ${group.company_name}` : ""} · {items.length} template{items.length === 1 ? "" : "s"}
                      </span>
                    </button>
                    <Button variant="ghost" size="sm" icon={<PencilSimple weight="bold" size={13} />} onClick={() => { setEditingGroup(group); setShowNewGroup(true); }}>
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" icon={<Trash weight="bold" size={13} />} onClick={() => setPendingGroupDelete(group)} className="text-[var(--rl-red)] hover:bg-[var(--rl-red-light)]">
                      Delete
                    </Button>
                  </div>
                  {open ? items.map(renderCard) : null}
                </div>
              );
            })}
            {byGroup(null).length > 0 ? (
              <div className="grid gap-3">
                <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Ungrouped</h2>
                {byGroup(null).map(renderCard)}
              </div>
            ) : null}
          </>
        )}
      </section>

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title={`Delete template "${pendingDelete.name}"?`}
          message="It moves to Trash and can be restored later."
          onConfirm={deleteTemplate}
        />
      ) : null}

      {pendingMaster ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingMaster(null); }}
          title={`Make "${pendingMaster.name}" the master template?`}
          message="The current master becomes a normal editable template. The master cannot be deleted and must always exist."
          confirmLabel="Set as master"
          onConfirm={makeMaster}
        />
      ) : null}

      {pendingGroupDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingGroupDelete(null); }}
          title={`Delete group "${pendingGroupDelete.name}"?`}
          message="Its templates move to Ungrouped. The group itself is deleted."
          onConfirm={deleteGroup}
        />
      ) : null}
    </AppShell>
  );
}
