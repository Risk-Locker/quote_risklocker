"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, CopySimple, FloppyDisk, LockKey, PencilSimple, Plus, X } from "@phosphor-icons/react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type TemplateRecord = {
  id: string;
  name: string;
  insurance_type: string;
  insurance_company_id?: string | null;
  insurance_company_name?: string | null;
  status: string;
  locked: boolean;
  is_default: boolean;
};

type Company = { id: string; name: string; status: string };

export default function BuilderTemplatesPage() {
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCompanyId, setNewCompanyId] = useState("");
  const { toast } = useToast();

  async function load() {
    const [tResult, cResult] = await Promise.all([
      api<{ templates: TemplateRecord[] }>("/admin/templates"),
      api<{ companies: Company[] }>("/admin/companies"),
    ]);
    setTemplates(tResult.templates);
    setCompanies(cResult.companies);
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
        }),
      });
      setShowCreate(false);
      setNewName("");
      setNewCompanyId("");
      window.location.href = `/builder/templates/${result.template.id}/builder`;
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

  const grouped: Record<string, TemplateRecord[]> = {};
  for (const t of templates) {
    const key = t.insurance_company_name || "Ungrouped";
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(t);
  }

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] mt-0">Templates</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Locked defaults must be copied before editing. Grouped by insurance company.</p>
          </div>
          <Button
            icon={<Plus weight="bold" size={16} />}
            onClick={() => setShowCreate((v) => !v)}
          >
            New template
          </Button>
        </div>
        <BuilderNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        {showCreate ? (
          <Card>
            <form className="grid gap-4 p-4" onSubmit={createTemplate}>
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">New template</h2>
              <div className="grid gap-4 sm:grid-cols-2">
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
              </div>
              <div className="flex gap-2">
                <Button type="submit" icon={<FloppyDisk weight="bold" size={16} />}>Create &amp; open builder</Button>
                <Button variant="secondary" icon={<X weight="bold" size={16} />} onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </form>
          </Card>
        ) : null}

        {Object.keys(grouped).length === 0 ? (
          <p className="text-[14px] text-[var(--rl-text-muted)]">No templates yet.</p>
        ) : (
          Object.entries(grouped).map(([companyName, items]) => (
            <div key={companyName} className="grid gap-3">
              <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{companyName}</h2>
              {items.map((template) => (
                <Card key={template.id}>
                  <div className="grid gap-3 p-4 md:grid-cols-[1fr_auto] md:items-center">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-bold text-[var(--rl-text-strong)]">{template.name}</h3>
                        {template.is_default ? (
                          <Badge variant="info">
                            <Check weight="bold" size={11} className="-ml-0.5 mr-1" />
                            Default
                          </Badge>
                        ) : null}
                        {template.locked ? (
                          <Badge>
                            <LockKey weight="bold" size={11} className="-ml-0.5 mr-1" />
                            Locked
                          </Badge>
                        ) : null}
                      </div>
                      <p className="mt-1 text-[14px] font-medium text-[var(--rl-text-muted)]">
                        {template.locked ? "Default template — copy before editing." : "Editable template."}
                        {template.status !== "active" ? ` Status: ${template.status}` : ""}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {template.locked ? (
                        <Button variant="secondary" icon={<CopySimple weight="bold" size={16} />} onClick={() => copyTemplate(template.id)}>
                          Copy
                        </Button>
                      ) : (
                        <Link href={`/builder/templates/${template.id}/builder`}>
                          <Button icon={<PencilSimple weight="bold" size={16} />}>
                            Open builder
                          </Button>
                        </Link>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ))
        )}
      </section>
    </AppShell>
  );
}
