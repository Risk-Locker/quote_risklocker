"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Copy, Edit3, RefreshCw } from "lucide-react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";

type TemplateRecord = {
  id: string;
  name: string;
  insurance_type: string;
  status: string;
  locked: boolean;
  is_default: boolean;
};

export default function BuilderTemplatesPage() {
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const result = await api<{ templates: TemplateRecord[] }>("/admin/templates");
    setTemplates(result.templates);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load templates."));
  }, []);

  async function copyTemplate(templateId: string) {
    const result = await api<{ template: TemplateRecord }>(`/admin/templates/${templateId}/copy`, { method: "POST", body: JSON.stringify({}) });
    setMessage("Template copied. Opening the builder for the editable copy.");
    await load();
    window.location.href = `/builder/templates/${result.template.id}/builder`;
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold text-rl-textStrong">Templates</h1>
            <p className="mt-2">Copy the locked default motor template, then craft the editable copy in the drag and drop builder.</p>
          </div>
          <button className="rl-button rl-button-secondary" type="button" onClick={load}>
            <RefreshCw aria-hidden="true" size={18} />
            Refresh
          </button>
        </div>
        <BuilderNav />
        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        {message ? <p className="rounded-md border border-rl-success bg-green-50 p-3 font-bold text-rl-success">{message}</p> : null}
        <div className="grid gap-3">
          {templates.map((template) => (
            <div key={template.id} className="rl-panel grid gap-3 p-4 md:grid-cols-[1fr_auto] md:items-center">
              <div>
                <h2 className="text-lg font-bold text-rl-textStrong">{template.name}</h2>
                <p className="mt-1 text-sm">{template.locked ? "Locked default. Copy it before editing." : "Editable template."} Status: {template.status}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {template.locked ? (
                  <button className="rl-button rl-button-secondary" type="button" onClick={() => copyTemplate(template.id)}>
                    <Copy aria-hidden="true" size={18} />
                    Copy
                  </button>
                ) : (
                  <Link className="rl-button" href={`/builder/templates/${template.id}/builder`}>
                    <Edit3 aria-hidden="true" size={18} />
                    Open builder
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
