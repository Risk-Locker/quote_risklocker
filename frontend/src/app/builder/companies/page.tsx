"use client";

import { useEffect, useState } from "react";
import { CaretDown, CaretUp, FloppyDisk, PencilSimple, Plus, Trash, X } from "@phosphor-icons/react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Company = {
  id: string;
  name: string;
  category: string;
  source_template_category: string;
  detection_phrases: string[];
  logo_path?: string | null;
  status: string;
};

export default function BuilderCompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editCategory, setEditCategory] = useState("Motor");
  const [editPhrases, setEditPhrases] = useState("");
  const [editLogo, setEditLogo] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createPhrases, setCreatePhrases] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Company | null>(null);
  const { toast } = useToast();

  async function load() {
    const result = await api<{ companies: Company[] }>("/admin/companies");
    setCompanies(result.companies);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load companies."));
  }, []);

  function startEdit(company: Company) {
    setEditId(company.id);
    setEditName(company.name);
    setEditCategory(company.category);
    setEditPhrases((company.detection_phrases || []).join("\n"));
    setEditLogo(company.logo_path || "");
  }

  function cancelEdit() {
    setEditId(null);
  }

  async function saveEdit(event: React.FormEvent) {
    event.preventDefault();
    if (!editId) return;
    setError("");
    try {
      await api("/admin/companies", {
        method: "POST",
        body: JSON.stringify({
          id: editId,
          name: editName,
          category: editCategory,
          detection_phrases: editPhrases.split(/\r?\n/).map((p) => p.trim()).filter(Boolean),
          logo_path: editLogo || null,
        }),
      });
      setEditId(null);
      toast("Company updated.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function toggleStatus(company: Company) {
    const next = company.status === "active" ? "inactive" : "active";
    setError("");
    try {
      await api("/admin/companies", {
        method: "POST",
        body: JSON.stringify({ id: company.id, status: next }),
      });
      toast(company.status === "active" ? "Company disabled." : "Company enabled.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function deleteCompany() {
    if (!pendingDelete) return;
    setError("");
    try {
      await api(`/admin/companies/${pendingDelete.id}`, { method: "DELETE" });
      toast(`"${pendingDelete.name}" deleted.`, "success");
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete company.");
    }
  }

  async function createCompany(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/admin/companies", {
        method: "POST",
        body: JSON.stringify({
          name: createName,
          category: "Motor",
          source_template_category: "Other / Unknown",
          detection_phrases: createPhrases.split(/\r?\n/).map((p) => p.trim()).filter(Boolean),
        }),
      });
      setCreateName("");
      setCreatePhrases("");
      setShowCreate(false);
      toast("Company created.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] mt-0">Companies</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Manage insurance companies, detection phrases, and active status.</p>
          </div>
          <Button
            icon={<Plus weight="bold" size={16} />}
            onClick={() => setShowCreate((v) => !v)}
          >
            New company
          </Button>
        </div>
        <BuilderNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        {showCreate ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={createCompany}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Create company</h2>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Name</label>
                <Input placeholder="Company name" value={createName} onChange={(e) => setCreateName(e.target.value)} required />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Detection phrases</label>
                <Textarea className="min-h-24" placeholder="Detection phrases, one per line" value={createPhrases} onChange={(e) => setCreatePhrases(e.target.value)} />
              </div>
              <div className="flex gap-2">
                <Button type="submit" icon={<FloppyDisk weight="bold" size={16} />}>Save</Button>
                <Button variant="secondary" icon={<X weight="bold" size={16} />} onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        <div className="grid gap-2">
          {companies.map((company) => {
            const isEditing = editId === company.id;
            const isOpen = expanded === company.id;
            return (
              <Card key={company.id} className="overflow-hidden">
                <button
                  className="grid w-full grid-cols-[1fr_auto] items-center gap-3 p-4 text-left"
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : company.id)}
                >
                  <div>
                    <div className="font-bold text-[var(--rl-text-strong)]">{company.name}</div>
                    <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
                      <Badge variant={company.status === "active" ? "success" : "default"}>{company.category}</Badge>
                      <Badge variant={company.status === "active" ? "success" : "danger"}>{company.status}</Badge>
                      <span className="text-[13px] text-[var(--rl-text-muted)]">
                        {(company.detection_phrases || []).length} detection phrase{(company.detection_phrases || []).length !== 1 ? "s" : ""}
                      </span>
                    </div>
                  </div>
                  <span className="text-[var(--rl-text-muted)]">
                    {isOpen ? <CaretUp weight="bold" size={16} /> : <CaretDown weight="bold" size={16} />}
                  </span>
                </button>

                {isOpen ? (
                  isEditing ? (
                    <form className="grid gap-4 border-t border-[var(--rl-border)] p-4" onSubmit={saveEdit}>
                      <div className="grid gap-1.5">
                        <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Name</label>
                        <Input value={editName} onChange={(e) => setEditName(e.target.value)} required />
                      </div>
                      <div className="grid gap-1.5">
                        <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Category</label>
                        <Input value={editCategory} onChange={(e) => setEditCategory(e.target.value)} />
                      </div>
                      <div className="grid gap-1.5">
                        <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Logo path</label>
                        <Input value={editLogo} onChange={(e) => setEditLogo(e.target.value)} placeholder="/assets/logos/company.png" />
                      </div>
                      <div className="grid gap-1.5">
                        <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Detection phrases</label>
                        <Textarea className="min-h-24" value={editPhrases} onChange={(e) => setEditPhrases(e.target.value)} />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button type="submit" icon={<FloppyDisk weight="bold" size={16} />}>Save</Button>
                        <Button variant="secondary" icon={<X weight="bold" size={16} />} onClick={cancelEdit}>Cancel</Button>
                      </div>
                    </form>
                  ) : (
                    <div className="grid gap-4 border-t border-[var(--rl-border)] p-4">
                      <div className="text-[14px] font-medium">
                        <span className="font-semibold text-[var(--rl-text-strong)]">Source template category:</span> {company.source_template_category}
                      </div>
                      <div className="text-[14px] font-medium">
                        <span className="font-semibold text-[var(--rl-text-strong)]">Detection phrases:</span>{" "}
                        {(company.detection_phrases || []).length ? company.detection_phrases.join(", ") : "None"}
                      </div>
                      {company.logo_path ? (
                        <div className="text-[14px] font-medium">
                          <span className="font-semibold text-[var(--rl-text-strong)]">Logo:</span> {company.logo_path}
                        </div>
                      ) : null}
                      <div className="flex flex-wrap gap-2">
                        <Button variant="secondary" icon={<PencilSimple weight="bold" size={16} />} onClick={() => startEdit(company)}>Edit</Button>
                        <Button variant="secondary" onClick={() => toggleStatus(company)}>
                          {company.status === "active" ? "Disable" : "Enable"}
                        </Button>
                        <Button
                          variant="secondary"
                          icon={<Trash weight="bold" size={16} />}
                          disabled={companies.length <= 1}
                          onClick={() => setPendingDelete(company)}
                        >
                          Delete
                        </Button>
                      </div>
                      {companies.length <= 1 ? (
                        <p className="text-[13px] text-[var(--rl-text-muted)]">At least one company must remain. Add another company before deleting this one.</p>
                      ) : null}
                    </div>
                  )
                ) : null}
              </Card>
            );
          })}
        </div>
      </section>

      {pendingDelete ? (
        <ConfirmDialog
          open
          onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
          title={`Delete "${pendingDelete.name}"?`}
          message="This cannot be undone."
          onConfirm={deleteCompany}
        />
      ) : null}
    </AppShell>
  );
}
