"use client";

import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";

type Company = { id: string; name: string; category: string; source_template_category: string; detection_phrases: string[]; status: string };

export default function BuilderCompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [name, setName] = useState("");
  const [phrases, setPhrases] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const result = await api<{ companies: Company[] }>("/admin/companies");
    setCompanies(result.companies);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load companies."));
  }, []);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    await api("/admin/companies", {
      method: "POST",
      body: JSON.stringify({ name, category: "Motor", source_template_category: "Other / Unknown", detection_phrases: phrases.split(/\r?\n/).map((item) => item.trim()).filter(Boolean) })
    });
    setName("");
    setPhrases("");
    await load();
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-3xl font-bold text-rl-textStrong">Companies</h1>
          <p className="mt-2">Manage insurer names and detection phrases.</p>
        </div>
        <BuilderNav />
        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        <form className="rl-panel grid gap-3 p-4" onSubmit={save}>
          <input className="rl-input" placeholder="Company name" value={name} onChange={(event) => setName(event.target.value)} required />
          <textarea className="rl-input min-h-24" placeholder="Detection phrases, one per line" value={phrases} onChange={(event) => setPhrases(event.target.value)} />
          <button className="rl-button w-fit" type="submit"><Save aria-hidden="true" size={18} />Save company</button>
        </form>
        <div className="grid gap-2">
          {companies.map((company) => (
            <div key={company.id} className="rl-panel p-4">
              <div className="font-bold text-rl-textStrong">{company.name}</div>
              <div className="text-sm">{company.category} · {company.source_template_category} · {company.status}</div>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
